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

