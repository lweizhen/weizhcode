import asyncio
from uuid import uuid4

from weizhcode.compact.contracts import CompactionBudget
from weizhcode.compact.layer1 import Layer1
from weizhcode.compact.state import SessionRuntime
from weizhcode.compact.archive import SessionStore
from weizhcode.compact.capture import CaptureHub
from weizhcode.conversation import Conversation
from weizhcode.models import ChatMessage, ToolCall, ToolResult
from weizhcode.permissions.sandbox import make_root
from weizhcode.redaction import Redactor
import pytest


async def test_ctx_t35_ctx_t36_ctx_t37_threshold_aggregate_and_frozen(tmp_path):
    runtime = SessionRuntime(context_window=128000)
    safe = Redactor()
    runtime.store = SessionStore(make_root(tmp_path), runtime.session_id, safe)
    runtime.sources = CaptureHub(safe)
    conversation = Conversation()
    conversation.add_user_message('test')
    calls, results, keys = [], [], []
    for i in range(6):
        key, text = f'exec:{i}', '中' * 13333 + 'x'
        sink = await runtime.sources.reserve(key, generation=1)
        await sink.begin(collected_bytes=len(text.encode()), truncated=False)
        for offset in range(0, len(text), 4096):
            await sink.feed(text[offset:offset+4096])
        await sink.finish()
        calls.append(ToolCall(str(i), 'read_file', '{}', {}))
        results.append(ToolResult(str(i), 'read_file', text[:100]))
        keys.append(key)
    conversation.add_tool_exchange(ChatMessage('assistant', tool_calls=tuple(calls)), results, result_keys=keys)
    layer = Layer1(runtime, safe)
    budget = CompactionBudget(uuid4().hex, asyncio.get_running_loop().time()+60)
    try:
        assert await layer.apply(conversation, cancel=asyncio.Event(), budget=budget) == 1
        decisions = runtime.replacements.snapshot()
        assert [d.kind for d in decisions] == ['replaced', 'kept', 'kept', 'kept', 'kept', 'kept']
        for d in decisions[:1]:
            assert len(d.preview.encode()) <= 2048 and len(d.preview.splitlines()) <= 20
            assert (tmp_path / d.reference.raw_path).read_text(encoding='utf-8') == '中' * 13333 + 'x'
        previous = conversation.messages()
        assert await layer.apply(conversation, cancel=asyncio.Event(), budget=budget) == 0
        assert conversation.messages() == previous
    finally:
        await runtime.store.aclose()
        await runtime.sources.aclose()


@pytest.mark.parametrize('size,expected', [(50000, 0), (50001, 1)])
async def test_ctx_t35_exact_utf8_boundary_and_partial_flags(size, expected, tmp_path):
    runtime = SessionRuntime(context_window=128000)
    runtime.sources = CaptureHub(Redactor())
    runtime.store = SessionStore(make_root(tmp_path), runtime.session_id, Redactor())
    text = '中'*16666 + 'x'*(size-49998)
    sink = await runtime.sources.reserve('exec', generation=1)
    await sink.begin(collected_bytes=size+100, truncated=True)
    for offset in range(0, len(text), 4096):
        await sink.feed(text[offset:offset+4096])
    await sink.finish(complete=False)
    conversation = Conversation()
    conversation.add_user_message('read')
    call = ToolCall('same-remote-id', 'read_file', '{}', {})
    conversation.add_tool_exchange(ChatMessage('assistant', tool_calls=(call,)),
        [ToolResult(call.call_id, call.name, text)], result_keys=('exec',))
    try:
        count = await Layer1(runtime, Redactor()).apply(conversation, cancel=asyncio.Event(),
            budget=CompactionBudget(uuid4().hex, asyncio.get_running_loop().time()+30))
        assert count == expected
        decision = runtime.replacements.get('exec')
        if expected:
            assert not decision.reference.complete and 'True' in decision.preview
            assert (tmp_path/decision.reference.raw_path).read_bytes() == text.encode()
    finally:
        await runtime.store.aclose()
        await runtime.sources.aclose()


@pytest.mark.parametrize('total,expected', [(200000, 0), (200001, 1)])
async def test_ctx_t36_exact_aggregate_boundary(total, expected, tmp_path):
    runtime = SessionRuntime(context_window=128000)
    runtime.store = SessionStore(make_root(tmp_path), runtime.session_id, Redactor())
    conversation = Conversation()
    conversation.add_user_message('aggregate')
    calls = tuple(ToolCall(str(i), 'read_file', '{}', {}) for i in range(5))
    results = [ToolResult(str(i), 'read_file', 'x'*(40000 if i < 4 else total-160000)) for i in range(5)]
    conversation.add_tool_exchange(ChatMessage('assistant', tool_calls=calls), results)
    try:
        count = await Layer1(runtime, Redactor()).apply(conversation, cancel=asyncio.Event(),
            budget=CompactionBudget(uuid4().hex, asyncio.get_running_loop().time()+30))
        assert count == expected
        if expected:
            decisions = runtime.replacements.snapshot()
            assert decisions[0].execution_key.endswith(':4')  # 最大项优先，非盲目第一项。
    finally:
        await runtime.store.aclose()


async def test_ctx_t37_save_failure_not_frozen_and_concurrent_retry_is_idempotent(tmp_path):
    from weizhcode.compact.archive import StoreResult
    runtime = SessionRuntime(context_window=128000)
    runtime.store = SessionStore(make_root(tmp_path), runtime.session_id, Redactor())
    conversation = Conversation()
    conversation.add_user_message('original')
    call = ToolCall('same-remote', 'read_file', '{}', {})
    conversation.add_tool_exchange(ChatMessage('assistant', tool_calls=(call,)), [ToolResult(call.call_id, call.name, 'x'*50001)])
    layer = Layer1(runtime, Redactor())
    original = runtime.store.save_text
    async def fail(*args, **kwargs): return StoreResult('known_failed', code='DISK_FULL')
    budget = CompactionBudget(uuid4().hex, asyncio.get_running_loop().time()+30)
    try:
        runtime.store.save_text = fail
        assert await layer.apply(conversation, cancel=asyncio.Event(), budget=budget) == 0
        assert not runtime.replacements.snapshot()
        runtime.store.save_text = original
        counts = await asyncio.gather(*(layer.apply(conversation, cancel=asyncio.Event(), budget=budget) for _ in range(2)))
        assert sorted(counts) == [0, 1] and len(runtime.replacements.snapshot()) == 1
    finally:
        await runtime.store.aclose()
