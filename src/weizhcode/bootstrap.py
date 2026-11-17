import asyncio
from pathlib import Path
from uuid import uuid4

from weizhcode.mcp.control import McpControl
from weizhcode.mcp.contracts import AuthorizedServers
from weizhcode.mcp.manager import McpManager
from weizhcode.mcp.startup import StartupTrustPrompt, request_for
from weizhcode.redaction import Redactor
from weizhcode.permissions.sandbox import make_root, verify_root


class ApplicationBootstrap:
    def __init__(self, root, home, redactor):
        self.root, self.home = Path(root).resolve(), Path(home).resolve()
        self.root_identity = make_root(root)
        self.redactor = redactor
        self.manager = None
        self.authorized = AuthorizedServers()
        self.notices = []

    def prepare(self, prompt=None):
        # No SDK connection/Future crosses this short configuration loop.
        control = McpControl(self.root, self.home)
        control.root_identity = self.root_identity
        verify_root(self.root_identity)
        async def inspect():
            try:
                config = await control.load()
                trusted = await control.inspect([c for c in config.servers if c.source == "project"])
                return config, trusted
            finally:
                await control.aclose()
        config, trusted = asyncio.run(inspect())
        self.redactor = Redactor((*self.redactor.secrets, *config.secret_values))
        self.manager = McpManager(self.root, self.redactor)
        self.manager.root_identity = self.root_identity
        verify_root(self.root_identity)
        prompt = prompt or StartupTrustPrompt(self.redactor)
        startup_id = uuid4().hex
        tickets = []
        self.notices.extend(f"MCP配置提示: {w.source} {w.server_name} {w.code} {w.variable}" for w in config.warnings)
        for server in config.servers:
            verify_root(self.root_identity)
            allowed = server.source == "user" or server.name in trusted
            if not allowed:
                allowed = prompt.choose(request_for(server, self.redactor, startup_id)) == "trust"
                verify_root(self.root_identity)
                if allowed:
                    result = asyncio.run(control.remember(server))
                    if result.committed is None:
                        self.notices.append(f"MCP {server.name}: 信任保存结果未知，未启动")
                        allowed = False
                    elif not result.saved:
                        self.notices.append(f"MCP {server.name}: 仅本次启动信任，未记住；请检查Git忽略与本地文件")
            if allowed:
                tickets.append(self.manager.authorize(server))
        self.authorized = AuthorizedServers(tickets)
        return self

    async def start(self, registry, permissions):
        await self.manager.start(self.authorized, cancel=asyncio.Event(), report=self.notices.append)
        for tool in self.manager.tools:
            registry.register_external(tool, tool.identity)
        permissions.external_identity = registry.external_identity
        return self.manager
