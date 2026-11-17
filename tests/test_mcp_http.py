import asyncio
import json

import httpx
import pytest

from fixtures.mcp_http_server import local_http
from test_mcp_manager import start
from weizhcode.mcp.contracts import McpServerConfig
from weizhcode.mcp.http import McpHttpTransport
from weizhcode.models import ToolCall


@pytest.mark.parametrize("sse", [False, True])
async def test_fixture_http_native_handshake_response_forms(tmp_path, sse):
    with local_http(sse=sse) as (url, server):
        config = McpServerConfig("remote", "user", "http", url=url, headers_json='{"Authorization":"Bearer synthetic-only"}')
        manager = await start(tmp_path, config)
        try:
            assert len(manager.tools) == 1, manager.snapshot()
            call = ToolCall("id", "mcp__remote__echo", "{}", {"text": "http-native"})
            result = await manager.call(manager.identity(call.name), call, cancel=asyncio.Event(), execution_started=lambda: None)
            assert result.content == "http-native" and not result.is_error
            assert server.gets == 0
            assert all(h.get("Authorization") == "Bearer synthetic-only" for _, h in server.requests)
            methods = [p.get("method") for p, _ in server.requests]
            assert methods.count("initialize") == 1 and methods.count("tools/call") == 1
        finally:
            assert (await manager.aclose()).clean


async def test_origin_no_replay():
    requests = []
    async def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"ok": True})
    transport = McpHttpTransport("https://example.test/mcp", httpx.MockTransport(handle))
    async with httpx.AsyncClient(transport=transport) as client:
        assert (await client.get("https://example.test/mcp")).status_code == 405
        with pytest.raises(ValueError):
            await client.post("https://other.test/mcp", json={"id": 1, "method": "tools/call"})
        await client.post("https://example.test/mcp", json={"id": 1, "method": "tools/call"})
        with pytest.raises(ValueError):
            await client.post("https://example.test/mcp", json={"id": 1, "method": "tools/call"})
    assert len(requests) == 1


@pytest.mark.parametrize("compressed", [False, True])
async def test_mcp_budget_decoded_http_stream(compressed):
    import gzip
    from weizhcode.mcp.limits import MAX_HTTP_RESPONSE_BYTES
    closed = []
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            raw = b"x" * (MAX_HTTP_RESPONSE_BYTES + 1)
            raw = gzip.compress(raw) if compressed else raw
            for index in range(0, len(raw), 4096):
                yield raw[index:index + 4096]
        async def aclose(self):
            closed.append(True)
    async def handle(request):
        return httpx.Response(200, headers={"Content-Encoding": "gzip"} if compressed else {}, stream=Stream())
    async with httpx.AsyncClient(transport=McpHttpTransport("https://example.test/mcp", httpx.MockTransport(handle))) as client:
        with pytest.raises(ValueError, match="MCP_HTTP_LIMIT"):
            await client.post("https://example.test/mcp", json={"id": 1, "method": "tools/call"})
    assert closed


async def test_http_redirect_same_origin_once_cross_origin_never_forwarded():
    seen = []
    async def handle(request):
        seen.append(str(request.url))
        if request.url.path == "/mcp":
            return httpx.Response(307, headers={"Location": "/next"})
        return httpx.Response(200, json={"ok": True})
    async with httpx.AsyncClient(transport=McpHttpTransport("https://example.test/mcp", httpx.MockTransport(handle)), follow_redirects=True) as client:
        await client.post("https://example.test/mcp", headers={"Authorization": "Bearer synthetic"}, json={"id": 1, "method": "tools/call"})
        with pytest.raises(ValueError, match="MCP_HTTP_REPLAY"):
            await client.post("https://example.test/mcp", json={"id": 1, "method": "tools/call"})
    assert seen == ["https://example.test/mcp", "https://example.test/next"]
    async def cross(request):
        return httpx.Response(307, headers={"Location": "https://other.test/mcp"})
    async with httpx.AsyncClient(transport=McpHttpTransport("https://example.test/mcp", httpx.MockTransport(cross)), follow_redirects=True) as client:
        with pytest.raises(ValueError, match="MCP_HTTP_ORIGIN"):
            await client.post("https://example.test/mcp", json={"id": 2, "method": "tools/call"})
