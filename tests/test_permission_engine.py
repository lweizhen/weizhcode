import pytest
import asyncio
import json

from weizhcode.models import ToolCall
from weizhcode.permissions.engine import PermissionEngine
from weizhcode.permissions.sandbox import resolve_target
from weizhcode.permissions.rules import parse_rule
from weizhcode.permissions.types import ApprovalChoice, SaveResult

from weizhcode.permissions.modes import mode_fallback, next_mode, normalize_runtime_mode, parse_mode
from weizhcode.permissions.types import Category, Decision, PermissionMode, Rule, RuleSet


def test_mode_contract():
    mode = PermissionMode.DEFAULT
    observed = []
    for _ in range(4):
        observed.append(mode)
        mode = next_mode(mode)
    assert observed == list(PermissionMode) and mode == PermissionMode.DEFAULT
    assert normalize_runtime_mode("normal") == PermissionMode.DEFAULT
    assert parse_mode("ACCEPTEDITS") == PermissionMode.ACCEPT_EDITS
    for value in ("normal", "bad", None, True):
        with pytest.raises(ValueError):
            parse_mode(value)


def test_contract():
    items = [Rule("Read")]
    rules = RuleSet(items)
    items.clear()
    assert len(rules.allow) == 1


@pytest.mark.parametrize("mode", list(PermissionMode))
@pytest.mark.parametrize("category", list(Category))
def test_mode_matrix(mode, category):
    actual = mode_fallback(mode, category)
    if mode == PermissionMode.PLAN and category != Category.READ:
        assert actual == Decision.DENY
    elif category == Category.READ or mode == PermissionMode.BYPASS or (mode == PermissionMode.ACCEPT_EDITS and category == Category.WRITE):
        assert actual == Decision.ALLOW
    else:
        assert actual == Decision.ASK


class MemoryIO:
    def __init__(self):
        self.inspections = 0
    async def inspect_path(self, raw, root, *, cancel):
        self.inspections += 1
        return resolve_target(raw, root)
    async def persist_allow(self, *args, **kwargs):
        return SaveResult(warning_code="injected")
    async def aclose(self):
        pass


def engine(tmp_path):
    return PermissionEngine.load(tmp_path, user_home=tmp_path / "home", io=MemoryIO())


def call(name="run_command", **args):
    return ToolCall("id", name, json.dumps(args), args)


async def test_command_pipeline(tmp_path):
    e = engine(tmp_path)
    cancel = asyncio.Event()
    from dataclasses import replace
    e.settings["user"] = replace(e.settings["user"], rules=RuleSet(deny=(parse_rule("Bash"),)))
    e.settings["local"] = replace(e.settings["local"], rules=RuleSet(allow=(parse_rule("Bash"),)))
    for mode in PermissionMode:
        result = await e.check(call(command="rm -rf /"), mode=mode, cancel=cancel)
        assert result.decision == Decision.DENY
    result = await e.check(call(command="git status"), mode="default", cancel=cancel)
    assert result.decision == Decision.ALLOW and result.matched_layer == "local"
    assert e.io.inspections == 0


async def test_file_pipeline(tmp_path):
    e, cancel = engine(tmp_path), asyncio.Event()
    for name in ("read_file", "write_file", "edit_file", "find_files", "search_content"):
        result = await e.check(call(name, path="../outside"), mode="bypassPermissions", cancel=cancel)
        assert result.source == "sandbox" and result.decision == Decision.DENY
    result = await e.check(call("write_file", path="src/x"), mode="default", cancel=cancel)
    assert result.decision == Decision.ASK
    result = await e.check(call("write_file", path="src/x"), mode="plan", cancel=cancel)
    assert result.source == "plan" and result.decision == Decision.DENY


async def test_grants(tmp_path):
    e, cancel = engine(tmp_path), asyncio.Event()
    c = call(command="echo *(hi)")
    checked = await e.check(c, mode="default", cancel=cancel)
    await e.accept(checked, ApprovalChoice.SESSION, cancel=cancel)
    assert (await e.check(c, mode="default", cancel=cancel)).decision == Decision.ALLOW
    assert (await e.check(call(command="echo x(hi)"), mode="default", cancel=cancel)).decision == Decision.ASK
    assert (await engine(tmp_path).check(c, mode="default", cancel=cancel)).decision == Decision.ASK
    checked = await e.check(call(command="different"), mode="default", cancel=cancel)
    result = await e.accept(checked, ApprovalChoice.PERMANENT, cancel=cancel)
    assert not result.saved
    assert (await e.check(call(command="different"), mode="default", cancel=cancel)).decision == Decision.ASK
