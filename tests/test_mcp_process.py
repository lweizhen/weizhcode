import importlib.metadata
import inspect

import pytest


def test_sdk_contract():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamable_http_client
    from mcp.shared.version import SUPPORTED_PROTOCOL_VERSIONS
    from weizhcode.mcp.limits import SUPPORTED_PROTOCOLS
    assert importlib.metadata.version("mcp") == "1.30.0"
    assert frozenset(SUPPORTED_PROTOCOL_VERSIONS) == SUPPORTED_PROTOCOLS
    assert {"cwd", "env", "args", "command"} <= StdioServerParameters.model_fields.keys()
    assert "errlog" in inspect.signature(stdio_client).parameters
    assert "http_client" in inspect.signature(streamable_http_client).parameters
    assert "cursor" in inspect.signature(ClientSession.list_tools).parameters


def test_contract_isolation():
    from weizhcode.mcp.contracts import McpServerConfig, McpConfigSnapshot, ServerStatus, ShutdownReport
    args = ["-m", "demo"]
    server = McpServerConfig("demo", "project", "stdio", "python", args, '{"TOKEN":"secret"}')
    args.clear()
    assert server.args == ("-m", "demo")
    env = server.env
    env.clear()
    assert server.env == {"TOKEN": "secret"}
    assert "secret" not in repr(server)
    source = [server]
    snapshot = McpConfigSnapshot(source, secret_values=["secret"])
    source.clear()
    assert snapshot.servers == (server,) and "secret" not in repr(snapshot)
    with pytest.raises(ValueError):
        ServerStatus("demo", "invalid")
    with pytest.raises(ValueError):
        ServerStatus("demo", "ready", True)
    forced = ["demo"]
    report = ShutdownReport(True, forced_servers=forced)
    forced.clear()
    assert report.forced_servers == ("demo",)


async def test_diagnostics_drain_redaction():
    import asyncio
    from weizhcode.mcp.diagnostics import DiagnosticCollector
    from weizhcode.redaction import Redactor
    secret = "synthetic-token-731"
    collector = DiagnosticCollector(Redactor([secret]))
    reader = asyncio.StreamReader()
    reader.feed_data(b"before synthetic-")
    reader.feed_data(b"token-731\x1b[31m after\x00")
    reader.feed_data(b"x" * 100_000)
    reader.feed_eof()
    await collector.drain(reader)
    output = "".join(collector.messages)
    assert secret not in output and "[redacted]" in output
    assert "\x1b" not in output and "\x00" not in output
    assert len(collector.messages) <= 16 and len(output.encode()) <= 16384
    assert collector.dropped_bytes > 0 and reader.at_eof()
    collector.finish()


def test_diagnostics_sdk_logging():
    import logging
    from weizhcode.mcp.diagnostics import SdkDiagnosticHandler
    output = []
    handler = SdkDiagnosticHandler(output.append)
    record = logging.LogRecord("mcp", logging.ERROR, "", 0, "secret=%s", ("raw-secret",), None)
    handler.emit(record)
    assert output == ["MCP_SDK_ERROR"]
