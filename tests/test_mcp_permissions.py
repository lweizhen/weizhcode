from weizhcode.models import ToolDefinition
from weizhcode.permissions.types import Category, PermissionTarget, Rule


def test_contract_position_compatibility():
    definition = ToolDefinition("read_file", "read", {}, True)
    assert definition.execution_kind == "worker"
    external = ToolDefinition("mcp__demo__echo", "echo", {}, False, "external")
    assert not external.read_only and external.execution_kind == "external"
    target = PermissionTarget("run_command", "Bash", Category.EXEC, "echo x", "echo x")
    assert target.external_identity is None
    assert Rule("Read", (), False, "Read", True).kind == "builtin"
