from __future__ import annotations

from dataclasses import dataclass

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Static, TextArea

from weizhcode.conversation import Conversation
from weizhcode.errors import redact_secret
from weizhcode.models import ProviderEvent
from weizhcode.providers.base import Provider


LOGO = r""" /\_/\ 
( o.o )
 > ^ <"""
STATUS_TEXT = "Connected to 0 MCP server(s), 0 tools registered"


@dataclass(frozen=True)
class UiContext:
    provider_name: str
    model: str
    project_path: str
    version: str


class MessageView(Static):
    def __init__(self, role: str, content: str = "") -> None:
        self.display_text = self._format(role, content)
        super().__init__(self.display_text)
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
            yield Static(self.message, id="error-message")
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
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+d", "quit", "Quit"),
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

    def compose(self) -> ComposeResult:
        with Horizontal(id="header"):
            yield Static(LOGO, id="logo")
            with Vertical(id="header-meta"):
                yield Static(f"weizhCode v{self.ui.version}", id="app-title")
                yield Static(self.ui.model, id="header-model")
                yield Static(self.ui.project_path, id="header-path")
        yield Static(STATUS_TEXT, id="status")
        yield VerticalScroll(id="messages")
        yield ChatInput(id="input")
        with Horizontal(id="footer"):
            yield Static(self.ui.provider_name, id="footer-left")
            yield Static(self.ui.model, id="footer-right")

    def on_mount(self) -> None:
        self.query_one(ChatInput).focus()

    async def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        await self.submit_text(event.value)

    async def submit_text(self, content: str) -> None:
        content = content.strip()
        if not content or self.is_generating:
            return
        if content in {"/exit", "/quit"}:
            self.exit()
            return

        input_widget = self.query_one(ChatInput)
        input_widget.clear_text()
        await self._append_message("user", content)
        self.conversation.add_user_message(content)
        self.run_worker(self._stream_reply(), exclusive=True)

    async def _stream_reply(self) -> None:
        self.is_generating = True
        assistant_message = await self._append_message("assistant", "")
        parts: list[str] = []
        try:
            async for event in self.provider.stream_chat(self.conversation.messages()):
                if event.type == "text_delta":
                    assistant_message.append_text(event.text)
                    parts.append(event.text)
                    await self._scroll_to_end()
                elif event.type == "error":
                    await self.show_error(event.message)
                    return
                elif event.type == "done":
                    break
            full_text = "".join(parts)
            if full_text:
                self.conversation.add_assistant_message(full_text)
        except Exception as exc:  # noqa: BLE001 - 用户界面需要兜底展示异常。
            await self.show_error(str(exc))
        finally:
            self.is_generating = False
            try:
                self.query_one("#input", ChatInput).focus()
            except NoMatches:
                pass

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
        safe_message = redact_secret(message)
        self.push_screen(ErrorDialog(safe_message))


class StartupErrorApp(App[None]):
    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def on_mount(self) -> None:
        self.push_screen(ErrorDialog(self.message, exit_after_ack=True))
