from __future__ import annotations

from dataclasses import dataclass, field
import json
import re


SERVER_NAME = re.compile(r"[A-Za-z0-9_-]{1,32}\Z")
TOOL_NAME = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


def valid_server_name(value):
    return isinstance(value, str) and bool(SERVER_NAME.fullmatch(value)) and "__" not in value


def _string_map(raw):
    data = json.loads(raw)
    if type(data) is not dict or any(type(k) is not str or type(v) is not str for k, v in data.items()):
        raise ValueError("Invalid MCP string map")
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class McpWarning:
    source: str
    code: str
    server_name: str = ""
    variable: str = ""


@dataclass(frozen=True)
class McpServerConfig:
    name: str
    source: str
    transport: str
    command: str = field(default="", repr=False)
    args: tuple[str, ...] = field(default=(), repr=False)
    env_json: str = field(default="{}", repr=False)
    url: str = field(default="", repr=False)
    headers_json: str = field(default="{}", repr=False)

    def __post_init__(self):
        if not valid_server_name(self.name) or self.source not in {"user", "project"} or self.transport not in {"stdio", "http"}:
            raise ValueError("Invalid MCP server contract")
        object.__setattr__(self, "args", tuple(self.args))
        if any(type(a) is not str for a in self.args):
            raise ValueError("Invalid MCP arguments")
        object.__setattr__(self, "env_json", _string_map(self.env_json))
        object.__setattr__(self, "headers_json", _string_map(self.headers_json))

    @property
    def env(self):
        return json.loads(self.env_json)

    @property
    def headers(self):
        return json.loads(self.headers_json)


@dataclass(frozen=True)
class McpConfigSnapshot:
    servers: tuple[McpServerConfig, ...] = ()
    warnings: tuple[McpWarning, ...] = ()
    secret_values: tuple[str, ...] = field(default=(), repr=False)

    def __post_init__(self):
        for key in ("servers", "warnings", "secret_values"):
            object.__setattr__(self, key, tuple(getattr(self, key)))


@dataclass(frozen=True)
class McpToolIdentity:
    full_name: str
    server_name: str
    remote_name: str
    generation: str

    def __post_init__(self):
        if (not valid_server_name(self.server_name) or not TOOL_NAME.fullmatch(self.remote_name)
                or "__" in self.remote_name or not TOOL_NAME.fullmatch(self.full_name)
                or self.full_name != f"mcp__{self.server_name}__{self.remote_name}"
                or not re.fullmatch(r"[a-f0-9]{32}", self.generation)):
            raise ValueError("Invalid MCP tool identity")


@dataclass(frozen=True)
class ServerStatus:
    name: str
    state: str
    tool_count: int = 0
    code: str = ""

    def __post_init__(self):
        if (not valid_server_name(self.name) or self.state not in
                {"created", "skipped", "connecting", "ready", "unavailable", "closing", "closed"}
                or type(self.tool_count) is not int or self.tool_count < 0):
            raise ValueError("Invalid MCP status")


@dataclass(frozen=True)
class McpStatusSnapshot:
    servers: tuple[ServerStatus, ...] = ()
    registered_tools: int = 0

    def __post_init__(self):
        object.__setattr__(self, "servers", tuple(self.servers))
        if type(self.registered_tools) is not int or self.registered_tools < 0:
            raise ValueError("Invalid MCP tool count")


@dataclass(frozen=True)
class McpDiscovery:
    definitions: tuple = ()
    identities: tuple[McpToolIdentity, ...] = ()
    status: McpStatusSnapshot = field(default_factory=McpStatusSnapshot)

    def __post_init__(self):
        from copy import deepcopy
        object.__setattr__(self, "definitions", tuple(deepcopy(self.definitions)))
        object.__setattr__(self, "identities", tuple(self.identities))


@dataclass(frozen=True)
class TrustRequest:
    startup_id: str
    approval_id: str
    server_name: str
    preview: str
    scope_hint: str


@dataclass(frozen=True)
class StartupTicket:
    config: McpServerConfig = field(repr=False)
    generation: str
    fingerprint: str = field(repr=False)


@dataclass(frozen=True)
class AuthorizedServers:
    tickets: tuple[StartupTicket, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "tickets", tuple(self.tickets))


@dataclass(frozen=True)
class TrustSnapshot:
    trusted_names: tuple[str, ...] = ()
    warnings: tuple[McpWarning, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "trusted_names", tuple(self.trusted_names))
        object.__setattr__(self, "warnings", tuple(self.warnings))


@dataclass(frozen=True)
class TrustSaveResult:
    saved: bool = False
    committed: bool | None = False
    code: str = ""


@dataclass(frozen=True)
class ShutdownReport:
    clean: bool
    unconfirmed_servers: tuple[str, ...] = ()
    forced_servers: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "unconfirmed_servers", tuple(self.unconfirmed_servers))
        object.__setattr__(self, "forced_servers", tuple(self.forced_servers))
