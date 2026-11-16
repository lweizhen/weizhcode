from typing import Protocol

from weizhcode.models import PreparedOperation, ToolCall, ToolContext, ToolDefinition, ToolResult
from weizhcode.permissions.types import PermissionFailure


class Tool(Protocol):
    definition: ToolDefinition

    def prepare(self, call: ToolCall, context: ToolContext) -> PreparedOperation: ...

    def execute(self, operation: PreparedOperation, context: ToolContext) -> ToolResult: ...


class ToolFailure(Exception):
    def __init__(self, code: str, message: str, **metadata: object) -> None:
        super().__init__(message)
        self.code, self.metadata = code, metadata


def failure(call: ToolCall, exc: Exception) -> ToolResult:
    if isinstance(exc, (ToolFailure, PermissionFailure)):
        return ToolResult.failure(call, exc.code, str(exc), **getattr(exc, "metadata", {}))
    if isinstance(exc, FileNotFoundError):
        return ToolResult.failure(call, "FILE_NOT_FOUND", "目标文件或目录不存在")
    if isinstance(exc, (IsADirectoryError, NotADirectoryError)):
        return ToolResult.failure(call, "NOT_A_FILE", "目标不是所需的文件或目录类型")
    if isinstance(exc, UnicodeError):
        return ToolResult.failure(call, "UNSUPPORTED_ENCODING", "仅支持严格 UTF-8 文本")
    if isinstance(exc, OSError):
        return ToolResult.failure(call, "IO_ERROR", f"文件系统操作失败：{exc.strerror or type(exc).__name__}")
    return ToolResult.failure(call, "INTERNAL_ERROR", f"工具内部错误：{type(exc).__name__}")


class BaseTool:
    definition: ToolDefinition

    def prepare(self, call: ToolCall, context: ToolContext) -> PreparedOperation:
        from dataclasses import replace
        from weizhcode.permissions.rules import TOOLS
        from weizhcode.permissions.sandbox import make_root, resolve_target
        from weizhcode.tools.file_utils import active_root
        token = None
        try:
            root = stamp = None
            if call.name in TOOLS and call.name != "run_command":
                root = context.permission_root or make_root(context.project_root)
                stamp = resolve_target((call.arguments or {}).get("path", "."), root)
                token = active_root.set(root)
            operation = self._prepare(call, context)
            return replace(operation, permission_stamp=stamp, permission_root=root)
        except Exception as exc:
            return PreparedOperation(call, call.arguments or {}, error=failure(call, exc))
        finally:
            if token is not None:
                active_root.reset(token)

    def execute(self, operation: PreparedOperation, context: ToolContext) -> ToolResult:
        if operation.error:
            return operation.error
        from weizhcode.permissions.rules import TOOLS
        from weizhcode.permissions.sandbox import recheck
        from weizhcode.tools.file_utils import active_root
        token = None
        try:
            if operation.call.name in TOOLS and operation.call.name != "run_command":
                if operation.permission_stamp is None or operation.permission_root is None:
                    raise PermissionFailure("PERMISSION_UNAVAILABLE", "文件执行缺少有效路径印记")
                current = recheck(operation.permission_stamp, operation.permission_root)
                if current.canonical_target != operation.target:
                    raise PermissionFailure("PERMISSION_TARGET_CHANGED", "执行目标已改变")
                token = active_root.set(operation.permission_root)
            return self._execute(operation, context)
        except Exception as exc:
            return failure(operation.call, exc)
        finally:
            if token is not None:
                active_root.reset(token)


def schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


TEXT = {"type": "string", "minLength": 1}
