import asyncio
from types import SimpleNamespace
from uuid import uuid4


async def test_ctx_t25_archive_read_uses_real_gate_and_detects_changes(tmp_path):
    from weizhcode.compact.archive import SessionStore
    from weizhcode.compact.contracts import CompactionBudget
    from weizhcode.compact.state import SessionRuntime
    from weizhcode.models import ToolCall, ToolContext, ToolSlot
    from weizhcode.permissions.sandbox import make_root
    from weizhcode.redaction import Redactor
    from weizhcode.tools import create_default_registry
    from test_tool_executor import ToolExecutor

    store = SessionStore(make_root(tmp_path), SessionRuntime(context_window=100_000).session_id, Redactor())
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path), context_runtime=SimpleNamespace(store=store))
    cancel = asyncio.Event()
    async def emit(event): pass
    try:
        saved = await store.save_text('tool', 'exec', 'original\n', cancel=cancel,
            budget=CompactionBudget(uuid4().hex, asyncio.get_running_loop().time()+30))
        assert saved.status == 'saved'
        import json
        path = saved.reference.view_path
        def slot():
            return ToolSlot(0, ToolCall('read', 'read_file', json.dumps({'path': path})))
        result = await executor.execute(slot(), mode='plan', cancel=cancel, emit=emit)
        assert result.status == 'success' and 'original' in result.content
        assert result.metadata['archive_verified'] is True
        from dataclasses import replace
        from weizhcode.permissions.rules import parse_rule
        from weizhcode.permissions.types import RuleSet
        previous = executor.permissions.settings['local']
        executor.permissions.settings['local'] = replace(previous, rules=RuleSet(deny=(parse_rule(f'Read({path})'),)))
        denied = await executor.execute(slot(), mode='plan', cancel=cancel, emit=emit)
        assert denied.status == 'denied' and denied.error_code == 'PERMISSION_RULE_DENIED'
        executor.permissions.settings['local'] = previous
        target = tmp_path / path
        original_view = target.read_bytes()
        target.write_text('changed')
        result = await executor.execute(slot(), mode='plan', cancel=cancel, emit=emit)
        assert result.error_code == 'ARCHIVE_CHANGED'
        assert 'changed' not in result.content
        backup = target.with_name(target.name+'.test-owned-backup')
        target.rename(backup)
        target.write_bytes(original_view)
        replaced = await executor.execute(slot(), mode='plan', cancel=cancel, emit=emit)
        assert replaced.error_code == 'ARCHIVE_CHANGED'  # 正文相同，身份替换也不冒充原资料。
        target.unlink()
        missing = await executor.execute(slot(), mode='plan', cancel=cancel, emit=emit)
        assert missing.is_error
    finally:
        await executor.aclose()
        await store.aclose()


async def test_ctx_t29_ctx_t30_executor_private_capture_and_same_read(tmp_path):
    import json
    from weizhcode.compact.capture import CaptureHub
    from weizhcode.compact.state import SessionRuntime
    from weizhcode.models import ToolCall, ToolContext, ToolSlot
    from weizhcode.redaction import Redactor
    from weizhcode.tools import create_default_registry
    from test_tool_executor import ToolExecutor

    text = '\ufeff' + (('原文🙂' + '🙂' * 800 + '\r\n') * 200)
    (tmp_path / 'sample.txt').write_bytes(text.encode())
    runtime = SessionRuntime(context_window=100_000)
    runtime.begin_operation()
    runtime.sources = CaptureHub(Redactor(), is_current=runtime.is_current)
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path), context_runtime=runtime)
    async def emit(event): pass
    slot = ToolSlot(0, ToolCall('remote-id', 'read_file', json.dumps({'path': 'sample.txt'})))
    try:
        result = await executor.execute(slot, mode='plan', cancel=asyncio.Event(), emit=emit, run_id='run')
        assert not result.is_error
        assert slot.source and slot.source.safe_bytes > 50_000
        assert slot.source.execution_key == f'run:{slot.local_id}'
        assert result.call_id == 'remote-id'
        assert slot.file_read.text.startswith('\ufeff原文🙂🙂')
        assert '\t原文' not in slot.file_read.text
        assert runtime.file_reads.snapshot()[0].accepted_sequence == 1
        # 额度不足时不得启动工作进程，也不能绕过执行前的权限门禁。
        held = []
        while sink := await runtime.sources.reserve(f'held:{len(held)}', generation=runtime.operation_generation):
            held.append(sink)
        executor.worker_factory = lambda: (_ for _ in ()).throw(AssertionError('must not start'))
        limited = ToolSlot(1, ToolCall('other', 'read_file', json.dumps({'path': 'sample.txt'})))
        result = await executor.execute(limited, mode='plan', cancel=asyncio.Event(), emit=emit, run_id='run')
        assert result.error_code == 'CONTEXT_CAPTURE_LIMIT' and not limited.execution_started
        from dataclasses import replace
        from weizhcode.permissions.types import RuleSet
        from weizhcode.permissions.rules import parse_rule
        engine = executor.permissions
        engine.settings['local'] = replace(engine.settings['local'], rules=RuleSet(deny=(parse_rule('Read(sample.txt)'),)))
        denied = ToolSlot(2, ToolCall('denied', 'read_file', json.dumps({'path': 'sample.txt'})))
        result = await executor.execute(denied, mode='plan', cancel=asyncio.Event(), emit=emit, run_id='run')
        assert result.error_code == 'PERMISSION_RULE_DENIED' and not denied.execution_started
    finally:
        await executor.aclose()
        await runtime.sources.aclose()


class PreparedScriptProvider:
    def __init__(self, *, window=128000, scripts=()):
        from weizhcode.models import ProviderConfig
        from weizhcode.providers.qwen import QwenProvider
        self.config = ProviderConfig('offline', 'qwen', 'offline', 'https://offline.invalid/v1', 'synthetic-key',
                                     context_window=window)
        self.adapter = QwenProvider(self.config)
        self.scripts, self.requests = list(scripts), []

    def prepare_request(self, *args, **kwargs):
        return self.adapter.prepare_request(*args, **kwargs)

    async def stream_prepared(self, request):
        from weizhcode.compact.prompts import SECTIONS
        from weizhcode.models import ProviderEvent, ChatMessage, TokenUsage
        self.requests.append(request)
        if request.purpose == 'summary':
            text = '<work_draft>SECRET-DRAFT</work_draft><summary>' + '\n'.join('## '+s+'\n已知事实' for s in SECTIONS) + '</summary>'
            yield ProviderEvent('usage', usage=TokenUsage(300, 200, True, 'qwen'))
            yield ProviderEvent('done', assistant_message=ChatMessage('assistant', text), finish_reason='stop')
        elif self.scripts:
            for event in self.scripts.pop(0):
                yield event
        else:
            from weizhcode.compact.estimator import projected_tokens
            yield ProviderEvent('usage', usage=TokenUsage(projected_tokens(request), 10, True, 'qwen'))
            yield ProviderEvent('text_delta', text='离线完成')
            yield ProviderEvent('done', assistant_message=ChatMessage('assistant', '离线完成'), finish_reason='stop')


def context_runner(tmp_path, provider, conversation=None):
    from weizhcode.compact.factory import build_context_runtime
    from weizhcode.models import ToolContext
    from weizhcode.permissions.sandbox import make_root
    from weizhcode.redaction import Redactor
    from weizhcode.tools import create_default_registry
    from weizhcode.turn_runner import TurnRunner
    from weizhcode.conversation import Conversation
    from test_tool_executor import ToolExecutor
    runtime = build_context_runtime(root_identity=make_root(tmp_path),
        context_window=provider.config.context_window, redactor=Redactor(['synthetic-key']))
    registry = create_default_registry()
    executor = ToolExecutor(registry, ToolContext(tmp_path), context_runtime=runtime)
    return TurnRunner(provider, conversation or Conversation(), registry, executor, context_runtime=runtime)


def long_history():
    from weizhcode.conversation import Conversation
    conversation = Conversation()
    for i in range(12):
        conversation.add_user_message(f'原话{i} '+ 'x'*8000)
        conversation.add_assistant_message('y'*8000)
    return conversation


async def test_ctx_t53_ctx_t56_ctx_t60_ctx_t61_ctx_t64_auto_two_summaries_and_usage(tmp_path):
    provider = PreparedScriptProvider(window=100000)
    conversation = long_history()
    for _ in range(4):
        conversation.add_user_message('old '*2000)
        conversation.add_assistant_message('old answer '*800)
    runner = context_runner(tmp_path, provider, conversation)
    try:
        events = [e async for e in runner.run('继续')]
        assert events[-1].reason == 'completed'
        assert [r.purpose for r in provider.requests] == ['summary', 'chat']
        assert runner.usage_totals.request_count == 2
        assert not any('SECRET-DRAFT' in e.text for e in events)
        assert runner.context_runtime.latest_summary is not None
        # 再累积一批任务，验证旧索引继承而非把旧摘要当用户原话归档。
        old_records = runner.context_runtime.human_index.snapshot()
        for _ in range(10):
            runner.conversation.add_user_message('new '*2500)
            runner.conversation.add_assistant_message('new answer '*1000)
        events = [e async for e in runner.run('再继续')]
        assert events[-1].reason == 'completed'
        assert sum(r.purpose == 'summary' for r in provider.requests) == 2
        records = dict(runner.context_runtime.human_index.snapshot())
        assert all(records[seq] == ref for seq, ref in old_records)
        from weizhcode.models import ToolSlot, ToolCall
        import json
        runtime = runner.context_runtime
        runtime.begin_operation()
        async def emit(event): pass
        try:
            first_ref = old_records[0][1]
            page = runtime.index_reference.pages[0]['path']
            for number, path in enumerate((page, first_ref.view_path)):
                slot = ToolSlot(number, ToolCall('history-'+str(number), 'read_file',
                    json.dumps({'path': path, 'line_count': 1})))
                result = await runner.executor.execute(slot, mode='plan', cancel=asyncio.Event(), emit=emit, run_id='history')
                assert not result.is_error and result.metadata['archive_verified']
                assert (first_ref.record_id in result.content) if number == 0 else ('原话0' in result.content)
        finally:
            runtime.finish_operation(runtime.operation_generation)
    finally:
        await runner.aclose()


async def test_ctx_t54_emergency_retries_same_iteration_once(tmp_path):
    from weizhcode.models import ProviderEvent
    from weizhcode.errors import ProviderFault
    provider = PreparedScriptProvider(scripts=[[ProviderEvent('error', fault=ProviderFault('qwen', kind='context_length'))]])
    runner = context_runner(tmp_path, provider, long_history())
    try:
        events = [e async for e in runner.run('继续')]
        assert events[-1].reason == 'completed'
        assert [r.purpose for r in provider.requests] == ['chat', 'summary', 'chat']
        assert len({r.request_id for r in provider.requests}) == 3
        assert len([e for e in events if e.type == 'iteration_started']) == 1
        assert runner.context_runtime.auto_failures == 0
        assert runner.usage_totals.request_count == 3
    finally:
        await runner.aclose()


async def test_ctx_t55_manual_idle_empty_and_no_fake_user(tmp_path):
    provider = PreparedScriptProvider()
    runner = context_runner(tmp_path, provider)
    try:
        before = runner.conversation.snapshot()
        events = [e async for e in runner.compact()]
        assert not provider.requests and runner.conversation.snapshot() == before
        runner.conversation = long_history()
        events = [e async for e in runner.compact()]
        assert [r.purpose for r in provider.requests] == ['summary']
        assert events[-1].reason == 'completed'
        assert not any(e.message.content == '/compact' for e in runner.conversation.snapshot().entries)
    finally:
        await runner.aclose()


async def test_ctx_t34_scheduler_sources_keep_read_limit_and_write_barrier(tmp_path):
    import json
    from weizhcode.models import ChatMessage, ToolCall, RunContext
    from weizhcode.tool_scheduler import ToolScheduler
    provider = PreparedScriptProvider()
    runner = context_runner(tmp_path, provider)
    runtime, executor = runner.context_runtime, runner.executor
    runtime.begin_operation()
    (tmp_path/'input').write_text('original')
    calls = [ToolCall(str(i), 'read_file', json.dumps({'path': 'input'})) for i in range(5)]
    calls.insert(4, ToolCall('write', 'write_file', json.dumps({'path': 'output', 'content': 'saved'})))
    original = executor.execute
    active, peak, log = set(), 0, []
    async def wrapped(slot, **kwargs):
        nonlocal peak
        active.add(slot.index)
        peak = max(peak, len(active))
        log.append(('start', slot.index))
        try: return await original(slot, **kwargs)
        finally:
            active.remove(slot.index)
            log.append(('end', slot.index))
    executor.execute = wrapped
    async def emit(e): pass
    context = RunContext()
    try:
        results = await runner.scheduler.execute(ChatMessage('assistant', tool_calls=tuple(calls)), context=context, emit=emit)
        assert all(not result.is_error for result in results)
        assert peak == 4 and len({s.source.execution_key for s in context.slots}) == 6
        assert log.index(('start', 4)) > max(log.index(('end', i)) for i in range(4))
        assert log.index(('start', 5)) > log.index(('end', 4))
    finally:
        runtime.finish_operation(runtime.operation_generation)
        await runner.aclose()


def test_ctx_t68_default_help_and_confirmation_are_side_effect_free(monkeypatch, capsys):
    from manual_context_smoke import main
    from weizhcode import config
    monkeypatch.setattr(config, 'load_config', lambda: (_ for _ in ()).throw(AssertionError('credential access')))
    assert main([]) == 0
    assert main(['--live', '--protocol', 'qwen', '--model', 'fake', '--base-url', 'https://offline.invalid/v1'],
                ask=lambda prompt: 'NO') == 0
    assert '未加载凭据' in capsys.readouterr().out
    import pytest
    with pytest.raises(SystemExit) as error:
        main(['--help'])
    assert error.value.code == 0
    with pytest.raises(SystemExit):
        main(['--terminal', '--live'])


async def test_ctx_t54_ctx_t64_ctx_t65_emergency_after_side_effect_never_replays(tmp_path):
    import json
    from weizhcode.errors import ProviderFault
    from weizhcode.models import ProviderEvent, ChatMessage, ToolCall
    call = ToolCall('write-once', 'write_file', json.dumps({'path': 'once.txt', 'content': 'only once'}))
    failed = ProviderEvent('error', fault=ProviderFault('qwen', kind='context_length'))
    provider = PreparedScriptProvider(scripts=[
        [ProviderEvent('done', assistant_message=ChatMessage('assistant', tool_calls=(call,)))], [failed], [failed]])
    runner = context_runner(tmp_path, provider, long_history())
    try:
        events = [e async for e in runner.run('写入后继续')]
        assert (tmp_path/'once.txt').read_text() == 'only once'
        assert len([e for e in events if e.type == 'tool_running']) == 1
        assert [e.iteration for e in events if e.type == 'iteration_started'] == [1, 2]
        assert sum(r.purpose == 'summary' for r in provider.requests) == 1
        assert events[-1].reason == 'provider_error'
        assert [e async for e in runner.run('之后继续')][-1].reason == 'completed'
    finally:
        await runner.aclose()


async def test_ctx_t64_large_recent_stops_without_sending(tmp_path):
    provider = PreparedScriptProvider(window=40000)
    runner = context_runner(tmp_path, provider)
    try:
        text = 'x'*200000
        events = [e async for e in runner.run(text)]
        assert not provider.requests
        assert events[-1].reason == 'internal_error'
        assert runner.conversation.messages()[0].content == text
        assert any('CONTEXT_BUDGET_EXCEEDED' in e.text for e in events)
    finally:
        await runner.aclose()


async def test_ctx_t35_ctx_t64_ctx_t66_real_tool_offload_then_authorized_reread(tmp_path):
    import json
    from weizhcode.models import ProviderEvent, ChatMessage, ToolCall, ToolSlot
    path = tmp_path/'large.txt'
    path.write_bytes((('🙂'*800+'\r\n')*30).encode())
    call = ToolCall('read-once', 'read_file', json.dumps({'path': 'large.txt'}))
    provider = PreparedScriptProvider(scripts=[
        [ProviderEvent('done', assistant_message=ChatMessage('assistant', tool_calls=(call,)))]] )
    runner = context_runner(tmp_path, provider)
    try:
        events = [e async for e in runner.run('读取并总结')]
        assert events[-1].reason == 'completed'
        decisions = runner.context_runtime.replacements.snapshot()
        saved = next(d for d in decisions if d.kind == 'replaced')
        data = (tmp_path/saved.reference.raw_path).read_bytes()
        assert len(data) > 50000 and '🙂'.encode() in data
        assert '工具原文已归档' in provider.requests[-1].body_json
        tool_message = next(m for m in provider.requests[-1].body()['messages'] if m['role'] == 'tool')
        assert json.loads(tool_message['content'])['content'] == saved.preview
        assert len(saved.preview.encode()) <= 2048
        assert len([e for e in events if e.type == 'tool_running']) == 1
        runtime = runner.context_runtime
        runtime.begin_operation()
        slot = ToolSlot(0, ToolCall('reread', 'read_file', json.dumps({'path': saved.reference.view_path, 'start_line': 10, 'line_count': 1})))
        async def emit(e): pass
        result = await runner.executor.execute(slot, mode='plan', cancel=asyncio.Event(), emit=emit, run_id='reread')
        assert not result.is_error and result.metadata['archive_verified']
        runtime.finish_operation(runtime.operation_generation)
    finally:
        await runner.aclose()


async def test_ctx_t59_ctx_t66_answers_stay_human_not_command_or_permission(tmp_path):
    import json
    from weizhcode.models import ProviderEvent, ChatMessage, ToolCall
    question = ToolCall('ask', 'AskUserQuestion', json.dumps({'question': '需求边界是什么？'}))
    provider = PreparedScriptProvider(scripts=[[ProviderEvent('done', assistant_message=ChatMessage('assistant', tool_calls=(question,)))]] )
    runner = context_runner(tmp_path, provider)
    token, events, asked = runner.bind_questions(), [], asyncio.Event()
    async def consume():
        async for event in runner.run('请澄清', mode='plan'):
            events.append(event)
            if event.type == 'question_request': asked.set()
    task = asyncio.create_task(consume())
    try:
        await asyncio.wait_for(asked.wait(), 10)
        rejected = [e async for e in runner.compact()]
        assert rejected[0].reason == 'busy'
        event = next(e for e in events if e.type == 'question_request')
        accepted, _ = runner.submit_answer(event.run_id, event.question.question_id, {'text': '/compact'})
        assert accepted
        await task
        answer = runner.context_runtime.snapshot().accepted_answers[0]
        assert answer.text == '/compact'
        assert len([e for e in runner.conversation.snapshot().entries if e.origin == 'human']) == 1
        for _ in range(12):
            runner.conversation.add_user_message('后续原话 '*2000)
            runner.conversation.add_assistant_message('answer '*1300)
        outcome = [e async for e in runner.compact()]
        assert outcome[-1].reason == 'completed'
        seq = runner.context_runtime.answer_sequences[answer.answer_id]
        ref = dict(runner.context_runtime.human_index.snapshot())[seq]
        assert (tmp_path/ref.raw_path).read_text(encoding='utf-8') == '/compact'
    finally:
        if not task.done():
            runner.cancel_current()
            await task
        runner.unbind_questions(token)
        await runner.aclose()


async def test_ctx_t31_ctx_t33_ctx_t64_real_mcp_agent_offloads_full_result(tmp_path):
    import json
    import sys
    from pathlib import Path
    from dataclasses import replace
    from weizhcode.mcp.manager import McpManager
    from weizhcode.mcp.contracts import McpServerConfig, AuthorizedServers
    from weizhcode.permissions.types import RuleSet
    from weizhcode.permissions.rules import parse_rule
    from weizhcode.models import ProviderEvent, ChatMessage, ToolCall
    call = ToolCall('mcp-call', 'mcp__demo__echo', json.dumps({'text': 'large'}))
    provider = PreparedScriptProvider(scripts=[
        [ProviderEvent('done', assistant_message=ChatMessage('assistant', tool_calls=(call,)))]] )
    runner = context_runner(tmp_path, provider)
    manager = McpManager(tmp_path)
    cfg = McpServerConfig('demo', 'user', 'stdio', sys.executable,
        (str(Path(__file__).parent/'fixtures/mcp_stdio_server.py'), '--context-large'))
    await manager.start(AuthorizedServers((manager.authorize(cfg),)), cancel=asyncio.Event())
    for tool in manager.tools:
        runner.registry.register_external(tool, tool.identity)
    runner.executor.mcp_manager = manager
    engine = runner.executor.permissions
    engine.external_identity = runner.registry.external_identity
    engine.settings['local'] = replace(engine.settings['local'], rules=RuleSet(allow=(parse_rule(call.name),)))
    try:
        events = [e async for e in runner.run('查看本地MCP样本')]
        assert events[-1].reason == 'completed'
        saved = next(d for d in runner.context_runtime.replacements.snapshot() if d.kind == 'replaced')
        assert saved.reference.safe_bytes == 80000
        assert (tmp_path/saved.reference.raw_path).read_text() == 'x'*80000
        tool_message = next(m for m in provider.requests[-1].body()['messages'] if m['role'] == 'tool')
        assert json.loads(tool_message['content'])['content'] == saved.preview
        assert not runner.context_runtime.file_reads.snapshot()  # 远端正文不得伪造本地快照。
    finally:
        await runner.aclose()
