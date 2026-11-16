from __future__ import annotations


def test_loop_event_contract_correlation_and_copies():
    from weizhcode.models import ToolCall, ToolResult, TokenUsage, TurnEvent, UsageTotals
    call = ToolCall("id", "read_file", '{}', {"path": "a"})
    result = ToolResult("id", "read_file", "ok", metadata={"lines": [1]})
    event = TurnEvent("tool_result", run_id="run", request_id="req", iteration=2,
                      local_id=call.local_id, tool_call=call, result=result,
                      mode="plan", usage=TokenUsage(0, 2, True), totals=UsageTotals())
    call.arguments["path"] = "changed"
    result.metadata["lines"].clear()
    assert event.tool_call.arguments == {"path": "a"}
    assert event.result.metadata == {"lines": [1]}
    assert (event.run_id, event.request_id, event.iteration, event.mode) == ("run", "req", 2, "plan")
    assert ToolCall("id2", "read_file", '{}').local_id != event.local_id

from collections.abc import AsyncIterator

from weizhcode.conversation import Conversation
from weizhcode.models import ChatMessage, ProviderEvent
from weizhcode.tui import ChatInput, ErrorDialog, MessageView, STATUS_TEXT, WeizhCodeApp


class FakeProvider:
    def __init__(self, events: list[ProviderEvent] | None = None) -> None:
        self.events = events or [
            ProviderEvent(type="start"),
            ProviderEvent(type="text_delta", text="你"),
            ProviderEvent(type="text_delta", text="好"),
            ProviderEvent(type="done", assistant_message=ChatMessage("assistant", "你好")),
        ]
        self.calls: list[list[ChatMessage]] = []

    async def stream_chat(
        self, messages: list[ChatMessage], **kwargs
    ) -> AsyncIterator[ProviderEvent]:
        self.calls.append(messages)
        for event in self.events:
            yield event


async def test_tui_renders_provider_and_input() -> None:
    app = make_app()

    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.provider_name == "demo"
        assert app.model == "demo-model"
        assert app.project_path == "D:/demo"
        assert app.version == "0.1.0"
        assert app.query_one("#logo")
        assert app.query_one("#app-title")
        assert app.query_one("#header-model")
        assert app.query_one("#header-path")
        assert app.query_one("#status")
        assert STATUS_TEXT == "Connected to 0 MCP server(s), 7 tools registered"
        assert app.query_one("#footer-left")
        assert app.query_one("#footer-right")
        assert app.query_one(ChatInput)


async def test_submit_streams_reply_into_one_message() -> None:
    provider = FakeProvider()
    conversation = Conversation()
    app = make_app(provider, conversation)

    async with app.run_test() as pilot:
        await app.submit_text("你好")
        await pilot.pause()
        await pilot.pause()

        messages = [view for view in app.query(MessageView).results() if view.role in {"user", "assistant"}]
        assert len(messages) == 2
        assert messages[0].message_content == "你好"
        assert messages[1].message_content == "你好"
        assert messages[0].display_text == "> 你好"
        assert messages[1].display_text == "  你好"
        assert [message.role for message in conversation.messages()] == [
            "user",
            "assistant",
        ]
        assert provider.calls[0][0].content == "你好"


async def test_blank_input_is_ignored() -> None:
    provider = FakeProvider()
    app = make_app(provider)

    async with app.run_test() as pilot:
        await app.submit_text("   ")
        await pilot.pause()

        assert not [view for view in app.query(MessageView).results() if view.role in {"user", "assistant"}]
        assert provider.calls == []


async def test_error_event_does_not_add_assistant_history() -> None:
    provider = FakeProvider(
        [
            ProviderEvent(type="start"),
            ProviderEvent(type="error", message="bad sk-secret"),
        ]
    )
    conversation = Conversation()
    app = make_app(provider, conversation)

    async with app.run_test() as pilot:
        await app.submit_text("hello")
        await pilot.pause()

        assert [message.role for message in conversation.messages()] == ["user", "assistant"]
        assert conversation.messages()[-1].provider_payload["source"] == "application"


async def test_error_dialog_shows_message_text() -> None:
    app = make_app()

    async with app.run_test() as pilot:
        app.push_screen(ErrorDialog("环境变量 DASHSCOPE_API_KEY 未设置"))
        await pilot.pause()

        screen = app.screen_stack[-1]
        assert isinstance(screen, ErrorDialog)
        assert "DASHSCOPE_API_KEY" in screen.message


async def test_exit_commands_close_app() -> None:
    app = make_app()

    async with app.run_test() as pilot:
        await app.submit_text("/quit")
        await pilot.pause()

        assert not app.is_running


def make_app(
    provider: FakeProvider | None = None,
    conversation: Conversation | None = None,
) -> WeizhCodeApp:
    from pathlib import Path
    from weizhcode.permissions.engine import PermissionEngine
    from weizhcode.models import ToolContext
    from weizhcode.tools import create_default_registry
    from weizhcode.tools.executor import ToolExecutor
    from weizhcode.turn_runner import TurnRunner
    provider, conversation = provider or FakeProvider(), conversation or Conversation()
    registry = create_default_registry()
    permissions = PermissionEngine.load(Path("D:/demo"), user_home=Path("D:/nonexistent-test-home"))
    runner = TurnRunner(provider, conversation, registry,
                        ToolExecutor(registry, ToolContext(Path("D:/demo")), permissions=permissions))
    return WeizhCodeApp(
        provider,
        conversation,
        provider_name="demo",
        model="demo-model",
        project_path="D:/demo",
        version="0.1.0",
        runner=runner,
    )


def test_event_contract_pending_is_not_done():
    from weizhcode.models import ToolCall, TurnEvent
    call = ToolCall("id", "read_file", '{}')
    pending = ProviderEvent("tool_call_start", tool_call=call)
    complete_call = ProviderEvent("tool_call", tool_call=call)
    assert pending.type != "done"
    assert complete_call.assistant_message is None
    assert TurnEvent("text_delta", text="x", iteration=2).iteration == 2
