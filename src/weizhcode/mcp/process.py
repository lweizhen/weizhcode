"""Owned application processes; servers never receive a connect instruction before ownership."""
from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
from uuid import uuid4

from weizhcode.tools.process import WindowsJob
from .limits import MAX_IPC_BYTES


def base_environment():
    names = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "HOME",
             "USERPROFILE", "APPDATA", "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH", "LANG"}
    return {**{k: v for k, v in os.environ.items() if k.upper() in names},
            "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


class OwnedProcess:
    def __init__(self, module):
        self.module = module
        self.id = uuid4().hex
        self.process = self.job = None
        self._closing = None
        self._drain = None
        self._descendants = {}

    async def start(self):
        if self._closing is not None:
            raise RuntimeError("MCP process already closed")
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
        creation = asyncio.create_task(asyncio.create_subprocess_exec(
            sys.executable, "-m", self.module, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            limit=MAX_IPC_BYTES + 1, env=base_environment(), **options))
        interrupted = False
        while True:
            try:
                self.process = await asyncio.shield(creation)
                break
            except asyncio.CancelledError:
                interrupted = True
        if interrupted or self._closing is not None:
            if self.process.returncode is None:
                self.process.kill()
            self.process.stdin.close()
            await self.process.wait()
            self.process._transport.close()
            raise asyncio.CancelledError()
        async def discard():
            while await self.process.stderr.read(4096):
                pass  # Never print raw SDK/worker diagnostics.
        self._drain = asyncio.create_task(discard())
        try:
            if os.name == "nt":
                self.job = WindowsJob()
                self.job.attach(self.process.pid)
        except BaseException:
            await self.aclose()
            raise

    async def send(self, kind, **data):
        raw = json.dumps({"version": 1, "host_id": self.id, "type": kind, **data},
                         ensure_ascii=False, allow_nan=False).encode() + b"\n"
        if len(raw) > MAX_IPC_BYTES:
            raise ValueError("MCP_IPC_LIMIT")
        if self.process is None or self.process.returncode is not None:
            raise ConnectionError("MCP_UNAVAILABLE")
        self.process.stdin.write(raw)
        await self.process.stdin.drain()

    async def receive(self):
        raw = await self.process.stdout.readline()
        if not raw or len(raw) > MAX_IPC_BYTES:
            raise ConnectionError("MCP_IPC_ERROR")
        value = json.loads(raw)
        if (type(value) is not dict or value.get("version") != 1 or value.get("host_id") != self.id
                or value.get("type") not in {"ready", "tool", "discovery_done", "started", "result", "diagnostic", "closed", "fatal", "control_result"}):
            raise ValueError("MCP_IPC_ERROR")
        return value

    async def aclose(self):
        if self._closing is None:
            self._closing = asyncio.create_task(self._close())
        await asyncio.shield(self._closing)

    async def _close(self):
        p = self.process
        if p is None:
            return
        if p.stdin:
            p.stdin.close()
        failure = None
        deadline = asyncio.get_running_loop().time() + 2
        if self.job:
            try:
                if not self.job.api.TerminateJobObject(self.job.handle, 1):
                    raise OSError("MCP_JOB_TERMINATE")
                async with asyncio.timeout_at(deadline):
                    while self.job.active_processes():
                        await asyncio.sleep(0.01)
            except (OSError, TimeoutError) as exc:
                failure = exc
            finally:
                try:
                    self.job.close()
                except OSError as exc:
                    failure = exc
                self.job = None
        else:
            # SDK stdio children may create their own process groups. Capture descendants
            # while their ancestor is still alive; never kill an unverified recycled PID.
            self.observe_descendants()
            current = _posix_process_table()
            for pid, birth in self._descendants.items():
                if current.get(pid, (None, None))[1] == birth:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            if p.returncode is None:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            try:
                async with asyncio.timeout_at(deadline):
                    while any(_posix_process_table().get(pid, (None, None))[1] == birth
                              for pid, birth in self._descendants.items()):
                        await asyncio.sleep(0.01)
            except (OSError, TimeoutError) as exc:
                failure = exc
        try:
            if p.returncode is None:
                try:
                    p.kill()
                except ProcessLookupError:
                    pass
            async with asyncio.timeout_at(deadline):
                await p.wait()
        except (OSError, TimeoutError) as exc:
            failure = exc
        finally:
            # Close pipe handles even if OS exit confirmation exhausted the shared budget.
            p._transport.close()
        if self._drain:
            try:
                async with asyncio.timeout_at(deadline):
                    await self._drain
            except (OSError, TimeoutError) as exc:
                failure = exc
            finally:
                if not self._drain.done():
                    self._drain.cancel()
                await asyncio.gather(self._drain, return_exceptions=True)
        if failure:
            raise failure

    def observe_descendants(self):
        if os.name == "nt" or self.process is None:
            return
        table = _posix_process_table()
        parents = {self.process.pid} | {pid for pid, birth in self._descendants.items()
                                       if table.get(pid, (None, None))[1] == birth}
        while True:
            found = {pid for pid, (ppid, _) in table.items() if ppid in parents and pid not in parents}
            if not found:
                break
            self._descendants.update({pid: table[pid][1] for pid in found})
            parents.update(found)


def _posix_process_table():
    result = {}
    if sys.platform.startswith("linux"):
        from pathlib import Path
        for path in Path("/proc").iterdir():
            if path.name.isdigit():
                try:
                    raw = (path / "stat").read_text()
                    values = raw[raw.rindex(")") + 2:].split()
                    if values[0] == "Z":
                        continue  # Exited zombie is not a continuing owned process.
                    result[int(path.name)] = (int(values[1]), values[19])
                except (OSError, ValueError, IndexError):
                    continue
    else:
        response = subprocess.run(["/bin/ps", "-axo", "pid=,ppid=,lstart="], capture_output=True, timeout=0.5)
        if response.returncode:
            raise OSError("MCP_PROCESS_OWNERSHIP")
        for line in response.stdout.decode().splitlines():
            fields = line.split(maxsplit=2)
            if len(fields) == 3:
                result[int(fields[0])] = (int(fields[1]), fields[2])
    return result


ManagedMcpHost = OwnedProcess
