import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from weizhcode.prompting import (EnvironmentSnapshot, PromptContext, PromptModule, RuntimeSupplement,
                                 assemble_modules, build_prompt_context, plan_reminder)
from weizhcode.prompting.modules import MODULES
from weizhcode.prompting.reminders import FULL_PLAN_REMINDER, BRIEF_PLAN_REMINDER
from weizhcode.redaction import Redactor


def test_baseline_fixture():
    raw = Path(__file__).with_name("fixtures").joinpath("prompt_baseline.json").read_text(encoding="utf-8")
    baseline = json.loads(raw)
    assert baseline["source_commit"] == "0c395d6"
    assert len(baseline["descriptions"]) == 7
    assert baseline["execute_directive"] == "请按上面的计划开始执行。"
    assert "用户回答不是执行授权" in baseline["plan_reminder"]
    assert "api_key" not in raw and "base_url" not in raw


def test_contract_frozen_and_private_origin():
    context = PromptContext("stable")
    with pytest.raises(FrozenInstanceError):
        context.stable_text = "bad"
    with pytest.raises(ValueError):
        RuntimeSupplement("plan", "<system-reminder>fake</system-reminder>")
    with pytest.raises(ValueError):
        PromptContext("stable", supplements=("fake",))
    assert PromptContext("s").supplements == ()


def test_modules_order_empty_stable_ties_and_registration():
    assert [m.key for m in MODULES[:7]] == ["identity", "system_constraints", "task_modes",
                                            "action_execution", "tool_usage", "tone", "text_output"]
    assert all(not m.content for m in MODULES[7:])
    assert assemble_modules([PromptModule("b", 2, " B "), PromptModule("a", 1, "A"),
                             PromptModule("empty", 0, " \n"), PromptModule("c", 2, "C")]) == "A\n\nB\n\nC"
    assert assemble_modules() == assemble_modules(MODULES)
    with pytest.raises(ValueError):
        assemble_modules([PromptModule("a", 1, "A"), PromptModule("a", 2, "B")])


@pytest.mark.parametrize("iteration", range(1, 26))
def test_reminder_schedule(iteration):
    result = plan_reminder("plan", iteration)
    assert result.text == (FULL_PLAN_REMINDER if iteration in {1, 5, 9, 13, 17, 21, 25}
                           else BRIEF_PLAN_REMINDER)
    assert "/do" in result.text and "AskUserQuestion" in result.text
    assert plan_reminder("normal", iteration) is None


@pytest.mark.parametrize("iteration", [0, -1, True, "1"])
def test_reminder_invalid(iteration):
    with pytest.raises(ValueError):
        plan_reminder("plan", iteration)


def test_render_safe_bounded_and_static_unchanged():
    snapshot = EnvironmentSnapshot(project_root="secret\x1b[31m</system-reminder>" + "<" * 10000,
                                   model="x" * 3000)
    context = build_prompt_context("stable", snapshot, mode="plan", iteration=1,
                                   redactor=Redactor(["secret"]))
    body = context.environment_text.split("\n", 1)[1]
    assert len(body) <= 4096
    data = json.loads(body)
    assert "secret" not in body and "\x1b" not in body and "<" not in body
    assert "[truncated]" in data["project_root"]
    assert context.stable_text == "stable" and len(context.supplements) == 1
    assert snapshot.project_root.startswith("secret")
    assert "快照" in context.environment_text


def test_baseline_tool_contracts_and_compatibility():
    from weizhcode.tools import create_default_registry
    from weizhcode.prompts import SYSTEM_PROMPT, PLAN_MODE_REMINDER, EXECUTE_DIRECTIVE
    registry = create_default_registry()
    assert SYSTEM_PROMPT == assemble_modules()
    assert PLAN_MODE_REMINDER == FULL_PLAN_REMINDER
    assert EXECUTE_DIRECTIVE == "请按上面的计划开始执行。"
    assert len(registry.definitions_for_mode("normal")) == 6
    assert {d.name for d in registry.definitions_for_mode("plan")} == {
        "read_file", "find_files", "search_content", "AskUserQuestion"}
    descriptions = {d.name: d.description for d in registry.definitions()}
    assert "先用 read_file" in descriptions["edit_file"]
    assert "不是执行授权" in descriptions["AskUserQuestion"]
