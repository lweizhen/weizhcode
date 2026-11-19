import pytest


def test_ctx_t40_recent_requires_both_bounds_and_keeps_current_group():
    from weizhcode.compact.history import split_recent
    from weizhcode.conversation import Conversation
    conversation = Conversation()
    for _ in range(10):
        conversation.add_user_message('short')
        conversation.add_assistant_message('answer')
    old, recent = split_recent(conversation.snapshot().entries)
    assert not old and len(recent) == 20  # 条数足但token不足，不能擅自缩短近期。
    conversation.add_user_message('x'*50000)
    conversation.add_assistant_message('last')
    old, recent = split_recent(conversation.snapshot().entries)
    assert len(recent) >= 5 and recent[-2].message.content == 'x'*50000
    assert all(e.turn_id != recent[0].turn_id for group in old for e in group)

from weizhcode.compact.contracts import HistoryEntry
from weizhcode.models import ChatMessage, ToolCall, ToolResult


def test_ctx_t05_complete_groups_and_human_sequence():
    from weizhcode.compact.history import validate_entries

    call = ToolCall("x", "read_file", "{}")
    assistant = HistoryEntry("a", "task", "provider", ChatMessage("assistant", tool_calls=(call,)))
    result = HistoryEntry("t", "task", "tool", ChatMessage("tool", tool_results=(ToolResult("x", "read_file"),)))
    validate_entries((assistant, result))
    with pytest.raises(ValueError, match="工具"):
        validate_entries((result, assistant))
    other = HistoryEntry("other", "other-task", "tool", result.message)
    with pytest.raises(ValueError, match="任务"):
        validate_entries((assistant, other))
    first = HistoryEntry("u1", "task", "human", ChatMessage("user", "a"), 2)
    second = HistoryEntry("u2", "task2", "human", ChatMessage("user", "b"), 1)
    with pytest.raises(ValueError, match="序号"):
        validate_entries((first, second))
