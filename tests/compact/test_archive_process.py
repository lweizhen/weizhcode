import asyncio
from dataclasses import asdict
from uuid import uuid4

import pytest
import os


@pytest.mark.skipif(os.name != 'nt', reason='Windows原生进程所有权专项')
@pytest.mark.parametrize('kind', ['archive', 'tools', 'mcp'])
async def test_ctx_t69_native_close_preserves_adjacent_owned_control(tmp_path, kind):
    import sys
    import subprocess
    from pathlib import Path
    from weizhcode.permissions.sandbox import make_root
    from weizhcode.models import ToolContext
    from weizhcode.mcp.process import OwnedProcess
    from weizhcode.compact.state import SessionRuntime
    sibling = await asyncio.create_subprocess_exec(sys.executable, '-c', 'import time; time.sleep(60)',
        creationflags=subprocess.CREATE_NO_WINDOW)
    owner = None
    try:
        if kind == 'archive':
            owner = OwnedProcess('weizhcode.compact.archive_worker')
            await owner.start()
            await owner.send('archive_init', root=asdict(make_root(tmp_path)),
                session_id=SessionRuntime(context_window=100000).session_id)
            assert (await owner.receive())['type'] == 'archive_ready'
            child = owner.process
        elif kind == 'tools':
            from weizhcode.tools.process import ManagedWorker
            owner = ManagedWorker()
            await owner.start(ToolContext(tmp_path, make_root(tmp_path)))
            child = owner.process
        else:
            from weizhcode.mcp.manager import McpManager
            from weizhcode.mcp.contracts import McpServerConfig, AuthorizedServers
            owner = McpManager(tmp_path)
            cfg = McpServerConfig('demo', 'user', 'stdio', sys.executable,
                (str(Path(__file__).parents[1]/'fixtures/mcp_stdio_server.py'),))
            await owner.start(AuthorizedServers((owner.authorize(cfg),)), cancel=asyncio.Event())
            child = owner.hosts['demo'].process
        await owner.aclose()
        assert child.returncode is not None
        assert sibling.returncode is None
        await owner.aclose()
        assert sibling.returncode is None
    finally:
        if owner is not None: await owner.aclose()
        if sibling.returncode is None: sibling.kill()
        await sibling.wait()


async def test_ctx_t21_owned_worker_save_verify_and_whitelist(tmp_path):
    from weizhcode.compact.state import SessionRuntime
    from weizhcode.mcp.process import OwnedProcess
    from weizhcode.permissions.sandbox import make_root

    process = OwnedProcess('weizhcode.compact.archive_worker')
    runtime = SessionRuntime(context_window=100_000)
    root = make_root(tmp_path)
    record_id = uuid4().hex
    request_id, operation_id = uuid4().hex, uuid4().hex
    try:
        await process.start()
        await process.send('archive_init', root=asdict(root), session_id=runtime.session_id)
        ready = await asyncio.wait_for(process.receive(), 5)
        assert ready['type'] == 'archive_ready'
        await process.send('archive_begin', request_id=request_id, operation_id=operation_id,
            action='save_record', args={'record_id': record_id, 'kind': 'tool', 'source_key': 'execution', 'complete': True})
        text = 'x' * 80_000
        for seq, offset in enumerate(range(0, len(text), 4096)):
            await process.send('archive_chunk', request_id=request_id, operation_id=operation_id,
                seq=seq, text=text[offset:offset+4096])
        await process.send('archive_end', request_id=request_id, operation_id=operation_id)
        result = await asyncio.wait_for(process.receive(), 5)
        assert result['status'] == 'saved'
        ref = result['result']
        assert tmp_path.joinpath(ref['raw_path']).read_text() == text
        assert ref['_proofs']['raw']['safe_bytes'] == 80_000
        reference = {key: value for key, value in ref.items() if key != '_proofs'}
        verify_request, verify_operation = uuid4().hex, uuid4().hex
        await process.send('archive_begin', request_id=verify_request, operation_id=verify_operation,
            action='verify_records', args={'references': [reference]})
        await process.send('archive_end', request_id=verify_request, operation_id=verify_operation)
        assert (await asyncio.wait_for(process.receive(), 5))['status'] == 'saved'
        await process.send('archive_begin', request_id=uuid4().hex, operation_id=uuid4().hex,
            action='bash', args={'command': 'anything'})
        denied = await asyncio.wait_for(process.receive(), 5)
        assert denied['status'] == 'known_failed'
        assert denied['code'] == 'ARCHIVE_ACTION_INVALID'
    finally:
        await process.aclose()


async def test_ctx_t22_store_is_lazy_and_deduplicates_sources(tmp_path):
    from weizhcode.compact.archive import SessionStore
    from weizhcode.compact.contracts import CompactionBudget
    from weizhcode.compact.state import SessionRuntime
    from weizhcode.permissions.sandbox import make_root
    from weizhcode.redaction import Redactor

    store = SessionStore(make_root(tmp_path), SessionRuntime(context_window=100_000).session_id, Redactor(['synthetic-secret']))
    assert not (tmp_path / '.weizhcode').exists()
    cancel = asyncio.Event()
    budget = CompactionBudget(uuid4().hex, asyncio.get_running_loop().time()+30)
    try:
        result = await store.save_text('human', 'user-1', 'original synthetic-secret\r\n', cancel=cancel, budget=budget)
        assert result.status == 'saved'
        assert tmp_path.joinpath(result.reference.raw_path).read_bytes() == b'original [redacted]\r\n'
        again = await store.save_text('human', 'user-1', 'original synthetic-secret\r\n', cancel=cancel, budget=budget)
        assert again.reference == result.reference
        conflict = await store.save_text('human', 'user-1', 'different', cancel=cancel, budget=budget)
        assert conflict.status == 'conflict'
        assert await store.verify_refs([result.reference], cancel=cancel, budget=budget)
        proof = store.proof_for_registered_path(tmp_path / result.reference.raw_path)
        assert proof.sha256 == result.reference.sha256 and proof.identity
        first = await store.publish_user_index([(1, result.reference)], cancel=cancel, budget=budget)
        second = await store.publish_user_index([(1, result.reference)], cancel=cancel, budget=budget)
        assert first and second and first.pages[0]['path'] != second.pages[0]['path']
        assert store.proof_for_registered_path(tmp_path / second.pages[0]['path'])
        assert tmp_path.joinpath(first.pages[0]['path']).exists()
    finally:
        await store.aclose()
        await store.aclose()
    assert tmp_path.joinpath(result.reference.raw_path).exists()


async def test_ctx_t24_secret_does_not_enter_any_artifact(tmp_path):
    from weizhcode.compact.archive import SessionStore
    from weizhcode.compact.contracts import CompactionBudget
    from weizhcode.compact.state import SessionRuntime
    from weizhcode.permissions.sandbox import make_root
    from weizhcode.redaction import Redactor

    secret = 'synthetic-private-key'
    store = SessionStore(make_root(tmp_path), SessionRuntime(context_window=100_000).session_id, Redactor([secret]))
    try:
        saved = await store.save_text('tool', 'source-'+secret, secret*100,
            facts={'description': secret}, cancel=asyncio.Event(),
            budget=CompactionBudget(uuid4().hex, asyncio.get_running_loop().time()+30))
        assert saved.status == 'saved'
    finally:
        await store.aclose()
    assert all(secret.encode() not in path.read_bytes() for path in (tmp_path / '.weizhcode').rglob('*') if path.is_file())


async def test_ctx_t23_hung_worker_is_bounded_and_owned_cleanup(tmp_path):
    from weizhcode.compact.archive import SessionStore
    from weizhcode.compact.contracts import CompactionBudget
    from weizhcode.compact.state import SessionRuntime
    from weizhcode.permissions.sandbox import make_root
    from weizhcode.redaction import Redactor

    class Hanging:
        closed = False
        ready = False
        async def start(self): pass
        async def send(self, *args, **kwargs): pass
        async def receive(self):
            if not self.ready:
                self.ready = True
                return {'type': 'archive_ready'}
            await asyncio.Event().wait()
        async def aclose(self): self.closed = True
    worker = Hanging()
    store = SessionStore(make_root(tmp_path), SessionRuntime(context_window=100_000).session_id,
                         Redactor(), process_factory=lambda module: worker)
    loop = asyncio.get_running_loop()
    started = loop.time()
    result = await store.save_text('tool', 'exec', 'data', cancel=asyncio.Event(),
                                  budget=CompactionBudget(uuid4().hex, started+2.05))
    assert result.status == 'uncertain' and result.reference is None
    assert loop.time()-started < 1 and worker.closed
    assert not (tmp_path / '.weizhcode').exists()
    await store.aclose()


async def test_ctx_t23_cancellation_while_waiting_lock_releases_it(tmp_path):
    from weizhcode.compact.archive import SessionStore
    from weizhcode.compact.contracts import CompactionBudget
    from weizhcode.compact.state import SessionRuntime
    from weizhcode.permissions.sandbox import make_root
    from weizhcode.redaction import Redactor

    store = SessionStore(make_root(tmp_path), SessionRuntime(context_window=100_000).session_id, Redactor())
    await store._lock.acquire()
    cancel = asyncio.Event()
    task = asyncio.create_task(store.save_text('human', 'u', 'text', cancel=cancel,
        budget=CompactionBudget(uuid4().hex, asyncio.get_running_loop().time()+30)))
    await asyncio.sleep(0)
    cancel.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, .5)
    assert store._lock.locked()  # 等待者不能释放另一操作拥有的锁。
    store._lock.release()
    assert store._process is None
    await store.aclose()


async def test_ctx_t23_lost_save_response_is_reconciled_without_overwrite(tmp_path, monkeypatch):
    from weizhcode.compact.archive import SessionStore
    from weizhcode.compact.contracts import CompactionBudget
    from weizhcode.compact.state import SessionRuntime
    from weizhcode.permissions.sandbox import make_root
    from weizhcode.redaction import Redactor

    store = SessionStore(make_root(tmp_path), SessionRuntime(context_window=100_000).session_id, Redactor())
    original = store._run
    lose = True
    async def lost(action, *args, **kwargs):
        nonlocal lose
        result = await original(action, *args, **kwargs)
        if action == 'save_record' and lose:
            lose = False
            return {'status': 'uncertain', 'code': 'TEST_RESPONSE_LOST'}
        return result
    monkeypatch.setattr(store, '_run', lost)
    budget = CompactionBudget(uuid4().hex, asyncio.get_running_loop().time()+30)
    try:
        first = await store.save_text('human', 'u', 'original', cancel=asyncio.Event(), budget=budget)
        assert first.status == 'uncertain' and first.reference is None
        second = await store.save_text('human', 'u', 'original', cancel=asyncio.Event(), budget=budget)
        assert second.status == 'saved'
        assert len(list((tmp_path / '.weizhcode').rglob('records/*.json'))) == 1
    finally:
        await store.aclose()
