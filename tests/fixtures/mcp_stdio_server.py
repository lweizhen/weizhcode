"""Local protocol fixture, never production configuration. No filesystem tools."""
import json
import sys
import time
import os
import subprocess

children = []


def respond(message):
    kind = message.get("method")
    if "id" not in message:
        return None
    if kind == "initialize":
        if "--slow-init" in sys.argv:
            time.sleep(60)
        result = {"protocolVersion": message["params"]["protocolVersion"], "capabilities": {"tools": {}},
                  "serverInfo": {"name": "offline-fixture", "version": "1"}}
        if "--grandchild" in sys.argv:
            children.append(subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"],
                                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        if "--unsupported-version" in sys.argv:
            result["protocolVersion"] = "1900-01-01"
    elif kind == "tools/list":
        if "--diagnostics" in sys.argv:
            sys.stderr.write("synthetic-" )
            sys.stderr.flush()
            sys.stderr.write("token-731\x1b[31m\x00" + "x" * 100000)
            sys.stderr.flush()
        result = {"tools": [{"name": "echo", "description": "Echo local test text", "annotations": {"readOnlyHint": True},
                             "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}]}
        if "--duplicate" in sys.argv:
            result["tools"] *= 2
        if "--bad-schema" in sys.argv:
            result["tools"].append({"name": "bad", "inputSchema": {"type": "object", "$ref": "https://example.invalid/schema"}})
        if "--pages" in sys.argv:
            if message.get("params", {}).get("cursor"):
                result["tools"][0]["name"] = "second"
            else:
                result["nextCursor"] = "page2"
        if "--repeat-cursor" in sys.argv:
            result["nextCursor"] = "repeated"
        if "--empty" in sys.argv:
            result["tools"] = []
        for flag, count, length in (("--tools-max", 256, 0), ("--tools-over", 257, 0), ("--directory-over", 256, 8500)):
            if flag in sys.argv:
                result["tools"] = [{"name": f"t{i:03}", "description": "x" * length, "inputSchema": {"type": "object"}} for i in range(count)]
        for flag, limit in (("--pages-max", 64), ("--pages-over", 65)):
            if flag in sys.argv:
                page = int(message.get("params", {}).get("cursor", "0"))
                result["tools"][0]["name"] = f"t{page:03}"
                if page + 1 < limit:
                    result["nextCursor"] = str(page + 1)
        for flag, length in (("--cursor-max", 4096), ("--cursor-over", 4097)):
            if flag in sys.argv:
                if message.get("params", {}).get("cursor"):
                    result["tools"][0]["name"] = "second"
                else:
                    result["nextCursor"] = "x" * length
    elif kind == "tools/call":
        text = message["params"].get("arguments", {}).get("text", "")
        if text == "pid":
            text = str(os.getpid())
        if text == "environment":
            text = json.dumps({"provider": os.environ.get("SYNTHETIC_PROVIDER_KEY"), "explicit": os.environ.get("EXPLICIT"), "cwd": os.getcwd()})
        if text == "children":
            text = json.dumps([os.getpid(), *(p.pid for p in children)])
        if text == "slow":
            time.sleep(60)
        if text == 'large' and '--context-large' in sys.argv:
            text = 'x'*80000
        result = {"content": [{"type": "text", "text": text}], "isError": text == "error"}
    else:
        return {"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32601, "message": "Unsupported"}}
    return {"jsonrpc": "2.0", "id": message["id"], "result": result}


if __name__ == "__main__":
    for line in sys.stdin:
        response = respond(json.loads(line))
        if response:
            print(json.dumps(response), flush=True)
