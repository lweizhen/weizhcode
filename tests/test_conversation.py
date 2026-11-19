from __future__ import annotations

from weizhcode.conversation import Conversation


def test_loop_exchange_contract_count_order_and_atomicity():
    import pytest
    from weizhcode.models import ChatMessage, ToolCall, ToolResult
    conv = Conversation()
    calls = (ToolCall("a", "read_file", '{}'), ToolCall("b", "read_file", '{}'))
    msg = ChatMessage("assistant", tool_calls=calls)
    for results in ([], [ToolResult("a", "read_file")],
                    [ToolResult("b", "read_file"), ToolResult("a", "read_file")],
                    [ToolResult("a", "wrong"), ToolResult("b", "read_file")]):
        with pytest.raises(ValueError):
            conv.add_tool_exchange(msg, results)
        assert conv.messages() == []
    conv.add_tool_exchange(msg, [ToolResult("a", "read_file"), ToolResult("b", "read_file")])
    assert len(conv.messages()) == 2
    invalid = ChatMessage("assistant", tool_calls=(ToolCall(None, "read_file", '{'),))
    with pytest.raises(ValueError):
        conv.add_tool_exchange(invalid, [])
    assert len(conv.messages()) == 2


def test_application_stop_notice_source_dedup_and_next_task():
    conv = Conversation()
    conv.add_user_message("do something")
    conv.add_assistant_message("preamble")
    conv.add_stop_notice("已取消，已有修改可能保留", "cancelled", run_id="a")
    conv.add_stop_notice("已取消，已有修改可能保留", "cancelled", run_id="a")
    assert len(conv.messages()) == 3
    assert conv.messages()[-1].provider_payload == {"source": "application", "reason": "cancelled", "run_id": "a"}
    conv.add_user_message("next")
    conv.add_stop_notice("已取消", "cancelled", run_id="b")
    assert len(conv.messages()) == 5


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


def test_ctx_t05_revision_cas_and_origin():
    import pytest
    from weizhcode.compact.contracts import HistoryEntry
    from weizhcode.models import ChatMessage

    conv = Conversation()
    assert conv.snapshot().revision == 0
    conv.add_user_message("原话")
    before = conv.snapshot()
    assert before.entries[0].origin == "human" and before.entries[0].human_seq == 1
    assert "原话" not in repr(before)
    conv.add_assistant_message("答复")
    assert not conv.replace_if_current(before.revision, before.entries)
    current = conv.snapshot()
    with pytest.raises(ValueError):
        conv.replace_if_current(current.revision, None)
    assert conv.snapshot() == current
    summary = HistoryEntry("summary-id", current.entries[-1].turn_id, "summary", ChatMessage("user", "摘要资料"))
    assert conv.replace_if_current(current.revision, (summary,))
    assert conv.snapshot().revision == current.revision + 1
    conv.add_user_message("下一条原话")
    assert conv.snapshot().entries[-1].human_seq == 2
    assert conv.messages()[0].content == "摘要资料"


def test_ctx_t05_snapshot_deep_copy_and_atomic_pair_validation():
    import pytest
    from weizhcode.models import ChatMessage, ToolCall, ToolResult

    conv = Conversation()
    conv.add_user_message("读")
    call = ToolCall("id", "read_file", "{}")
    conv.add_tool_exchange(ChatMessage("assistant", tool_calls=(call,), provider_payload={"items": [1]}),
                           [ToolResult("id", "read_file", "data")])
    before = conv.snapshot()
    before.entries[1].message.provider_payload["items"].clear()
    assert conv.messages()[1].provider_payload["items"] == [1]
    assert before.entries[1].turn_id == before.entries[2].turn_id == before.entries[0].turn_id
    for invalid in (before.entries[1:2], before.entries[2:], (before.entries[0], before.entries[2])):
        with pytest.raises(ValueError, match="工具"):
            conv.replace_if_current(before.revision, invalid)
        assert conv.snapshot() == before
    assert conv.replace_if_current(before.revision, before.entries)

