import asyncio
from dataclasses import asdict
import os
from pathlib import Path
from uuid import uuid4

from .contracts import McpConfigSnapshot, McpServerConfig, McpWarning, TrustSaveResult
from .process import OwnedProcess
from weizhcode.permissions.sandbox import make_root, verify_root


class McpControl:
    def __init__(self, root, home, *, timeout=5):
        self.root, self.home = Path(root).resolve(), Path(home).resolve()
        self.root_identity = make_root(root)
        self.timeout = timeout
        self.active = set()

    async def request(self, action, **data):
        worker = OwnedProcess("weizhcode.mcp.control_worker")
        self.active.add(worker)
        request_id = uuid4().hex
        try:
            async with asyncio.timeout(self.timeout):
                verify_root(self.root_identity)
                await worker.start()
                await worker.send("control", action=action, request_id=request_id,
                                  root=str(self.root), root_identity=asdict(self.root_identity), home=str(self.home), **data)
                response = await worker.receive()
                if response.get("request_id") != request_id or response["type"] != "control_result":
                    raise ValueError("MCP_CONTROL_INVALID")
                return response["result"]
        finally:
            try:
                await worker.aclose()
            finally:
                self.active.discard(worker)

    async def load(self):
        value = await self.request("load_config", environ=dict(os.environ))
        return McpConfigSnapshot(tuple(McpServerConfig(**v) for v in value["servers"]),
                                 tuple(McpWarning(**v) for v in value["warnings"]), tuple(value["secret_values"]))

    async def inspect(self, configs):
        try:
            return tuple((await self.request("inspect_trust", configs=[asdict(c) for c in configs])).get("trusted", ()))
        except (ValueError, OSError, TimeoutError):
            return ()

    async def remember(self, config):
        try:
            return TrustSaveResult(**await self.request("remember_trust", configs=[asdict(config)]))
        except (OSError, ValueError, TimeoutError):
            return TrustSaveResult(False, None, "MCP_TRUST_UNCERTAIN")

    async def aclose(self):
        await asyncio.gather(*(w.aclose() for w in tuple(self.active)))


McpTrustStore = McpControl
