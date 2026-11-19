from pathlib import Path
import hashlib
import io
import os

from weizhcode.models import PreparedOperation, ToolDefinition, ToolResult
from weizhcode.tools.base import BaseTool, TEXT, ToolFailure, schema
from weizhcode.tools.file_utils import original_path, guard_path
from weizhcode.tools.limits import MAX_LINE_CHARS, MAX_READ_LINES, MAX_RESULT_CHARS, excerpt


def _lines(stream):
    number = 0
    while text := stream.readline(MAX_LINE_CHARS + 1):
        number += 1
        if "\0" in text:
            raise ToolFailure("BINARY_FILE", "不支持二进制文件")
        too_long = len(text) > MAX_LINE_CHARS
        prefix = text[:MAX_LINE_CHARS]
        if too_long and not text.endswith(("\n", "\r")):
            while remainder := stream.readline(MAX_LINE_CHARS + 1):
                if "\0" in remainder:
                    raise ToolFailure("BINARY_FILE", "不支持二进制文件")
                if remainder.endswith(("\n", "\r")):
                    break
        yield number, prefix, too_long


def _archive_bytes(path, proof, context):
    from weizhcode.compact.archive_fs import ArchiveFailure, ArchiveGuard, read_bounded
    from weizhcode.compact.limits import USER_RECORD_BYTES
    try:
        if (set(proof) != {"canonical_path", "identity", "sha256", "safe_bytes", "session_id", "record_id"}
                or os.path.normcase(str(path)) != proof["canonical_path"]
                or type(proof["safe_bytes"]) is not int or not 0 <= proof["safe_bytes"] <= USER_RECORD_BYTES * 8):
            raise ValueError()
        root = context.permission_root
        parts = path.relative_to(root.canonical_root).parts
        guard = ArchiveGuard(root)
        with guard.pin_target(parts) as pinned:
            if not pinned.exists or list(pinned.identity) != proof["identity"]:
                raise ValueError()
            data = read_bounded(guard, parts, proof["safe_bytes"])
            if len(data) != proof["safe_bytes"] or hashlib.sha256(data).hexdigest() != proof["sha256"]:
                raise ValueError()
            pinned.verify()
            return data
    except (ArchiveFailure, OSError, ValueError, KeyError, TypeError, AttributeError):
        raise ToolFailure("ARCHIVE_CHANGED", "归档已变化、丢失或无法核验，未返回假原文") from None


class ReadFileTool(BaseTool):
    definition = ToolDefinition("read_file", "读取文件优先使用本工具。按行读取 UTF-8 文件，行号不是原文；edit_file 前先读取相关实际原文，保留原始换行。", schema({
        "path": TEXT,
        "start_line": {"type": "integer", "minimum": 1, "default": 1},
        "line_count": {"type": "integer", "minimum": 1, "maximum": MAX_READ_LINES, "default": MAX_READ_LINES},
    }, ["path"]), read_only=True)

    def _prepare(self, call, context):
        args = dict(call.arguments or {})
        args["start_line"] = int(args.get("start_line", 1))
        args["line_count"] = int(args.get("line_count", MAX_READ_LINES))
        path = guard_path(original_path(str(args["path"]), context))
        if not path.is_file():
            raise ToolFailure("NOT_A_FILE" if path.exists() else "FILE_NOT_FOUND", "目标不是文件或不存在")
        return PreparedOperation(call, args, str(path), str(path))

    def _execute(self, operation, context):
        path = Path(operation.target)
        start = int(operation.arguments["start_line"])
        limit = int(operation.arguments["line_count"])
        parts = []
        size = 0
        returned = 0
        truncated = False
        newline = "\n"
        next_line = start
        path = guard_path(path)
        proof = operation.state.get("archive_read_proof")
        binary = io.BytesIO(_archive_bytes(path, proof, context)) if proof is not None else path.open("rb")
        with binary:
            bom = binary.read(3) == b"\xef\xbb\xbf"
            binary.seek(0)
            with io.TextIOWrapper(binary, encoding="utf-8-sig", errors="strict", newline="") as stream:
                return self._read_lines(operation, path, stream, start, limit, bom)

    def _read_lines(self, operation, path, stream, start, limit, bom):
        parts, size, returned, truncated, newline, next_line = [], 0, 0, False, "\n", start
        original = "\ufeff" if bom and start == 1 else ""
        for number, text, long_line in _lines(stream):
            if number < start:
                continue
            if returned >= limit:
                truncated = True
                break
            if "\r\n" in text:
                newline = "\r\n"
            elif text.endswith("\r"):
                newline = "\r"
            piece = f"{number:6d}\t{text}"
            room = MAX_RESULT_CHARS - size - 32
            if room <= 0:
                truncated = True
                break
            parts.append(piece[:room])
            original += piece[:room][len(f"{number:6d}\t"):]
            size += min(len(piece), room)
            returned += 1
            next_line = number + 1
            if long_line or len(piece) > room:
                truncated = True
                break
        content = "".join(parts)
        if truncated:
            content = excerpt(content + "\n[truncated]")
        from weizhcode.compact.capture import worker_file_capture
        capture = worker_file_capture.get()
        if capture is not None:
            capture.update(canonical_path=str(path), start_line=start, returned_lines=returned,
                           text=original[:17500], truncated=truncated or len(original) > 17500, bom=bom, newline=newline)
        return ToolResult(operation.call.call_id, self.definition.name, content,
                          metadata={"path": str(path), "start_line": start, "lines": returned,
                                    "next_start_line": next_line, "bom": bom, "newline": newline,
                                    **({"archive_verified": True} if operation.state.get("archive_read_proof") else {})},
                          truncated=truncated)

