from __future__ import annotations

from collections.abc import Awaitable, Callable

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Grid, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static, TextArea

from weizhcode.conversation import Conversation
from weizhcode.errors import redact_secret
from weizhcode.models import ProviderEvent
from weizhcode.providers.base import Provider


class MessageView(Static):
    def __init__(self, role: str, content: str = "") -> None:
        super().__init__(self._format(role, content))
        self.role = role
        self.message_content = content

    def append_text(self, text: str) -> None:
        self.message_content += text
        self.update(self._format(self.role, self.message_content))

    @staticmethod
    def _format(role: str, content: str) -> str:
        name = "You" if role == "user" else "weizhCode"
        return f"{name}:\n{content}"


class ChatInput(TextArea):
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
        margin-bottom: 1;
    }
    """

    def __init__(self, message: str, *, exit_after_ack: bool = False) -> None:
        super().__init__()
        self.message = message
        self.exit_after_ack = exit_after_ack

    def compose(self) -> ComposeResult:
        with Grid(id="error-dialog"):
            yield Label("出了点问题", id="error-title")
            yield Label(self.message, id="error-message")
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
    }

    #provider {
        height: 1;
        padding: 0 1;
        background: $boost;
    }

    #messages {
        height: 1fr;
        padding: 1;
    }

    MessageView {
        width: 100%;
        margin-bottom: 1;
        padding: 1;
        border: solid $primary;
    }

    ChatInput {
        height: 7;
        border: solid $accent;
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
    ) -> None:
        super().__init__()
        self.provider = provider
        self.conversation = conversation
        self.provider_name = provider_name
        self.is_generating = False

    def compose(self) -> ComposeResult:
        yield Static(f"weizhCode · {self.provider_name}", id="provider")
        with Vertical(id="body"):
            yield VerticalScroll(id="messages")
            yield ChatInput(id="input")

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
