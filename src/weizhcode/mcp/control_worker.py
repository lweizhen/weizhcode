import json
import sys
import re
from dataclasses import asdict
from pathlib import Path

from .config import parse_config_layers
from .contracts import McpServerConfig, valid_server_name
from .limits import MAX_IPC_BYTES
from .trust import inspect_trust, read_bytes, remember
from weizhcode.permissions.sandbox import verify_root
from weizhcode.permissions.types import RootIdentity, PermissionFailure


def main():
    raw = sys.stdin.buffer.readline(MAX_IPC_BYTES + 1)
    request = json.loads(raw)
    response = {"version": 1, "host_id": request["host_id"], "request_id": request["request_id"], "type": "control_result"}
    action = request["action"]
    try:
        if (len(raw) > MAX_IPC_BYTES or request.get("version") != 1 or request.get("type") != "control"
                or not all(isinstance(request.get(k), str) and re.fullmatch(r"[a-f0-9]{32}", request[k]) for k in ("host_id", "request_id"))
                or action not in {"load_config", "inspect_trust", "remember_trust"}):
            raise ValueError()
        root, home = Path(request["root"]), Path(request["home"])
        if root.resolve(strict=True) != root or home.resolve() != home:
            raise ValueError()
        identity = RootIdentity(**request["root_identity"])
        if identity.canonical_root != str(root):
            raise ValueError()
        verify_root(identity)
        if action == "load_config":
            layers, notices = [], []
            for source, base in (("user", home), ("project", root)):
                try:
                    layers.append(read_bytes(base, ".weizhcode/mcp.yaml"))
                except (OSError, ValueError):
                    layers.append(None)
                    notices.append({"source": source, "code": "MCP_CONFIG_UNREADABLE", "server_name": "", "variable": ""})
            value = asdict(parse_config_layers(*layers, environ=request["environ"]))
            value["warnings"] = [*value["warnings"], *notices]
            response["result"] = value
        else:
            configs = [McpServerConfig(**v) for v in request["configs"]]
            if action == "inspect_trust":
                response["result"] = {"trusted": inspect_trust(root, home, configs)}
            else:
                if len(configs) != 1 or not valid_server_name(configs[0].name):
                    raise ValueError()
                remember(root, home, configs[0])
                response["result"] = {"saved": True, "committed": True, "code": ""}
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, PermissionFailure):
        response["result"] = ({"saved": False, "committed": False, "code": "MCP_TRUST_NOT_SAVED"}
                              if action == "remember_trust" else {"trusted": [], "code": "MCP_CONTROL_INVALID"})
    encoded = json.dumps(response, ensure_ascii=False).encode()
    if len(encoded) > MAX_IPC_BYTES:
        response = {k: v for k, v in response.items() if k != "result"}
        response["result"] = {"code": "MCP_CONTROL_LIMIT"}
    print(json.dumps(response, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
