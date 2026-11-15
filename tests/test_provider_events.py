from __future__ import annotations

import json
from collections.abc import AsyncIterator

import pytest

from weizhcode.errors import ProviderError
from weizhcode.models import ProviderConfig, ProviderEvent
from weizhcode.providers import create_provider
from weizhcode.providers.anthropic import AnthropicProvider
from weizhcode.providers.base import DEFAULT_MAX_OUTPUT_TOKENS
from weizhcode.providers.openai import OpenAIProvider
from weizhcode.providers.qwen import QwenProvider
from weizhcode.providers.sse import SSEEvent, parse_sse_lines
from weizhcode.models import ChatMessage


@pytest.mark.parametrize("value", [-1, True, 1.5, "2"])
def test_usage_contract_rejects_invalid_counts(value):
    from weizhcode.models import TokenUsage
    with pytest.raises(ValueError):
        TokenUsage(input_tokens=value)


def test_usage_contract_known_zero_partial_and_immutable():
    from dataclasses import FrozenInstanceError
    from weizhcode.models import TokenUsage, UsageTotals
    zero, partial = TokenUsage(0, 0, True, "test"), TokenUsage(5, None, False, "test")
    totals = UsageTotals().add(zero).add(partial)
    assert (totals.input_tokens, totals.output_tokens) == (5, 0)
    assert (totals.input_requests, totals.output_requests) == (2, 1)
    assert (totals.request_count, totals.incomplete_requests) == (2, 1)
    assert UsageTotals().input_requests == 0
    with pytest.raises(FrozenInstanceError):
        zero.input_tokens = 4
    with pytest.raises(ValueError):
        TokenUsage(None, 0, True)


def provider_config(protocol: str = "openai") -> ProviderConfig:
    return ProviderConfig(
        name="demo",
        protocol=protocol,  # type: ignore[arg-type]
        model="demo-model",
        base_url="https://example.test/v1",
        api_key="sk-test",
        thinking=False,
    )


async def _usage_stream(provider_type, protocol, packets):
    bodies = []
    async def stream(*args, **kwargs):
        bodies.append(kwargs["json_body"])
        for packet in packets:
            yield SSEEvent(None, packet if isinstance(packet, str) else json.dumps(packet))
    events = [e async for e in provider_type(provider_config(protocol), stream).stream_chat([])]
    return events, bodies


async def test_anthropic_usage_cumulative_cache_and_missing():
    packets = [
        {"type": "message_start", "message": {"usage": {"input_tokens": 10, "output_tokens": 0,
            "cache_creation_input_tokens": 3, "cache_read_input_tokens": 7,
            "cache_creation": {"ephemeral_5m_input_tokens": 3}}}},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 2}},
        {"type": "message_delta", "usage": {"output_tokens": 2}}, {"type": "message_stop"}]
    events, _ = await _usage_stream(AnthropicProvider, "anthropic", packets)
    snapshots = [e.usage for e in events if e.type == "usage"]
    assert snapshots[-1].input_tokens == 20 and snapshots[-1].output_tokens == 2
    assert snapshots[-1].complete
    assert [s.output_tokens for s in snapshots] == [0, 2, 2, 2]
    packets[0]["message"]["usage"] = {"input_tokens": 0, "output_tokens": 0}
    events, _ = await _usage_stream(AnthropicProvider, "anthropic", packets)
    missing = [e.usage for e in events if e.type == "usage"][-1]
    assert missing.input_tokens is None and missing.uncached_input_tokens == 0
    assert missing.cache_read.availability == "missing" and not missing.complete


async def test_anthropic_usage_null_invalid_and_decreasing():
    events, _ = await _usage_stream(AnthropicProvider, "anthropic", [
        {"type": "message_start", "message": {"usage": {"input_tokens": 4, "output_tokens": 3,
            "cache_read_input_tokens": None}}},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 1}},
        {"type": "message_stop"}])
    final = [e.usage for e in events if e.type == "usage"][-1]
    assert final.output_tokens == 3 and not final.complete
    assert final.input_tokens is None


async def test_responses_usage_details_are_not_added():
    usage = {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14,
             "input_tokens_details": {"cached_tokens": 8}, "output_tokens_details": {"reasoning_tokens": 3}}
    events, bodies = await _usage_stream(OpenAIProvider, "openai", [
        {"type": "response.completed", "response": {"status": "completed", "output": [], "usage": usage}}])
    final = [e.usage for e in events if e.type == "usage"][-1]
    assert (final.input_tokens, final.output_tokens, final.complete) == (10, 4, True)
    assert "stream_options" not in bodies[0]


async def test_responses_usage_incomplete_retained():
    events, _ = await _usage_stream(OpenAIProvider, "openai", [
        {"type": "response.incomplete", "response": {"usage": {"input_tokens": 0}}}])
    final = [e.usage for e in events if e.type == "usage"][-1]
    assert final.input_tokens == 0 and final.output_tokens is None and not final.complete
    assert events[-1].type == "error"


async def test_qwen_usage_empty_choices_repeated_and_request():
    packet = {"choices": [], "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}}
    events, bodies = await _usage_stream(QwenProvider, "qwen", [
        {"choices": [{"delta": {}, "finish_reason": "stop"}]}, packet, packet, "[DONE]"])
    final = [e.usage for e in events if e.type == "usage"][-1]
    assert (final.input_tokens, final.output_tokens, final.complete) == (5, 2, True)
    assert bodies[0]["stream_options"] == {"include_usage": True}


async def test_qwen_usage_missing_counts_not_zero():
    events, _ = await _usage_stream(QwenProvider, "qwen", [
        {"choices": [{"delta": {}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 0}}, "[DONE]"])
    final = [e.usage for e in events if e.type == "usage"][-1]
    assert final.input_tokens == 0 and final.output_tokens is None and not final.complete


def test_provider_event_can_represent_text_delta() -> None:
    event = ProviderEvent(type="text_delta", text="hello")

    assert event.type == "text_delta"
    assert event.text == "hello"


def test_factory_creates_anthropic_provider() -> None:
    assert isinstance(create_provider(provider_config("anthropic")), AnthropicProvider)


def test_factory_creates_openai_provider() -> None:
    assert isinstance(create_provider(provider_config("openai")), OpenAIProvider)


def test_factory_creates_qwen_provider() -> None:
    assert isinstance(create_provider(provider_config("qwen")), QwenProvider)


def test_factory_rejects_unknown_protocol() -> None:
    config = provider_config("other")

    with pytest.raises(ProviderError, match="未知 Provider 协议"):
        create_provider(config)


async def test_parse_sse_lines_handles_event_data_and_done() -> None:
    async def lines() -> AsyncIterator[str]:
        for line in [
            "event: message",
            "data: {\"hello\": \"world\"}",
            "",
            "data: [DONE]",
            "",
        ]:
            yield line

    events = [event async for event in parse_sse_lines(lines())]

    assert events == [
        SSEEvent(event="message", data='{"hello": "world"}'),
        SSEEvent(event=None, data="[DONE]"),
    ]


async def test_anthropic_provider_maps_text_delta_and_request() -> None:
    calls = []

    async def fake_stream(*args, **kwargs) -> AsyncIterator[SSEEvent]:
        calls.append((args, kwargs))
        yield SSEEvent(None, json.dumps({"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}))
        yield SSEEvent(
            event="content_block_delta",
            data=json.dumps(
                {
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": "你好"},
                }
            ),
        )
        yield SSEEvent(None, json.dumps({"type": "content_block_stop", "index": 0}))
        yield SSEEvent(None, json.dumps({"type": "message_delta", "delta": {"stop_reason": "end_turn"}}))
        yield SSEEvent(None, json.dumps({"type": "message_stop"}))

    provider = AnthropicProvider(provider_config("anthropic"), fake_stream)
    events = [
        event
        async for event in provider.stream_chat([ChatMessage("user", "hello")])
    ]

    assert [event.type for event in events] == ["start", "text_delta", "done"]
    assert events[1].text == "你好"
    args, kwargs = calls[0]
    assert args[:2] == ("POST", "https://example.test/v1/messages")
    assert kwargs["headers"]["x-api-key"] == "sk-test"
    assert kwargs["headers"]["anthropic-version"] == "2023-06-01"
    assert kwargs["json_body"]["max_tokens"] == DEFAULT_MAX_OUTPUT_TOKENS
    assert kwargs["json_body"]["stream"] is True
    assert "thinking" not in kwargs["json_body"]


async def test_openai_provider_maps_response_delta_and_request() -> None:
    calls = []

    async def fake_stream(*args, **kwargs) -> AsyncIterator[SSEEvent]:
        calls.append((args, kwargs))
        yield SSEEvent(
            event="response.output_text.delta",
            data=json.dumps({"type": "response.output_text.delta", "delta": "hi"}),
        )
        yield SSEEvent(None, json.dumps({"type": "response.completed", "response": {"status": "completed", "output": []}}))

    provider = OpenAIProvider(provider_config("openai"), fake_stream)
    events = [
        event
        async for event in provider.stream_chat([ChatMessage("user", "hello")])
    ]

    assert [event.type for event in events] == ["start", "text_delta", "done"]
    assert events[1].text == "hi"
    args, kwargs = calls[0]
    assert args[:2] == ("POST", "https://example.test/v1/responses")
    assert kwargs["headers"]["authorization"] == "Bearer sk-test"
    assert kwargs["json_body"]["input"] == [{"role": "user", "content": "hello"}]
    assert kwargs["json_body"]["stream"] is True
    assert kwargs["json_body"]["store"] is False
    assert kwargs["json_body"]["max_output_tokens"] == DEFAULT_MAX_OUTPUT_TOKENS


async def test_qwen_provider_maps_chat_completion_delta_and_request() -> None:
    calls = []

    async def fake_stream(*args, **kwargs) -> AsyncIterator[SSEEvent]:
        calls.append((args, kwargs))
        yield SSEEvent(
            event=None,
            data=json.dumps({"choices": [{"delta": {"content": "你好"}}]}),
        )
        yield SSEEvent(None, json.dumps({"choices": [{"delta": {}, "finish_reason": "stop"}]}))
        yield SSEEvent(event=None, data="[DONE]")

    provider = QwenProvider(provider_config("qwen"), fake_stream)
    events = [
        event
        async for event in provider.stream_chat([ChatMessage("user", "hello")])
    ]

    assert [event.type for event in events] == ["start", "text_delta", "done"]
    assert events[1].text == "你好"
    args, kwargs = calls[0]
    assert args[:2] == ("POST", "https://example.test/v1/chat/completions")
    assert kwargs["headers"]["authorization"] == "Bearer sk-test"
    assert kwargs["json_body"]["messages"] == [{"role": "user", "content": "hello"}]
    assert kwargs["json_body"]["stream"] is True
    assert kwargs["json_body"]["max_tokens"] == DEFAULT_MAX_OUTPUT_TOKENS


async def test_provider_converts_stream_error_to_error_event() -> None:
    async def fake_stream(*args, **kwargs) -> AsyncIterator[SSEEvent]:
        raise ProviderError("boom sk-test")
        yield SSEEvent(event=None, data="{}")

    provider = OpenAIProvider(provider_config("openai"), fake_stream)
    events = [event async for event in provider.stream_chat([])]

    assert events[-1].type == "error"
    assert "sk-test" not in events[-1].message
