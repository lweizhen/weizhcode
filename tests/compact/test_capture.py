import asyncio
import pytest


async def test_ctx_t26_bounded_reservations_redaction_and_release():
    from weizhcode.compact.capture import CaptureHub
    from weizhcode.redaction import Redactor

    hub = CaptureHub(Redactor(['private-key']))
    try:
        sinks = [await hub.reserve(str(index), generation=1) for index in range(16)]
        assert all(sinks) and await hub.reserve('overflow', generation=1) is None
        assert hub.queue_limit == 8
        sink = sinks[0]
        await sink.begin(collected_bytes=11, truncated=False)
        assert await sink.feed('private-')
        assert await sink.feed('key')
        source = await sink.finish()
        assert source.text == '[redacted]' and source.collected_bytes == 11
        assert source.capture_complete and 'private-key' not in repr(source)
        assert await hub.reserve('new', generation=1) is None
        assert await hub.reserve('0', generation=1) is None
        await hub.release('0')
        assert hub.get('0') is None
        assert await hub.reserve('new', generation=1) is not None
    finally:
        await hub.aclose()


@pytest.mark.parametrize('fault', ['foreign_id', 'bool_generation', 'sequence', 'missing_end'])
async def test_ctx_t65_private_worker_frames_fail_closed(fault):
    import json
    from types import SimpleNamespace
    from weizhcode.compact.capture import CaptureHub
    from weizhcode.models import ToolCall, ToolResult
    from weizhcode.redaction import Redactor
    from weizhcode.tools.process import ManagedWorker
    from weizhcode.tools.base import ToolFailure
    hub, worker = CaptureHub(Redactor()), ManagedWorker()
    sink = await hub.reserve('exec', generation=1)
    worker.capture_sink, worker._capture_operation = sink, 'op'
    worker._prepared_call = ToolCall('call', 'read_file', '{}', {})
    common = {'operation_id': 'op', 'execution_key': 'exec', 'generation': 1}
    frames = [{'type': 'capture_begin', **common, 'collected_bytes': 1, 'truncated': False,
               'call_id': 'call', 'tool_name': 'read_file'},
              {'type': 'capture_chunk', **common, 'seq': 0, 'text': 'x'}]
    if fault == 'foreign_id': frames[0]['execution_key'] = 'foreign'
    if fault == 'bool_generation': frames[0]['generation'] = True
    if fault == 'sequence': frames[1]['seq'] = 1
    frames.append({'type': 'result', 'result': {'call_id': 'call', 'tool_name': 'read_file', 'content': 'x'}})
    reader = asyncio.StreamReader()
    reader.feed_data(('\n'.join(json.dumps(f) for f in frames)+'\n').encode())
    reader.feed_eof()
    worker.process = SimpleNamespace(stdout=reader)
    try:
        with pytest.raises(ToolFailure): await worker._receive('result')
        assert hub.get('exec') is None
    finally:
        await sink.abort()
        await hub.aclose()


async def test_ctx_t26_close_unblocks_producers():
    from weizhcode.compact.capture import CaptureHub
    from weizhcode.redaction import Redactor

    hub = CaptureHub(Redactor())
    sink = await hub.reserve('closing', generation=1)
    await sink.begin(collected_bytes=100, truncated=False)
    tasks = [asyncio.create_task(sink.feed('x')) for _ in range(20)]
    await asyncio.sleep(0)
    await hub.aclose()
    await asyncio.wait_for(asyncio.gather(*tasks), 1)
    assert await hub.reserve('closed', generation=1) is None


async def test_ctx_t26_stale_generation_and_partial_capture():
    from weizhcode.compact.capture import CaptureHub
    from weizhcode.redaction import Redactor

    current = 1
    hub = CaptureHub(Redactor(), is_current=lambda generation: generation == current)
    try:
        sink = await hub.reserve('one', generation=1)
        await sink.begin(collected_bytes=10, truncated=True)
        await sink.feed('abc')
        source = await sink.finish(complete=False)
        assert source.text == 'abc' and not source.capture_complete and source.truncated_at_source
        late = await hub.reserve('late', generation=1)
        await late.begin(collected_bytes=3, truncated=False)
        current = 2
        assert not await late.feed('xyz')
        assert await late.finish() is None
    finally:
        await hub.aclose()


def test_ctx_t27_frames_capture_before_public_result_budget():
    import json
    from weizhcode.compact.capture import result_capture_frames
    from weizhcode.models import ToolResult

    result = ToolResult('id'*200, 'read_file', 'x'*80_000, truncated=True)
    frames = list(result_capture_frames(result, operation_id='op', execution_key='exec', generation=1))
    assert ''.join(frame['text'] for frame in frames if frame['type'] == 'capture_chunk') == result.content
    assert frames[0]['call_id'] == result.call_id and frames[0]['truncated']
    assert frames[-1]['complete'] and len(result.to_model_text()) <= 20_000
    assert all(len(json.dumps(frame).encode()) <= 128*1024 for frame in frames)


async def test_ctx_t28_managed_worker_captures_before_public_truncation(tmp_path):
    from weizhcode.compact.capture import CaptureHub
    from weizhcode.models import ToolCall, ToolContext
    from weizhcode.permissions.sandbox import make_root, resolve_target
    from weizhcode.redaction import Redactor
    from weizhcode.tools.process import ManagedWorker

    path = tmp_path / 'emojis'
    path.write_text('😀'*20_000, encoding='utf-8')
    root = make_root(tmp_path)
    call = ToolCall('long-id'*60, 'read_file', '{"path":"emojis"}', {'path': 'emojis'})
    hub, worker = CaptureHub(Redactor()), ManagedWorker()
    try:
        sink = await hub.reserve('exec', generation=1)
        await worker.start(ToolContext(tmp_path, root))
        preview = await worker.prepare(call, permission_stamp=resolve_target('emojis', root))
        result = await worker.execute(preview.operation_id, capture_sink=sink)
        source = worker.captured_source
        assert source and source.safe_bytes > 50_000 and source.capture_complete
        assert len(source.text) > len(result.content) and result.truncated
    finally:
        await worker.aclose()
        await hub.aclose()


async def test_ctx_t31_ctx_t32_ctx_t33_mcp_capture_before_dto(tmp_path):
    from weizhcode.mcp.manager import McpManager
    from weizhcode.mcp.contracts import McpServerConfig, AuthorizedServers
    from pathlib import Path
    import sys
    from weizhcode.compact.capture import CaptureHub
    from weizhcode.models import ToolCall
    from weizhcode.redaction import Redactor

    manager = McpManager(tmp_path)
    config = McpServerConfig('demo', 'user', 'stdio', sys.executable,
        (str(Path(__file__).parents[1] / 'fixtures/mcp_stdio_server.py'),),
        env_json='{"PYTHONIOENCODING":"utf-8","PYTHONUTF8":"1"}')
    await manager.start(AuthorizedServers((manager.authorize(config),)), cancel=asyncio.Event())
    hub = CaptureHub(Redactor())
    try:
        sink = await hub.reserve('mcp-exec', generation=1)
        text = '🙂' * 20_000
        call = ToolCall('remote-id', 'mcp__demo__echo', '{}', {'text': text})
        result = await manager.call(manager.identity(call.name), call, cancel=asyncio.Event(),
                                    execution_started=lambda: None, capture_sink=sink)
        assert not result.is_error, result.error_code
        source = hub.get('mcp-exec')
        assert source.text == text and source.safe_bytes == 80_000
        assert source.capture_complete and len(result.content) < len(text)
        assert 'capture' not in result.metadata
    finally:
        await manager.aclose()
        await hub.aclose()


def test_ctx_t27_capture_two_mib_cap_reports_incomplete():
    from weizhcode.compact.capture import result_capture_frames
    from weizhcode.models import ToolResult
    frames = list(result_capture_frames(ToolResult('id', 'read_file', 'x'*(2*1024*1024+1)),
        operation_id='op', execution_key='key', generation=1))
    assert frames[0]['collected_bytes'] == 2*1024*1024+1
    assert sum(len(f['text'].encode()) for f in frames if f['type'] == 'capture_chunk') == 2*1024*1024
    assert frames[-1]['complete'] is False
