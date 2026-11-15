import asyncio
import json

import pytest

from weizhcode.models import ChatMessage, ToolCall, ToolContext, ToolResult, ToolSlot
from weizhcode.tools import create_default_registry
from weizhcode.tools.executor import ToolExecutor
from weizhcode.user_questions import QuestionBroker


def question_call(options=None, call_id="q"):
    args = {"question": "确认范围？"}
    if options is not None:
        args["options"] = options
    return ToolCall(call_id, "AskUserQuestion", json.dumps(args))


@pytest.mark.parametrize("args", [{}, {"question":" "}, {"question":"x"*1001},
    {"question":"q", "options":["a"]*2}, {"question":"q", "options":["x"*201]},
    {"question":"q", "options":["a","b","c","d","e"]}])
def test_ask_question_schema_rejects_invalid(args):
    result = create_default_registry().validate(ToolCall("q", "AskUserQuestion", json.dumps(args)))
    assert isinstance(result, ToolResult) and result.error_code == "INVALID_ARGUMENTS"


def test_ask_question_modes_and_boundaries():
    registry = create_default_registry()
    assert len(registry.definitions()) == 7
    assert len(registry.definitions_for_mode("normal")) == 6
    assert [d.name for d in registry.definitions_for_mode("plan")] == ["read_file","find_files","search_content","AskUserQuestion"]
    assert not registry.is_parallel_read("AskUserQuestion")
    assert not isinstance(registry.validate(ToolCall("q", "AskUserQuestion", json.dumps(
        {"question":"x"*1000,"options":[str(i)*200 for i in range(4)]}))), ToolResult)


async def start_question(broker, cancel=None):
    slot = ToolSlot(0, create_default_registry().validate(question_call(["A", "B"])))
    ready, events = asyncio.Event(), []
    async def emit(event):
        events.append(event)
        ready.set()
    cancel = cancel or asyncio.Event()
    work = asyncio.create_task(broker.ask(slot, cancel=cancel, emit=emit))
    await asyncio.wait_for(ready.wait(), 1)
    return work, slot, events[0].question, cancel


@pytest.mark.parametrize("answer,expected", [({"option_index":1},"B"), ({"text":"自定义"},"自定义")])
async def test_ask_question_answer_mapping_and_duplicate(answer, expected):
    broker = QuestionBroker()
    broker.connect()
    work, slot, request, cancel = await start_question(broker)
    for bad in ({"text":" "}, {"text":"x"*4001}, {"option_index":4}, {"option_index":True}, {}, {"text":"a","option_index":0}):
        assert not broker.submit(request.question_id, bad)[0]
        assert not work.done()
    assert broker.submit(request.question_id, answer)[0]
    assert not broker.submit(request.question_id, answer)[0]
    assert json.loads((await work).content)["answer"] == expected
    assert slot.result.status == "success" and broker._pending is None


async def test_ask_question_lifecycle_cancel_disconnect_reuse_and_same_tick():
    broker = QuestionBroker()
    old = broker.connect()
    new = broker.connect()
    work, slot, request, cancel = await start_question(broker)
    broker.disconnect(old)
    assert not cancel.is_set()
    broker.disconnect(new)
    assert (await asyncio.wait_for(work, 1)).status == "cancelled"
    assert not broker.submit(request.question_id, {"text":"late"})[0]
    broker.connect()
    work, slot, request, cancel = await start_question(broker)
    assert broker.submit(request.question_id, {"text":"confirmed"})[0]
    cancel.set()
    work.cancel()
    assert (await work).status == "success"
    assert broker._pending is None


async def test_ask_question_lifecycle_unavailable_and_no_worker(tmp_path):
    broker = QuestionBroker()
    def forbidden():
        raise AssertionError("交互不应启动 worker")
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path), questions=broker, worker_factory=forbidden, timeout=.001)
    async def emit(event):
        pass
    slot = ToolSlot(0, question_call())
    result = await executor.execute(slot, mode="normal", cancel=asyncio.Event(), emit=emit)
    assert result.error_code == "TOOL_NOT_ALLOWED"
    result = await executor.execute(ToolSlot(0, question_call()), mode="plan", cancel=asyncio.Event(), emit=emit)
    assert result.error_code == "INTERACTION_UNAVAILABLE"
    broker.connect()
    async def answer_later(event):
        await asyncio.sleep(.01)
        broker.submit(event.question.question_id, {"text":"answer"})
    result = await executor.execute(ToolSlot(0, question_call()), mode="plan", cancel=asyncio.Event(), emit=answer_later)
    assert result.status == "success" and not executor._active


async def test_ask_question_runner_history_ownership_and_redaction(tmp_path):
    from weizhcode.conversation import Conversation
    from weizhcode.redaction import Redactor
    from weizhcode.turn_runner import TurnRunner
    from test_turn_runner import FakeProvider, reply
    registry, conv, safe = create_default_registry(), Conversation(), Redactor(["secret-key"])
    call = question_call(["secret-key", "other"])
    provider = FakeProvider([reply("", (call,)), reply("已确认，等待 /do")])
    from weizhcode.prompting import EnvironmentSnapshot
    from weizhcode.prompting.reminders import FULL_PLAN_REMINDER, BRIEF_PLAN_REMINDER
    class Capture:
        calls = 0
        async def capture(self, **kwargs):
            self.calls += 1
            return EnvironmentSnapshot(project_root=str(tmp_path))
    capture = Capture()
    runner = TurnRunner(provider, conv, registry, ToolExecutor(registry, ToolContext(tmp_path), safe), safe,
                        environment_collector=capture)
    token = runner.bind_questions()
    runner.set_mode("plan")
    events = []
    async for e in runner.run("需求"):
        events.append(e)
        if e.type == "question_request":
            assert "secret-key" not in repr(e.question)
            assert not runner.submit_answer("old", e.question.question_id, {"text":"bad"})[0]
            assert len(provider.requests) == 1
            await asyncio.sleep(.01)
            assert len(provider.requests) == 1 and capture.calls == 1
            assert runner.usage_totals.request_count == 1
            assert runner.submit_answer(e.run_id, e.question.question_id, {"option_index":0})[0]
    assert events[-1].reason == "completed" and events[-1].iteration == 2
    assert len(provider.requests) == 2 and runner.mode == "plan"
    assert capture.calls == 1 and runner.usage_totals.request_count == 2
    assert provider.requests[0][1]["prompt_context"].supplements[0].text == FULL_PLAN_REMINDER
    assert provider.requests[1][1]["prompt_context"].supplements[0].text == BRIEF_PLAN_REMINDER
    assert [m.role for m in conv.messages()] == ["user","assistant","tool","assistant"]
    assert "[redacted]" in conv.messages()[2].tool_results[0].content
    runner.unbind_questions(token)
    await runner.aclose()


async def test_ask_question_interactive_barrier(tmp_path):
    from weizhcode.models import RunContext
    from weizhcode.tool_scheduler import ToolScheduler
    registry, broker = create_default_registry(), QuestionBroker()
    broker.connect()
    executor = ToolExecutor(registry, ToolContext(tmp_path), questions=broker)
    (tmp_path / "a").write_text("data")
    calls = (ToolCall("r1","read_file",'{"path":"a"}'),question_call(call_id="q1"),
             question_call(call_id="q2"),ToolCall("r2","read_file",'{"path":"a"}'))
    seen = []
    async def emit(event):
        if event.type == "tool_start":
            seen.append(event.index)
        if event.type == "question_request":
            assert seen == ([0,1] if len(seen)==2 else [0,1,2])
            broker.submit(event.question.question_id, {"text":"ok"})
    results = await ToolScheduler(registry, executor).execute(ChatMessage("assistant",tool_calls=calls),
        context=RunContext(mode="plan"), emit=emit)
    assert all(r.status == "success" for r in results) and seen == [0,1,2,3]
