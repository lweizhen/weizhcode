from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

from weizhcode.errors import ProviderError, StreamError, redact_secret
from weizhcode.models import ChatMessage, ProviderConfig, ProviderEvent
from weizhcode.providers.base import DEFAULT_MAX_OUTPUT_TOKENS
from weizhcode.providers.sse import SSEEvent, stream_sse


StreamFunc = Callable[..., AsyncIterator[SSEEvent]]


class AnthropicProvider:
    def __init__(
        self, config: ProviderConfig, stream_func: StreamFunc = stream_sse
    ) -> None:
        self.config = config
        self._stream = stream_func

    async def stream_chat(
        self, messages: list[ChatMessage]
    ) -> AsyncIterator[ProviderEvent]:
        yield ProviderEvent(type="start")
        try:
            async for event in self._stream(
                "POST",
                f"{self.config.base_url}/messages",
                headers={
                    "content-type": "application/json",
                    "x-api-key": self.config.api_key,
                    "anthropic-version": "2023-06-01",
                },
                json_body={
                    "model": self.config.model,
                    "max_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
                    "messages": _messages_payload(messages),
                    "stream": True,
                },
            ):
                parsed = event.json()
                event_type = parsed.get("type")
                if event_type == "content_block_delta":
                    delta = parsed.get("delta")
                    if isinstance(delta, dict) and delta.get("type") == "text_delta":
                        text = delta.get("text")
                        if isinstance(text, str) and text:
                            yield ProviderEvent(type="text_delta", text=text)
                elif event_type == "error":
                    yield ProviderEvent(
                        type="error", message=_error_message(parsed, "Claude 请求失败")
                    )
                    return
            yield ProviderEvent(type="done")
        except (ProviderError, StreamError) as exc:
            yield ProviderEvent(
                type="error", message=redact_secret(str(exc), self.config.api_key)
            )


def _messages_payload(messages: list[ChatMessage]) -> list[dict[str, str]]:
    return [{"role": message.role, "content": message.content} for message in messages]


def _error_message(payload: dict[str, Any], fallback: str) -> str:
    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str):
            return message
    return fallback
