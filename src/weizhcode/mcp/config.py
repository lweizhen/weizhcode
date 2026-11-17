"""Pure MCP configuration parsing. Production file I/O belongs to ControlWorker."""
from __future__ import annotations

import json
import os
import re
import shutil
from urllib.parse import urlsplit, parse_qsl

from weizhcode.yaml_utils import SafeYamlError, load_mapping
from .contracts import McpConfigSnapshot, McpServerConfig, McpWarning, valid_server_name
from .limits import MAX_CONFIG_BYTES, MAX_CONFIG_ITEMS, MAX_EXPANDED_BYTES, MAX_FIELD_CHARS, MAX_SERVERS

ENV_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
ENV_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
HEADER_KEY = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+\Z")
PROTECTED_HEADERS = {"host", "content-length", "content-type", "accept", "mcp-session-id",
                     "mcp-protocol-version", "mcp-method", "mcp-name", "last-event-id", "transfer-encoding"}


def _field(value):
    if type(value) is not str or len(value) > MAX_FIELD_CHARS or "\0" in value:
        raise ValueError()
    return value


def _map(value, *, headers=False):
    if type(value) is not dict or len(value) > MAX_CONFIG_ITEMS:
        raise ValueError()
    out = {}
    for key, item in value.items():
        _field(key)
        _field(item)
        if headers:
            key = key.lower()
            if (not HEADER_KEY.fullmatch(key) or key in out or key in PROTECTED_HEADERS
                    or "\r" in item or "\n" in item):
                raise ValueError()
        elif not ENV_KEY.fullmatch(key):
            raise ValueError()
        out[key] = item
    return out


def _expand(values, environ):
    missing = set()
    out = {}
    for key, value in values.items():
        def replace(match):
            name = match[1]
            if name not in environ:
                missing.add(name)
                return ""
            return environ[name]
        out[key] = ENV_REF.sub(replace, value)
    return out, missing


def _server(name, source, raw, environ):
    if not valid_server_name(name) or type(raw) is not dict:
        raise ValueError()
    kind = raw.get("type")
    allowed = {"type", "command", "args", "env"} if kind == "stdio" else {"type", "url", "headers"}
    if kind not in {"stdio", "http"} or set(raw) - allowed:
        raise ValueError()
    command = url = ""
    args = ()
    if kind == "stdio":
        command = _field(raw.get("command"))
        if not command.strip():
            raise ValueError()
        argv = raw.get("args", [])
        if type(argv) is not list or len(argv) > MAX_CONFIG_ITEMS:
            raise ValueError()
        args = tuple(_field(v) for v in argv)
        values = _map(raw.get("env", {}))
    else:
        url = _field(raw.get("url"))
        parsed = urlsplit(url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.fragment or any(ord(c) <= 32 or ord(c) == 127 for c in url)):
            raise ValueError()
        _ = parsed.port  # Raises on malformed/out-of-range ports.
        values = _map(raw.get("headers", {}), headers=True)
    expanded, missing = _expand(values, environ)
    if missing:
        return None, tuple(McpWarning(source, "MCP_ENV_UNDEFINED", name, v) for v in sorted(missing))
    expanded = _map(expanded, headers=kind == "http")
    if kind == "stdio" and os.name == "nt":
        resolved = shutil.which(command, path=expanded.get("PATH", environ.get("PATH", "")))
        if command.lower().endswith((".cmd", ".bat")) or (resolved and resolved.lower().endswith((".cmd", ".bat"))):
            raise ValueError()
    encoded = json.dumps(expanded, ensure_ascii=False, sort_keys=True)
    return McpServerConfig(name, source, kind, command, args,
                           encoded if kind == "stdio" else "{}", url,
                           encoded if kind == "http" else "{}"), ()


def parse_config_layers(user: bytes | None, project: bytes | None, *, environ=None):
    """Parse already bounded file snapshots; no server, filesystem or network side effects."""
    environ = dict(os.environ if environ is None else environ)
    merged, warnings = {}, []
    for source, raw in (("user", user), ("project", project)):
        if raw is None:
            continue
        try:
            data = load_mapping(raw, max_bytes=MAX_CONFIG_BYTES)
            block = data.get("mcp_servers")
            if set(data) - {"mcp_servers"} or (block is not None and type(block) is not dict):
                raise SafeYamlError("invalid")
            for name, config in (block or {}).items():
                merged[name] = (source, config)
        except SafeYamlError as exc:
            warnings.append(McpWarning(source, "MCP_CONFIG_LIMIT" if exc.kind == "limit" else "MCP_CONFIG_INVALID"))
    servers, secrets = [], set()
    expanded_size = 0
    for name, (source, raw) in sorted(merged.items()):
        # Collect known credentials even from invalid definitions; never echo their raw values.
        if type(raw) is dict:
            if isinstance(raw.get("url"), str):
                try:
                    secrets.update(value for _, value in parse_qsl(urlsplit(raw["url"]).query) if value)
                except ValueError:
                    pass
            for field in ("env", "headers"):
                if type(raw.get(field)) is dict:
                    for value in raw[field].values():
                        if type(value) is str:
                            secrets.add(value)
                            for match in ENV_REF.finditer(value):
                                if type(environ.get(match[1])) is str:
                                    secrets.add(environ[match[1]])
                            if value.lower().startswith("bearer "):
                                secrets.add(value[7:])
        try:
            server, notices = _server(name, source, raw, environ)
            warnings.extend(notices)
            if server is None:
                continue
            for value in (*server.env.values(), *server.headers.values()):
                secrets.add(value)
                if value.lower().startswith("bearer "):
                    secrets.add(value[7:])
            size = len(json.dumps([server.command, server.args, server.env, server.url, server.headers],
                                   ensure_ascii=False).encode("utf-8"))
            if len(servers) >= MAX_SERVERS or expanded_size + size > MAX_EXPANDED_BYTES:
                warnings.append(McpWarning(source, "MCP_CONFIG_LIMIT", name))
                continue
            expanded_size += size
            servers.append(server)
        except (ValueError, TypeError, OverflowError):
            warnings.append(McpWarning(source, "MCP_SERVER_INVALID", name if valid_server_name(name) else ""))
    return McpConfigSnapshot(servers, warnings, sorted(secrets - {""}, key=lambda s: (-len(s), s)))
