from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import replace
from uuid import uuid4

from weizhcode.models import MAX_CONCURRENT_READ_TOOLS, ToolResult, ToolSlot, TurnEvent


class ToolScheduler:
    def __init__(self, registry, executor):
        self.registry, self.executor = registry, executor

    async def execute(self, assistant, *, context, emit):
        calls = assistant.tool_calls
        ids = Counter(c.call_id for c in calls if isinstance(c.call_id, str))
        local_ids = set()
        slots = []
        for index, original in enumerate(calls):
            call = original
            if not call.local_id or call.local_id in local_ids:
                call = replace(call, local_id=uuid4().hex)
            local_ids.add(call.local_id)
            slot = ToolSlot(index, call)
            if isinstance(call.call_id, str) and ids[call.call_id] > 1:
                slot.result = ToolResult.failure(call, "DUPLICATE_CALL_ID", "重复调用 ID：所有冲突调用均不执行")
            else:
                validated = self.registry.validate(call)
                if isinstance(validated, ToolResult):
                    slot.result = validated
                else:
                    slot.call = validated
            slots.append(slot)
        context.slots = slots
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_READ_TOOLS)
        emitted = set()

        async def send(event):
            await emit(replace(event, run_id=context.run_id, iteration=context.iteration,
                               request_id=context.stream.request_id if context.stream else "", mode=context.mode))

        def cancelled(slot):
            if slot.result is None:
                message = ("已停止，结果未确认，已有副作用可能保留" if slot.execution_started
                           else "已取消，未开始执行工具")
                slot.result = ToolResult.failure(slot.call, "TOOL_CANCELLED", message,
                                                  execution_started=slot.execution_started)
            slot.phase = "finished"

        async def run_slot(slot):
            try:
                if slot.result is not None:
                    slot.phase = "finished"
                    return
                async with semaphore:
                    if context.cancel_event.is_set():
                        cancelled(slot)
                        return
                    result = await self.executor.execute(slot, mode=context.mode,
                                                         cancel=context.cancel_event, emit=send)
                    if slot.result is None:
                        slot.result = result
                    if slot.result is None:
                        raise RuntimeError("工具未返回结果")
            except asyncio.CancelledError:
                cancelled(slot)
            except Exception:
                slot.cleanup_error = "INTERNAL_ERROR：工具协调失败，任务已停止"
                if slot.result is None:
                    slot.result = ToolResult.failure(slot.call, "INTERNAL_ERROR", slot.cleanup_error)
            finally:
                slot.phase = "finished"

        position = 0
        try:
            while position < len(slots) and not context.cancel_event.is_set():
                end = position + 1
                if slots[position].result is None and self.registry.is_read_only(slots[position].call.name):
                    while end < len(slots) and slots[end].result is None and self.registry.is_read_only(slots[end].call.name):
                        end += 1
                batch = slots[position:end]
                for slot in batch:
                    await send(TurnEvent("tool_start", local_id=slot.local_id, index=slot.index, tool_call=slot.call))
                tasks = [asyncio.create_task(run_slot(slot)) for slot in batch]
                context.owned_tasks.update(tasks)
                group = asyncio.gather(*tasks, return_exceptions=True)
                cancellation = asyncio.create_task(context.cancel_event.wait())
                context.owned_tasks.add(cancellation)
                try:
                    done, _ = await asyncio.wait((group, cancellation), return_when=asyncio.FIRST_COMPLETED)
                    if cancellation in done:
                        for task in tasks:
                            if not task.done():
                                task.cancel()
                    await group
                except asyncio.CancelledError:
                    context.cancel_event.set()
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.shield(group)
                finally:
                    cancellation.cancel()
                    await asyncio.gather(cancellation, return_exceptions=True)
                    context.owned_tasks.difference_update(tasks)
                    context.owned_tasks.discard(cancellation)
                for slot in batch:
                    if slot.result is None:
                        cancelled(slot)
                    await send(TurnEvent("tool_result", local_id=slot.local_id, index=slot.index,
                                         tool_call=slot.call, result=slot.result))
                    emitted.add(slot.index)
                position = end
                if any(s.cleanup_error or (s.result and s.result.error_code == "PROCESS_CONTROL_FAILED") for s in batch):
                    break
        finally:
            for slot in slots:
                if slot.result is None:
                    cancelled(slot)
                if slot.index not in emitted:
                    await send(TurnEvent("tool_result", local_id=slot.local_id, index=slot.index,
                                         tool_call=slot.call, result=slot.result))
        return [slot.result for slot in slots]
