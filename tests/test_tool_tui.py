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


@pytest.mark.parametrize("answer,expected", [("1", "本地使用"), ("还需要离线使用", "还需要离线使用")])
async def test_ask_question_ui_answer_and_busy_commands(tmp_path, answer, expected):
    call = ToolCall("q", "AskUserQuestion", json.dumps({"question":"使用范围？", "options":["本地使用","团队使用"]}))
    app = app_for(tmp_path, [reply("", (call,)), reply("已确认范围，等待 /do")], timeout=.001)
    app.runner.set_mode("plan")
    async with app.run_test() as pilot:
        await app.submit_text("制定计划")
        app.query_one(ChatInput).text = "保留草稿"
        await wait_for(pilot, lambda: app._pending_question is not None)
        assert app.query_one(ChatInput).text == "保留草稿"
        assert len(app.provider.requests) == 1
        for value in ("/do", "9", "x"*4001, "9"*5000):
            await app.submit_text(value)
            assert app._pending_question is not None
        assert app.query_one(ChatInput).text == "保留草稿" and app.runner.mode == "plan"
        await app.submit_text(answer)
        await wait_for(pilot, lambda: not app.is_generating)
        assert app.query_one(ChatInput).text == ""
        assert json.loads(app.conversation.messages()[2].tool_results[0].content)["answer"] == expected
        assert app.conversation.messages()[-1].content == "已确认范围，等待 /do"
        assert not app.runner.executor._active


async def test_ask_question_ui_cancel_then_new_question(tmp_path):
    call = ToolCall("q", "AskUserQuestion", '{"question":"范围？"}')
    app = app_for(tmp_path, [reply("", (call,)), reply("", (call,)), reply("新计划")])
    app.runner.set_mode("plan")
    async with app.run_test() as pilot:
        await app.submit_text("first")
        await wait_for(pilot, lambda: app._pending_question is not None)
        old_id, old_run = app._pending_question.question_id, app._active_run_id
        await pilot.press("escape")
        await wait_for(pilot, lambda: not app.is_generating)
        await app.submit_text("next")
        await wait_for(pilot, lambda: app._pending_question is not None)
        assert not app.runner.submit_answer(old_run, old_id, {"text":"late"})[0]
        await app.submit_text("新范围")
        await wait_for(pilot, lambda: not app.is_generating)
        assert app.conversation.messages()[-1].content == "新计划"


async def test_ask_question_ui_exit_while_waiting(tmp_path):
    app = app_for(tmp_path, [reply("", (ToolCall("q", "AskUserQuestion", '{"question":"范围？"}'),))])
    app.runner.set_mode("plan")
    async with app.run_test() as pilot:
        await app.submit_text("plan")
        await wait_for(pilot, lambda: app._pending_question is not None)
        await app.submit_text("/exit")
        assert not app.runner.busy and app.runner.questions._pending is None
        assert app.runner.questions._closed and not app.runner.executor._active


async def wait_for(pilot, predicate):
    for _ in range(80):
        if predicate():
            return
        await pilot.pause(0.05)
    assert predicate(), "界面状态未在时限内完成"


def loop_app_for(tmp_path, replies, *, provider=None, secrets=()):
    from weizhcode.turn_runner import TurnRunner
    from weizhcode.tui import WeizhCodeApp
    registry, conv, safe = create_default_registry(), Conversation(), Redactor(secrets)
    provider = provider or FakeProvider(replies)
    runner = TurnRunner(provider, conv, registry, ToolExecutor(registry, ToolContext(tmp_path), safe), safe)
    return WeizhCodeApp(provider, conv, provider_name="test", model="test-model",
                             project_path=str(tmp_path), version="0.1.0", runner=runner, redactor=safe)


async def test_loop_tool_view_cancelled_and_bounded_without_buttons(tmp_path):
    from weizhcode.tool_ui import ToolCallView
    app = loop_app_for(tmp_path, [reply("ok")], secrets=["secret-token"])
    async with app.run_test() as pilot:
        view = ToolCallView(ToolCall("a", "read_file", '{"path":"a"}'), app.redactor)
        await app.query_one("#messages", VerticalScroll).mount(view)
        view.finish(ToolResult("a", "read_file", "secret-token\n" + "x\n" * 100, "cancelled", "TOOL_CANCELLED"))
        assert view.state.startswith("已取消") and "failed" in view.classes
        assert not list(view.query(Button))
        assert len(view.summary) <= 1000 and len(view.summary.splitlines()) <= 8
        assert "secret-token" not in view.summary


async def test_loop_event_ui_only_event_consumer_and_order(tmp_path):
    from weizhcode.models import TurnEvent, UsageTotals
    from weizhcode.tool_ui import ToolCallView
    from weizhcode.tui import WeizhCodeApp
    call = ToolCall("a", "read_file", '{"path":"a"}')
    class EventsRunner:
        registry, mode, max_iterations, usage_totals = create_default_registry(), "normal", 25, UsageTotals()
        busy = False
        def run(self, text, **kwargs):
            self.busy = True
            async def events():
                for kind, extra in [
                    ("iteration_started", {}), ("text_delta", {"text": "before"}),
                    ("tool_start", {"tool_call": call, "local_id": call.local_id}),
                    ("tool_running", {"local_id": call.local_id}),
                    ("tool_result", {"tool_call": call, "local_id": call.local_id,
                                     "result": ToolResult("a", "read_file", "result")}),
                    ("text_delta", {"text": "final"}), ("turn_done", {"reason": "completed"})]:
                    yield TurnEvent(kind, run_id="fake-run", iteration=1, **extra)
                self.busy = False
            return events()
        def cancel_current(self):
            return False
        async def aclose(self):
            self.busy = False
    conv = Conversation()
    app = WeizhCodeApp(object(), conv, provider_name="test", model="model",
                            project_path=str(tmp_path), version="test", runner=EventsRunner())
    async with app.run_test() as pilot:
        await app.submit_text("hello")
        await wait_for(pilot, lambda: not app.is_generating)
        children = list(app.query_one("#messages", VerticalScroll).children)
        assert [type(c) for c in children] == [MessageView, MessageView, ToolCallView, MessageView]
        assert children[1].message_content == "before" and children[-1].message_content == "final"
        assert conv.messages() == []  # 界面不写模型历史、不执行工具。
        assert not app._tool_views


async def test_loop_mode_usage_ui_snapshots_and_do(tmp_path):
    from weizhcode.models import TokenUsage
    usage = ProviderEvent("usage", usage=TokenUsage(10, 2, True, "test"))
    app = loop_app_for(tmp_path, [[usage, usage, *reply("plan")], reply("executed")])
    async with app.run_test(size=(120, 40)) as pilot:
        await app.submit_text("/plan")
        assert not app.provider.requests and app.runner.mode == "plan"
        await app.submit_text("plan task")
        await wait_for(pilot, lambda: not app.is_generating)
        status = str(app.query_one("#status", Static).render())
        assert "Plan" in status and "↑10 ↓2" in status and "7 tools" in status
        await app.submit_text("/do")
        await wait_for(pilot, lambda: not app.is_generating)
        assert app.runner.mode == "normal" and len(app.provider.requests) == 2
        assert app.provider.requests[-1][0][-1].content == "请按上面的计划开始执行。"
        assert "统计不完整" in str(app.query_one("#status", Static).render())


@pytest.mark.parametrize("key", ["escape", "ctrl+c"])
async def test_loop_cancel_keys_focused_input_recovers_without_exit(tmp_path, key):
    entered = asyncio.Event()
    class WaitingProvider(FakeProvider):
        async def stream_chat(self, messages, **kwargs):
            if not self.requests:
                self.requests.append((messages, kwargs))
                entered.set()
                await asyncio.Event().wait()
            else:
                async for e in super().stream_chat(messages, **kwargs):
                    yield e
    provider = WaitingProvider([reply("recovered")])
    app = loop_app_for(tmp_path, [], provider=provider)
    async with app.run_test() as pilot:
        await app.submit_text("wait")
        await asyncio.wait_for(entered.wait(), 2)
        app.query_one(ChatInput).focus()
        await pilot.press(key)
        await wait_for(pilot, lambda: not app.is_generating)
        assert not app._tools_closing and not app.runner.executor._closed
        await app.submit_text("next")
        await wait_for(pilot, lambda: not app.is_generating)
        assert app.conversation.messages()[-1].content == "recovered"
        await pilot.press("escape")
        assert not app._tools_closing


async def test_loop_ui_race_isolation_busy_draft_and_late_ids(tmp_path):
    from weizhcode.models import TurnEvent
    entered = asyncio.Event()
    class WaitingProvider(FakeProvider):
        async def stream_chat(self, messages, **kwargs):
            self.requests.append((messages, kwargs))
            entered.set()
            await asyncio.Event().wait()
            yield ProviderEvent("done")
    provider = WaitingProvider([])
    app = loop_app_for(tmp_path, [], provider=provider)
    async with app.run_test() as pilot:
        await app.submit_text("wait")
        await entered.wait()
        app.query_one(ChatInput).text = "保留草稿"
        for content in ("/plan", "/do", "duplicate"):
            await app.submit_text(content)
        assert app.query_one(ChatInput).text == "保留草稿"
        assert len(provider.requests) == 1 and app.runner.mode == "normal"
        await app._consume_event(TurnEvent("text_delta", text="wrong", run_id="old", iteration=1))
        await app._consume_event(TurnEvent("turn_done", run_id="old"))
        assert app.is_generating
        assert not any(v.message_content == "wrong" for v in app.query(MessageView))
        await pilot.press("escape")
        await wait_for(pilot, lambda: not app.is_generating)
        assert app.query_one(ChatInput).text == "保留草稿"


async def test_loop_cancel_keys_idle_ctrl_c_quits(tmp_path):
    app = loop_app_for(tmp_path, [])
    async with app.run_test() as pilot:
        await pilot.press("ctrl+c")
    assert app._tools_closing and app.runner.executor._closed


async def test_loop_ui_race_isolation_old_consumer_error_does_not_cancel_new(tmp_path):
    app = loop_app_for(tmp_path, [])
    class BrokenOldStream:
        def __aiter__(self):
            return self
        async def __anext__(self):
            raise RuntimeError("old consumer failed")
        async def aclose(self):
            pass
    cancelled = []
    app.runner.cancel_current = lambda: cancelled.append(True)
    app._generation = 2
    await app._stream_reply(BrokenOldStream(), 1)
    assert not cancelled


@pytest.mark.parametrize("mode", ["normal", "plan"])
async def test_loop_production_path_write_mode_gate_no_buttons(tmp_path, mode):
    target = tmp_path / "new" / "a.txt"
    call = ToolCall("id", "write_file", json.dumps({"path": str(target), "content": "secret-token"}))
    app = app_for(tmp_path, [reply("准备", (call,)), reply("最终")], secrets=["secret-token"])
    if mode == "plan":
        app.runner.set_mode("plan")
    async with app.run_test(size=(100, 40)) as pilot:
        await app.submit_text("写文件")
        await wait_for(pilot, lambda: not app.is_generating)
        view = next(iter(app.query(ToolCallView)))
        assert not list(view.query(Button))
        assert target.exists() is (mode == "normal")
        if mode == "normal":
            assert target.read_text(encoding="utf-8") == "secret-token"
        else:
            assert not target.parent.exists()
        result = app.conversation.messages()[2].tool_results[0]
        assert result.error_code == (None if mode == "normal" else "TOOL_NOT_ALLOWED")
        assert "secret-token" not in view.state + view.title()
        children = list(app.query_one("#messages", VerticalScroll).children)
        assert [type(c) for c in children] == [MessageView, MessageView, ToolCallView, MessageView]
        assert children[-1].message_content == "最终"


async def test_loop_production_path_stale_write_no_overwrite(tmp_path):
    from weizhcode.tools.process import ManagedWorker
    target = tmp_path / "a.txt"
    target.write_text("old", encoding="utf-8")
    call = ToolCall("id", "write_file", json.dumps({"path": str(target), "content": "new"}))
    app = app_for(tmp_path, [reply("", (call,)), reply("文件已变化")])
    class ChangedWorker(ManagedWorker):
        async def prepare(self, call):
            preview = await super().prepare(call)
            target.write_text("user update", encoding="utf-8")
            return preview
    app.runner.executor.worker_factory = ChangedWorker
    async with app.run_test(size=(100, 40)) as pilot:
        await app.submit_text("写")
        await wait_for(pilot, lambda: not app.is_generating)
        assert target.read_text(encoding="utf-8") == "user update"
        assert "failed" in next(iter(app.query(ToolCallView))).classes
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
        assert [m.role for m in app.conversation.messages()] == ["user", "assistant"]
        assert app.conversation.messages()[-1].provider_payload["source"] == "application"
        await pilot.click("#ok")
        await app.submit_text("next")
        await wait_for(pilot, lambda: not app.is_generating)
        assert list(app.query(MessageView))[-1].message_content == "ok"


async def test_app_shutdown_prepared_write_before_execute(tmp_path):
    from weizhcode.tools.process import ManagedWorker
    target, entered = tmp_path / "never.txt", asyncio.Event()
    call = ToolCall("id", "write_file", json.dumps({"path": str(target), "content": "never"}))
    app = app_for(tmp_path, [reply("", (call,)), reply("must not request")])
    class WaitingPrepare(ManagedWorker):
        async def prepare(self, call):
            preview = await super().prepare(call)
            entered.set()
            await asyncio.Event().wait()
            return preview
    app.runner.executor.worker_factory = WaitingPrepare
    async with app.run_test(size=(100, 40)) as pilot:
        await app.submit_text("write")
        await asyncio.wait_for(entered.wait(), 5)
        await app.submit_text("/exit")
        await pilot.pause()
        assert not app.is_running and not target.exists()
        assert len(app.provider.requests) == 1 and not app.runner.executor._active


async def test_turn_event_ui_immediate_double_submit(tmp_path):
    app = app_for(tmp_path, [reply("one")])
    async with app.run_test() as pilot:
        await asyncio.gather(app.submit_text("first"), app.submit_text("second"))
        await wait_for(pilot, lambda: not app.is_generating)
        assert len(app.provider.requests) == 1
        assert sum(m.role == "user" for m in app.conversation.messages()) == 1
        assert "7 tools registered" in str(app.query_one("#status", Static).render())



async def test_app_shutdown_running_command_ui(tmp_path):
    from test_command_tool import python_command
    marker = tmp_path / "late.txt"
    command = python_command(f"import time; from pathlib import Path; time.sleep(4); Path({str(marker)!r}).write_text('late')")
    call = ToolCall("id", "run_command", json.dumps({"command": command}))
    app = app_for(tmp_path, [reply("", (call,)), reply("must not request")])
    async with app.run_test(size=(100, 40)) as pilot:
        await app.submit_text("run")
        await wait_for(pilot, lambda: any(v.state == "Running…" for v in app.query(ToolCallView)))
        view = next(iter(app.query(ToolCallView)))
        assert "run_command" in view.title()
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
    app.runner.collector.provider = app.provider
    async with app.run_test() as pilot:
        await app.submit_text("read")
        await wait_for(pilot, started.is_set)
        await app.action_quit()
        await pilot.pause()
        assert closed.is_set()
        assert len(app.provider.requests) == 2
        assert [m.role for m in app.conversation.messages()] == ["user", "assistant", "tool", "assistant"]
        assert app.conversation.messages()[-1].provider_payload["source"] == "application"
