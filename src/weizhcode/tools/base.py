from typing import Protocol

from weizhcode.models import PreparedOperation, ToolCall, ToolContext, ToolDefinition, ToolResult


class Tool(Protocol):
    definition: ToolDefinition

    def prepare(self, call: ToolCall, context: ToolContext) -> PreparedOperation: ...

    def execute(self, operation: PreparedOperation, context: ToolContext) -> ToolResult: ...


class ToolFailure(Exception):
    def __init__(self, code: str, message: str, **metadata: object) -> None:
        super().__init__(message)
        self.code, self.metadata = code, metadata


def failure(call: ToolCall, exc: Exception) -> ToolResult:
    if isinstance(exc, ToolFailure):
        return ToolResult.failure(call, exc.code, str(exc), **exc.metadata)
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
        try:
            return self._prepare(call, context)
        except Exception as exc:
            return PreparedOperation(call, call.arguments or {}, error=failure(call, exc))

    def execute(self, operation: PreparedOperation, context: ToolContext) -> ToolResult:
        if operation.error:
            return operation.error
        try:
            return self._execute(operation, context)
        except Exception as exc:
            return failure(operation.call, exc)


def schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


TEXT = {"type": "string", "minLength": 1}
