import asyncio
from types import SimpleNamespace

from weizhcode.compact.manager import ContextManager
from weizhcode.compact.state import SessionRuntime
from weizhcode.compact.archive import SessionStore
from weizhcode.conversation import Conversation
from weizhcode.models import ChatMessage, ProviderEvent, TokenUsage
from weizhcode.permissions.sandbox import make_root
from weizhcode.prompting.contracts import PromptContext
from weizhcode.providers.request import prepare_body
from weizhcode.redaction import Redactor
import pytest


class SummaryProvider:
    def prepare_request(self, messages, *, tools=(), system_prompt='', prompt_context=None, options=None, redactor=None):
        from weizhcode.providers.request import RequestOptions
        return prepare_body({'messages': [{'role': m.role, 'content': m.content} for m in messages],
            'system': system_prompt or (prompt_context.stable_text + ''.join(s.text for s in prompt_context.supplements)),
            'tools': [{'name': t.name} for t in tools], 'max_tokens': 4096},
            protocol='qwen', options=options or RequestOptions())

    async def stream_prepared(self, request):
        from test_summary import valid_summary
        assert request.purpose == 'summary' and not request.body()['tools']
        yield ProviderEvent('done', assistant_message=ChatMessage('assistant', valid_summary()), finish_reason='stop')


async def test_ctx_t40_ctx_t41_ctx_t48_ctx_t49_ctx_t50_transaction_and_archived_humans(tmp_path):
    runtime = SessionRuntime(context_window=128000)
    runtime.begin_operation()
    runtime.store = SessionStore(make_root(tmp_path), runtime.session_id, Redactor())
    provider = SummaryProvider()
    manager = ContextManager(runtime, provider, Redactor())
    conversation = Conversation()
    for i in range(12):
        conversation.add_user_message(f'用户{i} '+ 'u'*8000)
        conversation.add_assistant_message('a'*8000)
    events, usages = [], []
    async def emit(e): events.append(e)
    async def settle(req, usage, **kwargs): usages.append(req.request_id)
    try:
        before = conversation.snapshot()
        result = await manager.compact(conversation, tools=(), prompt=PromptContext('stable'), trigger='manual',
            cancel=asyncio.Event(), emit=emit, settle=settle, current=lambda: True)
        assert result.status == 'completed', result.code
        assert conversation.snapshot().revision > before.revision
        assert len(conversation.messages()) < len(before.entries)
        assert runtime.human_index.snapshot() and runtime.index_reference.pages
        assert 'private draft' not in str(conversation.messages())
        assert len(usages) == 1 and events[-1].compaction.phase == 'completed'
        previous = conversation.snapshot()
        for _ in range(3):
            outcome = await manager.compact(conversation, tools=(), prompt=PromptContext('stable'), trigger='auto',
                cancel=asyncio.Event(), emit=emit, settle=settle, current=lambda: False)
            assert outcome.status in {'failed', 'no_reduction'}
        assert runtime.auto_tripped and conversation.snapshot() == previous
    finally:
        await manager.aclose()


@pytest.mark.parametrize('fault', ['cancel', 'revision', 'mode', 'index', 'bad_summary', 'save_failure'])
async def test_ctx_t48_ctx_t52_ctx_t65_atomic_failures_keep_history(tmp_path, fault):
    runtime = SessionRuntime(context_window=128000)
    runtime.begin_operation()
    runtime.store = SessionStore(make_root(tmp_path), runtime.session_id, Redactor())
    conversation = Conversation()
    for i in range(12):
        conversation.add_user_message('u'*8000)
        conversation.add_assistant_message('a'*8000)
    provider = SummaryProvider()
    manager = ContextManager(runtime, provider, Redactor())
    cancel = asyncio.Event()
    before = conversation.snapshot()
    original_stream = provider.stream_prepared
    async def faulty_stream(request):
        if fault == 'cancel': cancel.set()
        if fault == 'revision': conversation.add_application_message('concurrent app notice')
        if fault == 'index':
            for path in tmp_path.glob('.weizhcode/sessions/*/users/page-*.jsonl'):
                path.write_text('tampered')
        if fault == 'bad_summary':
            yield ProviderEvent('done', assistant_message=ChatMessage('assistant', 'not a summary'))
        else:
            async for event in original_stream(request): yield event
    provider.stream_prepared = faulty_stream
    if fault == 'save_failure':
        from weizhcode.compact.archive import StoreResult
        async def failed(*args, **kwargs): return StoreResult('known_failed', code='ARCHIVE_RECORD_LIMIT')
        runtime.store.save_text = failed
    async def emit(e): pass
    async def settle(*args, **kwargs): pass
    try:
        result = await manager.compact(conversation, tools=(), prompt=PromptContext('stable'), trigger='auto',
            cancel=cancel, emit=emit, settle=settle, current=lambda: fault != 'mode')
        assert result.status in {'failed', 'cancelled'}
        if fault == 'revision':
            assert conversation.snapshot().entries[:len(before.entries)] == before.entries
        else:
            assert conversation.snapshot() == before
        assert runtime.latest_summary is None
        assert runtime.auto_failures == (0 if fault == 'cancel' else 1)
    finally:
        await manager.aclose()


async def test_ctx_t51_manual_bypasses_but_never_resets_breaker(tmp_path):
    runtime = SessionRuntime(context_window=128000)
    runtime.begin_operation()
    runtime.auto_failures = 3
    runtime.store = SessionStore(make_root(tmp_path), runtime.session_id, Redactor())
    conversation = Conversation()
    for _ in range(12):
        conversation.add_user_message('u'*8000)
        conversation.add_assistant_message('a'*8000)
    manager = ContextManager(runtime, SummaryProvider(), Redactor())
    async def emit(e): pass
    async def settle(*args, **kwargs): pass
    try:
        outcome = await manager.compact(conversation, tools=(), prompt=PromptContext('stable'), trigger='manual',
            cancel=asyncio.Event(), emit=emit, settle=settle, current=lambda: True)
        assert outcome.status == 'completed' and runtime.auto_failures == 3
    finally:
        await manager.aclose()


@pytest.mark.parametrize('estimate,expected', [(66999, 0), (67000, 1)])
async def test_ctx_t49_exact_auto_threshold_once(estimate, expected):
    runtime = SessionRuntime(context_window=100000)
    manager = ContextManager(runtime, SummaryProvider(), Redactor())
    manager.estimator.estimate = lambda request, **kwargs: estimate
    count = 0
    async def compact(*args, **kwargs):
        nonlocal count
        count += 1
    manager.compact = compact
    async def emit(e): pass
    async def settle(*args, **kwargs): pass
    request = await manager.before_request(Conversation(), tools=(), prompt=PromptContext('stable'),
        cancel=asyncio.Event(), emit=emit, settle=settle, current=lambda: True)
    assert count == expected and request.purpose == 'chat'
