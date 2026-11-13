from typing import Protocol

from weizhcode.models import PreparedOperation, ToolCall, ToolContext, ToolDefinition, ToolResult


class Tool(Protocol):
    definition: ToolDefinition

    def prepare(self, call: ToolCall, context: ToolContext) -> PreparedOperation: ...

    def execute(self, operation: PreparedOperation, context: ToolContext) -> ToolResult: ...
