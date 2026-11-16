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
