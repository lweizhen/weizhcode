from __future__ import annotations


def test_run_context_contract_isolation_and_frozen_mode():
    import pytest
    from weizhcode.models import MAX_ITERATIONS, MAX_UNKNOWN_RUN, RunContext, StreamState, RoundResponse, ChatMessage, TokenUsage
    first, second = RunContext(mode="plan"), RunContext()
    assert first.run_id != second.run_id and first.cancel_event is not second.cancel_event
    assert first.slots is not second.slots
    assert first.iteration == first.unknown_run == 0
    assert (MAX_ITERATIONS, MAX_UNKNOWN_RUN) == (25, 3)
    first.cancel_event.set()
    assert not second.cancel_event.is_set()
    with pytest.raises(AttributeError):
        first.mode = "normal"
    a, b = StreamState(), StreamState()
    assert a.request_id != b.request_id
    msg = ChatMessage("assistant", "ok", provider_payload={"items": ["opaque"]})
    response = RoundResponse(a.request_id, 1, msg, TokenUsage())
    msg.provider_payload["items"].clear()
    assert response.assistant_message.provider_payload["items"] == ["opaque"]


def test_loop_prompts_cover_plan_and_execution():
    from weizhcode.prompts import SYSTEM_PROMPT, PLAN_MODE_REMINDER, EXECUTE_DIRECTIVE
    assert "持续" in SYSTEM_PROMPT and "数据" in SYSTEM_PROMPT
    assert "不需要逐次审批" in SYSTEM_PROMPT
    assert "禁止" in PLAN_MODE_REMINDER and "/do" in PLAN_MODE_REMINDER
    assert EXECUTE_DIRECTIVE == "请按上面的计划开始执行。"


async def test_bounded_event_channel_backpressure_and_safe_copies():
    import asyncio
    from weizhcode.models import RunContext, ToolCall, ToolResult, TurnEvent
    from weizhcode.redaction import Redactor
    from weizhcode.turn_runner import _EventChannel
    context = RunContext()
    channel = _EventChannel(context, Redactor(["secret-key"]))
    call = ToolCall("id", "read_file", '{"path":"secret-key"}', {"path": "secret-key\x1b[31m"})
    result = ToolResult("id", "read_file", "secret-key" * 4000)
    async def produce():
        for i in range(130):
            await channel.emit(TurnEvent("text_delta", text=str(i), tool_call=call, result=result))
    producer = channel.start(produce())
    for _ in range(1000):
        if channel.queue.full():
            break
        await asyncio.sleep(0)
    assert channel.queue.qsize() == 128 and not producer.done()
    events = [e async for e in channel.events()]
    assert [e.text for e in events] == list(map(str, range(130)))
    assert "secret-key" not in events[0].tool_call.raw_arguments
    assert "\x1b" not in events[0].tool_call.arguments["path"]
    assert len(events[0].result.to_model_text()) <= 20000
    assert call.arguments["path"].startswith("secret-key")
    assert result.content.startswith("secret-key")


async def test_event_channel_shutdown_full_queue_cleans_without_sentinel():
    import asyncio
    from weizhcode.models import RunContext, TurnEvent
    from weizhcode.redaction import Redactor
    from weizhcode.turn_runner import _EventChannel
    context, cleaned = RunContext(), asyncio.Event()
    channel = _EventChannel(context, Redactor())
    async def produce():
        try:
            for _ in range(300):
                await channel.emit(TurnEvent("text_delta", text="x"))
                if context.cancel_event.is_set():
                    break
        finally:
            cleaned.set()
    producer = channel.start(produce())
    for _ in range(1000):
        if channel.queue.full():
            break
        await asyncio.sleep(0)
    stream = channel.events()
    await anext(stream)
    await asyncio.wait_for(stream.aclose(), 1)
    assert cleaned.is_set() and producer.done() and channel.done.is_set()
    assert context.cancel_event.is_set()


async def test_event_channel_shutdown_empty_queue_waiting_producer():
    import asyncio
    from weizhcode.models import RunContext, TurnEvent
    from weizhcode.redaction import Redactor
    from weizhcode.turn_runner import _EventChannel
    context, entered = RunContext(), asyncio.Event()
    channel = _EventChannel(context, Redactor())
    async def produce():
        await channel.emit(TurnEvent("iteration_started"))
        entered.set()
        await context.cancel_event.wait()
        await channel.emit(TurnEvent("turn_done"))
    channel.start(produce())
    stream = channel.events()
    await anext(stream)
    await entered.wait()
    await asyncio.wait_for(stream.aclose(), 1)
    assert channel.producer.done() and channel.done.is_set()

import asyncio

import pytest

from weizhcode.conversation import Conversation
from weizhcode.models import ChatMessage, ProviderEvent, ToolCall, ToolContext, ToolResult, TurnEvent
from weizhcode.prompts import SYSTEM_PROMPT
from weizhcode.redaction import Redactor
from weizhcode.tools import create_default_registry
from weizhcode.tools.executor import ToolExecutor
from weizhcode.turn_runner import TurnRunner


class FakeProvider:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    async def stream_chat(self, messages, **kwargs):
        self.requests.append((messages, kwargs))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        for item in reply:
            yield item


class FakeExecutor:
    def __init__(self, status="success"):
        self.calls = []
        self.closed = False
        self.status = status

    async def execute(self, slot, *, mode, cancel, emit):
        call = slot.call
        self.calls.append(call)
        slot.execution_started = True
        slot.result = ToolResult(call.call_id, call.name, "full result\n" * 20, self.status)
        return slot.result
    async def aclose(self):
        self.closed = True


def reply(text="answer", calls=()):
    return [ProviderEvent("text_delta", text=text), ProviderEvent("done",
            assistant_message=ChatMessage("assistant", text, tool_calls=calls))]


def runner(replies, executor=None):
    provider = FakeProvider(replies)
    conv = Conversation()
    executor = executor or FakeExecutor()
    return TurnRunner(provider, conv, create_default_registry(), executor, Redactor(["secret-token"]))


class LoopExecutor:
    def __init__(self):
        self.calls, self.closed = [], False
    async def execute(self, slot, *, mode, cancel, emit):
        self.calls.append(slot.call)
        slot.execution_started = True
        slot.result = ToolResult(slot.call.call_id, slot.call.name, "actual result")
        return slot.result
    async def aclose(self):
        self.closed = True


def loop_runner(replies, executor=None, **kwargs):
    from weizhcode.turn_runner import TurnRunner
    return TurnRunner(FakeProvider(replies), Conversation(), create_default_registry(),
                       executor or LoopExecutor(), Redactor(["secret-token"]), **kwargs)


async def test_environment_once_per_task_and_reminder_schedule(tmp_path):
    from weizhcode.models import ToolContext
    from weizhcode.prompting import EnvironmentSnapshot
    from weizhcode.prompting.reminders import FULL_PLAN_REMINDER, BRIEF_PLAN_REMINDER
    class Capture:
        def __init__(self):
            self.calls = []
        async def capture(self, **kwargs):
            self.calls.append(kwargs)
            return EnvironmentSnapshot(project_root=str(kwargs["project_root"]), model="test")
    capture = Capture()
    executor = LoopExecutor()
    executor.context = ToolContext(tmp_path)
    call = ToolCall("id", "read_file", '{"path":"x"}', {"path": "x"})
    r = loop_runner([*[reply(calls=(call,)) for _ in range(9)], reply("done"), reply("next"), reply("execute")],
                    executor, environment_collector=capture)
    r.set_mode("plan")
    try:
        events = [e async for e in r.run("plan")]
        assert events[-1].reason == "completed" and len(capture.calls) == 1
        assert capture.calls[0]["project_root"] == tmp_path
        contexts = [kwargs["prompt_context"] for _, kwargs in r.provider.requests]
        assert all(kwargs["system_prompt"] == "" for _, kwargs in r.provider.requests)
        for index, ctx in enumerate(contexts, 1):
            assert ctx.supplements[0].text == (FULL_PLAN_REMINDER if index in {1, 5, 9} else BRIEF_PLAN_REMINDER)
            assert ctx.stable_text == SYSTEM_PROMPT and ctx.environment_text == contexts[0].environment_text
        assert not any("<system-reminder>" in msg.content for msg in r.conversation.messages())
        _ = [e async for e in r.run("new plan")]
        assert len(capture.calls) == 2 and r.provider.requests[-1][1]["prompt_context"].supplements[0].text == FULL_PLAN_REMINDER
        r.set_mode("normal")
        _ = [e async for e in r.run("execute")]
        assert len(capture.calls) == 3 and not r.provider.requests[-1][1]["prompt_context"].supplements
    finally:
        await r.aclose()


async def test_environment_cancel_before_request_and_recover():
    import asyncio
    from weizhcode.prompting import EnvironmentSnapshot
    entered = asyncio.Event()
    class Capture:
        calls = 0
        async def capture(self, *, context, **kwargs):
            self.calls += 1
            if self.calls == 1:
                entered.set()
                await context.cancel_event.wait()
            return EnvironmentSnapshot()
    r = loop_runner([reply("recovered")], environment_collector=Capture())
    async def consume():
        return [e async for e in r.run("cancel")]
    work = asyncio.create_task(consume())
    await entered.wait()
    r.cancel_current()
    events = await work
    assert events[-1].reason == "cancelled" and r.usage_totals.request_count == 0
    assert not r.provider.requests and not r.busy
    events = [e async for e in r.run("next")]
    assert events[-1].reason == "completed" and r.usage_totals.request_count == 1
    await r.aclose()


async def test_environment_failure_degrades_and_cache_settles_once():
    from weizhcode.models import TokenUsage, UsageCounter
    class Capture:
        async def capture(self, **kwargs):
            raise OSError("private error")
    usage = TokenUsage(150, 4, True, "fake", UsageCounter(30, "reported"), UsageCounter(20, "reported"))
    r = loop_runner([[ProviderEvent("usage", usage=usage), ProviderEvent("usage", usage=usage), *reply()]],
                    environment_collector=Capture())
    events = [e async for e in r.run("test")]
    assert events[-1].reason == "completed"
    assert events[-1].totals.cache_read.known_tokens == 30
    assert events[-1].totals.cache_write.known_tokens == 20
    assert events[-1].totals.input_tokens == 150 and events[-1].totals.request_count == 1
    assert "private error" not in str(r.provider.requests)
    await r.aclose()


async def test_loop_single_flight_natural_and_empty_response():
    r = loop_runner([reply(), reply("")])
    stream = r.run("hello")
    assert r.busy
    rejected = [e async for e in r.run("duplicate")]
    assert rejected[0].reason == "busy" and not any(e.type == "turn_done" for e in rejected)
    events = [e async for e in stream]
    assert events[-1].reason == "completed" and not r.busy
    assert len(r.provider.requests) == 1 and len(r.conversation.messages()) == 2
    assert sum(e.type == "turn_done" for e in events) == 1
    events = [e async for e in r.run("empty")]
    assert events[-1].reason == "empty_response" and "未返回正文" in events[-2].text
    assert r.conversation.messages()[-1].provider_payload["source"] == "application"


async def test_loop_multistep_history_actual_files(tmp_path):
    from weizhcode.models import ToolContext
    from weizhcode.tools.executor import ToolExecutor
    (tmp_path / "source").write_text("hello", encoding="utf-8")
    r = loop_runner([
        reply("read", (ToolCall("1", "read_file", '{"path":"source"}'),)),
        reply("write", (ToolCall("2", "write_file", '{"path":"summary","content":"summary: hello"}'),)),
        reply("check", (ToolCall("3", "read_file", '{"path":"summary"}'),)), reply("finished")],
        ToolExecutor(create_default_registry(), ToolContext(tmp_path)))
    events = [e async for e in r.run("read summarize check")]
    assert events[-1].reason == "completed" and len(r.provider.requests) == 4
    assert (tmp_path / "summary").read_text() == "summary: hello"
    assert all(kwargs["allow_tools"] for _, kwargs in r.provider.requests)
    assert [m.role for m in r.conversation.messages()] == ["user", "assistant", "tool", "assistant", "tool", "assistant", "tool", "assistant"]
    assert "summary: hello" in r.provider.requests[-1][0][-1].tool_results[0].content
    assert [e.iteration for e in events if e.type == "iteration_started"] == [1, 2, 3, 4]


async def test_iteration_limit_boundary_exact_25_saves_last_multiple_results():
    calls = (ToolCall("a", "read_file", '{"path":"a"}'), ToolCall("b", "read_file", '{"path":"b"}'))
    r = loop_runner([reply("", calls) for _ in range(26)])
    events = [e async for e in r.run("continue")]
    assert len(r.provider.requests) == 25 and len(r.executor.calls) == 50
    assert events[-1].reason == "max_iterations" and "25" in events[-2].text
    assert len(r.conversation.messages()[-2].tool_results) == 2
    assert r.conversation.messages()[-1].provider_payload["source"] == "application"
    r.provider.replies = [reply("new task")]
    assert [e async for e in r.run("next")][-1].reason == "completed"
    assert len(r.executor.calls) == 50 and len(r.provider.requests) == 26


async def test_iteration_limit_boundary_final_text_counts_and_completes():
    call = ToolCall("a", "read_file", '{"path":"a"}')
    r = loop_runner([reply("", (call,)) for _ in range(24)] + [reply("done")])
    events = [e async for e in r.run("continue")]
    assert len(r.provider.requests) == 25 and events[-1].reason == "completed"
    assert len(r.executor.calls) == 24


async def test_iteration_limit_boundary_cancel_wins_no_next_tool():
    r = loop_runner([], max_iterations=1)
    class CancelProvider:
        async def stream_chat(self, *args, **kwargs):
            r.cancel_current()
            yield ProviderEvent("done", assistant_message=ChatMessage("assistant", tool_calls=(ToolCall("a", "read_file", '{"path":"a"}'),)))
    from weizhcode.stream_collector import StreamCollector
    r.collector = StreamCollector(CancelProvider())
    events = [e async for e in r.run("cancel")]
    assert events[-1].reason == "cancelled" and not r.executor.calls
    assert r.conversation.messages()[2].tool_results[0].status == "cancelled"


async def test_unknown_round_threshold_three_rounds_and_reset_per_task():
    unknown = ToolCall("u", "missing", '{}')
    r = loop_runner([reply("", (unknown,)) for _ in range(3)] + [reply("", (unknown,)), reply("ok")])
    events = [e async for e in r.run("unknown")]
    assert events[-1].reason == "unknown_tools" and len(r.provider.requests) == 3
    assert not r.executor.calls
    events = [e async for e in r.run("next")]
    assert events[-1].reason == "completed" and len(r.provider.requests) == 5


async def test_unknown_round_threshold_known_invalid_and_mixed_reset():
    unknown = ToolCall("u", "missing", '{}')
    known_bad = ToolCall("k", "read_file", '{"path":1}')
    r = loop_runner([reply("", (unknown,)), reply("", (unknown,)), reply("", (unknown, known_bad)),
                     reply("", (unknown,)), reply("", (unknown,)), reply("ok")])
    events = [e async for e in r.run("reset")]
    assert events[-1].reason == "completed" and len(r.provider.requests) == 6
    assert not r.executor.calls


async def test_loop_error_recovery_preserves_write_no_replay(tmp_path):
    from weizhcode.models import ToolContext
    from weizhcode.tools.executor import ToolExecutor
    r = loop_runner([reply("", (ToolCall("a", "write_file", '{"path":"a","content":"written"}'),)),
                     [ProviderEvent("error", message="secret-token failed")], reply("next")],
                    ToolExecutor(create_default_registry(), ToolContext(tmp_path)))
    events = [e async for e in r.run("write")]
    assert events[-1].reason == "provider_error" and "secret-token" not in str(events)
    assert (tmp_path / "a").read_text() == "written"
    assert r.conversation.messages()[2].tool_results[0].status == "success"
    events = [e async for e in r.run("next")]
    assert events[-1].reason == "completed" and len(r.provider.requests) == 3
    assert len([m for m in r.conversation.messages() if m.tool_results]) == 1


async def test_loop_error_recovery_partial_call_never_executes():
    call = ToolCall("a", "read_file", '{"path":"a"}')
    r = loop_runner([[ProviderEvent("tool_call", tool_call=call)], reply("next")])
    events = [e async for e in r.run("partial")]
    assert events[-1].reason == "provider_error" and not r.executor.calls
    assert not any(m.tool_calls for m in r.conversation.messages())
    assert [e async for e in r.run("next")][-1].reason == "completed"


async def test_loop_error_recovery_tool_failure_then_adjust(tmp_path):
    from weizhcode.models import ToolContext
    from weizhcode.tools.executor import ToolExecutor
    r = loop_runner([reply("", (ToolCall("a", "read_file", '{"path":"missing"}'),)),
                     reply("", (ToolCall("b", "write_file", '{"path":"a","content":"fixed"}'),)), reply("fixed")],
                    ToolExecutor(create_default_registry(), ToolContext(tmp_path)))
    events = [e async for e in r.run("recover")]
    assert events[-1].reason == "completed"
    assert r.provider.requests[1][0][-1].tool_results[0].error_code == "FILE_NOT_FOUND"
    assert (tmp_path / "a").read_text() == "fixed"


async def test_session_usage_settlement_once_across_user_turns():
    from weizhcode.models import TokenUsage
    usage = ProviderEvent("usage", usage=TokenUsage(10, 2, True, "test"))
    r = loop_runner([[usage, usage, *reply("first")], [*reply("second")]])
    events = [e async for e in r.run("one")]
    assert events[-1].totals.input_tokens == 10 and events[-1].totals.output_tokens == 2
    events = [e async for e in r.run("two")]
    totals = events[-1].totals
    assert totals.request_count == 2 and totals.incomplete_requests == 1
    assert totals.input_tokens == 10 and totals.output_tokens == 2


async def test_loop_mode_control_frozen_tools_plan_and_do(tmp_path):
    from weizhcode.models import ToolContext
    from weizhcode.tools.executor import ToolExecutor
    from weizhcode.prompts import EXECUTE_DIRECTIVE
    r = loop_runner([reply("", (ToolCall("a", "write_file", '{"path":"a","content":"x"}'),)),
                     reply("plan"), reply("", (ToolCall("b", "write_file", '{"path":"a","content":"x"}'),)), reply("done")],
                    ToolExecutor(create_default_registry(), ToolContext(tmp_path)))
    assert r.set_mode("plan").type == "mode_changed" and not r.provider.requests
    stream = r.run("plan it")
    assert r.set_mode("normal").reason == "busy" and r.mode == "plan"
    events = [e async for e in stream]
    assert events[-1].reason == "completed" and not (tmp_path / "a").exists()
    assert r.conversation.messages()[2].tool_results[0].error_code == "TOOL_NOT_ALLOWED"
    assert all(len(kw["tools"]) == 4 for _, kw in r.provider.requests)
    events = [e async for e in r.run(EXECUTE_DIRECTIVE, mode="normal")]
    assert events[-1].reason == "completed" and (tmp_path / "a").read_text() == "x"
    assert all(len(kw["tools"]) == 6 for _, kw in r.provider.requests[2:]) and r.mode == "normal"


async def test_loop_lifecycle_reuse_cancel_and_permanent_close():
    import asyncio
    r = loop_runner([reply("recovered")])
    original = r.collector
    entered = asyncio.Event()
    class WaitingCollector:
        async def collect(self, *args, context, state, **kwargs):
            entered.set()
            await context.cancel_event.wait()
            return None
    r.collector = WaitingCollector()
    async def consume():
        return [e async for e in r.run("wait")]
    work = asyncio.create_task(consume())
    await entered.wait()
    assert r.cancel_current() and r.cancel_current()
    events = await asyncio.wait_for(work, 1)
    assert events[-1].reason == "cancelled" and not r.busy and not r.executor.closed
    r.collector = original
    assert [e async for e in r.run("next")][-1].reason == "completed"
    await r.aclose()
    await r.aclose()
    assert r.executor.closed and not r.cancel_current()
    assert [e async for e in r.run("closed")][0].reason == "busy"


async def test_loop_lifecycle_reuse_consumer_closes_waiting_stream():
    import asyncio
    r = loop_runner([reply("recovered")])
    original = r.collector
    class WaitingCollector:
        async def collect(self, *args, context, **kwargs):
            await context.cancel_event.wait()
            return None
    r.collector = WaitingCollector()
    stream = r.run("wait")
    assert (await anext(stream)).type == "iteration_started"
    await asyncio.wait_for(stream.aclose(), 1)
    assert not r.busy and not r.executor.closed
    r.collector = original
    assert [e async for e in r.run("next")][-1].reason == "completed"


async def test_event_channel_shutdown_stream_closed_before_first_iteration():
    r = loop_runner([reply("next")])
    stream = r.run("never consumed")
    await asyncio.wait_for(stream.aclose(), 1)
    assert not r.busy and not r.provider.requests
    assert not r.executor.closed
    assert [e async for e in r.run("next")][-1].reason == "completed"


async def test_loop_error_recovery_cleanup_failure_stops_before_next_request():
    class BrokenCleanup(LoopExecutor):
        async def execute(self, slot, **kwargs):
            result = await super().execute(slot, **kwargs)
            slot.cleanup_error = "PROCESS_CONTROL_FAILED"
            return result
    r = loop_runner([reply("", (ToolCall("a", "read_file", '{"path":"a"}'),)), reply("must not request")], BrokenCleanup())
    events = [e async for e in r.run("work")]
    assert events[-1].reason == "internal_error" and len(r.provider.requests) == 1
    assert r.conversation.messages()[2].tool_results[0].status == "success"


async def test_unknown_round_threshold_known_execution_failure_resets():
    class FailedExecutor(LoopExecutor):
        async def execute(self, slot, **kwargs):
            self.calls.append(slot.call)
            slot.result = ToolResult.failure(slot.call, "FILE_NOT_FOUND", "missing")
            return slot.result
    unknown, known = ToolCall("u", "missing", '{}'), ToolCall("k", "read_file", '{"path":"a"}')
    r = loop_runner([reply("", (unknown,)), reply("", (unknown,)), reply("", (known,)),
                     reply("", (unknown,)), reply("", (unknown,)), reply("ok")], FailedExecutor())
    assert [e async for e in r.run("reset")][-1].reason == "completed"
    assert len(r.provider.requests) == 6 and len(r.executor.calls) == 1


async def test_loop_lifecycle_reuse_app_close_unconsumed_full_channel():
    import asyncio
    r = loop_runner([[ProviderEvent("text_delta", text="x") for _ in range(500)] + reply("x" * 500)])
    _ = r.run("stream")
    for _ in range(3000):
        if r._channel.queue.full():
            break
        await asyncio.sleep(0)
    assert r._channel.queue.full()
    await asyncio.wait_for(r.aclose(), 2)
    assert not r.busy and r.executor.closed and r._task.done()


async def test_loop_budget_context_large_result_and_no_history_trim(tmp_path):
    from weizhcode.models import ToolContext
    from weizhcode.tools.executor import ToolExecutor
    (tmp_path / "large").write_text(("fake-secret-token" + "x" * 2000 + "\n") * 300, encoding="utf-8")
    r = loop_runner([reply("", (ToolCall("a", "read_file", '{"path":"large"}'),)),
                     [ProviderEvent("error", message="context length exceeded")], reply("recovered")],
                    ToolExecutor(create_default_registry(), ToolContext(tmp_path), Redactor(["fake-secret-token"])))
    for i in range(30):
        r.conversation.add_user_message(f"old-{i}")
        r.conversation.add_assistant_message("history" * 100)
    before = r.conversation.messages()
    events = [e async for e in r.run("read large")]
    assert events[-1].reason == "provider_error"
    result = r.conversation.messages()[-2].tool_results[0]
    assert len(result.to_model_text()) <= 20000 and result.truncated
    assert "fake-secret-token" not in result.to_model_text()
    assert r.conversation.messages()[:60] == before
    assert [e async for e in r.run("next")][-1].reason == "completed"
    assert len([m for m in r.conversation.messages() if m.tool_results]) == 1


def test_prompts_match_tools():
    from weizhcode.prompts import PLAN_MODE_REMINDER
    assert all(t.name in SYSTEM_PROMPT for t in create_default_registry().definitions_for_mode("normal"))
    assert "AskUserQuestion" in PLAN_MODE_REMINDER
    assert "持续" in SYSTEM_PROMPT


async def test_runner_text_single_request_and_single_flight():
    r = runner([reply()])
    stream = r.run("hello")
    assert r.busy
    rejected = [e async for e in r.run("second")]
    assert rejected[-1].type == "notice"
    events = [e async for e in stream]
    assert events[-1].type == "turn_done"
    assert not r.busy
    assert len(r.provider.requests) == 1
    assert r.executor.calls == []
    assert [m.role for m in r.conversation.messages()] == ["user", "assistant"]
    assert len(r.provider.requests[0][1]["tools"]) == 6


@pytest.mark.parametrize("status", ["success", "error", "denied", "timeout"])
async def test_runner_tool_round(status):
    call = ToolCall("id", "read_file", '{"path":"a"}')
    r = runner([reply("before", (call,)), reply("final")], FakeExecutor(status))
    events = [e async for e in r.run("read")]
    assert len(r.executor.calls) == 1
    assert len(r.provider.requests) == 2
    assert r.provider.requests[1][1]["allow_tools"]
    assert [m.role for m in r.conversation.messages()] == ["user", "assistant", "tool", "assistant"]
    assert r.provider.requests[1][0][-1].tool_results[0].content.count("full result") == 20
    assert next(i for i,e in enumerate(events) if e.type == "tool_result") < next(i for i,e in enumerate(events) if e.type == "iteration_started" and e.iteration == 2)


@pytest.mark.parametrize("name,args", [("read_file", {"path":"a"}), ("write_file", {"path":"a","content":"x"}), ("run_command", {"command":"echo hi"})])
async def test_runner_multiple_calls_execute_in_safe_order(name, args):
    import json
    calls = tuple(ToolCall(f"id{i}", name, json.dumps(args)) for i in range(2))
    r = runner([reply("before", calls), reply()])
    events = [e async for e in r.run("do")]
    assert len(r.executor.calls) == 2 and len(r.provider.requests) == 2
    results = r.conversation.messages()[2].tool_results
    assert len(results) == 2 and all(not x.is_error for x in results)
    assert events[-1].reason == "completed"


async def test_runner_continues_beyond_second_tool_response():
    first = ToolCall("first", "read_file", '{"path":"a"}')
    second = ToolCall("second", "write_file", '{"path":"a","content":"x"}')
    r = runner([reply("before", (first,)), reply("again", (second,)), reply("done")])
    events = [e async for e in r.run("do")]
    assert len(r.provider.requests) == 3 and len(r.executor.calls) == 2
    assert events[-1].reason == "completed"


async def test_runner_recovery_incomplete_then_retry():
    r = runner([[ProviderEvent("text_delta", text="partial")], reply()])
    events = [e async for e in r.run("first")]
    assert events[-1].reason == "provider_error"
    assert [m.role for m in r.conversation.messages()] == ["user", "assistant"]
    assert r.conversation.messages()[-1].provider_payload["source"] == "application"
    _ = [e async for e in r.run("second")]
    assert len(r.executor.calls) == 0
    assert r.conversation.messages()[-1].content == "answer"


async def test_runner_recovery_final_failure_preserves_exchange():
    call = ToolCall("id", "write_file", '{"path":"a","content":"x"}')
    r = runner([reply("before", (call,)), RuntimeError("secret-token network"), reply()])
    events = [e async for e in r.run("write")]
    assert events[-1].reason == "provider_error"
    assert "secret-token" not in events[-1].text
    assert [m.role for m in r.conversation.messages()] == ["user", "assistant", "tool", "assistant"]
    _ = [e async for e in r.run("next")]
    assert len(r.executor.calls) == 1


async def test_security_pipeline_stream_and_original_arguments():
    call = ToolCall("id", "write_file", '{"path":"a","content":"secret-token"}')
    r = runner([[ProviderEvent("text_delta", text="secret-"), ProviderEvent("text_delta", text="token"),
                 ProviderEvent("done", assistant_message=ChatMessage("assistant", "secret-token", tool_calls=(call,)))],
                reply("secret-token")])
    events = [e async for e in r.run("write")]
    assert "secret-token" not in "".join(e.text for e in events)
    assert "secret-token" in r.executor.calls[0].raw_arguments
    assert "[redacted]" in r.conversation.messages()[1].content


async def test_app_shutdown_runner_cancels_stream():
    started = asyncio.Event()
    closed = asyncio.Event()
    class WaitingProvider:
        async def stream_chat(self, *args, **kwargs):
            started.set()
            try:
                await asyncio.Event().wait()
                yield ProviderEvent("done")
            finally:
                closed.set()
    r = runner([])
    r.provider = WaitingProvider()
    r.collector.provider = r.provider
    async def consume():
        return [e async for e in r.run("hello")]
    task = asyncio.create_task(consume())
    await started.wait()
    await r.aclose()
    await r.aclose()
    await asyncio.wait_for(task, 2)
    assert not task.cancelled() and closed.is_set() and r.executor.closed
    assert not r.busy


@pytest.mark.parametrize("protocol", ["anthropic", "openai", "qwen"])
async def test_protocol_integration_real_read(tmp_path, protocol):
    from test_provider_tools import tool_events, make_provider
    file = tmp_path / "中文.txt"
    file.write_text("actual fixture", encoding="utf-8")
    requests = []
    provider = make_provider(protocol, tool_events(protocol), requests)
    first_stream = provider._stream
    async def stream(*args, **kwargs):
        if not requests:
            async for event in first_stream(*args, **kwargs):
                yield event
        else:
            requests.append(kwargs["json_body"])
            from weizhcode.providers.sse import SSEEvent
            import json
            terminal = {
                "anthropic": [{"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}},
                              {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"summary"}},
                              {"type":"content_block_stop","index":0}, {"type":"message_delta","delta":{"stop_reason":"end_turn"}},
                              {"type":"message_stop"}],
                "openai": [{"type":"response.output_text.delta","delta":"summary"},
                           {"type":"response.completed","response":{"status":"completed","output":[]}}],
                "qwen": [{"choices":[{"delta":{"content":"summary"}}]},
                         {"choices":[{"delta":{},"finish_reason":"stop"}]}, "[DONE]"],
            }[protocol]
            for item in terminal:
                yield SSEEvent(None, item if isinstance(item,str) else json.dumps(item))
    provider._stream = stream
    registry = create_default_registry()
    executor = ToolExecutor(registry, ToolContext(tmp_path))
    r = TurnRunner(provider, Conversation(), registry, executor)
    events = [e async for e in r.run("read")]
    assert events[-1].type == "turn_done"
    assert len(requests) == 2
    assert "actual fixture" in r.conversation.messages()[2].tool_results[0].content
    assert r.conversation.messages()[-1].content == "summary"
    await r.aclose()
