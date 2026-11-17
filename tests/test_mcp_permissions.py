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


import asyncio
import pytest
from weizhcode.mcp.contracts import McpToolIdentity
from weizhcode.models import ToolCall
from weizhcode.permissions.engine import PermissionEngine
from weizhcode.permissions.rules import parse_rule, match_rules, exact_rule
from weizhcode.permissions.types import Decision, RuleSet, PermissionFailure


@pytest.mark.parametrize("mode,decision", [("default", Decision.ASK), ("acceptEdits", Decision.ASK),
                                           ("bypassPermissions", Decision.ALLOW), ("plan", Decision.DENY)])
async def test_external_mode_matrix_and_explicit_deny(tmp_path, mode, decision):
    engine = PermissionEngine.load(tmp_path, user_home=tmp_path / "home")
    identity = McpToolIdentity("mcp__demo__echo", "demo", "echo", "a" * 32)
    engine.external_identity = lambda name: identity if name == identity.full_name else None
    call = ToolCall("id", identity.full_name, '{"command":"rm -rf /","path":"../outside"}')
    try:
        checked = await engine.check(call, mode=mode, cancel=asyncio.Event())
        assert checked.decision == decision
        if checked.target:
            assert checked.target.path is None and checked.target.command is None
            assert exact_rule(checked.target).original == identity.full_name
        engine.session = RuleSet(deny=(parse_rule("mcp__demo__*"),))
        assert (await engine.check(call, mode=mode, cancel=asyncio.Event())).decision == Decision.DENY
        assert (await engine.check(ToolCall("x", "mcp__forged__echo", "{}"), mode="bypassPermissions", cancel=asyncio.Event())).decision == Decision.DENY
    finally:
        await engine.aclose()


def test_external_rules_case_scope_and_deny():
    exact = parse_rule("mcp__demo__echo")
    group = parse_rule("mcp__demo__*")
    assert exact.kind == "mcp_exact" and group.kind == "mcp_server"
    assert match_rules(RuleSet((group,), (exact,)), "mcp__demo__echo", "mcp__demo__echo")[0] == Decision.DENY
    assert match_rules(RuleSet((group,)), "mcp__demo2__echo", "mcp__demo2__echo") is None
    assert match_rules(RuleSet((exact,)), "mcp__Demo__echo", "mcp__Demo__echo") is None
    for value in ("mcp__demo__echo(*)", "mcp__*__echo", "mcp__bad__name__echo", "mcp__demo__e*"):
        with pytest.raises(PermissionFailure):
            parse_rule(value)
