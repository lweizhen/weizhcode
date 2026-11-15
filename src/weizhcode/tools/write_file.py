from weizhcode.models import PreparedOperation, ToolDefinition, ToolResult
from weizhcode.tools.base import BaseTool, TEXT, ToolFailure, schema
from weizhcode.tools.file_utils import atomic_update, bounded_lines, original_path, prepared_file, scan_file
from pathlib import Path
from weizhcode.tools.limits import excerpt


class WriteFileTool(BaseTool):
    definition = ToolDefinition("write_file", "依据用户目标创建或覆盖 UTF-8 文件，缺失父目录自动创建；有写入副作用，须以实际结果确认成功。",
                                schema({"path": TEXT, "content": {"type": "string"}}, ["path", "content"]), read_only=False)

    def _prepare(self, call, context):
        args = dict(call.arguments or {})
        if "\0" in str(args["content"]):
            raise ToolFailure("BINARY_FILE", "新文本不允许包含二进制空字符")
        str(args["content"]).encode("utf-8")
        snapshot, _, _ = scan_file(original_path(str(args["path"]), context))
        old = ""
        if snapshot.exists:
            for _, line, _ in bounded_lines(Path(snapshot.target)):
                old += line[:max(0, 8000 - len(old))]
                if len(old) >= 8000:
                    old += "\n[truncated]"
                    break
        preview = f"写入目标：{snapshot.target}\n{'覆盖已有文件' if snapshot.exists else '创建新文件'}\n原内容预览：\n{old}\n新内容：\n{excerpt(str(args['content']), 9000)}"
        return prepared_file(PreparedOperation(call, args, snapshot.target, preview, snapshot))

    def _execute(self, operation, context):
        size = atomic_update(operation)
        return ToolResult(operation.call.call_id, self.definition.name, f"已写入 {operation.target}",
                          metadata={"path": operation.target, "bytes": size})

