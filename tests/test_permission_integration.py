import asyncio
from copy import deepcopy
import json

import pytest

from weizhcode.approvals import ApprovalBroker
from weizhcode.conversation import Conversation
from weizhcode.models import ChatMessage, ToolCall, ToolContext, ToolResult, ToolSlot
from weizhcode.permissions.engine import PermissionEngine
from weizhcode.permissions.types import ApprovalChoice, Decision
from weizhcode.redaction import Redactor
from weizhcode.tools import create_default_registry
from weizhcode.tools.executor import ToolExecutor
from weizhcode.turn_runner import TurnRunner
from test_permission_engine import MemoryIO
from test_turn_runner import FakeProvider, reply


def call(name="write_file", path="sample.txt", **kwargs):
    args = {"path": path, **kwargs}
    if name == "write_file":
        args.setdefault("content", "hello")
    return ToolCall("id", name, json.dumps(args), args)


def rig(root, replies):
    registry = create_default_registry()
    safe = Redactor(["sample-secret"])
    permissions = PermissionEngine.load(root, user_home=root / ".test-home", io=MemoryIO())
    executor = ToolExecutor(registry, ToolContext(root), safe, permissions=permissions, approvals=ApprovalBroker(safe))
    return TurnRunner(FakeProvider(replies), Conversation(), registry, executor, safe)


async def test_denial_loop(tmp_path):
    runner = rig(tmp_path, [reply("", (call(path="../outside"),)), reply("", (call(),)), reply("done")])
    runner.bind_approvals()
    events = []
    try:
        async for event in runner.run("write"):
            events.append(event)
            if event.type == "approval_request":
                assert not (tmp_path / "sample.txt").exists()
                assert not runner.executor._active
                assert runner.submit_approval(event.run_id, event.approval.approval_id, ApprovalChoice.ONCE)[0]
        assert events[-1].reason == "completed"
        assert (tmp_path / "sample.txt").read_text() == "hello"
        results = [e.result for e in events if e.type == "tool_result"]
        assert [r.status for r in results] == ["denied", "success"]
        assert runner.provider.requests[1][0][-1].tool_results[0].error_code == "PATH_OUTSIDE_PROJECT"
        assert len(runner.provider.requests) == 3
    finally:
        await runner.aclose()


@pytest.mark.parametrize("choice", list(ApprovalChoice))
async def test_permission_approval(tmp_path, choice):
    runner = rig(tmp_path, [reply("", (call(),)), reply("done")])
    runner.bind_approvals()
    # Use native persistence for the permanent branch, not a fake successful save.
    if choice == ApprovalChoice.PERMANENT:
        from weizhcode.permissions.io import PermissionIO
        runner.executor.permissions.io = PermissionIO()
    try:
        async for event in runner.run("task"):
            if event.type == "approval_request":
                runner.submit_approval(event.run_id, event.approval.approval_id, choice)
        assert (tmp_path / "sample.txt").exists() is (choice != ApprovalChoice.DENY)
        result = runner.conversation.messages()[2].tool_results[0]
        assert result.status == ("denied" if choice == ApprovalChoice.DENY else "success")
        engine = runner.executor.permissions
        later = await engine.check(call(), mode="default", cancel=asyncio.Event())
        assert later.decision == (Decision.ALLOW if choice in {ApprovalChoice.SESSION, ApprovalChoice.PERMANENT} else Decision.ASK)
        assert (tmp_path / ".weizhcode/settings.local.yaml").exists() is (choice == ApprovalChoice.PERMANENT)
        if choice == ApprovalChoice.PERMANENT:
            reloaded = PermissionEngine.load(tmp_path, user_home=tmp_path / ".test-home", io=MemoryIO())
            assert (await reloaded.check(call(), mode="default", cancel=asyncio.Event())).decision == Decision.ALLOW
            await reloaded.aclose()
    finally:
        await runner.aclose()


async def test_shutdown_recovery(tmp_path):
    runner = rig(tmp_path, [reply("", (call(),)), reply("recovered")])
    runner.bind_approvals()
    try:
        async for event in runner.run("first"):
            if event.type == "approval_request":
                runner.cancel_current()
        assert event.reason == "cancelled" and not (tmp_path / "sample.txt").exists()
        assert runner.approvals._pending is None
        events = [event async for event in runner.run("next")]
        assert events[-1].reason == "completed" and runner.conversation.messages()[-1].content == "recovered"
    finally:
        await runner.aclose()


async def test_permission_preflight(tmp_path):
    # This uses the real production constructor, with no test wrapper or implicit grants.
    def forbidden():
        raise AssertionError("must not prepare or execute")
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path), worker_factory=forbidden)
    async def emit(event):
        pass
    result = await executor.execute(ToolSlot(0, call()), mode="bypassPermissions", cancel=asyncio.Event(), emit=emit)
    assert result.error_code == "PERMISSION_UNAVAILABLE" and not (tmp_path / "sample.txt").exists()
    await executor.aclose()


@pytest.mark.parametrize("protocol", ["anthropic", "openai", "qwen"])
async def test_permission_protocol(tmp_path, protocol):
    from test_prompt_protocols import config, request
    denied = ToolResult.failure(call(), "USER_DENIED", "User declined sample-secret")
    payload = {}
    if protocol == "anthropic":
        payload = {"anthropic_blocks": [{"type": "thinking", "thinking": "opaque", "signature": "exact-signature"},
            {"type": "tool_use", "id": "id", "name": "write_file", "input": call().arguments}]}
    elif protocol == "openai":
        payload = {"openai_items": [{"type": "reasoning", "id": "r", "encrypted_content": "exact-encrypted", "summary": []},
            {"type": "function_call", "call_id": "id", "name": "write_file", "arguments": call().raw_arguments}]}
    messages = [ChatMessage("user", "task"), ChatMessage("assistant", tool_calls=(call(),), provider_payload=payload),
                ChatMessage("tool", tool_results=(denied,))]
    saved = deepcopy(messages)
    body = await request(config(protocol), messages, mode="default")
    wire = json.dumps(body)
    assert "USER_DENIED" in wire and "id" in wire and messages == saved
    if protocol == "anthropic":
        assert "exact-signature" in wire
    elif protocol == "openai":
        assert "exact-encrypted" in wire


async def test_approval_keyboard_and_cancel_ui(tmp_path):
    from weizhcode.tui import ChatInput, WeizhCodeApp
    from weizhcode.approval_ui import ApprovalView
    from test_tool_tui import wait_for
    runner = rig(tmp_path, [reply("", (call(),)), reply("done")])
    app = WeizhCodeApp(runner.provider, runner.conversation, runner=runner, provider_name="hidden",
                       model="fake", project_path=str(tmp_path), version="test")
    async with app.run_test() as pilot:
        await app.submit_text("write")
        await wait_for(pilot, lambda: app._pending_approval is not None)
        assert app.query_one(ChatInput).disabled
        await pilot.press("4")
        await wait_for(pilot, lambda: not app.is_generating)
        assert not (tmp_path / "sample.txt").exists()
        assert not app.query_one(ApprovalView).active
        assert not app.query_one(ChatInput).disabled


def test_manual_permission_guards(monkeypatch, capsys):
    import manual_permission_smoke as manual
    import weizhcode.config as config_module
    def forbidden(*args, **kwargs):
        raise AssertionError("default must not load credentials or call APIs")
    monkeypatch.setattr(config_module, "load_config", forbidden)
    assert manual.main([]) == 0
    assert "未加载凭据" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        manual.main(["--live", "--terminal"])


def test_settings_example():
    from pathlib import Path
    from weizhcode.permissions.settings import parse_settings
    data = Path(__file__).parents[1].joinpath(".weizhcode/settings.yaml.example").read_bytes()
    settings = parse_settings(data)
    assert settings.default_mode == "default" and len(settings.rules.deny) == 3


async def test_permission_supplement(tmp_path):
    from weizhcode.prompting import EnvironmentSnapshot, build_prompt_context
    from weizhcode.prompting.reminders import FULL_PLAN_REMINDER, BRIEF_PLAN_REMINDER
    from weizhcode.permissions.types import PermissionMode
    from weizhcode.prompts import SYSTEM_PROMPT
    for mode in PermissionMode:
        for iteration in (1, 2, 5, 9):
            context = build_prompt_context(SYSTEM_PROMPT, EnvironmentSnapshot(), mode=mode, iteration=iteration)
            assert context.supplements[0].kind == "permission" and mode.value in context.supplements[0].text
            assert context.stable_text == SYSTEM_PROMPT
            if mode == PermissionMode.PLAN:
                assert context.supplements[1].text == (BRIEF_PLAN_REMINDER if iteration == 2 else FULL_PLAN_REMINDER)
            else:
                assert len(context.supplements) == 1


@pytest.mark.parametrize("key,expected", [("1", True), ("2", True), ("3", True), ("4", False), ("escape", False), ("ctrl+c", False),
                                          ("down,down,enter", True), ("up,enter", False)])
async def test_approval_keyboard(tmp_path, key, expected):
    from weizhcode.tui import ChatInput, WeizhCodeApp
    from test_tool_tui import wait_for
    runner = rig(tmp_path, [reply("", (call(),)), reply("done")])
    app = WeizhCodeApp(runner.provider, runner.conversation, runner=runner, provider_name="hidden",
                       model="fake", project_path=str(tmp_path), version="test")
    async with app.run_test() as pilot:
        await app.submit_text("task")
        app.query_one(ChatInput).text = "保留的草稿"
        await wait_for(pilot, lambda: app._pending_approval is not None)
        await pilot.press(*key.split(","))
        await wait_for(pilot, lambda: not app.is_generating)
        assert (tmp_path / "sample.txt").exists() is expected
        assert not app.query_one(ChatInput).disabled
        assert app.query_one(ChatInput).text == "保留的草稿"
        assert runner.approvals._pending is None


async def test_permission_mode_ui(tmp_path):
    from weizhcode.tui import WeizhCodeApp
    from textual.widgets import Static
    runner = rig(tmp_path, [])
    app = WeizhCodeApp(runner.provider, runner.conversation, runner=runner, provider_name="hidden",
                       model="fake", project_path=str(tmp_path), version="test")
    async with app.run_test() as pilot:
        for name, label in (("acceptEdits", "ACCEPT EDITS"), ("plan", "PLAN"),
                            ("bypassPermissions", "BYPASS"), ("default", "DEFAULT")):
            await pilot.press("shift+tab")
            assert runner.mode == name
            assert label in str(app.query_one("#footer-left", Static).render())


async def test_permission_recheck(tmp_path):
    from dataclasses import replace
    from weizhcode.permissions.types import PermissionFailure
    runner = rig(tmp_path, [])
    engine = runner.executor.permissions
    checked = await engine.check(call(), mode="default", cancel=asyncio.Event())
    before = engine.io.inspect_path
    async def changed(*args, **kwargs):
        return replace(await before(*args, **kwargs), canonical_target=str(tmp_path / "other.txt"))
    engine.io.inspect_path = changed
    with pytest.raises(PermissionFailure):
        await engine.accept(checked, ApprovalChoice.SESSION, cancel=asyncio.Event())
    assert not engine.session.allow
    await runner.aclose()


async def test_shutdown_recovery_consumer_closed(tmp_path):
    runner = rig(tmp_path, [reply("", (call(),)), reply("recovered")])
    runner.bind_approvals()
    stream = runner.run("first")
    async for event in stream:
        if event.type == "approval_request":
            break
    await asyncio.wait_for(stream.aclose(), 3)
    assert not runner.busy and runner.approvals._pending is None
    assert runner.conversation.messages()[2].tool_results[0].status == "cancelled"
    assert not (tmp_path / "sample.txt").exists()
    await runner.aclose()


@pytest.mark.parametrize("mode", ["acceptEdits", "bypassPermissions"])
async def test_permission_approval_bypass_matrix(tmp_path, mode):
    runner = rig(tmp_path, [reply("", (call(),)), reply("done")])
    runner.set_mode(mode)
    events = [event async for event in runner.run("write")]
    assert events[-1].reason == "completed" and (tmp_path / "sample.txt").exists()
    assert not any(event.type == "approval_request" for event in events)
    await runner.aclose()


async def test_permission_batch_real_checks_remain_concurrent(tmp_path):
    from weizhcode.models import RunContext
    from weizhcode.tool_scheduler import ToolScheduler
    ready = asyncio.Event()
    class ConcurrentIO(MemoryIO):
        def __init__(self):
            super().__init__()
            self.active = self.peak = 0
        async def inspect_path(self, raw, root, *, cancel):
            if raw == "../outside":
                return await super().inspect_path(raw, root, cancel=cancel)
            self.active += 1
            self.peak = max(self.peak, self.active)
            if self.peak == 4:
                ready.set()
            try:
                await asyncio.wait_for(ready.wait(), 3)
                await asyncio.sleep(0)
                return await super().inspect_path(raw, root, cancel=cancel)
            finally:
                self.active -= 1
    runner = rig(tmp_path, [])
    io = ConcurrentIO()
    runner.executor.permissions.io = io
    paths = ["0.txt", "1.txt", "../outside", "2.txt", "3.txt"]
    calls = []
    for index, path in enumerate(paths):
        if path != "../outside":
            (tmp_path / path).write_text("sample")
        calls.append(ToolCall(str(index), "read_file", json.dumps({"path": path})))
    events = []
    async def emit(event):
        events.append(event)
    results = await asyncio.wait_for(ToolScheduler(runner.registry, runner.executor).execute(
        ChatMessage("assistant", tool_calls=tuple(calls)), context=RunContext(), emit=emit), 10)
    assert io.peak == 4 and [r.call_id for r in results] == list(map(str, range(5)))
    assert [r.status for r in results] == ["success", "success", "denied", "success", "success"]
    assert not any(e.type == "approval_request" for e in events)
    await runner.aclose()
