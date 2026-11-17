import asyncio
import json

import pytest

from test_mcp_manager import start
from test_turn_runner import FakeProvider, reply
from weizhcode.approvals import ApprovalBroker
from weizhcode.conversation import Conversation
from weizhcode.models import ToolCall, ToolContext, ToolResult, ChatMessage
from weizhcode.permissions.engine import PermissionEngine
from weizhcode.permissions.types import ApprovalChoice, Decision
from weizhcode.redaction import Redactor
from weizhcode.tools import create_default_registry
from weizhcode.tools.executor import ToolExecutor
from weizhcode.turn_runner import TurnRunner


def call(text="fixture-731"):
    args = {"text": text}
    return ToolCall("mcp-id", "mcp__demo__echo", json.dumps(args), args)


async def rig(root, replies):
    manager = await start(root)
    registry = create_default_registry()
    for tool in manager.tools:
        registry.register_external(tool, tool.identity)
    engine = PermissionEngine.load(root, user_home=root / ".home")
    engine.external_identity = registry.external_identity
    safe = Redactor(["synthetic-private"])
    executor = ToolExecutor(registry, ToolContext(root), safe, permissions=engine, approvals=ApprovalBroker(safe))
    executor.mcp_manager = manager
    return TurnRunner(FakeProvider(replies), Conversation(), registry, executor, safe)


@pytest.mark.parametrize("choice", list(ApprovalChoice))
async def test_mcp_loop_approval_native(tmp_path, choice):
    runner = await rig(tmp_path, [reply("read", (call(),)), reply("final fixture-731")])
    runner.bind_approvals()
    try:
        events = []
        async for event in runner.run("echo"):
            events.append(event)
            if event.type == "approval_request":
                assert "不绑定本次参数" in event.approval.scope_hint
                assert runner.submit_approval(event.run_id, event.approval.approval_id, choice)[0]
        assert events[-1].reason == "completed"
        result = next(e.result for e in events if e.type == "tool_result")
        assert result.status == ("denied" if choice == ApprovalChoice.DENY else "success")
        if not result.is_error:
            assert result.content == "fixture-731" and result.call_id == "mcp-id"
        later = await runner.executor.permissions.check(call("different args"), mode="default", cancel=asyncio.Event())
        assert later.decision == (Decision.ALLOW if choice in {ApprovalChoice.SESSION, ApprovalChoice.PERMANENT} else Decision.ASK)
        if choice == ApprovalChoice.PERMANENT:
            reloaded = PermissionEngine.load(tmp_path, user_home=tmp_path / ".home")
            reloaded.external_identity = runner.registry.external_identity
            assert (await reloaded.check(call(), mode="default", cancel=asyncio.Event())).decision == Decision.ALLOW
            await reloaded.aclose()
    finally:
        await runner.aclose()


async def test_mcp_loop_plan_cancel_recovery(tmp_path):
    runner = await rig(tmp_path, [reply("", (call(),)), reply("plan done"), reply("", (call(),)), reply("recovered")])
    runner.bind_approvals()
    try:
        runner.set_mode("plan")
        events = [e async for e in runner.run("plan")]
        assert not any(e.type == "approval_request" for e in events)
        assert next(e.result for e in events if e.type == "tool_result").status == "denied"
        assert all(d.name != "mcp__demo__echo" for d in runner.registry.definitions_for_mode("plan"))
        runner.set_mode("default")
        async for event in runner.run("cancel"):
            if event.type == "approval_request":
                runner.cancel_current()
        assert event.reason == "cancelled"
        events = [e async for e in runner.run("next")]
        assert events[-1].reason == "completed"
    finally:
        await runner.aclose()


@pytest.mark.parametrize("protocol", ["anthropic", "openai", "qwen"])
async def test_mcp_protocol(tmp_path, protocol):
    from test_prompt_protocols import config, request
    runner = await rig(tmp_path, [])
    try:
        tool = runner.registry.get("mcp__demo__echo").definition
        message = call()
        payload = {}
        if protocol == "anthropic":
            payload = {"anthropic_blocks": [{"type": "tool_use", "id": message.call_id, "name": message.name, "input": message.arguments}]}
        elif protocol == "openai":
            payload = {"openai_items": [{"type": "function_call", "call_id": message.call_id, "name": message.name, "arguments": message.raw_arguments}]}
        messages = [ChatMessage("user", "task"), ChatMessage("assistant", tool_calls=(message,), provider_payload=payload),
                    ChatMessage("tool", tool_results=(ToolResult(message.call_id, message.name, "fixture-731"),))]
        body = await request(config(protocol), messages, mode="default", tools=[tool])
        wire = json.dumps(body)
        assert "mcp__demo__echo" in wire and "mcp-id" in wire and "fixture-731" in wire
    finally:
        await runner.aclose()
