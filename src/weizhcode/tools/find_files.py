from pathlib import Path

from weizhcode.models import PreparedOperation, ToolDefinition, ToolResult
from weizhcode.tools.base import BaseTool, TEXT, schema
from weizhcode.tools.file_utils import original_path
from weizhcode.tools.limits import MAX_FILE_MATCHES, MAX_RESULT_CHARS
from weizhcode.tools.search_utils import SearchWalk, match_glob

SEARCH_OPTIONS = {
    "path": TEXT,
    "include_hidden": {"type": "boolean", "default": False},
    "include_ignored": {"type": "boolean", "default": False},
}


class FindFilesTool(BaseTool):
    definition = ToolDefinition("find_files", "按 glob 递归找文件，默认遵循 .gitignore 且跳过隐藏项，结果为绝对路径。",
                                schema({"pattern": TEXT, **SEARCH_OPTIONS}, ["pattern"]), read_only=True)

    def _prepare(self, call, context):
        args = dict(call.arguments or {})
        root = original_path(str(args.get("path", ".")), context).resolve()
        if not root.is_dir():
            raise FileNotFoundError(str(root))
        return PreparedOperation(call, args, str(root), str(root))

    def _execute(self, operation, context):
        walk = SearchWalk(Path(operation.target), include_hidden=operation.arguments.get("include_hidden", False),
                          include_ignored=operation.arguments.get("include_ignored", False))
        paths = []
        size = 0
        truncated = False
        for path in walk.files():
            if not match_glob(path.relative_to(walk.root).as_posix(), str(operation.arguments["pattern"])):
                continue
            piece = str(path)
            if size + len(piece) > MAX_RESULT_CHARS - 512:
                truncated = True
                break
            paths.append(piece)
            size += len(piece) + 1
            if len(paths) >= MAX_FILE_MATCHES:
                truncated = True
                break
        content = "\n".join(paths) or "没有匹配项"
        if truncated:
            content += "\n[truncated]"
        return ToolResult(operation.call.call_id, self.definition.name, content,
                          status="error" if walk.errors else "success",
                          error_code="SEARCH_INCOMPLETE" if walk.errors else None,
                          metadata={"root": str(walk.root), "count": len(paths), "errors": walk.errors},
                          truncated=truncated)

