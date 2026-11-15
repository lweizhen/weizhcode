import asyncio
import sys
from pathlib import Path

import pytest

from weizhcode.models import RunContext
from weizhcode.prompting.contracts import GitSummary
from weizhcode.prompting.environment import (EnvironmentCollector, GIT_ARGV,
                                            finish_environment, parse_git_status)


def test_parse_records_not_lines():
    raw = b"MM a\nb\0R  new name\0old name\0?? folder/\0UU conflict\0"
    result = parse_git_status(raw)
    assert result == GitSummary("available", staged=3, unstaged=2, untracked=1, conflicted=1)
    assert "folder" not in repr(result)
    assert parse_git_status(b"") == GitSummary("available", 0, 0, 0, 0)


@pytest.mark.parametrize("raw", [b"M x", b"R  new\0", b"bad\0", b"XX file\0"])
def test_parse_bad_or_truncated(raw):
    result = parse_git_status(raw)
    assert result.truncated and result.staged is None
    assert parse_git_status(b"?? x\0", truncated=True).truncated


async def test_capture_native_non_repository(tmp_path):
    context = RunContext()
    result = await EnvironmentCollector().capture(project_root=tmp_path, app_version="test", model="fake",
                                                   context=context)
    assert result.project_root == str(tmp_path)
    assert result.git.status == "not_repository"
    assert result.app_version == "test" and result.model == "fake"
    assert not context.owned_tasks


async def test_capture_native_repository_and_no_file_names(tmp_path):
    init = await asyncio.create_subprocess_exec("git", "init", "--quiet", cwd=tmp_path)
    assert await init.wait() == 0
    (tmp_path / "private-name.txt").write_text("hello", encoding="utf-8")
    result = await EnvironmentCollector().capture(project_root=tmp_path, app_version="test", model="fake",
                                                   context=RunContext())
    assert result.git == GitSummary("available", 0, 0, 1, 0)
    assert "private-name" not in repr(result)


@pytest.mark.parametrize("error", [FileNotFoundError(), PermissionError(), NotADirectoryError()])
async def test_capture_errors_degrade(tmp_path, error):
    async def spawn(*args, **kwargs):
        assert args == GIT_ARGV and kwargs["cwd"] == str(tmp_path)
        raise error
    context = RunContext()
    result = await EnvironmentCollector(spawn=spawn).capture(project_root=tmp_path, app_version="v", model="m",
                                                            context=context)
    assert result.git.status == "unavailable" and result.git.staged is None
    assert not context.owned_tasks


async def test_capture_missing_root_and_pre_cancel_no_process():
    async def forbidden(*args, **kwargs):
        raise AssertionError("must not spawn")
    context = RunContext()
    result = await EnvironmentCollector(spawn=forbidden).capture(project_root=None, app_version="v", model="m",
                                                                context=context)
    assert result.project_root == "unavailable"
    context.cancel_event.set()
    await EnvironmentCollector(spawn=forbidden).capture(project_root=Path.cwd(), app_version="v", model="m",
                                                        context=context)


async def test_cleanup_native_timeout_drains_and_reaps(tmp_path):
    processes = []
    async def spawn(*args, **kwargs):
        process = await asyncio.create_subprocess_exec(sys.executable, "-c",
            "import sys,time;sys.stdout.buffer.write(b'x'*1000000);sys.stdout.flush();time.sleep(30)",
            **kwargs)
        processes.append(process)
        return process
    context = RunContext()
    ticks = 0
    async def heartbeat():
        nonlocal ticks
        while True:
            ticks += 1
            await asyncio.sleep(0.001)
    pulse = asyncio.create_task(heartbeat())
    result = await EnvironmentCollector(timeout=0.2, spawn=spawn).capture(
        project_root=tmp_path, app_version="v", model="m", context=context)
    assert result.git.status == "timeout"
    await asyncio.wait_for(finish_environment(context), 5)
    pulse.cancel()
    await asyncio.gather(pulse, return_exceptions=True)
    assert ticks > 1 and processes and all(p.returncode is not None for p in processes)
    assert not context.owned_tasks and not context.cleanup_tasks


async def test_cleanup_late_creation_after_cancel(tmp_path):
    entered, release = asyncio.Event(), asyncio.Event()
    processes = []
    async def spawn(*args, **kwargs):
        entered.set()
        await release.wait()
        p = await asyncio.create_subprocess_exec(sys.executable, "-c", "import time;time.sleep(30)", **kwargs)
        processes.append(p)
        return p
    context = RunContext()
    work = asyncio.create_task(EnvironmentCollector(spawn=spawn).capture(
        project_root=tmp_path, app_version="v", model="m", context=context))
    await entered.wait()
    context.cancel_event.set()
    result = await work
    assert result.git.status == "unavailable"
    release.set()
    await asyncio.wait_for(finish_environment(context), 5)
    assert processes[0].returncode is not None
    assert not context.owned_tasks


async def test_capture_output_cap_without_deadlock(tmp_path):
    async def spawn(*args, **kwargs):
        return await asyncio.create_subprocess_exec(sys.executable, "-c",
            "import sys;sys.stdout.buffer.write(b'?? file\\0'*50000);sys.stderr.buffer.write(b'e'*100000)",
            **kwargs)
    context = RunContext()
    result = await EnvironmentCollector(spawn=spawn).capture(project_root=tmp_path, app_version="v", model="m",
                                                            context=context)
    assert result.git.status == "available" and result.git.truncated
    assert result.git.untracked is None and not context.owned_tasks
