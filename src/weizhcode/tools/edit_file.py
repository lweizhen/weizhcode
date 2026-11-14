from weizhcode.models import PreparedOperation, ToolDefinition, ToolResult
from weizhcode.tools.base import BaseTool, TEXT, ToolFailure, schema
from weizhcode.tools.file_utils import atomic_update, original_path, prepared_file, scan_file
from weizhcode.tools.limits import excerpt


class EditFileTool(BaseTool):
    definition = ToolDefinition("edit_file", "对原文精确唯一匹配后替换，须用户批准。old_text 不含读取行号，换行必须与原文一致。",
                                schema({"path": TEXT, "old_text": TEXT, "new_text": {"type": "string"}},
                                       ["path", "old_text", "new_text"]), requires_confirmation=True, read_only=False)

    def _prepare(self, call, context):
        args = dict(call.arguments or {})
        old = str(args["old_text"])
        if not old:
            raise ToolFailure("INVALID_ARGUMENTS", "old_text 不得为空")
        snapshot, count, position = scan_file(original_path(str(args["path"]), context), old.encode("utf-8"))
        if not snapshot.exists:
            raise ToolFailure("FILE_NOT_FOUND", "文件不存在")
        if count != 1:
            raise ToolFailure("MATCH_COUNT_ERROR", f"原文匹配 {count} 处，需要精确匹配 1 处；请提供更明确的原文", match_count=count)
        if "\0" in str(args["new_text"]):
            raise ToolFailure("BINARY_FILE", "新文本不允许包含二进制空字符")
        str(args["new_text"]).encode("utf-8")
        preview = f"修改目标：{snapshot.target}\n原文：\n{excerpt(old, 9000)}\n替换为：\n{excerpt(str(args['new_text']), 9000)}"
        return prepared_file(PreparedOperation(call, args, snapshot.target, preview, snapshot, {"position": position}))

    def _execute(self, operation, context):
        size = atomic_update(operation, edit=True)
        return ToolResult(operation.call.call_id, self.definition.name, f"已修改 {operation.target}",
                          metadata={"path": operation.target, "bytes": size, "match_count": 1})

