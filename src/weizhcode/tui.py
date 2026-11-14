from __future__ import annotations

from dataclasses import dataclass
import asyncio
from pathlib import Path
from time import monotonic

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Static, TextArea

from weizhcode.conversation import Conversation
from weizhcode.errors import redact_secret
from weizhcode.models import ToolContext
from weizhcode.providers.base import Provider
from weizhcode.redaction import Redactor
from weizhcode.tools import create_default_registry
from weizhcode.tools.executor import ToolExecutor
from weizhcode.turn_runner import TurnRunner
from weizhcode.tool_ui import ToolCallView


LOGO = r""" /\_/\ 
( o.o )
 > ^ <"""
STATUS_TEXT = "Connected to 0 MCP server(s), 6 tools registered"


@dataclass(frozen=True)
class UiContext:
    provider_name: str
    model: str
    project_path: str
    version: str


class MessageView(Static):
    def __init__(self, role: str, content: str = "") -> None:
        self.display_text = self._format(role, content)
        super().__init__(self.display_text, markup=False)
        self.role = role
        self.message_content = content

    def append_text(self, text: str) -> None:
        self.message_content += text
        self.display_text = self._format(self.role, self.message_content)
        self.update(self.display_text)

    @staticmethod
    def _format(role: str, content: str) -> str:
        if role == "user":
            return f"> {content}"
        return f"  {content}"


class ChatInput(TextArea):
    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("placeholder", "› Send a message...")
        kwargs.setdefault("compact", True)
        kwargs.setdefault("show_line_numbers", False)
        super().__init__(*args, **kwargs)

    class Submitted(Message):
        def __init__(self, value: str) -> None:
            self.value = value
            super().__init__()

    def _on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            event.prevent_default()
            self.post_message(self.Submitted(self.text))
        elif event.key == "shift+enter":
            event.prevent_default()
            self.insert("\n")

    def clear_text(self) -> None:
        self.text = ""


class ErrorDialog(ModalScreen[None]):
    CSS = """
    ErrorDialog {
        align: center middle;
    }

    #error-dialog {
        width: 70%;
        max-width: 88;
        height: auto;
        border: heavy $error;
        background: $surface;
        padding: 1 2;
    }

    #error-title {
        text-style: bold;
        color: $error;
        margin-bottom: 1;
    }

    #error-message {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    #ok {
        width: 16;
    }
    """

    def __init__(self, message: str, *, exit_after_ack: bool = False) -> None:
        super().__init__()
        self.message = message
        self.exit_after_ack = exit_after_ack

    def compose(self) -> ComposeResult:
        with Vertical(id="error-dialog"):
            yield Static("出了点问题", id="error-title")
            yield Static(self.message, id="error-message", markup=False)
            yield Button("确定", id="ok", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            if self.exit_after_ack:
                self.app.exit()
            else:
                self.app.pop_screen()


class WeizhCodeApp(App[None]):
    CSS = """
    Screen {
        layout: vertical;
        background: #141414;
        color: #d8d8d8;
    }

    #header {
        height: 4;
        padding: 0 2 0 2;
        background: #141414;
    }

    #logo {
        width: 10;
        height: 3;
        color: #b296ff;
        text-style: bold;
    }

    #header-meta {
        width: 1fr;
        height: 3;
        color: #909090;
    }

    #app-title {
        color: #d8d8d8;
        text-style: bold;
    }

    #header-model {
        color: #a8a8a8;
    }

    #header-path {
        color: #858585;
    }

    #status {
        height: 2;
        padding: 0 3;
        color: #8a8a8a;
        background: #141414;
    }

    #messages {
        height: 1fr;
        padding: 0 3 1 3;
        background: #141414;
    }

    MessageView {
        width: 100%;
        margin-bottom: 1;
        padding: 0;
        border: none;
        color: #cfcfcf;
    }

    MessageView.user {
        color: #d8d8d8;
    }

    MessageView.assistant {
        color: #a8a8a8;
    }

    ChatInput {
        height: 3;
        margin: 0 3;
        padding: 0 1;
        border-top: solid #303030;
        border-bottom: solid #303030;
        border-left: none;
        border-right: none;
        background: #141414;
        color: #d8d8d8;
    }

    ChatInput:focus {
        border-left: solid #55d6c2;
    }

    #footer {
        height: 1;
        padding: 0 3;
        background: #141414;
        color: #777777;
    }

    #footer-left {
        width: 1fr;
        text-align: left;
    }

    #footer-right {
        width: 1fr;
        text-align: right;
        color: #8e8e8e;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel_task", "Cancel", priority=True),
        Binding("ctrl+c", "interrupt", "Cancel / Quit", priority=True),
        Binding("ctrl+d", "quit", "Quit", priority=True),
    ]

    def __init__(
        self,
        provider: Provider,
        conversation: Conversation,
        *,
        provider_name: str,
        model: str,
        project_path: str,
        version: str,
        runner: TurnRunner | None = None,
        redactor: Redactor | None = None,
    ) -> None:
        super().__init__()
        self.provider = provider
        self.conversation = conversation
        self.ui = UiContext(
            provider_name=provider_name,
            model=model,
            project_path=project_path,
            version=version,
        )
        self.provider_name = provider_name
        self.model = model
        self.project_path = project_path
        self.version = version
        self.is_generating = False
        self.redactor = redactor or Redactor()
        if runner is None:
            registry = create_default_registry()
            executor = ToolExecutor(registry, ToolContext(Path(project_path)), self.redactor)
            runner = TurnRunner(provider, conversation, registry, executor, self.redactor)
        self.runner = runner
        self._tool_views = {}
        self._tools_closing = False
        self._close_task = None

        self._generation = 0
        self._active_run_id = None
        self._text_view = self._text_key = None
        self._mode = runner.mode
        self._iteration, self._max_iterations = 0, runner.max_iterations
        self._totals = runner.usage_totals
        self._active_tools = {}
        self._started_at = None
        self._cancel_requested = False

    def compose(self) -> ComposeResult:
        with Horizontal(id="header"):
            yield Static(LOGO, id="logo")
            with Vertical(id="header-meta"):
                yield Static(f"weizhCode v{self.ui.version}", id="app-title")
                yield Static(self.redactor.display(self.ui.model), id="header-model", markup=False)
                yield Static(self.redactor.display(self.ui.project_path), id="header-path", markup=False)
        yield Static(f"Connected to 0 MCP server(s), {len(self.runner.registry.definitions())} tools registered", id="status", markup=False)
        yield VerticalScroll(id="messages")
        yield ChatInput(id="input")
        with Horizontal(id="footer"):
            yield Static(self.redactor.display(self.ui.provider_name), id="footer-left", markup=False)
            yield Static(self.redactor.display(self.ui.model), id="footer-right", markup=False)

    async def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        await self.submit_text(event.value)

    def on_mount(self):
        self.query_one(ChatInput).focus()
        self.set_interval(.1, self._update_status)
        self._update_status()

    def _update_status(self):
        if not self.is_mounted:
            return
        totals = self._totals
        inputs = str(totals.input_tokens) if totals.input_requests else "—"
        outputs = str(totals.output_tokens) if totals.output_requests else "—"
        usage = f"↑{inputs} ↓{outputs}"
        if totals.incomplete_requests:
            usage += f" · 统计不完整（{totals.incomplete_requests} 次请求）"
        mode = "Plan · 只读" if self._mode == "plan" else "Normal"
        progress = "Ready"
        if self.is_generating:
            progress = f"Iteration {self._iteration}/{self._max_iterations}"
            if self._cancel_requested:
                progress += " · 正在取消并清理…"
            elif self._active_tools:
                progress += " · " + ", ".join(list(self._active_tools.values())[:4])
            else:
                progress += " · 等待模型…"
            if self._started_at is not None:
                progress += f" · {monotonic() - self._started_at:.1f}s"
        count = len(self.runner.registry.definitions())
        try:
            self.query_one("#status", Static).update(
                f"Connected to 0 MCP server(s), {count} tools registered\n{mode} · {progress} · {usage}")
        except NoMatches:
            pass

    async def submit_text(self, content):
        from weizhcode.prompts import EXECUTE_DIRECTIVE
        content = content.strip()
        if not content or self._tools_closing:
            return
        if content in {"/exit", "/quit"}:
            await self.action_quit()
            return
        if self.is_generating or self.runner.busy:
            return
        if content == "/plan":
            event = self.runner.set_mode("plan")
            if event.type == "mode_changed":
                self.query_one(ChatInput).clear_text()
            await self._consume_event(event)
            return
        text = EXECUTE_DIRECTIVE if content == "/do" else content
        stream = self.runner.run(text, **({"mode": "normal"} if content == "/do" else {}))
        self._generation += 1
        epoch = self._generation
        self.is_generating = True
        self._active_run_id = None
        self._text_view = self._text_key = None
        self._iteration = 0
        self._started_at = monotonic()
        self._cancel_requested = False
        self.query_one(ChatInput).clear_text()
        await self._append_message("user", self.redactor.display(text))
        self._update_status()
        self.run_worker(self._stream_reply(stream, epoch), group="agent-loop", exclusive=False)

    async def _stream_reply(self, stream, epoch):
        try:
            async for event in stream:
                if epoch == self._generation:
                    await self._consume_event(event)
        except asyncio.CancelledError:
            if epoch == self._generation:
                self.runner.cancel_current()
            raise
        except Exception:
            if epoch == self._generation:
                self.runner.cancel_current()
                await self.show_error("对话事件处理失败，正在停止当前任务")
        finally:
            await stream.aclose()
            if epoch == self._generation and not self.runner.busy:
                self.is_generating = False
                self._update_status()

    async def _consume_event(self, event):
        if event.type == "mode_changed" and not event.run_id:
            self._mode = event.mode
            await self._append_message("notice", self.redactor.display(event.text))
            self._update_status()
            return
        if not self.is_generating:
            return
        if self._active_run_id is None:
            self._active_run_id = event.run_id
        if event.run_id != self._active_run_id:
            return
        if event.type == "iteration_started":
            self._mode, self._iteration = event.mode, event.iteration
            self._max_iterations = event.max_iterations
            self._text_view = self._text_key = None
        elif event.type == "text_delta":
            key = (event.run_id, event.iteration)
            if self._text_view is None or self._text_key != key:
                self._text_view = await self._append_message("assistant", "")
                self._text_key = key
            self._text_view.append_text(self.redactor.display(event.text))
            await self._scroll_to_end()
        elif event.type in {"tool_pending", "tool_start", "tool_preparing", "tool_running", "tool_result"}:
            view = await self._tool_view(event)
            if view is not None:
                if event.type == "tool_result" and event.result is not None:
                    view.finish(event.result)
                    self._active_tools.pop(event.local_id, None)
                else:
                    state = {"tool_pending": "Receiving…", "tool_start": "Queued…",
                             "tool_preparing": "Preparing…", "tool_running": "Running…"}[event.type]
                    view.set_state(state)
                    self._active_tools[event.local_id] = self.redactor.display(view.call.name) + " " + state
            self._text_view = self._text_key = None
            await self._scroll_to_end()
        elif event.type == "usage" and event.totals is not None:
            self._totals = event.totals
        elif event.type == "notice":
            await self._append_message("notice", self.redactor.display(event.text))
        elif event.type == "error":
            if self._text_view is not None:
                self._text_view.append_text("\n[本次回复未完成]")
            await self.show_error(event.text)
        elif event.type == "turn_done":
            for view in self._tool_views.values():
                if view.state in {"Receiving…", "Queued…", "Preparing…", "Running…"}:
                    view.set_state("未执行：响应未完成/已取消" if view.state != "Running…" else "已停止，结果未确认")
            if event.totals is not None:
                self._totals = event.totals
            self._mode = event.mode
            self._active_tools.clear()
            self._tool_views.clear()  # 已挂载的历史组件保留，可滚动回看。
            self.is_generating = False
            self._active_run_id = None
            self._cancel_requested = False
            try:
                self.query_one(ChatInput).focus()
            except NoMatches:
                pass
        self._update_status()

    async def _tool_view(self, event):
        key = (event.run_id, event.local_id)
        view = self._tool_views.get(key)
        if view is None:
            if event.tool_call is None:
                return None
            view = ToolCallView(event.tool_call, self.redactor)
            self._tool_views[key] = view
            await self.query_one("#messages", VerticalScroll).mount(view)
        elif event.tool_call is not None:
            view.update_call(event.tool_call)
        return view

    def action_cancel_task(self):
        if self.runner.cancel_current():
            self._cancel_requested = True
            self._update_status()

    async def action_interrupt(self):
        if self.is_generating or self.runner.busy:
            self.action_cancel_task()
        else:
            await self.action_quit()

    async def _shutdown_tools(self):
        self._tools_closing = True
        await self.runner.aclose()
        for view in self._tool_views.values():
            view.invalidate()
        self._tool_views.clear()


    async def _ensure_shutdown(self):
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._shutdown_tools())
        await asyncio.shield(self._close_task)

    async def action_quit(self):
        await self._ensure_shutdown()
        self.exit()

    async def on_unmount(self):
        await self._ensure_shutdown()

    async def _append_message(self, role: str, content: str) -> MessageView:
        widget = MessageView(role, content)
        widget.add_class(role)
        messages = self.query_one("#messages", VerticalScroll)
        await messages.mount(widget)
        await self._scroll_to_end()
        return widget

    async def _scroll_to_end(self) -> None:
        messages = self.query_one("#messages", VerticalScroll)
        self.call_after_refresh(messages.scroll_end, animate=False)

    async def show_error(self, message: str) -> None:
        safe_message = self.redactor.display(redact_secret(message))
        self.push_screen(ErrorDialog(safe_message))


class StartupErrorApp(App[None]):
    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def on_mount(self) -> None:
        self.push_screen(ErrorDialog(self.message, exit_after_ack=True))
