from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from uuid import uuid4

from weizhcode.models import ApprovalRequest, TurnEvent
from weizhcode.permissions.types import ApprovalChoice
from weizhcode.redaction import Redactor


@dataclass
class _Pending:
    run_id: str
    request: ApprovalRequest
    future: asyncio.Future
    cancel: asyncio.Event


class ApprovalBroker:
    def __init__(self, redactor=None):
        self.redactor = redactor or Redactor()
        self._connections = set()
        self._pending = None
        self._closed = False

    def connect(self):
        if self._closed:
            raise RuntimeError("审批通道已关闭")
        token = uuid4().hex
        self._connections.add(token)
        return token

    def disconnect(self, token):
        self._connections.discard(token)
        if not self._connections and self._pending is not None:
            self._pending.cancel.set()

    def close(self):
        self._closed = True
        self._connections.clear()
        if self._pending is not None:
            self._pending.cancel.set()

    def submit(self, run_id, approval_id, choice):
        pending = self._pending
        if (self._closed or pending is None or pending.run_id != run_id
                or pending.request.approval_id != approval_id or pending.future.done()
                or pending.cancel.is_set() or not isinstance(choice, ApprovalChoice)):
            return False, "审批已结束、选择无效或不属于当前任务"
        pending.future.set_result(choice)
        return True, "选择已接收"

    async def request(self, slot, checked, *, run_id, cancel, emit):
        if self._closed or not self._connections or self._pending is not None or not run_id or cancel.is_set():
            return None
        target = checked.target
        safe = lambda value, limit: self.redactor.display(value)[:limit]
        args = json.dumps(slot.call.arguments or {}, ensure_ascii=False)
        scope = ("精确命令授权不绑定 cwd；本会话/永久许可会复用于同一完整命令。" if target.command is not None
                 else "此工具＋真实路径授权不绑定本次内容；搜索授权针对搜索根。")
        request = ApprovalRequest(uuid4().hex, slot.call.name, target.friendly_name, safe(args, 4096),
                                  safe(target.match_target, 2048), safe(checked.reason, 1024), scope)
        pending = _Pending(run_id, request, asyncio.get_running_loop().create_future(), cancel)
        self._pending = pending
        cancelled = asyncio.create_task(cancel.wait())
        try:
            await emit(TurnEvent("approval_request", run_id=run_id, local_id=slot.local_id,
                                 index=slot.index, approval=request))
            await asyncio.wait((pending.future, cancelled), return_when=asyncio.FIRST_COMPLETED)
            return pending.future.result() if pending.future.done() and not cancel.is_set() else None
        finally:
            if self._pending is pending:
                self._pending = None
            if not pending.future.done():
                pending.future.cancel()
            cancelled.cancel()
            await asyncio.gather(cancelled, return_exceptions=True)
            await emit(TurnEvent("approval_resolved", run_id=run_id, local_id=slot.local_id,
                                 index=slot.index, approval=request))
