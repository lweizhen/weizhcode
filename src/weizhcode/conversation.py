from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from weizhcode.models import ChatMessage, ToolResult, wire_calls_valid


class Conversation:
    def __init__(self) -> None:
        self._messages: list[ChatMessage] = []

    def add_user_message(self, content: str) -> None:
        self._messages.append(ChatMessage(role="user", content=content))

    def add_assistant_message(self, content: str) -> None:
        self._messages.append(ChatMessage(role="assistant", content=content))

    def messages(self) -> list[ChatMessage]:
        return deepcopy(self._messages)

    def add_assistant_turn(self, message: ChatMessage) -> None:
        if message.role != "assistant":
            raise ValueError("助手回合角色错误")
        self._messages.append(deepcopy(message))

    def add_tool_exchange(self, assistant: ChatMessage, results: list[ToolResult]) -> None:
        if assistant.role != "assistant" or not assistant.tool_calls:
            raise ValueError("工具交换必须包含助手调用")
        diagnostic = not wire_calls_valid(assistant.tool_calls) or any(r.error_code == "UNKNOWN_TOOL" for r in results)
        if not diagnostic:
            expected = [call.call_id for call in assistant.tool_calls]
            actual = [result.call_id for result in results]
            if len(expected) != len(actual) or set(expected) != set(actual):
                raise ValueError("工具调用与结果 ID 不对应")
        payload = {**assistant.provider_payload, "diagnostic": diagnostic}
        self._messages.extend(deepcopy([
            replace(assistant, provider_payload=payload),
            ChatMessage("tool", tool_results=tuple(results), provider_payload={"diagnostic": diagnostic}),
        ]))

