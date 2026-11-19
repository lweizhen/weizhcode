from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from weizhcode.compact.contracts import HistoryEntry, HistorySnapshot
from weizhcode.compact.history import validate_entries
from weizhcode.models import ChatMessage, ToolResult, wire_calls_valid


class Conversation:
    def __init__(self) -> None:
        self._entries: tuple[HistoryEntry, ...] = ()
        self._revision = 0
        self._human_seq = 0
        self._turn_id = uuid4().hex

    def _entry(self, message, origin, *, human_seq=None, result_keys=()):
        return HistoryEntry(uuid4().hex, self._turn_id, origin, message, human_seq,
                            datetime.now(timezone.utc).isoformat(), result_keys)

    def _append(self, *entries):
        # 原历史始终完整；只验证这批新增交换，单次公开追加不可暴露半截。
        validate_entries(entries)
        self._entries += tuple(entries)
        self._revision += 1

    def add_user_message(self, content: str) -> None:
        self._turn_id = uuid4().hex
        self._human_seq += 1
        self._append(self._entry(ChatMessage(role="user", content=content), "human", human_seq=self._human_seq))

    def reserve_human_sequence(self):
        self._human_seq += 1
        return self._human_seq

    def add_application_message(self, content: str) -> None:
        self._turn_id = uuid4().hex
        self._append(self._entry(ChatMessage("user", content), "application"))

    def add_assistant_message(self, content: str) -> None:
        self._append(self._entry(ChatMessage(role="assistant", content=content), "provider"))

    def messages(self) -> list[ChatMessage]:
        return [entry.message for entry in self._entries]

    def snapshot(self) -> HistorySnapshot:
        return HistorySnapshot(self._revision, self._entries)

    def replace_if_current(self, expected_revision: int, entries: tuple[HistoryEntry, ...]) -> bool:
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("历史版本无效")
        if expected_revision != self._revision:
            return False
        candidate = validate_entries(entries)
        # 验证完成后无await整体交换，不因空值或验证异常清空历史。
        self._entries = candidate
        self._revision += 1
        self._human_seq = max(self._human_seq, max((entry.human_seq or 0 for entry in candidate), default=0))
        if candidate:
            self._turn_id = candidate[-1].turn_id
        return True

    def add_assistant_turn(self, message: ChatMessage) -> None:
        if message.role != "assistant":
            raise ValueError("助手回合角色错误")
        self._append(self._entry(message, "provider"))

    def add_tool_exchange(self, assistant: ChatMessage, results: list[ToolResult], *, result_keys=()) -> None:
        if assistant.role != "assistant" or not assistant.tool_calls:
            raise ValueError("工具交换必须包含助手调用")
        if len(assistant.tool_calls) != len(results):
            raise ValueError("工具调用与结果数量不对应")
        if any(call.call_id != result.call_id or call.name != result.tool_name
               for call, result in zip(assistant.tool_calls, results)):
            raise ValueError("工具调用与结果顺序或标识不对应")
        diagnostic = not wire_calls_valid(assistant.tool_calls) or any(r.error_code == "UNKNOWN_TOOL" for r in results)
        if not diagnostic:
            expected = [call.call_id for call in assistant.tool_calls]
            actual = [result.call_id for result in results]
            if len(expected) != len(actual) or set(expected) != set(actual):
                raise ValueError("工具调用与结果 ID 不对应")
        payload = {**assistant.provider_payload, "diagnostic": diagnostic}
        self._append(
            self._entry(replace(assistant, provider_payload=payload), "provider"),
            self._entry(ChatMessage("tool", tool_results=tuple(results), provider_payload={"diagnostic": diagnostic}),
                        "tool", result_keys=result_keys),
        )

    def add_stop_notice(self, text: str, reason: str, *, run_id: str = "") -> None:
        payload = {"source": "application", "reason": reason, "run_id": run_id}
        if self._entries and self._entries[-1].message.provider_payload == payload:
            return
        self._append(self._entry(ChatMessage("assistant", text, provider_payload=payload), "application"))

