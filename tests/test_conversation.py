from __future__ import annotations

from weizhcode.conversation import Conversation


def test_conversation_keeps_messages_in_order() -> None:
    conversation = Conversation()

    conversation.add_user_message("你好")
    conversation.add_assistant_message("你好，我是 weizhCode")
    conversation.add_user_message("记得我刚才说了什么吗？")

    assert [message.role for message in conversation.messages()] == [
        "user",
        "assistant",
        "user",
    ]


def test_messages_returns_copy() -> None:
    conversation = Conversation()
    conversation.add_user_message("hello")

    messages = conversation.messages()
    messages.clear()

    assert len(conversation.messages()) == 1


def test_event_contract_tool_message_data() -> None:
    from weizhcode.models import ChatMessage, ToolCall, ToolResult
    call = ToolCall("id", "read_file", '{}')
    payload = {"items": [{"type": "reasoning"}]}
    message = ChatMessage("assistant", tool_calls=(call,), provider_payload=payload)
    payload["items"].clear()
    assert message.tool_calls[0].call_id == "id"
    assert message.provider_payload["items"]
    assert ChatMessage("tool", tool_results=(ToolResult("id", "read_file"),)).role == "tool"


def test_tool_history_exchange_and_defensive_copy():
    from weizhcode.models import ChatMessage, ToolCall, ToolResult
    conv = Conversation()
    conv.add_user_message("read")
    call = ToolCall("id", "read_file", '{"path":"a"}')
    conv.add_tool_exchange(ChatMessage("assistant", "first", tool_calls=(call,), provider_payload={"items": [{"type": "reasoning"}]}),
                           [ToolResult("id", "read_file", "file content", metadata={"n": 1})])
    conv.add_assistant_turn(ChatMessage("assistant", "final"))
    assert [m.role for m in conv.messages()] == ["user", "assistant", "tool", "assistant"]
    copy = conv.messages()
    copy[1].provider_payload["items"].clear()
    copy[2].tool_results[0].metadata["n"] = 99
    assert conv.messages()[1].provider_payload["items"]
    assert conv.messages()[2].tool_results[0].metadata["n"] == 1


def test_tool_history_rejects_unpaired_valid_call():
    import pytest
    from weizhcode.models import ChatMessage, ToolCall, ToolResult
    conv = Conversation()
    with pytest.raises(ValueError):
        conv.add_tool_exchange(ChatMessage("assistant", tool_calls=(ToolCall("a", "read_file", '{}'),)),
                               [ToolResult("b", "read_file")])
    assert conv.messages() == []


def test_tool_history_invalid_json_uses_diagnostic():
    from weizhcode.models import ChatMessage, ToolCall, ToolResult
    conv = Conversation()
    call = ToolCall(None, "read_file", '{')
    conv.add_tool_exchange(ChatMessage("assistant", tool_calls=(call,)),
                           [ToolResult.failure(call, "INVALID_JSON", "invalid")])
    assert all(m.provider_payload["diagnostic"] for m in conv.messages())

