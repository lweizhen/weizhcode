from pathlib import Path

from weizhcode.models import PreparedOperation, ToolDefinition, ToolResult
from weizhcode.tools.base import BaseTool, TEXT, ToolFailure, schema
from weizhcode.tools.file_utils import bounded_lines, original_path
from weizhcode.tools.limits import MAX_READ_LINES, MAX_RESULT_CHARS, excerpt


class ReadFileTool(BaseTool):
    definition = ToolDefinition("read_file", "按行读取 UTF-8 文件，行号不是原文。保留原始换行供精确编辑。", schema({
        "path": TEXT,
        "start_line": {"type": "integer", "minimum": 1, "default": 1},
        "line_count": {"type": "integer", "minimum": 1, "maximum": MAX_READ_LINES, "default": MAX_READ_LINES},
    }, ["path"]))

    def _prepare(self, call, context):
        args = dict(call.arguments or {})
        args["start_line"] = int(args.get("start_line", 1))
        args["line_count"] = int(args.get("line_count", MAX_READ_LINES))
        path = original_path(str(args["path"]), context).resolve()
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
        with path.open("rb") as stream:
            bom = stream.read(3) == b"\xef\xbb\xbf"
        for number, text, long_line in bounded_lines(path):
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
            size += min(len(piece), room)
            returned += 1
            next_line = number + 1
            if long_line or len(piece) > room:
                truncated = True
                break
        content = "".join(parts)
        if truncated:
            content = excerpt(content + "\n[truncated]")
        return ToolResult(operation.call.call_id, self.definition.name, content,
                          metadata={"path": str(path), "start_line": start, "lines": returned,
                                    "next_start_line": next_line, "bom": bom, "newline": newline},
                          truncated=truncated)

