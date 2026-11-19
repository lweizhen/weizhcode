from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from uuid import uuid4

from weizhcode.compact.contracts import _accepted_answer
from weizhcode.models import QuestionRequest, ToolResult, TurnEvent


@dataclass
class _Pending:
    request: QuestionRequest
    slot: object
    cancel: asyncio.Event
    future: asyncio.Future


class QuestionBroker:
    def __init__(self):
        self._connections = set()
        self._pending = None
        self._closed = False

    def connect(self):
        if self._closed:
            raise RuntimeError("交互通道已关闭")
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

    def submit(self, question_id, answer):
        pending = self._pending
        if (pending is None or pending.request.question_id != question_id
                or pending.future.done() or pending.cancel.is_set() or self._closed):
            return False, "问题已结束、已回答或不属于当前任务"
        if not isinstance(answer, dict) or len(answer) != 1:
            return False, "请提交一个选项序号或自由回答"
        if "option_index" in answer:
            index = answer["option_index"]
            if type(index) is not int or not 0 <= index < len(pending.request.options):
                return False, "选项序号超出范围，请重新输入"
            text, source = pending.request.options[index], "option"
        elif "text" in answer:
            text, source = answer["text"], "text"
            if not isinstance(text, str) or not text.strip() or len(text) > 4000:
                return False, "回答不能为空，且不能超过 4000 字符"
            text = text.strip()
        else:
            return False, "回答格式不正确"
        content = {"question": pending.request.question, "answer": text, "source": source}
        if source == "option":
            content["option_index"] = index
        call = pending.slot.call
        result = ToolResult(call.call_id, call.name, json.dumps(content, ensure_ascii=False))
        # 在唤醒等待者前保存事实，取消不会抹掉已接收答案。
        pending.slot.accepted_answer = _accepted_answer(
            pending.slot.local_id, pending.request.question_id,
            answer["text"] if source == "text" else text, source,
        )
        pending.slot.result = result
        pending.future.set_result(result)
        return True, "回答已接收"

    async def ask(self, slot, *, cancel, emit):
        call = slot.call
        if self._closed or not self._connections or self._pending is not None:
            return ToolResult.failure(call, "INTERACTION_UNAVAILABLE", "没有可用的用户交互通道")
        if cancel.is_set():
            return ToolResult.failure(call, "TOOL_CANCELLED", "提问已取消")
        args = call.arguments
        request = QuestionRequest(uuid4().hex, args["question"], tuple(args.get("options", [])))
        pending = _Pending(request, slot, cancel, asyncio.get_running_loop().create_future())
        self._pending = pending
        cancelled = asyncio.create_task(cancel.wait())
        try:
            slot.execution_started = True
            await emit(TurnEvent("question_request", local_id=slot.local_id, index=slot.index, question=request))
            await asyncio.wait((pending.future, cancelled), return_when=asyncio.FIRST_COMPLETED)
            return slot.result or ToolResult.failure(call, "TOOL_CANCELLED", "用户提问已取消，未继续制定计划")
        except asyncio.CancelledError:
            return slot.result or ToolResult.failure(call, "TOOL_CANCELLED", "用户提问已取消")
        finally:
            if self._pending is pending:
                self._pending = None
            if not pending.future.done():
                pending.future.cancel()
            cancelled.cancel()
            await asyncio.gather(cancelled, return_exceptions=True)
