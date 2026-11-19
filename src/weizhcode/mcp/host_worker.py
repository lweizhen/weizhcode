"""One server, one SDK context owner. Internal IPC is not the MCP wire protocol."""
import asyncio
from contextlib import AsyncExitStack
from dataclasses import asdict
import json
import logging
import os
import re
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
import httpx

from .contracts import McpServerConfig
from .diagnostics import DiagnosticCollector
from .http import McpHttpTransport
from .limits import MAX_IPC_BYTES, MAX_PAGES, MAX_TOOLS_PER_SERVER, MAX_DIRECTORY_BYTES, MAX_CURSOR_CHARS, MAX_QUEUE_FRAMES, SUPPORTED_PROTOCOLS
from .tool import adapt_result
from weizhcode.models import ToolCall
from weizhcode.redaction import Redactor


async def main():
    logging.disable(logging.CRITICAL)
    first = json.loads(await asyncio.to_thread(sys.stdin.buffer.readline, MAX_IPC_BYTES + 1))
    host_id, request_id = first["host_id"], first["request_id"]
    if first.get("version") != 1 or first.get("type") != "connect" or not re.fullmatch("[a-f0-9]{32}", host_id):
        return
    def emit(kind, **data):
        raw = json.dumps({"version": 1, "host_id": host_id, "type": kind, **data}, ensure_ascii=False, allow_nan=False)
        if len(raw.encode()) > MAX_IPC_BYTES:
            raise ValueError("MCP_IPC_LIMIT")
        print(raw, flush=True)
    cfg = McpServerConfig(**first["config"])
    safe = Redactor(first["secrets"])
    diagnostics = DiagnosticCollector(safe)
    diagnostic_count = 0
    def publish_diagnostics():
        nonlocal diagnostic_count
        for text in diagnostics.messages[diagnostic_count:]:
            emit("diagnostic", text=text)
            diagnostic_count += 1
    drain = input_task = work = None
    write_pipe = None
    try:
        async with AsyncExitStack() as stack:
            if cfg.transport == "stdio":
                read_fd, write_fd = os.pipe()
                read_pipe = os.fdopen(read_fd, "rb", buffering=0)
                write_pipe = os.fdopen(write_fd, "w", encoding="utf-8")
                async def read_diagnostics():
                    try:
                        while chunk := await asyncio.to_thread(read_pipe.read, 4096):
                            diagnostics.push(chunk)
                            publish_diagnostics()
                    finally:
                        read_pipe.close()
                        diagnostics.finish()
                        publish_diagnostics()
                drain = asyncio.create_task(read_diagnostics())
                params = StdioServerParameters(command=cfg.command, args=list(cfg.args), env=cfg.env, cwd=first["root"])
                streams = await stack.enter_async_context(stdio_client(params, errlog=write_pipe))
            else:
                client = await stack.enter_async_context(httpx.AsyncClient(
                    headers=cfg.headers, transport=McpHttpTransport(cfg.url), timeout=30, trust_env=False))
                streams = await stack.enter_async_context(streamable_http_client(cfg.url, http_client=client))
            session = await stack.enter_async_context(ClientSession(streams[0], streams[1]))
            initialized = await session.initialize()
            if initialized.protocolVersion not in SUPPORTED_PROTOCOLS:
                raise ValueError("MCP_UNSUPPORTED_PROTOCOL")
            cursor, seen, size, tools = None, set(), 0, []
            if initialized.capabilities.tools:
                for _ in range(MAX_PAGES):
                    page = await session.list_tools(cursor=cursor)
                    for tool in page.tools:
                        data = tool.model_dump(mode="json", by_alias=True)
                        size += len(json.dumps(data).encode())
                        tools.append(data)
                        if size > MAX_DIRECTORY_BYTES or len(tools) > MAX_TOOLS_PER_SERVER:
                            raise ValueError("MCP_DISCOVERY_LIMIT")
                    cursor = page.nextCursor
                    if cursor is None:
                        break
                    if not isinstance(cursor, str) or len(cursor) > MAX_CURSOR_CHARS or cursor in seen:
                        raise ValueError("MCP_DISCOVERY_CURSOR")
                    seen.add(cursor)
                else:
                    raise ValueError("MCP_DISCOVERY_LIMIT")
            for tool in tools:
                if len(json.dumps(tool).encode()) > MAX_IPC_BYTES - 1024:
                    name = tool.get("name", "")
                    tool = {"name": name if len(name) <= 64 else "_invalid", "inputSchema": {"type": "invalid"}}
                emit("tool", request_id=request_id, tool=tool)
            emit("discovery_done", request_id=request_id)
            queue = asyncio.Queue(MAX_QUEUE_FRAMES)
            async def inputs():
                while True:
                    raw = await asyncio.to_thread(sys.stdin.buffer.readline, MAX_IPC_BYTES + 1)
                    if not raw or len(raw) > MAX_IPC_BYTES:
                        await queue.put({"type": "close"})
                        return
                    try:
                        value = json.loads(raw)
                        if value.get("host_id") != host_id or value.get("version") != 1:
                            raise ValueError()
                        await queue.put(value)
                        if value["type"] == "close":
                            return
                    except (ValueError, KeyError, TypeError):
                        await queue.put({"type": "close"})
                        return
            input_task = asyncio.create_task(inputs())
            active_id = None
            active_call = None
            async def invoke(value):
                call = ToolCall(value["call_id"], value["full_name"], json.dumps(value["arguments"]))
                try:
                    emit("started", request_id=value["request_id"])
                    result = await session.call_tool(value["remote_name"], arguments=value["arguments"])
                    capture = value.get("capture")
                    if capture is not None and (not isinstance(capture, dict)
                            or set(capture) != {"execution_key", "generation"}
                            or not re.fullmatch(r"[A-Za-z0-9:_-]{1,256}", capture.get("execution_key", ""))
                            or type(capture.get("generation")) is not int):
                        raise ValueError("MCP_CAPTURE_INVALID")
                    adapted = adapt_result(call, result, safe, bounded=False)
                    if capture is not None:
                        from weizhcode.compact.capture import result_capture_frames
                        for frame in result_capture_frames(adapted, operation_id=value["request_id"], **capture):
                            kind = frame.pop("type")
                            emit(kind, request_id=value["request_id"], **frame)
                    emit("result", request_id=value["request_id"], result=json.loads(adapted.to_model_text()))
                except asyncio.CancelledError:
                    raise
                except Exception:
                    emit("fatal", request_id=value["request_id"], code="MCP_TRANSPORT_ERROR")
            while True:
                value = await queue.get()
                kind = value.get("type")
                if kind == "close":
                    break
                if kind == "cancel":
                    if work and not work.done() and value.get("request_id") == active_id:
                        work.cancel()
                        await asyncio.gather(work, return_exceptions=True)
                        from weizhcode.models import ToolResult
                        call = ToolCall(active_call["call_id"], active_call["full_name"], "{}")
                        emit("result", request_id=active_id, result=asdict(ToolResult.failure(
                            call, "TOOL_CANCELLED", "MCP请求已取消；远端副作用可能保留")))
                    continue
                if kind != "call" or (work and not work.done()):
                    raise ValueError("MCP_IPC_STATE")
                active_id = value["request_id"]
                active_call = value
                work = asyncio.create_task(invoke(value))
            if work and not work.done():
                work.cancel()
                await asyncio.gather(work, return_exceptions=True)
        emit("closed")
    except Exception:
        emit("fatal", request_id=request_id, code="MCP_CONNECTION_FAILED")
    finally:
        if write_pipe:
            write_pipe.close()
        if drain:
            await drain
        if input_task:
            input_task.cancel()
            await asyncio.gather(input_task, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
