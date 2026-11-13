from __future__ import annotations

import asyncio

import pytest

from weizhcode.conversation import Conversation
from weizhcode.models import ChatMessage, ProviderEvent, ToolCall, ToolContext, ToolResult, TurnEvent
from weizhcode.prompts import SYSTEM_PROMPT, FINAL_PROMPT
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

    async def run(self, call, *, approve=None):
        self.calls.append(call)
        yield TurnEvent("tool_result", local_id=call.local_id,
                        result=ToolResult(call.call_id, call.name, "full result\n" * 20, self.status))
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


def test_prompts_match_tools():
    assert all(t.name in SYSTEM_PROMPT for t in create_default_registry().definitions())
    assert "禁止再次调用" in FINAL_PROMPT


async def test_runner_text_single_request_and_single_flight():
    r = runner([reply()])
    stream = r.run("hello")
    assert r.busy
    rejected = [e async for e in r.run("second")]
    assert rejected[-1].type == "error"
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
    assert not r.provider.requests[1][1]["allow_tools"]
    assert [m.role for m in r.conversation.messages()] == ["user", "assistant", "tool", "assistant"]
    assert r.provider.requests[1][0][-1].tool_results[0].content.count("full result") == 20
    assert next(i for i,e in enumerate(events) if e.type == "tool_result") < next(i for i,e in enumerate(events) if e.phase == "final")


@pytest.mark.parametrize("name", ["read_file", "write_file", "run_command"])
async def test_runner_limits_multiple_calls_execute_none(name):
    calls = tuple(ToolCall(f"id{i}", name, '{}') for i in range(2))
    r = runner([reply("before", calls), reply()])
    _ = [e async for e in r.run("do")]
    assert r.executor.calls == []
    assert len(r.provider.requests) == 2
    results = r.conversation.messages()[2].tool_results
    assert len(results) == 2
    assert all(x.error_code == "TOO_MANY_TOOL_CALLS" for x in results)


async def test_runner_limits_final_extra_call():
    first = ToolCall("first", "read_file", '{}')
    final = ToolCall("final", "write_file", '{}')
    r = runner([reply("before", (first,)), reply("again", (final,))])
    events = [e async for e in r.run("do")]
    assert len(r.provider.requests) == 2
    assert len(r.executor.calls) == 1
    assert r.conversation.messages()[-1].tool_results[0].error_code == "TOOL_ROUND_LIMIT"
    assert "上限" in events[-2].text


async def test_runner_recovery_incomplete_then_retry():
    r = runner([[ProviderEvent("text_delta", text="partial")], reply()])
    events = [e async for e in r.run("first")]
    assert events[-1].type == "error"
    assert [m.role for m in r.conversation.messages()] == ["user"]
    _ = [e async for e in r.run("second")]
    assert len(r.executor.calls) == 0
    assert r.conversation.messages()[-1].content == "answer"


async def test_runner_recovery_final_failure_preserves_exchange():
    call = ToolCall("id", "write_file", '{}')
    r = runner([reply("before", (call,)), RuntimeError("secret-token network"), reply()])
    events = [e async for e in r.run("write")]
    assert events[-1].type == "error"
    assert "secret-token" not in events[-1].text
    assert [m.role for m in r.conversation.messages()] == ["user", "assistant", "tool"]
    _ = [e async for e in r.run("next")]
    assert len(r.executor.calls) == 1


async def test_security_pipeline_stream_and_original_arguments():
    call = ToolCall("id", "write_file", '{"content":"secret-token"}')
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
    async def consume():
        return [e async for e in r.run("hello")]
    task = asyncio.create_task(consume())
    await started.wait()
    await r.aclose()
    await r.aclose()
    assert task.cancelled() and closed.is_set() and r.executor.closed
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
