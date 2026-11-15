from weizhcode.models import ToolDefinition, ToolResult
from weizhcode.tools.base import BaseTool, schema


class AskUserQuestionTool(BaseTool):
    definition = ToolDefinition(
        "AskUserQuestion", "仅计划模式使用：向用户确认尚不明确的需求、范围或验收边界。每次一题，可提供单选项，也可自由回答；不重复询问已明确条件。用户回答不是执行授权，计划仍等待 /do。",
        schema({"question": {"type": "string", "minLength": 1, "maxLength": 1000, "pattern": r"\S"},
                "options": {"type": "array", "maxItems": 4, "uniqueItems": True,
                            "items": {"type": "string", "minLength": 1, "maxLength": 200, "pattern": r"\S"}}},
               ["question"]), read_only=True, execution_kind="interactive")

    def _prepare(self, call, context):
        from weizhcode.models import PreparedOperation
        return PreparedOperation(call, call.arguments or {}, error=ToolResult.failure(
            call, "INTERACTION_UNAVAILABLE", "用户提问只能在主会话的交互通道执行"))

    def _execute(self, operation, context):
        return operation.error
