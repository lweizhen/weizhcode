from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

if TYPE_CHECKING:
    from weizhcode.models import ChatMessage


HistoryOrigin = Literal["human", "provider", "tool", "application", "summary"]
CompactTrigger = Literal["auto", "manual", "emergency"]
CompactStatus = Literal["skipped", "completed", "no_reduction", "failed", "cancelled", "tripped"]


@dataclass(frozen=True, init=False)
class HistoryEntry:
    entry_id: str
    turn_id: str
    origin: HistoryOrigin
    _message: ChatMessage = field(repr=False)
    human_seq: int | None = None
    created_at: str = ""
    result_keys: tuple[str, ...] = ()

    def __init__(self, entry_id, turn_id, origin, message, human_seq=None, created_at="", result_keys=()):
        if not entry_id or not turn_id:
            raise ValueError("历史记录必须有应用身份和任务身份")
        if origin not in {"human", "provider", "tool", "application", "summary"}:
            raise ValueError("历史来源无效")
        if human_seq is not None and (type(human_seq) is not int or human_seq < 1 or origin != "human"):
            raise ValueError("用户原话序号必须属于真实用户来源")
        if message is None:
            raise ValueError("历史消息不能为空")
        for name, value in (("entry_id", entry_id), ("turn_id", turn_id), ("origin", origin),
                            ("_message", deepcopy(message)), ("human_seq", human_seq),
                            ("created_at", created_at), ("result_keys", tuple(result_keys))):
            object.__setattr__(self, name, value)

    @property
    def message(self) -> ChatMessage:
        # 调用者不能经可变原生payload反向改写快照。
        return deepcopy(self._message)


@dataclass(frozen=True)
class HistorySnapshot:
    revision: int
    entries: tuple[HistoryEntry, ...]

    def __post_init__(self):
        if type(self.revision) is not int or self.revision < 0:
            raise ValueError("历史版本必须是非负整数")
        entries = tuple(deepcopy(self.entries))
        if any(not isinstance(entry, HistoryEntry) for entry in entries):
            raise ValueError("历史快照只能包含来源记录")
        if len({entry.entry_id for entry in entries}) != len(entries):
            raise ValueError("历史记录身份重复")
        object.__setattr__(self, "entries", entries)


@dataclass(frozen=True)
class ArchiveRef:
    session_id: str
    record_id: str
    kind: Literal["human", "tool"]
    source_key: str
    sha256: str
    safe_bytes: int
    raw_path: str
    view_path: str
    view_sha256: str
    complete: bool


@dataclass(frozen=True)
class ToolSource:
    execution_key: str
    text: str = field(repr=False)
    collected_bytes: int
    safe_bytes: int
    truncated_at_source: bool
    capture_complete: bool

    def __post_init__(self):
        if any(type(n) is not int or n < 0 for n in (self.collected_bytes, self.safe_bytes)):
            raise ValueError("来源体量必须是非负整数")
        if self.safe_bytes != len(self.text.encode("utf-8")):
            raise ValueError("来源字节数与安全正文不一致")


@dataclass(frozen=True)
class FileReadCapture:
    execution_key: str
    canonical_path: str
    start_line: int
    returned_lines: int
    text: str = field(repr=False)
    truncated: bool
    accepted_sequence: int
    read_at: str
    bom: bool = False
    newline: str = "\n"


@dataclass(frozen=True)
class CompactionBudget:
    operation_id: str
    deadline: float
    max_summary_requests: int = 12

    def __post_init__(self):
        if not self.operation_id or not math.isfinite(self.deadline):
            raise ValueError("压缩操作身份或期限无效")
        if type(self.max_summary_requests) is not int or not 1 <= self.max_summary_requests <= 12:
            raise ValueError("摘要请求预算必须在1到12之间")


@dataclass(frozen=True)
class CompactOutcome:
    trigger: CompactTrigger
    status: CompactStatus
    before_tokens: int
    after_tokens: int | None
    offloaded_results: int
    summary_requests: int
    code: str = ""
    omitted_turn_ranges: tuple[tuple[str, str], ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "omitted_turn_ranges", tuple(tuple(pair) for pair in self.omitted_turn_ranges))


@dataclass(frozen=True)
class CompactionNotice:
    operation_id: str
    trigger: CompactTrigger
    phase: str
    before_tokens: int | None = None
    after_tokens: int | None = None
    offloaded_results: int = 0
    summary_requests: int = 0
    code: str = ""


@dataclass(frozen=True)
class SummaryRecord:
    text: str = field(repr=False)
    source_entry_ids: tuple[str, ...] = ()
    omitted_turn_ranges: tuple[tuple[str, str], ...] = ()


class _AnswerOrigin(Enum):
    BROKER = "accepted_by_question_broker"


@dataclass(frozen=True)
class AcceptedAnswer:
    answer_id: str
    execution_key: str
    question_id: str
    text: str = field(repr=False)
    source: Literal["text", "option"]
    created_at: str
    _origin: object = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self._origin is not _AnswerOrigin.BROKER:
            raise ValueError("用户答案必须由真实交互通道接纳")
        if not self.answer_id or not self.execution_key or not self.question_id or self.source not in {"text", "option"}:
            raise ValueError("已接纳答案身份无效")
        if not isinstance(self.text, str):
            raise ValueError("已接纳答案正文无效")


def _accepted_answer(execution_key, question_id, text, source):
    """仅供问题Broker在成功接纳时调用；模型文字不能创建此来源。"""
    return AcceptedAnswer(uuid4().hex, execution_key, question_id, text, source,
                          datetime.now(timezone.utc).isoformat(), _AnswerOrigin.BROKER)
