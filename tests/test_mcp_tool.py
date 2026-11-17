import pytest

from weizhcode.mcp.contracts import McpToolIdentity


@pytest.mark.parametrize("server,remote", [("a__b", "x"), ("a", "x__y"), ("a", ".x"), ("a", "x" * 64)])
def test_contract_identity_rejects_ambiguous_names(server, remote):
    with pytest.raises(ValueError):
        McpToolIdentity(f"mcp__{server}__{remote}", server, remote, "a" * 32)


def adapter():
    from types import SimpleNamespace
    from weizhcode.mcp.tool import McpToolAdapter
    from weizhcode.redaction import Redactor
    manager = SimpleNamespace(generation="a" * 32, redactor=Redactor(["synthetic-key"]))
    return McpToolAdapter(manager, "demo", {"name": "echo", "inputSchema": {"type": "object"}, "annotations": {"readOnlyHint": True}})


def test_adapter_pure_prepare_and_sync_guard():
    from weizhcode.models import ToolCall, ToolContext
    tool = adapter()
    assert tool.definition.execution_kind == "external" and not tool.definition.read_only
    call = ToolCall("id", tool.definition.name, "{}", {})
    operation = tool.prepare(call, ToolContext("unused"))
    assert tool.execute(operation, None).error_code == "MCP_EXTERNAL_DISPATCH_REQUIRED"


@pytest.mark.parametrize("schema", [True, {}, {"type": "string"}, {"type": "object", "$ref": "x"},
                                    {"type": "object", "properties": {"x\u001b": {"type": "string"}}}])
def test_schema_unsupported(schema):
    from weizhcode.mcp.tool import checked_schema
    with pytest.raises(Exception):
        checked_schema(schema)


def test_mcp_budget_schema_size_depth_nodes():
    from weizhcode.mcp.tool import checked_schema
    checked_schema({"type": "object", "description": "x" * 65000})
    cases = [{"type": "object", "description": "x" * 65536},
             {"type": "object", "enum": list(range(4096))}]
    nested = {}
    for _ in range(17):
        nested = {"anyOf": [nested]}
    cases.append({"type": "object", "properties": {"nested": nested}})
    for schema in cases:
        with pytest.raises(ValueError):
            checked_schema(schema)


@pytest.mark.parametrize("kind", ["text", "structured", "mixed", "image", "error", "empty"])
def test_result_projection(kind):
    import json
    from mcp.types import CallToolResult, TextContent, ImageContent
    from weizhcode.models import ToolCall
    from weizhcode.mcp.tool import adapt_result
    from weizhcode.redaction import Redactor
    image = ImageContent(type="image", data="AA==", mimeType="image/png")
    content = [TextContent(type="text", text="a synthetic-key\u001b[31m"), TextContent(type="text", text="b")]
    if kind in {"image", "mixed"}:
        content = [image] if kind == "image" else [content[0], image]
    if kind in {"empty", "structured"}:
        content = []
    value = CallToolResult(content=content, structuredContent={"n": 1} if kind == "structured" else None, isError=kind == "error")
    result = adapt_result(ToolCall("original-id", "mcp__demo__echo", "{}"), value, Redactor(["synthetic-key"]))
    assert result.call_id == "original-id" and "synthetic-key" not in result.content and "\u001b" not in result.content
    assert result.is_error is (kind in {"image", "error"})
    if kind == "structured":
        assert json.loads(result.content) == {"n": 1}
    if kind in {"mixed", "image"}:
        assert "omitted" in result.content and "AA==" not in result.content


def test_mcp_budget_result_and_arguments():
    import json
    from mcp.types import CallToolResult, TextContent
    from weizhcode.mcp.tool import adapt_result
    from weizhcode.models import ToolCall, ToolResult
    from weizhcode.tools.registry import ToolRegistry
    from weizhcode.redaction import Redactor
    call = ToolCall("id", "mcp__demo__echo", "{}")
    result = adapt_result(call, CallToolResult(content=[TextContent(type="text", text="x" * 50000)]), Redactor())
    encoded = result.to_model_text()
    assert len(encoded) <= 20000 and json.loads(encoded)["truncated"] and result.call_id == "id"
    tool = adapter()
    tool.manager.tools = [tool]
    tool.manager.identity = lambda name: tool.identity
    registry = ToolRegistry()
    with pytest.raises(ValueError):
        registry.register(tool)
    registry.register_external(tool, tool.identity)
    assert registry.definitions_for_mode("plan") == []
    assert not isinstance(registry.validate(ToolCall("id", call.name, json.dumps({"x": "y" * 65000}))), ToolResult)
    assert registry.validate(ToolCall("id", call.name, json.dumps({"x": "y" * 65536}))).is_error


def test_mcp_budget_description_name_and_schema_secret():
    from weizhcode.mcp.tool import McpToolAdapter
    tool = adapter()
    manager = tool.manager
    def make(description, schema=None, name="echo"):
        return McpToolAdapter(manager, "demo", {"name": name, "description": description, "inputSchema": schema or {"type": "object"}})
    assert len(make("x" * 8192).definition.description) == 8192
    with pytest.raises(ValueError):
        make("x" * 8193)
    assert make("synthetic-key").definition.description == "[redacted]"
    with pytest.raises(ValueError):
        make("safe", {"type": "object", "properties": {"x": {"const": "synthetic-key"}}})
    assert len(make("safe", name="t" * 53).definition.name) == 64
    with pytest.raises(ValueError):
        make("safe", name="t" * 54)
