import asyncio
from pathlib import Path
import sys

import pytest

from weizhcode.mcp.contracts import AuthorizedServers, McpServerConfig, StartupTicket
from weizhcode.mcp.manager import McpManager
from weizhcode.models import ToolCall


def local_config():
    fixture = Path(__file__).parent / "fixtures/mcp_stdio_server.py"
    return McpServerConfig("demo", "user", "stdio", sys.executable, (str(fixture),))


async def start(tmp_path, config=None, **kwargs):
    manager = McpManager(tmp_path, **kwargs)
    ticket = manager.authorize(config or local_config())
    await manager.start(AuthorizedServers((ticket,)), cancel=asyncio.Event())
    return manager


async def test_native_handshake_call_cache_close_budget(tmp_path):
    manager = await start(tmp_path)
    try:
        assert len(manager.tools) == 1, manager.snapshot()
        assert manager.snapshot().servers[0].state == "ready"
        pid = manager.hosts["demo"].process.pid
        request = ToolCall("pid", "mcp__demo__echo", "{}", {"text": "pid"})
        server_pid = int((await manager.call(manager.identity(request.name), request,
                                            cancel=asyncio.Event(), execution_started=lambda: None)).content)
        for text in ("hello", "second", "error", "after error"):
            call = ToolCall("id", "mcp__demo__echo", "{}", {"text": text})
            result = await manager.call(manager.identity(call.name), call, cancel=asyncio.Event(), execution_started=lambda: None)
            assert result.content == text
            assert result.is_error is (text == "error")
            assert manager.hosts["demo"].process.pid == pid
        assert not manager.tools[0].definition.read_only
    finally:
        report = await manager.aclose()
        assert report.clean
        assert manager.hosts["demo"].process.returncode is not None
        import os
        if os.name == "nt":
            import win32api, win32event
            try:
                process = win32api.OpenProcess(0x100000, False, server_pid)
            except Exception:
                process = None
            if process:
                try:
                    assert win32event.WaitForSingleObject(process, 1000) == 0
                finally:
                    process.Close()
        assert await manager.aclose() == report


async def test_native_lifecycle_timeout_no_replay(tmp_path):
    manager = await start(tmp_path, call_timeout=0.2)
    try:
        call = ToolCall("id", "mcp__demo__echo", "{}", {"text": "slow"})
        result = await manager.call(manager.identity(call.name), call, cancel=asyncio.Event(), execution_started=lambda: None)
        assert result.status == "timeout"
        pid = manager.hosts["demo"].process.pid
        result = await manager.call(manager.identity(call.name), call, cancel=asyncio.Event(), execution_started=lambda: None)
        assert result.error_code == "MCP_UNAVAILABLE"
        assert manager.hosts["demo"].process.pid == pid
    finally:
        await manager.aclose()


@pytest.mark.parametrize("flag,count,state", [("--pages", 2, "ready"), ("--duplicate", 0, "ready"),
                                              ("--bad-schema", 1, "ready"), ("--repeat-cursor", 0, "unavailable")])
async def test_discovery_directory(flag, count, state, tmp_path):
    from dataclasses import replace
    cfg = local_config()
    manager = await start(tmp_path, replace(cfg, args=(*cfg.args, flag)))
    try:
        assert len(manager.tools) == count
        assert manager.snapshot().servers[0].state == state
    finally:
        await manager.aclose()


async def test_startup_failure_isolation_native(tmp_path):
    from dataclasses import replace
    manager = McpManager(tmp_path, startup_timeout=5)
    good = local_config()
    slow = replace(good, name="slow", args=(*good.args, "--slow-init"))
    await manager.start(AuthorizedServers(tuple(manager.authorize(c) for c in (good, slow))), cancel=asyncio.Event())
    try:
        assert len(manager.tools) == 1
        assert manager.states["demo"].state == "ready" and manager.states["slow"].state == "unavailable"
        assert manager.hosts["slow"].process.returncode is not None
    finally:
        await manager.aclose()


async def test_tickets_bound_to_manager_config_and_root(tmp_path):
    from dataclasses import replace
    manager = McpManager(tmp_path)
    ticket = manager.authorize(local_config())
    forged = replace(ticket, config=replace(ticket.config, args=("different",)))
    assert not manager._valid_ticket(forged)
    other = McpManager(tmp_path)
    assert not other._valid_ticket(ticket)
    await manager.start(AuthorizedServers((forged,)), cancel=asyncio.Event())
    assert not manager.hosts and not manager.tools
    await manager.aclose()


async def test_native_lifecycle_startup_cancel(tmp_path):
    from dataclasses import replace
    manager = McpManager(tmp_path)
    cfg = local_config()
    cfg = replace(cfg, args=(*cfg.args, "--slow-init"))
    cancel = asyncio.Event()
    task = asyncio.create_task(manager.start(AuthorizedServers((manager.authorize(cfg),)), cancel=cancel))
    await asyncio.sleep(0.1)
    cancel.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 5)
    assert (await manager.aclose()).clean
    assert all(h.process is None or h.process.returncode is not None for h in manager.hosts.values())


async def test_native_lifecycle_cancel_call_no_replay(tmp_path):
    manager = await start(tmp_path)
    cancel = asyncio.Event()
    called = asyncio.Event()
    call = ToolCall("cancel-id", "mcp__demo__echo", "{}", {"text": "slow"})
    task = asyncio.create_task(manager.call(manager.identity(call.name), call, cancel=cancel, execution_started=called.set))
    try:
        await asyncio.wait_for(called.wait(), 5)
        cancel.set()
        result = await asyncio.wait_for(task, 5)
        assert result.status == "cancelled" and result.call_id == "cancel-id"
        assert manager.hosts["demo"].process.returncode is not None
        assert (await manager.call(manager.identity(call.name), call, cancel=asyncio.Event(), execution_started=lambda: None)).error_code == "MCP_UNAVAILABLE"
    finally:
        await manager.aclose()


async def test_stdio_environment_and_bounded_diagnostics(tmp_path, monkeypatch):
    import json
    from dataclasses import replace
    from weizhcode.redaction import Redactor
    monkeypatch.setenv("SYNTHETIC_PROVIDER_KEY", "provider-must-not-be-inherited")
    cfg = local_config()
    cfg = replace(cfg, args=(*cfg.args, "--diagnostics"), env_json='{"EXPLICIT":"yes"}')
    manager = McpManager(tmp_path, Redactor(["synthetic-token-731"]))
    notices = []
    await manager.start(AuthorizedServers((manager.authorize(cfg),)), cancel=asyncio.Event(), report=notices.append)
    try:
        assert len(manager.tools) == 1
        call = ToolCall("env", "mcp__demo__echo", "{}", {"text": "environment"})
        result = await manager.call(manager.identity(call.name), call, cancel=asyncio.Event(), execution_started=lambda: None)
        env = json.loads(result.content)
        assert env["provider"] is None and env["explicit"] == "yes"
        assert Path(env["cwd"]).resolve() == tmp_path.resolve()
        diagnostics = "".join(notices)
        assert diagnostics and "synthetic-token-731" not in diagnostics and "\x1b" not in diagnostics and "\x00" not in diagnostics
        assert len(notices) <= 16
    finally:
        await manager.aclose()


@pytest.mark.parametrize("flag,count,state", [("--empty", 0, "ready"), ("--unsupported-version", 0, "unavailable"),
    ("--tools-max", 256, "ready"), ("--tools-over", 0, "unavailable"), ("--directory-over", 0, "unavailable"),
    ("--pages-max", 64, "ready"), ("--pages-over", 0, "unavailable"),
    ("--cursor-max", 2, "ready"), ("--cursor-over", 0, "unavailable")])
async def test_mcp_budget_directory_native(tmp_path, flag, count, state):
    from dataclasses import replace
    config = local_config()
    manager = await start(tmp_path, replace(config, args=(*config.args, flag)))
    try:
        assert len(manager.tools) == count, manager.snapshot()
        assert manager.snapshot().servers[0].state == state
    finally:
        await manager.aclose()


async def test_native_lifecycle_owned_grandchild(tmp_path):
    import json
    import os
    from dataclasses import replace
    cfg = local_config()
    manager = await start(tmp_path, replace(cfg, args=(*cfg.args, "--grandchild")))
    call = ToolCall("children", "mcp__demo__echo", "{}", {"text": "children"})
    result = await manager.call(manager.identity(call.name), call, cancel=asyncio.Event(), execution_started=lambda: None)
    pids = json.loads(result.content)
    assert len(pids) == 2
    assert (await manager.aclose()).clean
    if os.name == "nt":
        import win32api, win32event
        import pywintypes
        for pid in pids:
            try:
                handle = win32api.OpenProcess(0x100000, False, pid)
            except pywintypes.error as exc:
                assert exc.winerror == 87  # The exact owned PID no longer exists.
            else:
                try:
                    assert win32event.WaitForSingleObject(handle, 1000) == 0
                finally:
                    handle.Close()
    else:
        from weizhcode.mcp.process import _posix_process_table
        assert all(pid not in _posix_process_table() for pid in pids)
