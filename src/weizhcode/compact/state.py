from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from .contracts import AcceptedAnswer, ArchiveRef, FileReadCapture, SummaryRecord
from .limits import FILE_HEAD_CHARS, MAX_AUTO_FAILURES, MAX_RECENT_FILES


@dataclass(frozen=True)
class ReplacementDecision:
    execution_key: str
    source_digest: str
    kind: Literal["kept", "replaced"]
    reference: ArchiveRef | None = None
    preview: str = field(default="", repr=False)

    def __post_init__(self):
        if self.kind not in {"kept", "replaced"}:
            raise ValueError("轻量决定无效")
        if self.kind == "replaced" and (self.reference is None or not self.preview):
            raise ValueError("替换决定必须有已确认资料引用和预览")
        if self.kind == "kept" and (self.reference is not None or self.preview):
            raise ValueError("原文保留决定不能携带替换资料")
        if self.reference is not None and (self.reference.source_key != self.execution_key
                                          or self.reference.sha256 != self.source_digest):
            raise ValueError("替换引用与来源身份/摘要不一致")


class ReplacementLedger:
    """只允许一次性冻结整个决定，不暴露可分开修改的seen/preview集合。"""

    def __init__(self):
        self._decisions = {}
        self._lock = asyncio.Lock()

    def get(self, execution_key):
        return self._decisions.get(execution_key)

    def snapshot(self):
        return tuple(self._decisions.values())

    async def freeze(self, decision: ReplacementDecision):
        async with self._lock:
            existing = self._decisions.get(decision.execution_key)
            if existing is not None:
                if existing.source_digest != decision.source_digest:
                    raise ValueError("同一执行身份的安全原文冲突")
                return existing
            self._decisions[decision.execution_key] = decision
            return decision


class HumanArchiveIndex:
    def __init__(self):
        self._records = {}

    def register(self, human_seq: int, reference: ArchiveRef):
        if type(human_seq) is not int or human_seq < 1 or reference.kind != "human":
            raise ValueError("原话索引身份无效")
        existing = self._records.get(human_seq)
        if existing is not None and existing != reference:
            raise ValueError("用户原话索引冲突")
        self._records[human_seq] = reference

    def snapshot(self):
        return tuple(sorted(self._records.items()))


class RecentFileState:
    def __init__(self):
        self._files = OrderedDict()

    def accept(self, capture: FileReadCapture):
        previous = self._files.get(capture.canonical_path)
        if previous is not None and capture.accepted_sequence <= previous.accepted_sequence:
            return False
        if len(capture.text) > FILE_HEAD_CHARS:
            capture = replace(capture, text=capture.text[:FILE_HEAD_CHARS], truncated=True)
        self._files[capture.canonical_path] = capture
        self._files = OrderedDict(sorted(self._files.items(), key=lambda pair: pair[1].accepted_sequence))
        while len(self._files) > MAX_RECENT_FILES:
            self._files.popitem(last=False)
        return True

    def snapshot(self):
        return tuple(self._files.values())


@dataclass(frozen=True)
class RuntimeSnapshot:
    session_id: str
    operation_generation: int
    auto_failures: int
    replacements: tuple[ReplacementDecision, ...]
    human_index: tuple[tuple[int, ArchiveRef], ...]
    file_reads: tuple[FileReadCapture, ...]
    latest_summary: SummaryRecord | None = field(repr=False)
    accepted_answers: tuple[AcceptedAnswer, ...] = field(default=(), repr=False)


class SessionRuntime:
    """父事件循环拥有的会话状态；构造不会建立目录或启动资料进程。"""

    def __init__(self, *, context_window, root=None, store=None, sources=None):
        if type(context_window) is not int or context_window <= 33_000:
            raise ValueError("会话窗口必须大于33000")
        self.session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex
        self.root = root
        self.context_window = context_window
        self.store = store
        self.sources = sources
        self.replacements = ReplacementLedger()
        self.human_index = HumanArchiveIndex()
        self.file_reads = RecentFileState()
        self.anchor = None
        self.auto_failures = 0
        self.latest_summary = None
        self.operation_generation = 0
        self._active_generation = None
        self._accepted_answers = {}
        self._file_sequence = 0
        self.recovery_text = ''
        self.index_reference = None
        self.answer_sequences = {}

    def begin_operation(self):
        if self._active_generation is not None:
            raise RuntimeError("当前会话已有压缩操作")
        self.operation_generation += 1
        self._active_generation = self.operation_generation
        return self.operation_generation

    def is_current(self, generation):
        return self._active_generation == generation and self.operation_generation == generation

    def finish_operation(self, generation):
        if not self.is_current(generation):
            return False
        self._active_generation = None
        return True

    def invalidate_operation(self):
        self.operation_generation += 1
        self._active_generation = None

    def accept_file_read(self, capture, *, generation):
        if not self.is_current(generation):
            return False
        self._file_sequence += 1
        capture = replace(capture, accepted_sequence=self._file_sequence)
        return self.file_reads.accept(capture)

    def accept_answer(self, answer, *, generation):
        if not self.is_current(generation) or not isinstance(answer, AcceptedAnswer):
            return False
        if answer.answer_id in self._accepted_answers:
            return False
        self._accepted_answers[answer.answer_id] = answer
        return True

    @property
    def auto_tripped(self):
        return self.auto_failures >= MAX_AUTO_FAILURES

    def record_outcome(self, trigger, status):
        if trigger != "auto":
            return
        if status == "completed":
            self.auto_failures = 0
        elif status in {"failed", "no_reduction"}:
            self.auto_failures += 1

    def snapshot(self):
        return RuntimeSnapshot(self.session_id, self.operation_generation, self.auto_failures,
                               self.replacements.snapshot(), self.human_index.snapshot(),
                               self.file_reads.snapshot(), self.latest_summary,
                               tuple(self._accepted_answers.values()))
