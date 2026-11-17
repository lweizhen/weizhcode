"""Loopback-only MCP HTTP fixture. Authentication values are synthetic."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading


@contextmanager
def local_http(*, sse=False):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.server.gets += 1
            self.send_response(405)
            self.end_headers()

        def do_DELETE(self):
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.server.requests.append((payload, dict(self.headers)))
            if "id" not in payload:
                self.send_response(202)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            method = payload["method"]
            if method == "initialize":
                result = {"protocolVersion": payload["params"]["protocolVersion"], "capabilities": {"tools": {}},
                          "serverInfo": {"name": "local-http-fixture", "version": "1"}}
            elif method == "tools/list":
                result = {"tools": [{"name": "echo", "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}}}]}
            else:
                result = {"content": [{"type": "text", "text": payload["params"]["arguments"]["text"]}]}
            response = json.dumps({"jsonrpc": "2.0", "id": payload["id"], "result": result})
            raw = (f"event: message\ndata: {response}\n\n" if sse else response).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream" if sse else "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    server.requests, server.gets = [], 0
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/mcp", server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
