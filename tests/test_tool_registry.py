import json

import pytest

from weizhcode.models import ToolCall, ToolDefinition, ToolResult
from weizhcode.tools.registry import ToolRegistry


class SampleTool:
    definition = ToolDefinition("sample", "测试工具", {
        "type": "object", "properties": {"line": {"type": "integer", "minimum": 1, "maximum": 200}},
        "required": ["line"], "additionalProperties": False,
    })


def test_model_contract_copies_inputs():
    schema = {"type": "object"}
    definition = ToolDefinition("x", "用途", schema)
    schema["type"] = "array"
    assert definition.parameters["type"] == "object"
    args = {"path": "a"}
    call = ToolCall("id", "x", "{}", args)
    args["path"] = "b"
    assert call.arguments == {"path": "a"}
    assert call.local_id


def test_model_contract_result_states():
    call = ToolCall("id", "x", "{}")
    assert not ToolResult("id", "x", "没有匹配项").is_error
    assert ToolResult.failure(call, "USER_DENIED", "拒绝").status == "denied"
    assert ToolResult.failure(call, "TOOL_TIMEOUT", "超时").status == "timeout"


@pytest.mark.parametrize("content", ["中文" * 30000, '"\\\n' * 30000], ids=["unicode", "escaped"])
def test_result_budget_preserves_metadata(content):
    result = ToolResult("id", "x", content, metadata={"exit_code": 3, "match_count": 17, "detail": "x" * 30000})
    for budget in (512, 20000):
        text = result.to_model_text(budget)
        parsed = json.loads(text)
        assert len(text) <= budget
        assert parsed["truncated"]
        assert parsed["metadata"]["exit_code"] == 3
        assert parsed["metadata"]["match_count"] == 17
        assert "[truncated]" in parsed["content"]


def test_registry_order_duplicate_and_copies():
    registry = ToolRegistry()
    tool = SampleTool()
    registry.register(tool)
    assert registry.get("sample") is tool
    assert registry.get("missing") is None
    registry.definitions()[0].parameters["type"] = "array"
    assert registry.definitions()[0].parameters["type"] == "object"
    with pytest.raises(ValueError, match="重复"):
        registry.register(tool)


@pytest.mark.parametrize("args", ['[]', '{}', '{"line":true}', '{"line":201}', '{"line":1,"extra":2}', '{"line":"1"}', 'NaN', '{'])
def test_registry_rejects_invalid_arguments(args):
    registry = ToolRegistry()
    registry.register(SampleTool())
    result = registry.validate(ToolCall("id", "sample", args))
    assert isinstance(result, ToolResult)
    assert result.is_error


def test_registry_valid_call_and_unknown():
    registry = ToolRegistry()
    registry.register(SampleTool())
    assert registry.validate(ToolCall("id", "sample", '{"line":1}')).arguments == {"line": 1}
    assert registry.validate(ToolCall("id", "missing", '{}')).error_code == "UNKNOWN_TOOL"
    assert registry.validate(ToolCall(None, "sample", '{}')).error_code == "INVALID_ARGUMENTS"


def test_registry_disallows_schema_references():
    class Referencing:
        definition = ToolDefinition("ref", "测试", {"$ref": "https://example.test/schema"})
    with pytest.raises(ValueError, match="引用"):
        ToolRegistry().register(Referencing())


def test_default_registry_six_order_and_permissions():
    from weizhcode.tools import create_default_registry
    registry = create_default_registry()
    definitions = registry.definitions()
    assert [d.name for d in definitions] == ["read_file", "write_file", "edit_file", "run_command", "find_files", "search_content"]
    assert {d.name for d in definitions if d.requires_confirmation} == {"write_file", "edit_file", "run_command"}
    assert all(registry.get(d.name) is not None for d in definitions)
