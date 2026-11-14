from pathlib import Path


def test_tool_slot_contract_isolation_and_cancel_budget():
    from weizhcode.models import ToolCall, ToolResult, ToolSlot
    call = ToolCall("a", "read_file", '{}', {"path": "a"})
    first, second = ToolSlot(0, call), ToolSlot(1, ToolCall("b", "read_file", '{}'))
    call.arguments["path"] = "changed"
    assert first.call.arguments == {"path": "a"}
    assert first.local_id != second.local_id
    assert first.phase == "pending" and not first.execution_started
    first.execution_started = True
    first.result = ToolResult("a", "read_file", "confirmed")
    second.result = ToolResult.failure(second.call, "TOOL_CANCELLED", "未执行" * 30000)
    assert first.result.status == "success"
    assert second.result.status == "cancelled" and second.result.is_error
    assert len(second.result.to_model_text()) <= 20000

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


async def execute_slot(executor, call, *, mode="normal", cancel=None):
    from weizhcode.models import ToolSlot
    slot, events = ToolSlot(0, call), []
    async def emit(event):
        events.append(event)
    result = await executor.execute(slot, mode=mode, cancel=cancel or asyncio.Event(), emit=emit)
    return result, slot, events


async def test_loop_execute_basic_write_read_and_errors(tmp_path):
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path))
    result, slot, events = await execute_slot(executor, tool_call("write_file", path="sub/a", content="hello"))
    assert result.status == "success" and slot.execution_started
    assert (tmp_path / "sub/a").read_text() == "hello"
    assert [e.type for e in events] == ["tool_preparing", "tool_running"]
    result, _, _ = await execute_slot(executor, tool_call("read_file", path="sub/a"))
    assert "hello" in result.content
    result, _, _ = await execute_slot(executor, tool_call("read_file", path="missing"))
    assert result.error_code == "FILE_NOT_FOUND" and not executor._active


@pytest.mark.parametrize("name,args", [
    ("write_file", {"path": "sub/a", "content": "x"}),
    ("edit_file", {"path": "a", "old_text": "old", "new_text": "new"}),
    ("run_command", {"command": "echo unsafe"})])
async def test_plan_execution_gate_zero_worker_and_side_effect(tmp_path, name, args):
    (tmp_path / "a").write_text("old")
    workers = []
    def forbidden():
        workers.append(True)
        raise AssertionError("should not create worker")
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path), worker_factory=forbidden)
    result, slot, _ = await execute_slot(executor, tool_call(name, **args), mode="plan")
    assert result.error_code == "TOOL_NOT_ALLOWED" and not slot.execution_started
    assert not workers and not (tmp_path / "sub").exists()
    assert (tmp_path / "a").read_text() == "old"


class LoopWorker:
    def __init__(self, *, prepare_delay=0, execute_delay=0, cleanup_gate=None, cleanup_error=False):
        self.prepare_delay, self.execute_delay = prepare_delay, execute_delay
        self.cleanup_gate, self.cleanup_error = cleanup_gate, cleanup_error
        self.running, self.cleaning = asyncio.Event(), asyncio.Event()
        self.partial = {"stdout": "", "stderr": ""}
        self.closed = False
        self.call = None
    async def start(self, context):
        pass
    async def prepare(self, call):
        self.call = call
        await asyncio.sleep(self.prepare_delay)
        return PreparedOperationPreview("operation", "", "")
    async def execute(self, operation):
        self.running.set()
        await asyncio.sleep(self.execute_delay)
        return ToolResult(self.call.call_id, self.call.name, "confirmed")
    async def aclose(self):
        self.cleaning.set()
        if self.cleanup_gate:
            await self.cleanup_gate.wait()
        self.closed = True
        if self.cleanup_error:
            raise OSError("secret cleanup details")


async def test_loop_tool_budget_prepare_and_execute_share_one_deadline(tmp_path):
    worker = LoopWorker(prepare_delay=.06, execute_delay=.06)
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path), timeout=.1, worker_factory=lambda: worker)
    result, slot, _ = await execute_slot(executor, tool_call("read_file", path="a"))
    assert result.error_code == "TOOL_TIMEOUT" and worker.closed
    assert slot.execution_started


async def test_cancel_preserves_result_during_cleanup(tmp_path):
    gate, cancel = asyncio.Event(), asyncio.Event()
    worker = LoopWorker(cleanup_gate=gate)
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path), worker_factory=lambda: worker)
    task = asyncio.create_task(execute_slot(executor, tool_call("read_file", path="a"), cancel=cancel))
    await worker.cleaning.wait()
    cancel.set()
    task.cancel()  # 模拟调度器监督取消，不能抹去已经确认的结果。
    gate.set()
    result, slot, _ = await task
    assert result.content == "confirmed" and result.status == "success"
    assert worker.closed and slot.phase == "finished" and not executor._closed


async def test_cancel_preserves_result_same_tick_as_execute_reply(tmp_path):
    cancel = asyncio.Event()
    class SameTickWorker(LoopWorker):
        async def execute(self, operation):
            cancel.set()
            return ToolResult(self.call.call_id, self.call.name, "confirmed")
    worker = SameTickWorker()
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path), worker_factory=lambda: worker)
    result, slot, _ = await execute_slot(executor, tool_call("read_file", path="a"), cancel=cancel)
    assert result.status == "success" and slot.result.content == "confirmed" and worker.closed


async def test_cancel_preserves_result_unconfirmed_has_honest_status(tmp_path):
    worker, cancel = LoopWorker(execute_delay=10), asyncio.Event()
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path), worker_factory=lambda: worker)
    task = asyncio.create_task(execute_slot(executor, tool_call("read_file", path="a"), cancel=cancel))
    await worker.running.wait()
    cancel.set()
    result, slot, _ = await asyncio.wait_for(task, 1)
    assert result.error_code == "TOOL_CANCELLED" and slot.execution_started
    assert "可能保留" in result.content and worker.closed
    result, slot, _ = await execute_slot(executor, tool_call("read_file", path="a"), cancel=cancel)
    assert not slot.execution_started and "未开始" in result.content


async def test_cleanup_infrastructure_failure_retains_success(tmp_path):
    worker = LoopWorker(cleanup_error=True)
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path), worker_factory=lambda: worker)
    result, slot, _ = await execute_slot(executor, tool_call("read_file", path="a"))
    assert result.content == "confirmed"
    assert "PROCESS_CONTROL_FAILED" in slot.cleanup_error
    assert "secret cleanup details" not in slot.cleanup_error


async def test_loop_process_cleanup_cancel_preparing_and_creation(tmp_path, monkeypatch):
    original = asyncio.create_subprocess_exec
    created, entered, release = [], asyncio.Event(), asyncio.Event()
    async def delayed(*args, **kwargs):
        proc = await original(*args, **kwargs)
        created.append(proc)
        entered.set()
        await release.wait()
        return proc
    monkeypatch.setattr(asyncio, "create_subprocess_exec", delayed)
    cancel = asyncio.Event()
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path))
    work = asyncio.create_task(execute_slot(executor, tool_call("write_file", path="a", content="x"), cancel=cancel))
    await asyncio.wait_for(entered.wait(), 5)
    cancel.set()
    release.set()
    result, slot, _ = await asyncio.wait_for(work, 5)
    assert result.status == "cancelled" and not slot.execution_started
    assert created[0].returncode is not None and not (tmp_path / "a").exists()
    assert not executor._active


async def test_loop_process_cleanup_cancel_real_prepare_phase(tmp_path):
    entered, cancel = asyncio.Event(), asyncio.Event()
    class PreparingWorker(ManagedWorker):
        async def prepare(self, call):
            result = await super().prepare(call)
            entered.set()
            await asyncio.Event().wait()
            return result
    worker = PreparingWorker()
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path), worker_factory=lambda: worker)
    work = asyncio.create_task(execute_slot(executor, tool_call("write_file", path="a", content="new"), cancel=cancel))
    await asyncio.wait_for(entered.wait(), 5)
    cancel.set()
    result, slot, _ = await asyncio.wait_for(work, 5)
    assert result.status == "cancelled" and not slot.execution_started
    assert worker.process.returncode is not None and not (tmp_path / "a").exists()


async def test_loop_process_cleanup_cancel_command_tree_and_reuse(tmp_path):
    from test_command_tool import python_command
    script = ('import subprocess,sys,time,os,json,pathlib; '
              'child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); '
              'pathlib.Path("pids.json").write_text(json.dumps([os.getpid(),child.pid])); '
              'time.sleep(60); pathlib.Path("late-marker").write_text("bad")')
    cancel = asyncio.Event()
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path))
    work = asyncio.create_task(execute_slot(executor, tool_call("run_command", command=python_command(script)), cancel=cancel))
    for _ in range(500):
        if (tmp_path / "pids.json").exists():
            break
        await asyncio.sleep(.01)
    assert (tmp_path / "pids.json").exists()
    ids = json.loads((tmp_path / "pids.json").read_text())
    cancel.set()
    result, _, _ = await asyncio.wait_for(work, 5)
    assert result.status == "cancelled" and all(not process_running(pid) for pid in ids)
    assert not (tmp_path / "late-marker").exists() and not executor._closed
    result, _, _ = await execute_slot(executor, tool_call("write_file", path="next", content="ok"))
    assert result.status == "success" and (tmp_path / "next").read_text() == "ok"


@pytest.mark.parametrize("replace_resource", [False, True])
async def test_loop_process_cleanup_cancel_atomic_temp_ownership(tmp_path, monkeypatch, replace_resource):
    target, user = tmp_path / "a", tmp_path / ".weizhcode-user.tmp"
    target.write_text("original")
    user.write_text("keep")
    original = asyncio.create_subprocess_exec
    bootstrap = (
        "import time; from weizhcode.tools import worker; original=worker.emit\n"
        "def paused(message):\n"
        "    original(message)\n"
        "    if message.get('type')=='resource': time.sleep(60)\n"
        "worker.emit=paused\nworker.main()\n")
    async def spawn(*args, **kwargs):
        if args[1:3] == ("-m", "weizhcode.tools.worker"):
            args = (args[0], "-c", bootstrap, *args[3:])
        return await original(*args, **kwargs)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    worker, cancel = ManagedWorker(), asyncio.Event()
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path), worker_factory=lambda: worker)
    work = asyncio.create_task(execute_slot(executor, tool_call("write_file", path="a", content="new"), cancel=cancel))
    for _ in range(500):
        if worker.resources:
            break
        await asyncio.sleep(.01)
    assert worker.resources, "没有资源登记不能作为此场景通过"
    resource = next(iter(worker.resources))
    if replace_resource:
        replacement = tmp_path / "replacement"
        replacement.write_text("external")
        original_lstat = Path.lstat
        replaced = False
        def replace_before_identity_check(path, *args, **kwargs):
            nonlocal replaced
            # Windows 不允许替换仍被工作进程打开的文件；在实际进程结束后、
            # 归属检查前模拟外部替换，才能准确验证不能误删新对象。
            if path == resource and worker.process.returncode is not None and not replaced:
                os.replace(replacement, resource)
                replaced = True
            return original_lstat(path, *args, **kwargs)
        monkeypatch.setattr(Path, "lstat", replace_before_identity_check)
    cancel.set()
    result, _, _ = await asyncio.wait_for(work, 5)
    assert result.status == "cancelled" and worker.process.returncode is not None
    assert target.read_text() == "original" and user.read_text() == "keep"
    assert resource.exists() is replace_resource
    if replace_resource:
        assert resource.read_text() == "external"


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



@pytest.mark.parametrize("name", ["read_file", "run_command"])
async def test_security_pipeline_actual_content_and_command_preserved(tmp_path, name):
    from weizhcode.redaction import Redactor
    from test_command_tool import python_command
    secret = "fake-secret-token"
    marker = tmp_path / "marker"
    if name == "read_file":
        marker.write_text(secret, encoding="utf-8")
        call = tool_call(name, path=str(marker))
    else:
        code = f"import sys; from pathlib import Path; Path({str(marker)!r}).write_text({secret!r}); print({secret!r}); print({secret!r},file=sys.stderr)"
        call = tool_call(name, command=python_command(code))
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path), Redactor([secret]))
    previews = []
    async def approve(request):
        previews.append(request)
        assert secret not in request.preview + request.command
        return True
    events = await collect(executor, call, approve)
    result = events[-1].result
    assert not result.is_error
    assert secret not in result.to_model_text()
    assert "[redacted]" in result.content
    assert marker.read_text(encoding="utf-8") == secret
    assert bool(previews) == (name == "run_command")



async def test_atomic_temp_cleanup_after_real_worker_timeout(tmp_path, monkeypatch):
    target = tmp_path / "a"
    target.write_text("original", encoding="utf-8")
    user_temp = tmp_path / ".weizhcode-user.tmp"
    user_temp.write_text("keep", encoding="utf-8")
    original_spawn = asyncio.create_subprocess_exec
    # 只在测试子进程中暂停资源登记之后的写入；不更改生产执行路径。
    bootstrap = (
        "import time; from weizhcode.tools import worker; original = worker.emit\n"
        "def paused(message):\n"
        "    original(message)\n"
        "    if message.get('type') == 'resource': time.sleep(60)\n"
        "worker.emit = paused\n"
        "worker.main()\n"
    )
    async def spawn(*args, **kwargs):
        if len(args) >= 3 and args[1:3] == ("-m", "weizhcode.tools.worker"):
            args = (args[0], "-c", bootstrap, *args[3:])
        return await original_spawn(*args, **kwargs)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    workers = []
    def factory():
        worker = ManagedWorker()
        workers.append(worker)
        return worker
    executor = ToolExecutor(create_default_registry(), ToolContext(tmp_path), timeout=3, worker_factory=factory)
    events = await collect(executor, tool_call("write_file", path="a", content="new"), allow)
    assert events[-1].result.error_code == "TOOL_TIMEOUT"
    worker = workers[0]
    assert worker.resources, "实际工作进程未登记临时资源，不能当作该场景已覆盖"
    assert worker.process.returncode is not None
    assert all(not path.exists() for path in worker.resources)
    assert target.read_text(encoding="utf-8") == "original"
    assert user_temp.read_text(encoding="utf-8") == "keep"

