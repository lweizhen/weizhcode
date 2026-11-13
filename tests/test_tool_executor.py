from pathlib import Path

from weizhcode.models import PreparedOperation, PreparedOperationPreview, ToolCall, ToolContext, ToolResult


def test_operation_contract_failed_preparation_is_not_executable():
    call = ToolCall("id", "write_file", '{}')
    error = ToolResult.failure(call, "INVALID_ARGUMENTS", "缺少路径")
    operation = PreparedOperation(call, {}, error=error)
    preview = PreparedOperationPreview(operation.operation_id, "", "", error=error)
    assert operation.error.is_error
    assert preview.error.is_error
    assert not hasattr(preview, "state")
    assert not hasattr(ToolContext(Path.cwd()), "api_key")


def test_operation_contract_parameters_separate_from_preview():
    call = ToolCall("id", "write_file", '{}')
    operation = PreparedOperation(call, {"content": "original"}, preview="[redacted]")
    assert operation.arguments["content"] == "original"
    assert operation.operation_id


import asyncio
import ctypes
import json
import os
import subprocess
import sys

import pytest

from weizhcode.models import ToolResult
from weizhcode.redaction import Redactor
from weizhcode.tools import create_default_registry
from weizhcode.tools.executor import ToolExecutor
from weizhcode.tools.process import ManagedWorker, WindowsJob
from weizhcode.tools import process as process_module


def tool_call(name, **args):
    return ToolCall("call-id", name, json.dumps(args))


async def collect(executor, call, approve=None):
    return [event async for event in executor.run(call, approve=approve)]


async def allow(request):
    return True


@pytest.mark.skipif(os.name != "nt", reason="需要 Windows 原生 Job")
async def test_windows_job_kills_assigned_process():
    child = await asyncio.create_subprocess_exec(sys.executable, "-c", "import sys; sys.stdin.read()",
                                                  stdin=asyncio.subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
    job = WindowsJob()
    try:
        job.attach(child.pid)
        job.close()
        await asyncio.wait_for(child.wait(), 3)
        assert child.returncode is not None
        job.close()
    finally:
        if child.returncode is None:
            child.kill()
            await child.wait()


@pytest.mark.skipif(os.name == "nt", reason="POSIX 进程组需对应系统实测")
async def test_posix_process_worker_closes(tmp_path):
    worker = ManagedWorker()
    try:
        await worker.start(ToolContext(tmp_path))
    finally:
        await worker.aclose()
    assert worker.process.returncode is not None


async def test_worker_protocol_rejects_wrong_state(tmp_path):
    worker = ManagedWorker()
    try:
        await worker.start(ToolContext(tmp_path))
        with pytest.raises(Exception, match="状态"):
            await worker.execute("not-prepared")
    finally:
        await worker.aclose()
    assert list(tmp_path.iterdir()) == []


async def test_managed_worker_read_and_duplicate_execute(tmp_path):
    (tmp_path / "a").write_text("hello")
    worker = ManagedWorker()
    try:
        await worker.start(ToolContext(tmp_path))
        preview = await worker.prepare(tool_call("read_file", path="a"))
        result = await worker.execute(preview.operation_id)
        assert "hello" in result.content
        with pytest.raises(Exception, match="状态"):
            await worker.execute(preview.operation_id)
    finally:
        await worker.aclose()
        await worker.aclose()
    assert worker.process.returncode is not None


@pytest.mark.skipif(os.name != "nt", reason="Windows 控制建立失败分支")
async def test_windows_job_assignment_failure_prevents_execution(tmp_path, monkeypatch):
    def deny(self, pid):
        raise OSError("denied")
    monkeypatch.setattr(WindowsJob, "attach", deny)
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path))
    events = await collect(executor, tool_call("write_file", path="a", content="x"), allow)
    assert events[-1].result.error_code == "PROCESS_CONTROL_FAILED"
    assert not (tmp_path / "a").exists()


@pytest.mark.parametrize("call", [
    ToolCall("id", "missing", "{}"), ToolCall("id", "read_file", "{"),
    ToolCall("id", "read_file", '{"path":1}'), ToolCall(None, "read_file", '{"path":"a"}'),
])
async def test_executor_validation_does_not_start_worker(tmp_path, call):
    def forbidden():
        raise AssertionError("无效调用启动了进程")
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path), worker_factory=forbidden)
    events = await collect(executor, call)
    assert len(events) == 1 and events[0].result.is_error


@pytest.mark.parametrize("name,args", [
    ("read_file", {"path": "a"}), ("find_files", {"pattern": "*.txt"}),
    ("search_content", {"pattern": "hello"}),
])
async def test_executor_readonly_no_approval(tmp_path, name, args):
    (tmp_path / "a").write_text("hello")
    async def reject_approval(request):
        raise AssertionError("只读工具请求了审批")
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path))
    events = await collect(executor, tool_call(name, **args), reject_approval)
    assert [e.type for e in events] == ["tool_preparing", "tool_running", "tool_result"]
    assert not events[-1].result.is_error
    assert not executor._active


@pytest.mark.parametrize("approved", [True, False, None])
async def test_executor_approval_no_early_write(tmp_path, approved):
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path))
    async def decide(request):
        assert not (tmp_path / "sub").exists()
        assert request.command == ""
        assert str(tmp_path / "sub/a") in request.preview
        return approved
    events = await collect(executor, tool_call("write_file", path="sub/a", content="hello"), decide)
    result = events[-1].result
    assert (tmp_path / "sub/a").exists() is (approved is True)
    assert result.status == ("success" if approved is True else "denied")
    assert not list(tmp_path.rglob(".weizhcode-*.tmp"))


async def test_executor_approval_stale_after_wait(tmp_path):
    path = tmp_path / "a"
    path.write_text("old")
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path))
    async def decide(request):
        path.write_text("external")
        return True
    events = await collect(executor, tool_call("write_file", path="a", content="new"), decide)
    assert events[-1].result.error_code == "PREVIEW_STALE"
    assert path.read_text() == "external"


async def test_executor_approval_missing_handler_denies(tmp_path):
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path))
    events = await collect(executor, tool_call("write_file", path="a", content="new"))
    assert events[-1].result.status == "denied"
    assert not (tmp_path / "a").exists()


class SlowWorker:
    def __init__(self):
        self.partial = {"stdout": "", "stderr": ""}
        self.closed = False
    async def start(self, context):
        await asyncio.sleep(.02)
    async def prepare(self, call):
        await asyncio.sleep(.02)
        self.call = call
        return PreparedOperationPreview("operation", "target", "preview")
    async def execute(self, operation_id):
        await asyncio.sleep(.04)
        return ToolResult(self.call.call_id, self.call.name, "ok")
    async def aclose(self):
        self.closed = True


async def test_executor_timeout_approval_pauses_budget(tmp_path):
    worker = SlowWorker()
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path), timeout=.15, worker_factory=lambda: worker)
    async def decide(request):
        await asyncio.sleep(.25)
        return True
    events = await collect(executor, tool_call("write_file", path="a", content="new"), decide)
    assert events[-1].result.status == "success" and worker.closed


async def test_executor_timeout_budget_not_reset(tmp_path):
    worker = SlowWorker()
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path), timeout=.06, worker_factory=lambda: worker)
    events = await collect(executor, tool_call("read_file", path="a"))
    assert events[-1].result.status == "timeout" and worker.closed


def process_running(pid):
    if os.name == "nt":
        from ctypes import wintypes
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        api.OpenProcess.restype = wintypes.HANDLE
        api.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = api.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            return bool(api.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
        finally:
            api.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        status = Path(f"/proc/{pid}/stat")
        return not status.exists() or status.read_text().split()[2] != "Z"
    except ProcessLookupError:
        return False


async def test_process_tree_timeout_kills_parent_and_child(tmp_path):
    from test_command_tool import python_command
    script = ('import subprocess,sys,time,os,json,pathlib; '
              'child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); '
              'pathlib.Path("pids.json").write_text(json.dumps([os.getpid(),child.pid])); '
              'print("ready",flush=True); time.sleep(60)')
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path), timeout=3)
    events = await collect(executor, tool_call("run_command", command=python_command(script)), allow)
    assert events[-1].result.status == "timeout"
    assert (tmp_path / "pids.json").exists(), events[-1].result
    ids = json.loads((tmp_path / "pids.json").read_text())
    assert all(not process_running(pid) for pid in ids)
    assert "ready" in events[-1].result.content


async def test_output_pressure_real_worker(tmp_path):
    from test_command_tool import python_command
    script = 'import sys; print("x"*200000); print("y"*200000,file=sys.stderr)'
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path), timeout=10)
    events = await collect(executor, tool_call("run_command", command=python_command(script)), allow)
    result = events[-1].result
    assert not result.is_error, result
    assert result.truncated and len(result.to_model_text()) <= 20000
    assert result.metadata["exit_code"] == 0
    assert result.metadata["stdout_chars"] >= 200000
    assert result.metadata["stderr_chars"] >= 200000


async def test_app_shutdown_executor_active_worker(tmp_path):
    from test_command_tool import python_command
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path))
    task = asyncio.create_task(collect(executor, tool_call("run_command", command=python_command("import time; time.sleep(60)")), allow))
    for _ in range(100):
        if executor._active:
            break
        await asyncio.sleep(.01)
    await executor.aclose()
    await asyncio.wait_for(task, 5)
    assert not executor._active


async def test_app_shutdown_during_subprocess_start(tmp_path, monkeypatch):
    original = asyncio.create_subprocess_exec
    created = []
    async def delayed(*args, **kwargs):
        process = await original(*args, **kwargs)
        created.append(process)
        await asyncio.sleep(.1)
        return process
    monkeypatch.setattr(asyncio, "create_subprocess_exec", delayed)
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path))
    task = asyncio.create_task(collect(executor, tool_call("write_file", path="a", content="x"), allow))
    for _ in range(200):
        if created:
            break
        await asyncio.sleep(.005)
    assert created
    await executor.aclose()
    events = await asyncio.wait_for(task, 5)
    assert events[-1].result.is_error
    assert created[0].returncode is not None
    assert not (tmp_path / "a").exists()


async def test_worker_protocol_wrong_operation_id_no_write(tmp_path):
    worker = ManagedWorker()
    try:
        await worker.start(ToolContext(tmp_path))
        await worker.prepare(tool_call("write_file", path="a", content="x"))
        assert not (tmp_path / "a").exists()
        with pytest.raises(Exception, match="状态"):
            await worker.execute("wrong")
    finally:
        await worker.aclose()
    assert not (tmp_path / "a").exists()

