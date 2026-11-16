import asyncio
import json

import pytest

from weizhcode.approvals import ApprovalBroker
from weizhcode.models import ToolCall, ToolSlot
from weizhcode.permissions.types import ApprovalChoice, Category, Decision, PermissionCheck, PermissionTarget
from weizhcode.redaction import Redactor


def request_data():
    args = {"command": "echo secret-key"}
    slot = ToolSlot(0, ToolCall("call", "run_command", json.dumps(args), args))
    checked = PermissionCheck(Decision.ASK, "mode", "needs confirmation",
        PermissionTarget("run_command", "Bash", Category.EXEC, args["command"], args["command"]))
    return slot, checked


@pytest.mark.parametrize("choice", list(ApprovalChoice))
async def test_broker(choice):
    broker = ApprovalBroker(Redactor(["secret-key"]))
    broker.connect()
    events = []
    slot, checked = request_data()
    async def emit(event):
        events.append(event)
        if event.type == "approval_request":
            assert "secret-key" not in str(event)
            assert slot.result is None and not slot.execution_started
            assert not broker.submit("wrong", event.approval.approval_id, choice)[0]
            assert broker.submit("run", event.approval.approval_id, choice)[0]
            assert not broker.submit("run", event.approval.approval_id, choice)[0]
    result = await broker.request(slot, checked, run_id="run", cancel=asyncio.Event(), emit=emit)
    assert result == choice and broker._pending is None and slot.result is None


async def test_race():
    broker = ApprovalBroker()
    connection = broker.connect()
    slot, checked = request_data()
    cancel = asyncio.Event()
    async def emit(event):
        if event.type == "approval_request":
            broker.submit("r", event.approval.approval_id, ApprovalChoice.ONCE)
            broker.disconnect(connection)
    assert await broker.request(slot, checked, run_id="r", cancel=cancel, emit=emit) is None
    assert cancel.is_set() and broker._pending is None
    broker = ApprovalBroker()
    assert await broker.request(slot, checked, run_id="r", cancel=asyncio.Event(), emit=emit) is None
