from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ProtocolName = Literal["anthropic", "openai", "qwen"]
MessageRole = Literal["user", "assistant"]
ProviderEventType = Literal["start", "text_delta", "done", "error"]


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    protocol: ProtocolName
    model: str
    base_url: str
    api_key: str
    thinking: bool | None = None


@dataclass(frozen=True)
class AppConfig:
    default: str
    providers: list[ProviderConfig]


@dataclass(frozen=True)
class ChatMessage:
    role: MessageRole
    content: str


@dataclass(frozen=True)
class ProviderEvent:
    type: ProviderEventType
    text: str = ""
    message: str = ""

