from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from weizhcode.models import ChatMessage, ProviderEvent


DEFAULT_MAX_OUTPUT_TOKENS = 4096


class Provider(Protocol):
    async def stream_chat(
        self, messages: list[ChatMessage]
    ) -> AsyncIterator[ProviderEvent]:
        ...

