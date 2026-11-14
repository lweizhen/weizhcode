import asyncio

import pytest

from weizhcode.models import ChatMessage, ProviderEvent, RunContext, StreamState, TokenUsage, ToolCall
from weizhcode.redaction import Redactor
from weizhcode.stream_collector import StreamCollector


class ScriptProvider:
    def __init__(self, script):
        self.script = script
        self.closed = False

    async def stream_chat(self, messages, **kwargs):
        try:
            for value in self.script:
                if isinstance(value, asyncio.Event):
                    await value.wait()
                else:
                    yield value
        finally:
            self.closed = True


async def collect(script, *, context=None, events=None, redactor=None):
    provider = ScriptProvider(script)
    context = context or RunContext()
    state = StreamState(iteration=1)
    events = events if events is not None else []
    async def emit(event):
        events.append(event)
    result = await StreamCollector(provider, redactor).collect([], tools=[], system_prompt="",
                                                             context=context, state=state, emit=emit)
    return result, state, events, provider


async def test_collector_dual_path_text_visible_before_done():
    gate, events, context = asyncio.Event(), [], RunContext()
    work = asyncio.create_task(collect([
        ProviderEvent("text_delta", text="hello"), gate,
        ProviderEvent("done", assistant_message=ChatMessage("assistant", "hello world"))],
        context=context, events=events))
    for _ in range(50):
        if events:
            break
        await asyncio.sleep(0)
    assert "".join(e.text for e in events) == "hello" and not work.done()
    gate.set()
    result, state, events, provider = await work
    assert result.assistant_message.content == "hello world"
    assert "".join(e.text for e in events) == "hello world"
    assert state.completed and provider.closed


async def test_collector_dual_path_redacts_split_key_and_opaque_hidden():
    result, state, events, _ = await collect([
        ProviderEvent("text_delta", text="hello sec"), ProviderEvent("text_delta", text="ret-key"),
        ProviderEvent("done", assistant_message=ChatMessage("assistant", "hello secret-key",
            provider_payload={"signature": "secret-key-opaque"}))], redactor=Redactor(["secret-key"]))
    assert "".join(e.text for e in events) == "hello [redacted]"
    assert result.assistant_message.provider_payload["signature"] == "secret-key-opaque"
    assert all(e.tool_call is None for e in events)


@pytest.mark.parametrize("script", [[], [ProviderEvent("text_delta", text="partial")],
    [ProviderEvent("done")], [ProviderEvent("error", message="failed")],
    [ProviderEvent("text_delta", text="wrong"), ProviderEvent("done", assistant_message=ChatMessage("assistant", "other"))]])
async def test_collector_completion_gate_rejects_incomplete(script):
    result, state, _, provider = await collect(script)
    assert result is None and state.error and provider.closed


async def test_collector_completion_gate_done_authoritative_no_duplicate_calls():
    call = ToolCall("a", "read_file", '{"path":"a"}')
    result, state, events, _ = await collect([
        ProviderEvent("tool_call_start", tool_call=call), ProviderEvent("tool_call", tool_call=call),
        ProviderEvent("done", assistant_message=ChatMessage("assistant", tool_calls=(call,)))])
    assert result.assistant_message.tool_calls == (call,)
    assert [e.type for e in events] == ["tool_pending"]
    assert state.pending_ids == [call.local_id]


@pytest.mark.parametrize("content", ["", "only final"])
async def test_collector_completion_gate_done_only_and_empty(content):
    result, state, events, _ = await collect([ProviderEvent("done", assistant_message=ChatMessage("assistant", content))])
    assert result is not None and "".join(e.text for e in events) == content


async def test_collector_cancellation_without_tokens_closes_stream():
    context, waiting = RunContext(), asyncio.Event()
    provider = ScriptProvider([waiting])
    state, events = StreamState(), []
    async def emit(e):
        events.append(e)
    work = asyncio.create_task(StreamCollector(provider).collect([], tools=[], system_prompt="",
                               context=context, state=state, emit=emit))
    for _ in range(5):
        await asyncio.sleep(0)
    context.cancel_event.set()
    assert await asyncio.wait_for(work, 1) is None
    assert provider.closed and state.cancelled and not context.owned_tasks


async def test_collector_cancellation_same_tick_preserves_usage_blocks_execution():
    context = RunContext()
    class RaceProvider:
        async def stream_chat(self, *args, **kwargs):
            context.cancel_event.set()
            yield ProviderEvent("usage", usage=TokenUsage(4, 2, True, "test"))
    state = StreamState()
    async def emit(e):
        pass
    result = await StreamCollector(RaceProvider()).collect([], tools=[], system_prompt="",
                   context=context, state=state, emit=emit)
    assert result is None and state.cancelled
    assert state.usage.input_tokens == 4 and not state.usage.complete


@pytest.mark.parametrize("protocol", ["anthropic", "openai", "qwen"])
async def test_collector_cancellation_closes_real_provider_source(protocol):
    from weizhcode.models import ProviderConfig
    from weizhcode.providers.anthropic import AnthropicProvider
    from weizhcode.providers.openai import OpenAIProvider
    from weizhcode.providers.qwen import QwenProvider
    entered, closed, wait = asyncio.Event(), asyncio.Event(), asyncio.Event()
    async def source(*args, **kwargs):
        try:
            entered.set()
            await wait.wait()
            yield None
        finally:
            closed.set()
    provider = {"anthropic": AnthropicProvider, "openai": OpenAIProvider, "qwen": QwenProvider}[protocol](
        ProviderConfig("test", protocol, "test", "https://example.test/v1", "fake"), source)
    context, state = RunContext(), StreamState()
    async def emit(event):
        pass
    work = asyncio.create_task(StreamCollector(provider).collect([], tools=[], system_prompt="",
                               context=context, state=state, emit=emit))
    await entered.wait()
    context.cancel_event.set()
    assert await asyncio.wait_for(work, 1) is None
    assert closed.is_set() and not context.owned_tasks


async def test_collector_usage_snapshot_merge_no_sum_and_incomplete():
    result, state, _, _ = await collect([
        ProviderEvent("usage", usage=TokenUsage(10, 2, False, "test")),
        ProviderEvent("usage", usage=TokenUsage(None, 3, False, "test")),
        ProviderEvent("usage", usage=TokenUsage(10, 3, True, "test")),
        ProviderEvent("done", assistant_message=ChatMessage("assistant", "ok"))])
    assert (result.usage.input_tokens, result.usage.output_tokens, result.usage.complete) == (10, 3, True)
    _, state, _, _ = await collect([
        ProviderEvent("usage", usage=TokenUsage(10, 4, False, "test")),
        ProviderEvent("usage", usage=TokenUsage(9, 2, True, "test")), ProviderEvent("error", message="stop")])
    assert (state.usage.input_tokens, state.usage.output_tokens, state.usage.complete) == (10, 4, False)
