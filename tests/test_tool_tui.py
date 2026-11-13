from __future__ import annotations

import asyncio
import json

import pytest
from textual.widgets import Button, Static
from textual.containers import VerticalScroll

from weizhcode.conversation import Conversation
from weizhcode.models import ChatMessage, ProviderEvent, ToolCall, ToolContext, ToolResult
from weizhcode.redaction import Redactor
from weizhcode.tool_ui import ToolCallView, result_summary
from weizhcode.tools import create_default_registry
from weizhcode.tools.executor import ToolExecutor
from weizhcode.turn_runner import TurnRunner
from weizhcode.tui import ChatInput, MessageView, ErrorDialog, WeizhCodeApp
from test_turn_runner import FakeProvider, reply


def app_for(tmp_path, replies, *, secrets=(), timeout=30):
    registry = create_default_registry()
    conv = Conversation()
    safe = Redactor(secrets)
    provider = FakeProvider(replies)
    executor = ToolExecutor(registry, ToolContext(tmp_path), safe, timeout=timeout)
    runner = TurnRunner(provider, conv, registry, executor, safe)
    return WeizhCodeApp(provider, conv, provider_name="test", model="test-model",
                        project_path=str(tmp_path), version="0.1.0", runner=runner, redactor=safe)


async def wait_for(pilot, predicate):
    for _ in range(80):
        if predicate():
            return
        await pilot.pause(0.05)
    assert predicate(), "界面状态未在时限内完成"


@pytest.mark.parametrize("allowed", [False, True])
async def test_approval_ui_write_and_decision_binding(tmp_path, allowed):
    target = tmp_path / "new" / "a.txt"
    call = ToolCall("id", "write_file", json.dumps({"path": str(target), "content": "secret-token"}))
    app = app_for(tmp_path, [reply("准备", (call,)), reply("最终")], secrets=["secret-token"])
    async with app.run_test(size=(100, 40)) as pilot:
        await app.submit_text("写文件")
        await wait_for(pilot, lambda: bool(app._approvals))
        view = next(iter(app.query(ToolCallView)))
        assert view.state == "等待确认（默认拒绝）"
        assert app.focused.id == "deny"
        assert not target.parent.exists()
        assert "secret-token" not in str(view.query_one(".tool-preview", Static).render())
        request = view.request
        # 过期或错误操作标识不能释放当前审批。
        app.on_tool_call_view_decision(ToolCallView.Decision(request.request_id, "wrong", True))
        assert not next(iter(app._approvals.values()))[1].done()
        app.query_one(ChatInput).text = "保留草稿"
        await app.submit_text("第二条不应发送")
        assert len(app.provider.requests) == 1
        await pilot.click(view.query_one("#allow" if allowed else "#deny", Button))
        await wait_for(pilot, lambda: not app.is_generating)
        assert len(app.provider.requests) == 2
        assert target.exists() == allowed
        if allowed:
            assert target.read_text(encoding="utf-8") == "secret-token"
        else:
            assert not target.parent.exists()
        assert app.query_one(ChatInput).text == "保留草稿"
        result = app.conversation.messages()[2].tool_results[0]
        assert result.status == ("success" if allowed else "denied")
        assert not app._approvals
        assert all(b.disabled for b in view.query(Button))
        assert len(app.query(ToolCallView)) == 1
        children = list(app.query_one("#messages", VerticalScroll).children)
        assert [type(c) for c in children] == [MessageView, MessageView, ToolCallView, MessageView]
        assert children[-1].message_content == "最终"


async def test_approval_ui_stale_write_no_overwrite(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("old", encoding="utf-8")
    call = ToolCall("id", "write_file", json.dumps({"path": str(target), "content": "new"}))
    app = app_for(tmp_path, [reply("", (call,)), reply("文件已变化")])
    async with app.run_test(size=(100, 40)) as pilot:
        await app.submit_text("写")
        await wait_for(pilot, lambda: bool(app._approvals))
        target.write_text("user update", encoding="utf-8")
        view = next(iter(app.query(ToolCallView)))
        await pilot.click(view.query_one("#allow", Button))
        await wait_for(pilot, lambda: not app.is_generating)
        assert target.read_text(encoding="utf-8") == "user update"
        assert "failed" in view.classes
        assert app.conversation.messages()[2].tool_results[0].error_code == "PREVIEW_STALE"


async def test_tool_view_summary_safe_and_bounded():
    result = ToolResult("id", "read_file", "\x1b[31m[bold]secret-token\n" + "x\n" * 3000)
    text = result_summary(result, Redactor(["secret-token"]))
    assert len(text) <= 1000 and len(text.splitlines()) <= 8
    assert "secret-token" not in text and "\x1b" not in text
    assert "[bold]" in text and "[truncated]" in text
    assert len(result.content) > 1000


async def test_tui_recovery_error_then_normal(tmp_path):
    call = ToolCall("id", "read_file", '{"path":"missing"}')
    app = app_for(tmp_path, [reply("", (call,)), reply("未找到"), reply("正常")])
    async with app.run_test(size=(100, 40)) as pilot:
        await app.submit_text("read")
        await wait_for(pilot, lambda: not app.is_generating)
        view = next(iter(app.query(ToolCallView)))
        assert "failed" in view.classes
        assert not isinstance(app.screen, ErrorDialog)
        await app.submit_text("next")
        await wait_for(pilot, lambda: not app.is_generating)
        assert list(app.query(MessageView))[-1].message_content == "正常"


async def test_tui_recovery_split_secret_markup_and_model_failure(tmp_path):
    app = app_for(tmp_path, [[ProviderEvent("text_delta", text="secret-"),
                             ProviderEvent("text_delta", text="token[bold]\x1b[31m"),
                             ProviderEvent("error", message="secret-token failed")], reply("ok")],
                  secrets=["secret-token"])
    async with app.run_test(size=(100, 40)) as pilot:
        await app.submit_text("secret-token")
        await wait_for(pilot, lambda: not app.is_generating)
        assert isinstance(app.screen, ErrorDialog)
        assert "secret-token" not in app.screen.message
        texts = "".join(m.message_content for m in app.query(MessageView))
        assert "secret-token" not in texts and "\x1b" not in texts
        assert "[bold]" in texts and "未完成" in texts
        assert [m.role for m in app.conversation.messages()] == ["user"]
        await pilot.click("#ok")
        await app.submit_text("next")
        await wait_for(pilot, lambda: not app.is_generating)
        assert list(app.query(MessageView))[-1].message_content == "ok"


async def test_app_shutdown_invalidates_pending_approval(tmp_path):
    target = tmp_path / "never.txt"
    call = ToolCall("id", "write_file", json.dumps({"path": str(target), "content": "never"}))
    app = app_for(tmp_path, [reply("", (call,)), reply("must not request")])
    async with app.run_test(size=(100, 40)) as pilot:
        await app.submit_text("write")
        await wait_for(pilot, lambda: bool(app._approvals))
        pending = next(iter(app._approvals.values()))[1]
        await app.submit_text("/exit")
        await pilot.pause()
        assert not app.is_running
        assert pending.done()
        assert not app._approvals and not target.exists()
        assert len(app.provider.requests) == 1
        assert not app.runner.executor._active


async def test_turn_event_ui_immediate_double_submit(tmp_path):
    app = app_for(tmp_path, [reply("one")])
    async with app.run_test() as pilot:
        await asyncio.gather(app.submit_text("first"), app.submit_text("second"))
        await wait_for(pilot, lambda: not app.is_generating)
        assert len(app.provider.requests) == 1
        assert sum(m.role == "user" for m in app.conversation.messages()) == 1
        assert "6 tools registered" in str(app.query_one("#status", Static).render())



async def test_app_shutdown_running_command_ui(tmp_path):
    from test_command_tool import python_command
    marker = tmp_path / "late.txt"
    command = python_command(f"import time; from pathlib import Path; time.sleep(4); Path({str(marker)!r}).write_text('late')")
    call = ToolCall("id", "run_command", json.dumps({"command": command}))
    app = app_for(tmp_path, [reply("", (call,)), reply("must not request")])
    async with app.run_test(size=(100, 40)) as pilot:
        await app.submit_text("run")
        await wait_for(pilot, lambda: bool(app._approvals))
        view = next(iter(app.query(ToolCallView)))
        assert command in str(view.query_one(".tool-preview", Static).render())
        await pilot.click(view.query_one("#allow", Button))
        await wait_for(pilot, lambda: view.state == "Running…")
        await app.action_quit()
        await pilot.pause()
        assert not app.is_running and not app.runner.executor._active
        assert len(app.provider.requests) == 1
        assert not marker.exists()


async def test_app_shutdown_final_stream_ui(tmp_path):
    first = ToolCall("id", "read_file", '{"path":"missing"}')
    app = app_for(tmp_path, [])
    started = asyncio.Event()
    closed = asyncio.Event()
    class WaitingProvider:
        def __init__(self):
            self.requests = []
        async def stream_chat(self, messages, **kwargs):
            self.requests.append(kwargs)
            if len(self.requests) == 1:
                for event in reply("", (first,)):
                    yield event
            else:
                started.set()
                try:
                    await asyncio.Event().wait()
                    yield ProviderEvent("done")
                finally:
                    closed.set()
    app.provider = app.runner.provider = WaitingProvider()
    async with app.run_test() as pilot:
        await app.submit_text("read")
        await wait_for(pilot, started.is_set)
        await app.action_quit()
        await pilot.pause()
        assert closed.is_set()
        assert len(app.provider.requests) == 2
        assert [m.role for m in app.conversation.messages()] == ["user", "assistant", "tool"]
