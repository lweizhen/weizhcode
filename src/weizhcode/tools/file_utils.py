from __future__ import annotations

import codecs
import hashlib
import os
import re
import stat
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Callable

from weizhcode.models import FileSnapshot, PreparedOperation, ToolContext
from weizhcode.tools.base import ToolFailure
from weizhcode.tools.limits import CHUNK_SIZE, MAX_LINE_CHARS

BOM = b"\xef\xbb\xbf"
resource_created: Callable[[Path, tuple[int, int]], None] | None = None


def original_path(value: str, context: ToolContext) -> Path:
    path = Path(value).expanduser()
    return Path(os.path.abspath(path if path.is_absolute() else context.project_root / path))


def scan_file(original: Path, needle: bytes | None = None):
    """严格解码、计算指纹和原文计数，不缓存整个文件。"""
    target = original.resolve()
    if not target.exists():
        return FileSnapshot(str(original), str(target), False), 0, None
    if not target.is_file():
        raise ToolFailure("NOT_A_FILE", "目标不是普通文件")
    digest = hashlib.sha256()
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    counts: Counter[str] = Counter()
    pending_cr = False
    bom = False
    suffix = b""
    processed = count = next_start = 0
    position = None
    with target.open("rb") as stream:
        before = os.fstat(stream.fileno())
        first = True
        while raw := stream.read(CHUNK_SIZE):
            digest.update(raw)
            data = raw
            if first:
                bom = raw.startswith(BOM)
                data = raw[3:] if bom else raw
                first = False
            if b"\0" in data:
                raise ToolFailure("BINARY_FILE", "不支持二进制文件")
            text = decoder.decode(data)
            for char in text:
                if pending_cr:
                    counts["\r\n" if char == "\n" else "\r"] += 1
                    pending_cr = False
                    if char == "\n":
                        continue
                if char == "\r":
                    pending_cr = True
                elif char == "\n":
                    counts["\n"] += 1
            if needle:
                buffer = suffix + data
                base = processed - len(suffix)
                index = max(0, next_start - base)
                while (found := buffer.find(needle, index)) >= 0:
                    count += 1
                    position = base + found
                    next_start = position + len(needle)
                    index = found + len(needle)
                processed += len(data)
                suffix = buffer[-(len(needle) - 1):] if len(needle) > 1 else b""
        decoder.decode(b"", final=True)
        if pending_cr:
            counts["\r"] += 1
        after = os.fstat(stream.fileno())
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ToolFailure("PREVIEW_STALE", "读取期间文件发生变化")
    newline = max(counts, key=counts.get) if counts else "\n"
    snapshot = FileSnapshot(str(original), str(target), True, (before.st_dev, before.st_ino),
                            digest.hexdigest(), bom, newline, stat.S_IMODE(before.st_mode))
    return snapshot, count, position


def verify_snapshot(snapshot: FileSnapshot) -> None:
    current, _, _ = scan_file(Path(snapshot.original))
    if (current.target, current.exists, current.identity, current.sha256) != (
        snapshot.target, snapshot.exists, snapshot.identity, snapshot.sha256
    ):
        raise ToolFailure("PREVIEW_STALE", "文件或解析目标已变化，原审批预览失效")


def bounded_lines(path: Path):
    """最多保留一行的有限前缀，超长部分排空并报告。"""
    with path.open("r", encoding="utf-8-sig", errors="strict", newline="") as stream:
        number = 0
        while True:
            piece = stream.readline(MAX_LINE_CHARS + 1)
            if not piece:
                break
            number += 1
            if "\0" in piece:
                raise ToolFailure("BINARY_FILE", "不支持二进制文件")
            too_long = len(piece) > MAX_LINE_CHARS
            prefix = piece[:MAX_LINE_CHARS]
            if too_long and not piece.endswith(("\n", "\r")):
                while remainder := stream.readline(MAX_LINE_CHARS + 1):
                    if "\0" in remainder:
                        raise ToolFailure("BINARY_FILE", "不支持二进制文件")
                    if remainder.endswith(("\n", "\r")):
                        break
            yield number, prefix, too_long


def prepared_file(operation: PreparedOperation) -> PreparedOperation:
    temp = str(Path(operation.target).with_name(f".weizhcode-{operation.operation_id}.tmp"))
    return replace(operation, state={**operation.state, "temp_path": temp})


def normalize_new_text(text: str, newline: str) -> bytes:
    return re.sub(r"\r\n|\r|\n", lambda _: newline, text).encode("utf-8")


def _copy(source, destination, count: int | None = None):
    while count is None or count > 0:
        chunk = source.read(CHUNK_SIZE if count is None else min(CHUNK_SIZE, count))
        if not chunk:
            if count:
                raise ToolFailure("PREVIEW_STALE", "源文件长度发生变化")
            return
        destination.write(chunk)
        if count is not None:
            count -= len(chunk)


def atomic_update(operation: PreparedOperation, *, edit: bool = False) -> int:
    snapshot = operation.snapshot
    if snapshot is None:
        raise ToolFailure("INVALID_ARGUMENTS", "缺少文件快照")
    verify_snapshot(snapshot)
    target = Path(operation.target)
    target.parent.mkdir(parents=True, exist_ok=True)
    verify_snapshot(snapshot)
    temp = Path(str(operation.state["temp_path"]))
    created_identity = None
    try:
        with temp.open("xb") as destination:
            info = os.fstat(destination.fileno())
            created_identity = (info.st_dev, info.st_ino)
            if resource_created:
                resource_created(temp, created_identity)
            if edit:
                position = int(operation.state["position"]) + (3 if snapshot.bom else 0)
                old = str(operation.arguments["old_text"]).encode("utf-8")
                new = normalize_new_text(str(operation.arguments["new_text"]), snapshot.newline)
                with target.open("rb") as source:
                    _copy(source, destination, position)
                    source.seek(len(old), 1)
                    destination.write(new)
                    _copy(source, destination)
            else:
                if snapshot.bom:
                    destination.write(BOM)
                destination.write(normalize_new_text(str(operation.arguments["content"]), snapshot.newline))
            destination.flush()
            os.fsync(destination.fileno())
        if snapshot.mode is not None:
            os.chmod(temp, snapshot.mode)
        verify_snapshot(snapshot)
        size = temp.stat().st_size
        os.replace(temp, target)
        return size
    finally:
        if created_identity is not None and temp.exists():
            info = temp.stat()
            if (info.st_dev, info.st_ino) == created_identity:
                temp.unlink()

