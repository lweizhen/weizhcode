import asyncio
import hashlib
import hmac
import os
from collections import Counter
from dataclasses import asdict
from uuid import uuid4

from weizhcode.models import ToolResult
from weizhcode.redaction import Redactor
from .contracts import McpDiscovery, McpStatusSnapshot, ServerStatus, ShutdownReport, StartupTicket
from .process import OwnedProcess
from .tool import McpToolAdapter
from .trust import encode


class McpManager:
    def __init__(self, root, redactor=None, *, startup_timeout=30, call_timeout=30):
        self.root, self.redactor = root, redactor or Redactor()
        from weizhcode.permissions.sandbox import make_root
        self.root_identity = make_root(root)
        self.generation = uuid4().hex
        self.startup_timeout, self.call_timeout = startup_timeout, call_timeout
        self.hosts, self.states, self.tools = {}, {}, []
        self._close_task = None
        self._ticket_key = os.urandom(32)
        self._started = False
        self._busy = set()
        self._uncertain = set()
        self._report = lambda text: None
        self._diagnostic_counts = {}

    def authorize(self, config):
        """Application bootstrap calls only after a trusted source or a real choice."""
        from weizhcode.permissions.sandbox import verify_root
        verify_root(self.root_identity)
        body = encode([self.generation, asdict(self.root_identity), asdict(config)])
        return StartupTicket(config, self.generation, hmac.new(self._ticket_key, body, hashlib.sha256).hexdigest())

    def _valid_ticket(self, ticket):
        if not isinstance(ticket, StartupTicket) or ticket.generation != self.generation:
            return False
        return hmac.compare_digest(ticket.fingerprint, self.authorize(ticket.config).fingerprint)

    def _diagnostic(self, server, value):
        count = self._diagnostic_counts.get(server, 0)
        if count < 16 and isinstance(value.get("text"), str):
            self._diagnostic_counts[server] = count + 1
            self._report(f"MCP {server} 诊断（非指令）: {self.redactor.display(value['text'])[:2048]}")

    async def start(self, authorized, *, cancel, report=lambda text: None):
        if self._started or self._close_task:
            raise RuntimeError("MCP manager is startup-only")
        self._started = True
        self._report = report
        async def connect(ticket):
            cfg = ticket.config
            if not self._valid_ticket(ticket) or cancel.is_set():
                report("MCP: 无效或取消的启动授权，未创建Host")
                return []
            host = OwnedProcess("weizhcode.mcp.host_worker")
            self.hosts[cfg.name] = host
            self.states[cfg.name] = ServerStatus(cfg.name, "connecting")
            specs = []
            try:
                async with asyncio.timeout(self.startup_timeout):
                    if ticket.generation != self.generation or cancel.is_set():
                        raise ValueError("MCP_STARTUP_AUTHORIZATION")
                    from weizhcode.permissions.sandbox import verify_root
                    verify_root(self.root_identity)
                    await host.start()
                    request_id = uuid4().hex
                    await host.send("connect", request_id=request_id, root=str(self.root), config=asdict(cfg),
                                    secrets=list(self.redactor.secrets))
                    while True:
                        value = await host.receive()
                        if value["type"] == "diagnostic":
                            self._diagnostic(cfg.name, value)
                            continue
                        if value.get("request_id") != request_id:
                            raise ValueError("MCP_IPC_ID")
                        if value["type"] == "discovery_done":
                            break
                        if value["type"] != "tool":
                            raise ValueError("MCP_DISCOVERY_FAILED")
                        specs.append(value["tool"])
                host.observe_descendants()
                self.states[cfg.name] = ServerStatus(cfg.name, "ready")
                return [(cfg.name, s) for s in specs]
            except BaseException as exc:
                try:
                    await host.aclose()
                except Exception:
                    self._uncertain.add(cfg.name)
                    report(f"MCP {cfg.name}: 无法确认自有进程已清理，请检查；未继续连接")
                self.states[cfg.name] = ServerStatus(cfg.name, "unavailable", code="MCP_CONNECTION_FAILED")
                report(f"MCP {cfg.name}: 连接失败或超时，已跳过")
                if isinstance(exc, asyncio.CancelledError):
                    raise
                return []
        if len(authorized.tickets) > 16 or len({t.config.name for t in authorized.tickets}) != len(authorized.tickets):
            raise ValueError("MCP_STARTUP_TICKET_SET")
        jobs = [asyncio.create_task(connect(t)) for t in authorized.tickets]
        collection = asyncio.gather(*jobs)
        interrupted = asyncio.create_task(cancel.wait())
        try:
            done, _ = await asyncio.wait((collection, interrupted), return_when=asyncio.FIRST_COMPLETED)
            if interrupted in done and cancel.is_set():
                raise asyncio.CancelledError()
            lists = await collection
        except BaseException:
            for job in jobs:
                job.cancel()
            await asyncio.gather(*jobs, return_exceptions=True)
            await self.aclose()
            raise
        finally:
            interrupted.cancel()
            await asyncio.gather(interrupted, return_exceptions=True)
            # Retrieve the gather outcome even when cancellation selected the other branch.
            if not collection.done():
                collection.cancel()
            await asyncio.gather(collection, return_exceptions=True)
        candidates = [item for group in lists for item in group]
        names = Counter(f"mcp__{server}__{spec.get('name')}" for server, spec in candidates)
        for server, spec in sorted(candidates, key=lambda p: (p[0], str(p[1].get("name")))):
            try:
                name = f"mcp__{server}__{spec['name']}"
                if names[name] > 1 or len(self.tools) >= 256:
                    raise ValueError()
                self.tools.append(McpToolAdapter(self, server, spec))
            except Exception:
                report(f"MCP {server}: 已跳过一个不支持或冲突的工具")
        for name, state in list(self.states.items()):
            if state.state == "ready":
                self.states[name] = ServerStatus(name, "ready", sum(t.identity.server_name == name for t in self.tools))
        return McpDiscovery(tuple(t.definition for t in self.tools), tuple(t.identity for t in self.tools), self.snapshot())

    def identity(self, name):
        return next((t.identity for t in self.tools if t.definition.name == name), None)

    def snapshot(self):
        for name, host in self.hosts.items():
            if (self.states[name].state == "ready" and host.process is not None
                    and host.process.returncode is not None):
                self.states[name] = ServerStatus(name, "unavailable", code="MCP_TRANSPORT_ERROR")
        return McpStatusSnapshot(tuple(self.states.values()), len(self.tools))

    async def call(self, identity, call, *, cancel, execution_started):
        if identity.server_name in self._busy:
            return ToolResult.failure(call, "MCP_BUSY", "同一MCP连接已有调用，未发送本次请求")
        self._busy.add(identity.server_name)
        self._diagnostic_counts[identity.server_name] = 0
        try:
            return await self._call(identity, call, cancel=cancel, execution_started=execution_started)
        finally:
            self._busy.discard(identity.server_name)

    async def _call(self, identity, call, *, cancel, execution_started):
        state = self.states.get(identity.server_name)
        if self._close_task or identity != self.identity(call.name) or state is None or state.state != "ready":
            return ToolResult.failure(call, "MCP_UNAVAILABLE", "MCP连接不可用，未自动重连")
        host = self.hosts[identity.server_name]
        request_id = uuid4().hex
        async def operation():
            async with asyncio.timeout(self.call_timeout):
                if cancel.is_set():
                    raise asyncio.CancelledError()
                execution_started()
                host.observe_descendants()
                await host.send("call", request_id=request_id, remote_name=identity.remote_name, full_name=identity.full_name,
                                call_id=call.call_id, arguments=call.arguments)
                while True:
                    value = await host.receive()
                    if value["type"] == "diagnostic":
                        self._diagnostic(identity.server_name, value)
                        continue
                    if value.get("request_id") != request_id:
                        raise ValueError("MCP_IPC_ID")
                    if value["type"] == "started":
                        continue
                    if value["type"] != "result":
                        raise ConnectionError()
                    return ToolResult(**value["result"])
        work = asyncio.create_task(operation())
        cancellation = asyncio.create_task(cancel.wait())
        code = None
        confirmed = None
        try:
            done, _ = await asyncio.wait((work, cancellation), return_when=asyncio.FIRST_COMPLETED)
            if work in done:
                return await work
            code = "TOOL_CANCELLED"
        except asyncio.CancelledError:
            code = "TOOL_CANCELLED"
        except TimeoutError:
            code = "TOOL_TIMEOUT"
        except Exception:
            code = "MCP_TRANSPORT_ERROR"
        finally:
            cancellation.cancel()
            if code:
                work.cancel()
                await asyncio.gather(work, return_exceptions=True)
                try:
                    async with asyncio.timeout(1):
                        await host.send("cancel", request_id=request_id)
                        while True:
                            response = await host.receive()
                            if response.get("request_id") != request_id:
                                raise ValueError("MCP_IPC_ID")
                            if response["type"] == "result":
                                candidate = ToolResult(**response["result"])
                                if candidate.status == "success":
                                    confirmed = candidate
                                break
                except Exception:
                    pass
                try:
                    await host.aclose()
                except Exception:
                    self._uncertain.add(identity.server_name)
                    self._report(f"MCP {identity.server_name}: 无法确认自有进程已清理，远端副作用可能保留")
                self.states[identity.server_name] = ServerStatus(identity.server_name, "unavailable", code=code)
            await asyncio.gather(cancellation, return_exceptions=True)
        return confirmed or ToolResult.failure(call, code, "MCP调用已停止或失败；远端副作用可能保留，未自动重试")

    async def aclose(self):
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._close())
        return await asyncio.shield(self._close_task)

    async def _close(self):
        uncertain, forced = set(self._uncertain), []
        deadline = asyncio.get_running_loop().time() + 5
        async def close(name, host):
            try:
                async with asyncio.timeout_at(deadline):
                    await host.send("close", request_id=uuid4().hex)
                    while (await host.receive())["type"] != "closed":
                        pass
            except Exception:
                forced.append(name)
            try:
                await host.aclose()
            except Exception:
                uncertain.add(name)
            self.states[name] = ServerStatus(name, "closed")
        await asyncio.gather(*(close(name, host) for name, host in self.hosts.items()))
        return ShutdownReport(not uncertain, tuple(sorted(uncertain)), tuple(sorted(forced)))
