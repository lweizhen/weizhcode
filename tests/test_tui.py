from __future__ import annotations

from collections.abc import AsyncIterator

from weizhcode.conversation import Conversation
from weizhcode.models import ChatMessage, ProviderEvent
from weizhcode.tui import ChatInput, ErrorDialog, MessageView, WeizhCodeApp


class FakeProvider:
    def __init__(self, events: list[ProviderEvent] | None = None) -> None:
        self.events = events or [
            ProviderEvent(type="start"),
            ProviderEvent(type="text_delta", text="你"),
            ProviderEvent(type="text_delta", text="好"),
            ProviderEvent(type="done"),
        ]
        self.calls: list[list[ChatMessage]] = []

    async def stream_chat(
        self, messages: list[ChatMessage]
    ) -> AsyncIterator[ProviderEvent]:
        self.calls.append(messages)
        for event in self.events:
            yield event


async def test_tui_renders_provider_and_input() -> None:
    app = WeizhCodeApp(FakeProvider(), Conversation(), provider_name="demo")

    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.provider_name == "demo"
        assert app.query_one(ChatInput)


async def test_submit_streams_reply_into_one_message() -> None:
    provider = FakeProvider()
    conversation = Conversation()
    app = WeizhCodeApp(provider, conversation, provider_name="demo")

    async with app.run_test() as pilot:
        await app.submit_text("你好")
        await pilot.pause()
        await pilot.pause()

        messages = list(app.query(MessageView).results())
        assert len(messages) == 2
        assert messages[0].message_content == "你好"
        assert messages[1].message_content == "你好"
        assert [message.role for message in conversation.messages()] == [
            "user",
            "assistant",
        ]
        assert provider.calls[0][0].content == "你好"


async def test_blank_input_is_ignored() -> None:
    provider = FakeProvider()
    app = WeizhCodeApp(provider, Conversation(), provider_name="demo")

    async with app.run_test() as pilot:
        await app.submit_text("   ")
        await pilot.pause()

        assert list(app.query(MessageView).results()) == []
        assert provider.calls == []


async def test_error_event_does_not_add_assistant_history() -> None:
    provider = FakeProvider(
        [
            ProviderEvent(type="start"),
            ProviderEvent(type="error", message="bad sk-secret"),
        ]
    )
    conversation = Conversation()
    app = WeizhCodeApp(provider, conversation, provider_name="demo")

    async with app.run_test() as pilot:
        await app.submit_text("hello")
        await pilot.pause()

        assert [message.role for message in conversation.messages()] == ["user"]


async def test_error_dialog_shows_message_text() -> None:
    app = WeizhCodeApp(FakeProvider(), Conversation(), provider_name="demo")

    async with app.run_test() as pilot:
        app.push_screen(ErrorDialog("环境变量 DASHSCOPE_API_KEY 未设置"))
        await pilot.pause()

        screen = app.screen_stack[-1]
        assert isinstance(screen, ErrorDialog)
        assert "DASHSCOPE_API_KEY" in screen.message


async def test_exit_commands_close_app() -> None:
    app = WeizhCodeApp(FakeProvider(), Conversation(), provider_name="demo")

    async with app.run_test() as pilot:
        await app.submit_text("/quit")
        await pilot.pause()

        assert not app.is_running
