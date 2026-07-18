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

