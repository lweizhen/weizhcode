from __future__ import annotations

import asyncio
import ctypes
import json
import os
import signal
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from weizhcode.models import PreparedOperationPreview, ToolCall, ToolContext, ToolResult
from weizhcode.tools.base import ToolFailure
from weizhcode.tools.limits import MAX_RESULT_CHARS


class WindowsJob:
    """只管理本轮进程生命周期，不授予或降低系统权限。"""

    def __init__(self):
        if os.name != "nt":
            raise OSError("Windows Job 仅适用于 Windows")
        from ctypes import wintypes
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = wintypes.HANDLE
        definitions = {
            "CreateJobObjectW": ([ctypes.c_void_p, wintypes.LPCWSTR], handle),
            "SetInformationJobObject": ([handle, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
            "OpenProcess": ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], handle),
            "AssignProcessToJobObject": ([handle, handle], wintypes.BOOL),
            "TerminateJobObject": ([handle, wintypes.UINT], wintypes.BOOL),
            "CloseHandle": ([handle], wintypes.BOOL),
        }
        for name, (args, result) in definitions.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = args, result

        class Basic(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", ctypes.c_uint32), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", ctypes.c_uint32),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", ctypes.c_uint32), ("SchedulingClass", ctypes.c_uint32),
            ]

        class Extended(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", Basic), ("IoInfo", ctypes.c_ulonglong * 6),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = Extended()
        limits.BasicLimitInformation.LimitFlags = 0x2000
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def attach(self, pid: int):
        process = self.api.OpenProcess(0x0100 | 0x0001, False, pid)
        if not process:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not self.api.AssignProcessToJobObject(self.handle, process):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            self.api.CloseHandle(process)

    def close(self):
        handle, self.handle = getattr(self, "handle", None), None
        if handle:
            self.api.TerminateJobObject(handle, 1)
            self.api.CloseHandle(handle)


class ManagedWorker:
    def __init__(self):
        self.process = None
        self.job = None
        self.stderr_task = None
        self.diagnostic = ""
        self.preview = None
        self.resources: dict[Path, tuple[int, int]] = {}
        self.partial = {"stdout": "", "stderr": ""}
        self._closed = False
        self._close_task = None

    async def start(self, context: ToolContext):
        if self._closed:
            raise ToolFailure("INTERNAL_ERROR", "工作进程已关闭")
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
        environment = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        creation = asyncio.create_task(asyncio.create_subprocess_exec(
            sys.executable, "-m", "weizhcode.tools.worker", stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env=environment, limit=256_000, **options,
        ))
        try:
            self.process = await asyncio.shield(creation)
        except asyncio.CancelledError:
            # 创建系统进程的等待被取消，仍须接管实际创建结果再清理。
            self.process = await creation
            if self.process.returncode is None:
                self.process.kill()
            await self.process.wait()
            self.process.stdin.close()
            raise
        if self._closed:
            # 退出可能发生在创建子进程的 await 期间，此时尚未释放任何执行指令。
            self.process.kill()
            await self.process.wait()
            self.process.stdin.close()
            raise ToolFailure("INTERNAL_ERROR", "启动期间已退出，工作进程已清理")
        self.stderr_task = asyncio.create_task(self._drain_stderr())
        if os.name == "nt":
            try:
                self.job = WindowsJob()
                self.job.attach(self.process.pid)
            except OSError as exc:
                raise ToolFailure("PROCESS_CONTROL_FAILED", "无法建立命令进程管理，未执行工具") from exc
        await self._send({"type": "start", "project_root": str(context.project_root)})
        await self._receive("ready")

    async def _drain_stderr(self):
        while chunk := await self.process.stderr.read(4096):
            if len(self.diagnostic) < 4096:
                self.diagnostic += chunk.decode("utf-8", "replace")[:4096 - len(self.diagnostic)]

    async def _send(self, message):
        if self._closed or self.process is None or self.process.returncode is not None:
            raise ToolFailure("INTERNAL_ERROR", "工具工作进程已结束")
        self.process.stdin.write((json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8"))
        await self.process.stdin.drain()

    async def _receive(self, expected):
        while raw := await self.process.stdout.readline():
            try:
                message = json.loads(raw)
            except (ValueError, UnicodeError):
                raise ToolFailure("INTERNAL_ERROR", "工具工作进程通信格式错误") from None
            if not isinstance(message, dict):
                raise ToolFailure("INTERNAL_ERROR", "工具工作进程通信类型错误")
            if message.get("type") == "output":
                label, text = message.get("label"), message.get("text")
                if label not in self.partial or not isinstance(text, str):
                    raise ToolFailure("INTERNAL_ERROR", "非法命令输出消息")
                room = max(0, MAX_RESULT_CHARS - 512 - sum(map(len, self.partial.values())))
                self.partial[label] += text[:room]
                continue
            if message.get("type") == "resource":
                path = Path(str(message.get("path")))
                identity = message.get("identity")
                expected_path = None if self.preview is None else Path(self.preview.target).with_name(
                    f".weizhcode-{self.preview.operation_id}.tmp"
                )
                if path != expected_path or not isinstance(identity, list) or len(identity) != 2 or not all(type(n) is int for n in identity):
                    raise ToolFailure("INTERNAL_ERROR", "非法临时资源登记")
                self.resources[path] = tuple(identity)
                continue
            if message.get("type") != expected:
                raise ToolFailure("INTERNAL_ERROR", "工具工作进程状态不匹配")
            return message
        raise ToolFailure("INTERNAL_ERROR", "工具工作进程异常终止")

    async def prepare(self, call: ToolCall) -> PreparedOperationPreview:
        await self._send({"type": "prepare", "call": asdict(call)})
        message = await self._receive("prepared")
        payload = message["preview"]
        if payload.get("error"):
            payload["error"] = ToolResult(**payload["error"])
        self.preview = PreparedOperationPreview(**payload)
        return self.preview

    async def execute(self, operation_id: str) -> ToolResult:
        await self._send({"type": "execute", "operation_id": operation_id})
        message = await self._receive("result")
        return ToolResult(**message["result"])

    async def aclose(self):
        if self._close_task is None:
            self._closed = True
            self._close_task = asyncio.create_task(self._close_impl())
        await asyncio.shield(self._close_task)

    async def _close_impl(self):
        process = self.process
        if process:
            if self.job:
                self.job.close()
                self.job = None
            elif os.name == "nt":
                if process.returncode is None:
                    process.kill()
            else:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    await asyncio.wait_for(process.wait(), 0.15)
                except TimeoutError:
                    pass
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            try:
                await asyncio.wait_for(process.wait(), 3)
            finally:
                if process.stdin:
                    process.stdin.close()
                if self.stderr_task:
                    await asyncio.wait_for(self.stderr_task, 3)
        for path, identity in self.resources.items():
            try:
                info = path.lstat()
                if not path.is_symlink() and (info.st_dev, info.st_ino) == identity:
                    path.unlink()
            except FileNotFoundError:
                pass

