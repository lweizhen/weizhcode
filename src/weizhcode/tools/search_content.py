import re
from pathlib import Path

from weizhcode.models import PreparedOperation, ToolDefinition, ToolResult
from weizhcode.tools.base import BaseTool, TEXT, ToolFailure, schema
from weizhcode.tools.file_utils import bounded_lines, original_path
from weizhcode.tools.find_files import SEARCH_OPTIONS
from weizhcode.tools.limits import MAX_CONTENT_MATCHES, MAX_RESULT_CHARS
from weizhcode.tools.search_utils import SearchWalk


class SearchContentTool(BaseTool):
    definition = ToolDefinition("search_content", "搜索 UTF-8 文件内容，默认区分大小写的普通文本，可显式启用正则。返回文件/行/内容。",
                                schema({"pattern": TEXT, "is_regex": {"type": "boolean", "default": False},
                                        **SEARCH_OPTIONS}, ["pattern"]))

    def _prepare(self, call, context):
        args = dict(call.arguments or {})
        root = original_path(str(args.get("path", ".")), context).resolve()
        if not root.is_dir():
            raise FileNotFoundError(str(root))
        rx = None
        if args.get("is_regex", False):
            try:
                rx = re.compile(str(args["pattern"]))
            except re.error:
                raise ToolFailure("INVALID_REGEX", "正则表达式非法") from None
        return PreparedOperation(call, args, str(root), str(root), state={"rx": rx})

    def _execute(self, operation, context):
        walk = SearchWalk(Path(operation.target), include_hidden=operation.arguments.get("include_hidden", False),
                          include_ignored=operation.arguments.get("include_ignored", False))
        rx = operation.state["rx"]
        pattern = str(operation.arguments["pattern"])
        results = []
        size = 0
        truncated = False
        for path in walk.files():
            before_count, before_size = len(results), size
            try:
                for number, line, too_long in bounded_lines(path):
                    if too_long:
                        walk.long_lines += 1
                        continue
                    if not (rx.search(line) if rx else pattern in line):
                        continue
                    piece = f"{path}:{number}:{line.rstrip()}"
                    room = MAX_RESULT_CHARS - 512 - size
                    if room <= 0:
                        truncated = True
                        break
                    results.append(piece[:room])
                    size += min(room, len(piece)) + 1
                    if len(piece) > room or len(results) >= MAX_CONTENT_MATCHES:
                        truncated = True
                        break
            except (UnicodeError, ToolFailure):
                del results[before_count:]
                size = before_size
                walk.skipped_files += 1
            except OSError as exc:
                walk.error(path, exc)
            if truncated:
                break
        incomplete = bool(walk.errors or walk.long_lines)
        content = "\n".join(results) or ("未找到匹配项，但检索不完整" if incomplete else "没有匹配项")
        if truncated:
            content += "\n[truncated]"
        if walk.long_lines:
            content += "\n存在超长行，未完整搜索"
        return ToolResult(operation.call.call_id, self.definition.name, content,
                          status="error" if incomplete else "success",
                          error_code="SEARCH_INCOMPLETE" if incomplete else None,
                          metadata={"count": len(results), "skipped_files": walk.skipped_files,
                                    "long_lines": walk.long_lines, "errors": walk.errors}, truncated=truncated)

