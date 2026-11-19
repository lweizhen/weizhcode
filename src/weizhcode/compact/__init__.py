"""上下文管理的轻量契约；导入本包不访问磁盘、模型或进程。"""

from .contracts import (
    ArchiveRef, CompactOutcome, CompactionBudget, CompactionNotice,
    FileReadCapture, HistoryEntry, HistorySnapshot, ToolSource,
)

__all__ = [
    "ArchiveRef", "CompactOutcome", "CompactionBudget", "CompactionNotice",
    "FileReadCapture", "HistoryEntry", "HistorySnapshot", "ToolSource",
]
