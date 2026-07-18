from __future__ import annotations

from weizhcode.models import ChatMessage


class Conversation:
    def __init__(self) -> None:
        self._messages: list[ChatMessage] = []

    def add_user_message(self, content: str) -> None:
        self._messages.append(ChatMessage(role="user", content=content))

    def add_assistant_message(self, content: str) -> None:
        self._messages.append(ChatMessage(role="assistant", content=content))

    def messages(self) -> list[ChatMessage]:
        return list(self._messages)

