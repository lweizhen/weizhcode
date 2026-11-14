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
