from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from weizhcode.errors import ProviderError, StreamError, redact_secret
from weizhcode.models import ChatMessage, ProviderConfig, ProviderEvent
from weizhcode.providers.base import DEFAULT_MAX_OUTPUT_TOKENS
from weizhcode.providers.sse import SSEEvent, stream_sse


StreamFunc = Callable[..., AsyncIterator[SSEEvent]]


class QwenProvider:
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
                f"{self.config.base_url}/chat/completions",
                headers={
                    "content-type": "application/json",
                    "authorization": f"Bearer {self.config.api_key}",
                },
                json_body={
                    "model": self.config.model,
                    "messages": _messages_payload(messages),
                    "stream": True,
                    "max_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
                },
            ):
                if event.data == "[DONE]":
                    break
                parsed = event.json()
                text = _extract_delta(parsed)
                if text:
                    yield ProviderEvent(type="text_delta", text=text)
            yield ProviderEvent(type="done")
        except (ProviderError, StreamError) as exc:
            yield ProviderEvent(
                type="error", message=redact_secret(str(exc), self.config.api_key)
            )


def _messages_payload(messages: list[ChatMessage]) -> list[dict[str, str]]:
    return [{"role": message.role, "content": message.content} for message in messages]


def _extract_delta(payload: dict[str, object]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    delta = first.get("delta")
    if not isinstance(delta, dict):
        return ""
    content = delta.get("content")
    return content if isinstance(content, str) else ""
