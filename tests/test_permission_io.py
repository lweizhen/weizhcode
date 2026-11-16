import asyncio
from dataclasses import asdict
from pathlib import Path

import pytest

from weizhcode.models import ToolContext
from weizhcode.permissions.io import PermissionIO
from weizhcode.permissions.sandbox import make_root
from weizhcode.permissions.types import Category, PermissionFailure, PermissionTarget
from weizhcode.tools.process import ManagedWorker


async def test_native_permission_inspect(tmp_path):
    io = PermissionIO()
    stamp = await io.inspect_path("a/b", make_root(tmp_path), cancel=asyncio.Event())
    assert stamp.project_relative == "a/b" and not stamp.target_exists
    assert not io._active
    await io.aclose()


async def test_native_permission_persist(tmp_path):
    io, root = PermissionIO(), make_root(tmp_path)
    target = PermissionTarget("run_command", "Bash", Category.EXEC, "echo hello", "echo hello")
    result = await io.persist_allow(target, tmp_path / ".weizhcode/settings.local.yaml", root, cancel=asyncio.Event())
    assert result.saved and result.committed
    assert (tmp_path / ".weizhcode/settings.local.yaml").is_file()
    assert not io._active


async def test_purpose(tmp_path):
    worker = ManagedWorker(purpose="permission")
    try:
        await worker.start(ToolContext(tmp_path))
        await worker._send({"type": "prepare", "call": {}})
        with pytest.raises(Exception):
            await worker._receive("prepared")
    finally:
        await worker.aclose()


async def test_lifecycle(tmp_path):
    io = PermissionIO(timeout=.001)
    with pytest.raises(PermissionFailure):
        await io.inspect_path("a", make_root(tmp_path), cancel=asyncio.Event())
    assert not io._active
    cancel = asyncio.Event()
    cancel.set()
    with pytest.raises(asyncio.CancelledError):
        await io.inspect_path("a", make_root(tmp_path), cancel=cancel)
    await io.aclose()


@pytest.mark.parametrize("saving", [False, True])
async def test_native_permission_cancel_helper(tmp_path, saving):
    entered = asyncio.Event()
    workers = []
    class WaitingWorker(ManagedWorker):
        async def permission_operation(self, action, payload):
            entered.set()
            await asyncio.Event().wait()
    def factory(**kwargs):
        worker = WaitingWorker(**kwargs)
        workers.append(worker)
        return worker
    io = PermissionIO(worker_factory=factory)
    root, cancel = make_root(tmp_path), asyncio.Event()
    target = PermissionTarget("run_command", "Bash", Category.EXEC, "echo hi", "echo hi")
    if saving:
        task = asyncio.create_task(io.persist_allow(target, tmp_path / ".weizhcode/settings.local.yaml", root, cancel=cancel))
    else:
        task = asyncio.create_task(io.inspect_path("file", root, cancel=cancel))
    await asyncio.wait_for(entered.wait(), 5)
    cancel.set()
    if saving:
        result = await asyncio.wait_for(task, 3)
        assert result.committed is None and not result.saved
    else:
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
    assert not io._active and workers[0].process.returncode is not None
    assert not (tmp_path / ".weizhcode/settings.local.yaml").exists()


async def test_inspect_invalid_response(tmp_path):
    class BadWorker:
        def __init__(self, **kwargs):
            pass
        async def start(self, context):
            pass
        async def permission_operation(self, *args):
            return {"result": {"original": "x", "canonical_target": str(tmp_path.parent / "outside"),
                "project_relative": "../outside", "target_exists": False, "nearest_existing": str(tmp_path.parent)}}
        async def aclose(self):
            pass
    io = PermissionIO(worker_factory=BadWorker)
    with pytest.raises(PermissionFailure):
        await io.inspect_path("x", make_root(tmp_path), cancel=asyncio.Event())
    assert not io._active


async def test_native_permission_persist_ack_lost(tmp_path):
    class LostReplyWorker(ManagedWorker):
        async def permission_operation(self, action, payload):
            response = await super().permission_operation(action, payload)
            if action == "persist_permission_allow":
                raise OSError("simulated lost acknowledgment after commit")
            return response
    io = PermissionIO(worker_factory=LostReplyWorker)
    root = make_root(tmp_path)
    target = PermissionTarget("run_command", "Bash", Category.EXEC, "echo hi", "echo hi")
    result = await io.persist_allow(target, tmp_path / ".weizhcode/settings.local.yaml", root, cancel=asyncio.Event())
    assert result.committed is None and result.warning_code == "SAVE_UNCERTAIN"
    assert (tmp_path / ".weizhcode/settings.local.yaml").exists() and not io._active
