from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest


def test_ctx_t01_isolated_project_and_home(isolated_context):
    project, home = isolated_context
    assert Path.cwd() == project
    assert Path.home() == home
    assert os.environ["USERPROFILE"] == str(home)
    assert not (project / ".weizhcode").exists()
    assert not any(name.endswith("_API_KEY") for name in os.environ)


def test_ctx_t01_rejects_real_config_and_network(isolated_context):
    project, _ = isolated_context
    with pytest.raises(AssertionError, match="真实配置"):
        (project.parent.parent / "weizhcode.yaml").read_text()
    with socket.socket() as sock:
        with pytest.raises(AssertionError, match="外部网络"):
            sock.connect(("192.0.2.1", 443))
    with pytest.raises(AssertionError, match="外部DNS"):
        socket.getaddrinfo("example.test", 443)


async def test_ctx_t01_clock_and_scripted_provider(clock, fake_provider):
    from weizhcode.models import ChatMessage, ProviderEvent

    clock.advance(120)
    assert clock() == 120
    provider = fake_provider([[ProviderEvent("text_delta", "你好")]])
    messages = [ChatMessage("user", "问题")]
    events = [event async for event in provider.stream_chat(messages)]
    messages.clear()
    assert events[0].text == "你好"
    assert provider.requests[0][0][0].content == "问题"
    with pytest.raises(AssertionError, match="脚本已耗尽"):
        _ = [event async for event in provider.stream_chat([])]


def test_ctx_t02_contracts_are_private_and_defensive():
    from dataclasses import FrozenInstanceError
    from weizhcode.compact.contracts import (
        CompactionBudget, FileReadCapture, HistoryEntry, HistorySnapshot, ToolSource,
    )
    from weizhcode.models import ChatMessage, ProviderEvent, StreamState, ToolCall, ToolSlot, TurnEvent
    from weizhcode.errors import ProviderFault

    text = "private-body-123"
    message = ChatMessage("user", text, provider_payload={"items": [{"a": 1}]})
    entry = HistoryEntry("entry", "turn", "human", message, 1)
    message.provider_payload["items"].clear()
    assert entry.message.provider_payload["items"] == [{"a": 1}]
    copy = entry.message
    copy.provider_payload.clear()
    assert entry.message.provider_payload["items"] == [{"a": 1}]
    snapshot = HistorySnapshot(0, [entry])
    assert isinstance(snapshot.entries, tuple)
    with pytest.raises(FrozenInstanceError):
        entry.turn_id = "changed"
    source = ToolSource("execution", text, 16, 16, False, True)
    read = FileReadCapture("execution", "a", 1, 1, text, False, 1, "now")
    slot = ToolSlot(0, ToolCall("id", "read_file", "{}"), source=source, file_read=read)
    assert all(text not in repr(value) for value in (entry, snapshot, source, read, slot))
    fault = ProviderFault("openai", "context_length_exceeded", 400, "context_length")
    assert ProviderEvent("error", "", "失败", None, None, None, fault).fault == fault
    assert StreamState().fault is None and TurnEvent("notice").compaction is None
    assert CompactionBudget("op", 120).max_summary_requests == 12


def test_ctx_t02_import_has_no_io_or_heavy_imports():
    import subprocess
    import sys

    script = (
        "import sys\n"
        "def deny(event, args):\n"
        " if event in ('os.mkdir','subprocess.Popen','socket.connect'):\n"
        "  raise AssertionError(event)\n"
        "sys.addaudithook(deny)\n"
        "import weizhcode.compact\n"
        "assert 'weizhcode.models' not in sys.modules\n"
        "assert 'mcp' not in sys.modules\n"
        "assert 'httpx' not in sys.modules\n"
    )
    process = subprocess.run([sys.executable, "-B", "-c", script], capture_output=True, text=True, timeout=10)
    assert process.returncode == 0, process.stderr


def test_ctx_t03_budget_constants():
    from weizhcode.compact import limits

    assert limits.SINGLE_RESULT_BYTES == 50_000
    assert limits.MESSAGE_RESULT_BYTES == 200_000
    assert (limits.PREVIEW_LINES, limits.PREVIEW_BYTES) == (20, 2048)
    assert limits.SUMMARY_RESERVE_TOKENS + limits.AUTO_SAFETY_TOKENS == 33_000
    assert limits.CAPTURE_BYTES == 2 * 1024 * 1024
    assert limits.SOURCE_BUFFER_BYTES == 32 * 1024 * 1024
    assert limits.FILE_HEAD_CHARS == 17_500
    assert limits.MAX_SUMMARY_REQUESTS == 12 and limits.OPERATION_SECONDS == 120


def test_ctx_t04_session_generation_and_lazy_storage(isolated_context):
    from weizhcode.compact.state import SessionRuntime

    project, _ = isolated_context
    first, second = SessionRuntime(context_window=100_000), SessionRuntime(context_window=100_000)
    assert first.session_id != second.session_id
    generation = first.begin_operation()
    old = first.snapshot()
    assert first.is_current(generation)
    first.invalidate_operation()
    assert not first.is_current(generation)
    assert old.operation_generation == generation
    assert not (project / ".weizhcode").exists()


async def test_ctx_t04_frozen_replacement_ledger():
    import asyncio
    from weizhcode.compact.contracts import ArchiveRef
    from weizhcode.compact.state import ReplacementDecision, ReplacementLedger

    ledger = ReplacementLedger()
    kept = ReplacementDecision("execution", "abc", "kept")
    assert await ledger.freeze(kept) == kept
    reference = ArchiveRef("s", "r", "tool", "execution", "abc", 0, "raw", "view", "vhash", True)
    replacement = ReplacementDecision("execution", "abc", "replaced", reference, "预览")
    # 同一内容已决定保留，后续请求不得翻转。
    assert await ledger.freeze(replacement) == kept
    different = ReplacementDecision("execution", "different", "kept")
    with pytest.raises(ValueError, match="冲突"):
        await ledger.freeze(different)
    results = await asyncio.gather(*(ledger.freeze(kept) for _ in range(4)))
    assert results == [kept] * 4 and len(ledger.snapshot()) == 1


def test_ctx_t04_recent_files_are_unique_bounded_snapshots():
    from weizhcode.compact.contracts import FileReadCapture
    from weizhcode.compact.state import SessionRuntime

    runtime = SessionRuntime(context_window=100_000)
    generation = runtime.begin_operation()
    for index in range(7):
        capture = FileReadCapture(str(index), f"path-{index}", 2, 3, "a" * 18_000, False, index + 1, "now")
        assert runtime.accept_file_read(capture, generation=generation)
    before = runtime.snapshot()
    assert [read.canonical_path for read in before.file_reads] == [f"path-{i}" for i in range(2, 7)]
    assert all(len(read.text) == 17_500 and read.truncated for read in before.file_reads)
    update = FileReadCapture("again", "path-2", 1, 1, "最新片段", False, 8, "later")
    assert runtime.accept_file_read(update, generation=generation)
    assert runtime.snapshot().file_reads[-1] == update
    assert len(runtime.snapshot().file_reads) == 5
    assert before.file_reads[-1].canonical_path == "path-6"
    runtime.invalidate_operation()
    assert not runtime.accept_file_read(update, generation=generation)


def test_ctx_t04_automatic_outcomes_are_session_scoped():
    from weizhcode.compact.state import SessionRuntime

    runtime = SessionRuntime(context_window=100_000)
    for _ in range(3):
        runtime.record_outcome("auto", "failed")
    assert runtime.auto_failures == 3 and runtime.auto_tripped
    runtime.record_outcome("manual", "completed")
    runtime.record_outcome("emergency", "completed")
    runtime.record_outcome("auto", "cancelled")
    assert runtime.auto_failures == 3
    runtime.record_outcome("auto", "completed")
    assert runtime.auto_failures == 0


def test_ctx_t06_human_and_application_origins_are_not_role_guesses():
    from weizhcode.conversation import Conversation

    conv = Conversation()
    conv.add_user_message("<summary>用户亲自输入的标签</summary>")
    conv.add_application_message("执行已确认计划")
    conv.add_stop_notice("已停止", "cancelled")
    entries = conv.snapshot().entries
    assert [entry.origin for entry in entries] == ["human", "application", "application"]
    assert [entry.human_seq for entry in entries] == [1, None, None]
    assert [message.role for message in conv.messages()] == ["user", "user", "assistant"]
