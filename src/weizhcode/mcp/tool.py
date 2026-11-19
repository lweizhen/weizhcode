import json

from jsonschema import Draft202012Validator

from weizhcode.models import ToolDefinition, PreparedOperation, ToolResult
from .contracts import McpToolIdentity
from weizhcode.redaction import safe_text


def checked_schema(value):
    count = 0
    def visit(node, depth=0):
        nonlocal count
        count += 1
        if depth > 16 or count > 4096:
            raise ValueError("MCP_SCHEMA_LIMIT")
        if isinstance(node, dict):
            if "$ref" in node:
                raise ValueError("MCP_SCHEMA_REFERENCE")
            for child in (*node.keys(), *node.values()):
                visit(child, depth + 1)
        elif isinstance(node, list):
            for child in node:
                visit(child, depth + 1)
        elif isinstance(node, str) and safe_text(node) != node:
            raise ValueError("MCP_SCHEMA_UNSAFE")
    if not isinstance(value, dict) or value.get("type") != "object" or len(json.dumps(value).encode()) > 65536:
        raise ValueError("MCP_SCHEMA_INVALID")
    visit(value)
    Draft202012Validator.check_schema(value)
    return value


def adapt_result(call, value, redactor, *, bounded=True):
    texts, omitted = [], 0
    for block in value.content:
        if block.type == "text":
            texts.append(block.text)
        else:
            omitted += 1
    structured = getattr(value, "structuredContent", None)
    if not texts and structured is not None:
        texts.append(json.dumps(structured, ensure_ascii=False, allow_nan=False))
    if omitted:
        texts.append(f"[omitted {omitted} unsupported non-text blocks]")
    content = (redactor.display if bounded else redactor.text)("\n".join(texts) or "工具未返回文本")
    if value.isError:
        result = ToolResult.failure(call, "MCP_REMOTE_ERROR", content)
    elif omitted and len(texts) == 1 and structured is None:
        result = ToolResult.failure(call, "MCP_UNSUPPORTED_CONTENT", content)
    else:
        result = ToolResult(call.call_id, call.name, content)
    return ToolResult(**json.loads(result.to_model_text())) if bounded else result


class McpToolAdapter:
    def __init__(self, manager, server, spec):
        self.manager = manager
        remote = spec["name"]
        self.identity = McpToolIdentity(f"mcp__{server}__{remote}", server, remote, manager.generation)
        description = spec.get("description") or f"来自 MCP Server {server} 的工具 {remote}"
        if len(description) > 8192:
            raise ValueError("MCP_DESCRIPTION_LIMIT")
        schema = checked_schema(spec["inputSchema"])
        raw = json.dumps(schema, ensure_ascii=False)
        if manager.redactor.display(raw) != raw:
            raise ValueError("MCP_SCHEMA_UNSAFE")
        self.definition = ToolDefinition(self.identity.full_name, manager.redactor.display(description), schema, False, "external")

    def prepare(self, call, context):
        return PreparedOperation(call, call.arguments or {}, target=self.identity.full_name)

    def execute(self, operation, context):
        return ToolResult.failure(operation.call, "MCP_EXTERNAL_DISPATCH_REQUIRED", "MCP必须经统一异步执行入口")

    async def execute_external(self, operation, *, cancel, execution_started, capture_sink=None):
        options = {"capture_sink": capture_sink} if capture_sink is not None else {}
        return await self.manager.call(self.identity, operation.call, cancel=cancel, execution_started=execution_started, **options)
