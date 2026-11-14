from __future__ import annotations

import asyncio
from contextlib import aclosing
from dataclasses import replace
import json

from weizhcode.models import (ChatMessage, ToolResult, TurnEvent, RunContext, StreamState, ToolSlot,
                              TokenUsage, UsageTotals, MAX_ITERATIONS, MAX_UNKNOWN_RUN)
from weizhcode.prompts import SYSTEM_PROMPT, FINAL_PROMPT
from weizhcode.redaction import Redactor, StreamingRedactor, safe_text


class _EventChannel:
    """单任务有界通道；完成信号不占队列容量。"""

    def __init__(self, context, redactor):
        from weizhcode.models import EVENT_QUEUE_SIZE
        self.context = context
        self.redactor = redactor
        self.queue = asyncio.Queue(maxsize=EVENT_QUEUE_SIZE)
        self.done = asyncio.Event()
        self.producer = None

    def start(self, coroutine):
        async def drive():
            try:
                await coroutine
            finally:
                self.done.set()
        self.producer = asyncio.create_task(drive())
        return self.producer

    def _value(self, value):
        if isinstance(value, str):
            return self.redactor.display(value)
        if isinstance(value, dict):
            return {self.redactor.display(str(k)): self._value(v) for k, v in value.items()}
        if isinstance(value, (tuple, list)):
            return [self._value(v) for v in value]
        return value

    def _safe(self, event):
        call, result = event.tool_call, event.result
        if call is not None:
            call = replace(call, call_id=self._value(call.call_id), name=self._value(call.name),
                           raw_arguments=self._value(call.raw_arguments), arguments=self._value(call.arguments))
        if result is not None:
            result = replace(result, call_id=self._value(result.call_id), tool_name=self._value(result.tool_name),
                             content=self._value(result.content), metadata=self._value(result.metadata),
                             error_code=self._value(result.error_code))
            result = ToolResult(**json.loads(result.to_model_text()))
        return replace(event, text=self.redactor.display(event.text), reason=self.redactor.display(event.reason),
                       tool_call=call, result=result,
                       usage=replace(event.usage, source=self.redactor.display(event.usage.source))
                       if event.usage else None)

    async def emit(self, event):
        if self.context.consumer_closed.is_set():
            return
        put = asyncio.create_task(self.queue.put(self._safe(event)))
        closed = asyncio.create_task(self.context.consumer_closed.wait())
        try:
            await asyncio.wait((put, closed), return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in (put, closed):
                if not task.done():
                    task.cancel()
            await asyncio.gather(put, closed, return_exceptions=True)

    async def events(self):
        try:
            while not self.done.is_set() or not self.queue.empty():
                if not self.queue.empty():
                    yield self.queue.get_nowait()
                    continue
                get = asyncio.create_task(self.queue.get())
                finished = asyncio.create_task(self.done.wait())
                try:
                    ready, _ = await asyncio.wait((get, finished), return_when=asyncio.FIRST_COMPLETED)
                    if get in ready:
                        yield get.result()
                finally:
                    for task in (get, finished):
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(get, finished, return_exceptions=True)
            if self.producer is not None:
                await self.producer
        finally:
            self.context.consumer_closed.set()
            if not self.done.is_set():
                self.context.cancel_event.set()
            if self.producer is not None:
                await asyncio.shield(self.producer)


class _LoopRunner:
    """在正式入口原子切换前，独立验证新的循环驱动。"""

    def __init__(self, provider, conversation, registry, executor, redactor=None, *,
                 collector=None, scheduler=None, max_iterations=MAX_ITERATIONS,
                 max_unknown_run=MAX_UNKNOWN_RUN, system_prompt=None):
        from weizhcode.prompts import LOOP_SYSTEM_PROMPT
        from weizhcode.stream_collector import StreamCollector
        from weizhcode.tool_scheduler import ToolScheduler
        if type(max_iterations) is not int or max_iterations < 1 or type(max_unknown_run) is not int or max_unknown_run < 1:
            raise ValueError("循环上限必须是正整数")
        self.provider, self.conversation = provider, conversation
        self.registry, self.executor = registry, executor
        self.redactor = redactor or Redactor()
        self.collector = collector or StreamCollector(provider, self.redactor)
        self.scheduler = scheduler or ToolScheduler(registry, executor)
        self.max_iterations, self.max_unknown_run = max_iterations, max_unknown_run
        self.system_prompt = LOOP_SYSTEM_PROMPT if system_prompt is None else system_prompt
        self.mode = "normal"
        self.usage_totals = UsageTotals()
        self._settled = set()
        self.busy, self._closed = False, False
        self._context = self._channel = self._task = self._close_task = None

    def set_mode(self, mode):
        if self.busy or self._closed:
            return TurnEvent("notice", reason="busy", text="当前任务尚未结束或应用已退出，模式未改变", mode=self.mode)
        if mode not in {"normal", "plan"}:
            raise ValueError("未知模式")
        self.mode = mode
        return TurnEvent("mode_changed", mode=mode, text="计划模式（只读）" if mode == "plan" else "普通执行模式")

    def run(self, user_text, *, mode=None):
        if self.busy or self._closed:
            async def rejected():
                yield TurnEvent("notice", reason="busy", text="当前任务尚未结束或应用已退出", mode=self.mode)
            return rejected()
        if mode is not None:
            self.set_mode(mode)
        self.busy = True
        context = RunContext(mode=self.mode)
        channel = _EventChannel(context, self.redactor)
        self._context, self._channel = context, channel
        self._task = channel.start(self._drive(user_text, context, channel.emit))
        return channel.events()

    def cancel_current(self):
        if not self.busy or self._context is None:
            return False
        self._context.cancel_event.set()
        return True

    async def aclose(self):
        if self._close_task is None:
            self._closed = True
            async def close():
                if self._context is not None:
                    self._context.cancel_event.set()
                    self._context.consumer_closed.set()
                if self._task is not None:
                    await asyncio.gather(self._task, return_exceptions=True)
                await self.executor.aclose()
            self._close_task = asyncio.create_task(close())
        await asyncio.shield(self._close_task)

    def _safe_result(self, call, result):
        safe = replace(result, content=self.redactor.text(result.content), metadata=self.redactor.value(result.metadata))
        safe = ToolResult(**json.loads(safe.to_model_text()))
        return replace(safe, call_id=call.call_id, tool_name=call.name)

    def _commit_exchange(self, assistant, context):
        if context.exchange_committed:
            return
        slots = context.slots
        while len(slots) < len(assistant.tool_calls):
            slots.append(ToolSlot(len(slots), assistant.tool_calls[len(slots)]))
        results, facts = [], []
        for call, slot in zip(assistant.tool_calls, slots):
            if slot.result is None:
                slot.result = ToolResult.failure(call, "TOOL_CANCELLED",
                    "任务已停止，结果未确认，已有副作用可能保留" if slot.execution_started else "任务已停止，未开始执行工具",
                    execution_started=slot.execution_started)
            results.append(self._safe_result(call, slot.result))
            facts.append({"local_id": slot.local_id, "execution_started": slot.execution_started,
                          "cleanup_error": self.redactor.display(slot.cleanup_error)})
        message = replace(assistant, content=self.redactor.text(assistant.content),
                          provider_payload={**assistant.provider_payload, "execution_facts": facts})
        self.conversation.add_tool_exchange(message, results)
        context.exchange_committed = True

    async def _drive(self, user_text, context, emit):
        from weizhcode.prompts import PLAN_MODE_REMINDER
        reason, detail, assistant, external_cancel = "internal_error", "", None, False
        async def send(kind, **kwargs):
            state = context.stream
            await emit(TurnEvent(kind, run_id=context.run_id, request_id=state.request_id if state else "",
                                 iteration=context.iteration, mode=context.mode,
                                 max_iterations=self.max_iterations, **kwargs))
        self.conversation.add_user_message(user_text)
        try:
            for iteration in range(1, self.max_iterations + 1):
                if context.cancel_event.is_set():
                    reason = "cancelled"
                    break
                context.iteration = iteration
                context.slots, context.exchange_committed, assistant = [], False, None
                await send("iteration_started")
                state = StreamState(iteration=iteration)
                context.stream = state
                prompt = self.system_prompt + ("\n" + PLAN_MODE_REMINDER if context.mode == "plan" else "")
                try:
                    response = await self.collector.collect(self.conversation.messages(),
                        tools=self.registry.definitions(read_only=context.mode == "plan"), system_prompt=prompt,
                        context=context, state=state, emit=emit)
                finally:
                    if state.request_id not in self._settled:
                        self._settled.add(state.request_id)
                        self.usage_totals = self.usage_totals.add(state.usage)
                        await send("usage", usage=state.usage, totals=self.usage_totals)
                if response is None:
                    if state.completed and state.assistant_message is not None:
                        assistant = state.assistant_message
                    reason = "cancelled" if context.cancel_event.is_set() else "provider_error"
                    detail = state.error
                    if reason == "provider_error":
                        await send("error", text=detail or "模型回复未完整结束", reason=reason)
                    break
                assistant = response.assistant_message
                if assistant.tool_calls:
                    all_unknown = all(not isinstance(call.name, str) or self.registry.get(call.name) is None
                                      for call in assistant.tool_calls)
                    context.unknown_run = context.unknown_run + 1 if all_unknown else 0
                    await self.scheduler.execute(assistant, context=context, emit=emit)
                    self._commit_exchange(assistant, context)
                    if context.cancel_event.is_set():
                        reason = "cancelled"
                        break
                    if any(s.cleanup_error or (s.result and s.result.error_code == "PROCESS_CONTROL_FAILED") for s in context.slots):
                        reason, detail = "internal_error", "工具基础设施或清理失败，任务已停止"
                        await send("error", text=detail, reason=reason)
                        break
                    if context.unknown_run >= self.max_unknown_run:
                        reason = "unknown_tools"
                        break
                    if iteration == self.max_iterations:
                        reason = "max_iterations"
                        break
                elif context.cancel_event.is_set():
                    reason = "cancelled"
                    break
                elif assistant.content.strip():
                    self.conversation.add_assistant_turn(replace(assistant, content=self.redactor.text(assistant.content)))
                    reason = "completed"
                    break
                else:
                    reason = "empty_response"
                    break
        except asyncio.CancelledError:
            context.cancel_event.set()
            reason, external_cancel = "cancelled", True
        except Exception:
            reason, detail = "internal_error", "任务协调失败，已停止；已有修改可能保留"
            await send("error", text=detail, reason=reason)
        finally:
            try:
                if assistant is None and context.stream and context.stream.completed:
                    assistant = context.stream.assistant_message
                if assistant is not None and assistant.tool_calls and not context.exchange_committed:
                    self._commit_exchange(assistant, context)
                notices = {
                    "empty_response": "模型未返回正文，任务未确认完成",
                    "max_iterations": f"已达到 {self.max_iterations} 轮上限，任务可能未完成",
                    "unknown_tools": f"连续 {self.max_unknown_run} 轮全部调用未知工具，任务已停止",
                    "cancelled": "已取消，已有修改可能保留，未完成操作不会自动继续",
                    "provider_error": "本次回复未完成：" + (detail or "模型请求失败"),
                    "internal_error": detail or "内部错误，任务已停止，已有修改可能保留",
                }
                if reason != "completed":
                    notice = self.redactor.display(notices[reason])
                    self.conversation.add_stop_notice(notice, reason, run_id=context.run_id)
                    await send("notice", text=notice, reason=reason)
                await send("turn_done", reason=reason, totals=self.usage_totals)
            finally:
                if self._context is context:
                    self.busy = False
                    self._context = None
        if external_cancel:
            raise asyncio.CancelledError


class TurnRunner:
    def __init__(self, provider, conversation, registry, executor, redactor=None, *, system_prompt=SYSTEM_PROMPT):
        self.provider = provider
        self.conversation = conversation
        self.registry = registry
        self.executor = executor
        self.redactor = redactor or Redactor()
        self.system_prompt = system_prompt
        self.busy = False
        self._closed = False
        self._task = None

    def run(self, user_text, *, approve=None):
        # 在返回迭代器之前占用，避免两个提交同时进入。
        if self.busy or self._closed:
            async def rejected():
                yield TurnEvent("error", text="当前回合尚未结束或应用已退出")
            return rejected()
        self.busy = True
        return self._run(user_text, approve)

    async def _request(self, phase, state):
        redactor = StreamingRedactor(self.redactor)
        parts = []
        prompt = self.system_prompt + ("\n" + FINAL_PROMPT if phase == "final" else "")
        stream = self.provider.stream_chat(self.conversation.messages(), tools=self.registry.definitions(),
                                          system_prompt=prompt, allow_tools=phase == "initial")
        async with aclosing(stream):
            async for event in stream:
                if event.type == "text_delta":
                    parts.append(event.text)
                    text = safe_text(redactor.push(event.text))
                    if text:
                        yield TurnEvent("text_delta", text=text, phase=phase)
                elif event.type == "tool_call_start":
                    # 接收态不能被当成已批准或可执行调用。
                    yield TurnEvent("tool_pending", phase=phase,
                                    local_id=event.tool_call.local_id, tool_call=event.tool_call)
                elif event.type == "error":
                    yield TurnEvent("error", text=self.redactor.display(event.message), phase=phase)
                    return
                elif event.type == "done":
                    tail = safe_text(redactor.finish())
                    if tail:
                        yield TurnEvent("text_delta", text=tail, phase=phase)
                    message = event.assistant_message or ChatMessage("assistant", "".join(parts))
                    state["message"] = replace(message, content=self.redactor.text(message.content))
                    return
        yield TurnEvent("error", text="模型回复未完整结束，本次内容未保存", phase=phase)

    async def _run(self, user_text, approve):
        self._task = asyncio.current_task()
        try:
            self.conversation.add_user_message(user_text)
            initial = {}
            async for event in self._request("initial", initial):
                yield event
            assistant = initial.get("message")
            if assistant is None or self._closed:
                return
            calls = assistant.tool_calls
            if not calls:
                self.conversation.add_assistant_turn(assistant)
                yield TurnEvent("turn_done")
                return
            results = []
            if len(calls) > 1:
                for call in calls:
                    result = ToolResult.failure(call, "TOO_MANY_TOOL_CALLS", "本回合只允许一个工具；本批调用全部未执行")
                    results.append(result)
                    yield TurnEvent("tool_result", local_id=call.local_id, tool_call=call, result=result)
            else:
                call = calls[0]
                # 同一完整调用更新接收态；展示层始终自行脱敏，不改执行参数。
                yield TurnEvent("tool_pending", local_id=call.local_id, tool_call=call)
                async for event in self.executor.run(call, approve=approve):
                    if event.result:
                        results.append(event.result)
                    yield event
            if self._closed:
                return
            if len(results) != len(calls):
                raise RuntimeError("工具执行器未返回对应结果")
            self.conversation.add_tool_exchange(assistant, results)
            final = {}
            async for event in self._request("final", final):
                yield event
            message = final.get("message")
            if message is None or self._closed:
                return
            if message.tool_calls:
                results = [ToolResult.failure(c, "TOOL_ROUND_LIMIT", "单轮工具阶段已结束，此调用未执行")
                           for c in message.tool_calls]
                self.conversation.add_tool_exchange(message, results)
                for call, result in zip(message.tool_calls, results):
                    yield TurnEvent("tool_result", phase="final", local_id=call.local_id, tool_call=call, result=result)
                yield TurnEvent("text_delta", phase="final", text="\n已达到单轮工具上限，未执行后续调用。")
            else:
                self.conversation.add_assistant_turn(message)
            yield TurnEvent("turn_done", phase="final")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            yield TurnEvent("error", text=self.redactor.display(str(exc)))
        finally:
            self.busy = False
            self._task = None

    async def aclose(self):
        self._closed = True
        task = self._task
        if task is not None and task is not asyncio.current_task() and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await self.executor.aclose()
