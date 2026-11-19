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
            "QueryInformationJobObject": ([handle, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p], wintypes.BOOL),
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
            try:
                if not self.api.TerminateJobObject(handle, 1):
                    raise ctypes.WinError(ctypes.get_last_error() or 1)
            finally:
                if not self.api.CloseHandle(handle):
                    raise ctypes.WinError(ctypes.get_last_error() or 1)

    def active_processes(self):
        class Accounting(ctypes.Structure):
            _fields_ = [("times", ctypes.c_longlong * 4), ("faults", ctypes.c_uint32),
                        ("total", ctypes.c_uint32), ("active", ctypes.c_uint32), ("terminated", ctypes.c_uint32)]
        info = Accounting()
        if not self.api.QueryInformationJobObject(self.handle, 1, ctypes.byref(info), ctypes.sizeof(info), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return info.active


class ManagedWorker:
    def __init__(self, *, purpose="tools", request_id=None):
        if purpose not in {"tools", "permission"}:
            raise ValueError("非法工作进程目的")
        from uuid import uuid4
        self.purpose = purpose
        self.request_id = request_id or uuid4().hex
        self.permission_temp = None
        self.process = None
        self.job = None
        self.stderr_task = None
        self.diagnostic = ""
        self.preview = None
        self.resources: dict[Path, tuple[int, int]] = {}
        self.partial = {"stdout": "", "stderr": ""}
        self._closed = False
        self._close_task = None
        self.capture_sink = None
        self.captured_source = None
        self.file_read_capture = None
        self._capture_operation = None
        self._capture_started = self._capture_ended = False
        self._capture_seq = 0
        self._prepared_call = None

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
        if self.purpose == "permission":
            self.permission_temp = context.project_root / ".weizhcode" / f".settings.local.{self.request_id}.tmp"
        await self._send({"type": "start", "project_root": str(context.project_root),
                          "purpose": self.purpose, "request_id": self.request_id,
                          "permission_root": asdict(context.permission_root) if context.permission_root else None})
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
            if message.get("type") == "file_capture":
                sink = self.capture_sink
                if (self.purpose != "tools" or expected != "result" or sink is None
                        or len(raw) > 128*1024 or self.file_read_capture is not None
                        or self._capture_started or self._prepared_call.name != "read_file"
                        or message.get("operation_id") != self._capture_operation
                        or message.get("execution_key") != sink.execution_key
                        or type(message.get('generation')) is not int or message.get("generation") != sink.generation
                        or message.get("canonical_path") != self.preview.target
                        or type(message.get("start_line")) is not int
                        or message["start_line"] != self._prepared_call.arguments.get("start_line", 1)
                        or type(message.get("returned_lines")) is not int
                        or not 0 <= message["returned_lines"] <= self._prepared_call.arguments.get("line_count", 2000)
                        or not isinstance(message.get("text"), str) or len(message["text"]) > 17500
                        or type(message.get('bom')) is not bool or message.get('newline') not in {'\n', '\r', '\r\n'}
                        or type(message.get("truncated")) is not bool):
                    raise ToolFailure("INTERNAL_ERROR", "文件原文捕获帧无效")
                from weizhcode.compact.contracts import FileReadCapture
                from datetime import datetime, timezone
                self.file_read_capture = FileReadCapture(sink.execution_key, message["canonical_path"],
                    message["start_line"], message["returned_lines"], sink.hub.redactor.text(message["text"]),
                    message["truncated"], 0, datetime.now(timezone.utc).isoformat(), message['bom'], message['newline'])
                continue
            if message.get("type") in {"capture_begin", "capture_chunk", "capture_end"}:
                sink = self.capture_sink
                if (self.purpose != "tools" or expected != "result" or sink is None
                        or len(raw) > 128*1024 or message.get("operation_id") != self._capture_operation
                        or message.get("execution_key") != sink.execution_key
                        or type(message.get('generation')) is not int or message.get("generation") != sink.generation or self._capture_ended):
                    raise ToolFailure("INTERNAL_ERROR", "捕获帧与当前执行不匹配")
                kind = message["type"]
                if kind == "capture_begin":
                    if (self._capture_started or message.get("call_id") != self._prepared_call.call_id
                            or message.get("tool_name") != self._prepared_call.name
                            or not await sink.begin(collected_bytes=message.get("collected_bytes"), truncated=message.get("truncated"))):
                        raise ToolFailure("INTERNAL_ERROR", "捕获开始帧无效")
                    self._capture_started = True
                elif kind == "capture_chunk":
                    if (not self._capture_started or type(message.get("seq")) is not int
                            or message["seq"] != self._capture_seq or not await sink.feed(message.get("text"))):
                        raise ToolFailure("INTERNAL_ERROR", "捕获分片无效")
                    self._capture_seq += 1
                else:
                    if not self._capture_started or type(message.get("complete")) is not bool:
                        raise ToolFailure("INTERNAL_ERROR", "捕获结束帧无效")
                    self.captured_source = await sink.finish(complete=message["complete"])
                    self._capture_ended = True
                continue
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
                if self.purpose == "permission":
                    expected_path = self.permission_temp
                if path != expected_path or not isinstance(identity, list) or len(identity) != 2 or not all(type(n) is int for n in identity):
                    raise ToolFailure("INTERNAL_ERROR", "非法临时资源登记")
                self.resources[path] = tuple(identity)
                continue
            if message.get("type") != expected:
                raise ToolFailure("INTERNAL_ERROR", "工具工作进程状态不匹配")
            if expected == "result" and self.capture_sink is not None and not self._capture_ended:
                raise ToolFailure("INTERNAL_ERROR", "捕获未完整结束")
            return message
        raise ToolFailure("INTERNAL_ERROR", "工具工作进程异常终止")

    async def prepare(self, call: ToolCall, *, permission_stamp=None, archive_read_proof=None) -> PreparedOperationPreview:
        self._prepared_call = call
        await self._send({"type": "prepare", "call": asdict(call),
                          "permission_stamp": asdict(permission_stamp) if permission_stamp else None,
                          "archive_read_proof": asdict(archive_read_proof) if archive_read_proof else None})
        message = await self._receive("prepared")
        payload = message["preview"]
        if payload.get("error"):
            payload["error"] = ToolResult(**payload["error"])
        self.preview = PreparedOperationPreview(**payload)
        return self.preview

    async def execute(self, operation_id: str, *, capture_sink=None) -> ToolResult:
        self.capture_sink, self._capture_operation = capture_sink, operation_id
        options = ({"capture": {"execution_key": capture_sink.execution_key, "generation": capture_sink.generation}}
                   if capture_sink is not None else {})
        await self._send({"type": "execute", "operation_id": operation_id, **options})
        message = await self._receive("result")
        return ToolResult(**message["result"])

    async def permission_operation(self, action, payload):
        if self.purpose != "permission" or action not in {"inspect_permission_path", "persist_permission_allow"}:
            raise ToolFailure("INTERNAL_ERROR", "非法权限辅助指令")
        await self._send({"type": action, "request_id": self.request_id, **payload})
        message = await self._receive("permission_result")
        if message.get("request_id") != self.request_id:
            raise ToolFailure("INTERNAL_ERROR", "权限辅助响应 ID 错误")
        return message

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

