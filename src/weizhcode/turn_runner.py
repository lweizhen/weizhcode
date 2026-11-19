from __future__ import annotations

import asyncio
from dataclasses import replace
import json

from weizhcode.models import (ChatMessage, ToolResult, TurnEvent, RunContext, StreamState, ToolSlot,
                              UsageTotals, MAX_ITERATIONS, MAX_UNKNOWN_RUN)
from weizhcode.redaction import Redactor
from weizhcode.permissions.modes import normalize_runtime_mode
from weizhcode.permissions.types import PermissionMode


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
                       question=replace(event.question, question=self.redactor.display(event.question.question),
                                        options=tuple(self.redactor.display(s) for s in event.question.options))
                       if event.question else None,
                       approval=replace(event.approval, arguments_preview=self.redactor.display(event.approval.arguments_preview),
                           target_preview=self.redactor.display(event.approval.target_preview),
                           reason=self.redactor.display(event.approval.reason),
                           scope_hint=self.redactor.display(event.approval.scope_hint),
                           tool_name=self.redactor.display(event.approval.tool_name),
                           friendly_name=self.redactor.display(event.approval.friendly_name)) if event.approval else None,
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


class _EventStream:
    """尚未开始迭代的流也拥有确定性的关闭入口。"""

    def __init__(self, channel):
        self.channel = channel
        self.iterator = channel.events()
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.closed:
            raise StopAsyncIteration
        return await anext(self.iterator)

    async def aclose(self):
        self.closed = True
        context = self.channel.context
        context.consumer_closed.set()
        if not self.channel.done.is_set():
            context.cancel_event.set()
        await self.iterator.aclose()
        if self.channel.producer is not None:
            await asyncio.shield(self.channel.producer)


class TurnRunner:
    """拥有模式、历史及资源生命周期的异步工具循环。"""

    def __init__(self, provider, conversation, registry, executor, redactor=None, *,
                 collector=None, scheduler=None, max_iterations=MAX_ITERATIONS,
                 max_unknown_run=MAX_UNKNOWN_RUN, system_prompt=None, questions=None,
                 environment_collector=None, approvals=None, context_runtime=None, context_manager=None):
        from weizhcode.prompts import SYSTEM_PROMPT
        from weizhcode.stream_collector import StreamCollector
        from weizhcode.tool_scheduler import ToolScheduler
        if type(max_iterations) is not int or max_iterations < 1 or type(max_unknown_run) is not int or max_unknown_run < 1:
            raise ValueError("循环上限必须是正整数")
        self.provider, self.conversation = provider, conversation
        self.registry, self.executor = registry, executor
        self.redactor = redactor or Redactor()
        self.collector = collector or StreamCollector(provider, self.redactor)
        self.scheduler = scheduler or ToolScheduler(registry, executor)
        from weizhcode.user_questions import QuestionBroker
        existing = getattr(executor, "questions", None)
        if questions is not None and existing is not None and questions is not existing:
            raise ValueError("交互通道注入不一致")
        self.questions = questions or existing or QuestionBroker()
        executor.questions = self.questions
        from weizhcode.approvals import ApprovalBroker
        existing_approvals = getattr(executor, "approvals", None)
        if approvals is not None and existing_approvals is not None and approvals is not existing_approvals:
            raise ValueError("审批通道注入不一致")
        self.approvals = approvals or existing_approvals or ApprovalBroker(self.redactor)
        executor.approvals = self.approvals
        self.max_iterations, self.max_unknown_run = max_iterations, max_unknown_run
        self.system_prompt = SYSTEM_PROMPT if system_prompt is None else system_prompt
        from weizhcode.prompting.environment import EnvironmentCollector
        self.environment_collector = environment_collector or EnvironmentCollector()
        permissions = getattr(executor, "permissions", None)
        self.mode = permissions.start_mode if permissions is not None else PermissionMode.DEFAULT
        self.usage_totals = UsageTotals()
        self._settled = set()
        self.busy, self._closed = False, False
        self._context = self._channel = self._task = self._close_task = None
        from weizhcode.compact.factory import build_context_runtime, NoopContextManager
        from weizhcode.compact.manager import ContextManager
        if isinstance(context_manager, NoopContextManager):
            self.context_runtime = None
        else:
            runtime = context_runtime or getattr(executor, 'context_runtime', None)
            if runtime is None:
                from weizhcode.config import effective_context_window
                config = getattr(provider, 'config', None)
                window = effective_context_window(config) if config is not None else 128000
                runtime = build_context_runtime(root_identity=getattr(permissions, 'root', None),
                    context_window=window, redactor=self.redactor)
            self.context_runtime = executor.context_runtime = runtime
            context_manager = context_manager or ContextManager(runtime, provider, self.redactor)
        self.context_manager = context_manager
        from weizhcode.providers.base import RequestUsageLedger
        self.usage_ledger = RequestUsageLedger()

    def set_mode(self, mode):
        if self.busy or self._closed:
            return TurnEvent("notice", reason="busy", text="当前任务尚未结束或应用已退出，模式未改变", mode=self.mode)
        mode = normalize_runtime_mode(mode)
        self.mode = mode
        return TurnEvent("mode_changed", mode=mode, text="计划模式（只读）" if mode == "plan" else "权限模式：" + mode.value)

    def run(self, user_text, *, mode=None, application=False):
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
        self._task = channel.start(self._drive(user_text, context, channel.emit, application=application))
        return _EventStream(channel)

    def cancel_current(self):
        if not self.busy or self._context is None:
            return False
        self._context.cancel_event.set()
        return True

    def compact(self):
        if self.busy or self._closed:
            async def rejected():
                yield TurnEvent('notice', reason='busy', text='当前任务尚未结束，未排队压缩', mode=self.mode)
            return rejected()
        self.busy = True
        context = RunContext(mode=self.mode)
        channel = _EventChannel(context, self.redactor)
        self._context, self._channel = context, channel
        self._task = channel.start(self._drive_compact(context, channel.emit))
        return _EventStream(channel)

    async def _drive_compact(self, context, emit):
        from weizhcode.prompting import build_prompt_context, EnvironmentSnapshot
        runtime, generation = self.context_runtime, None
        async def send(event):
            await emit(replace(event, run_id=context.run_id, mode=context.mode))
        async def settle(request, usage, *, trigger='manual'):
            if self.usage_ledger.settle(request.request_id, usage, purpose=request.purpose, trigger=trigger):
                self.usage_totals = self.usage_ledger.totals
                await send(TurnEvent('usage', request_id=request.request_id, usage=usage, totals=self.usage_totals,
                    request_purpose='summary', compaction_trigger=trigger))
        reason = 'completed'
        try:
            if runtime is None:
                await send(TurnEvent('notice', text='当前嵌入会话未启用上下文管理'))
                return
            generation = runtime.begin_operation()
            prompt = build_prompt_context(self.system_prompt, EnvironmentSnapshot(), mode=context.mode,
                                          iteration=1, redactor=self.redactor)
            tools = self.registry.definitions_for_mode(context.mode)
            outcome = await self.context_manager.compact(self.conversation, tools=tools, prompt=prompt,
                trigger='manual', cancel=context.cancel_event, emit=send, settle=settle,
                current=lambda: self.mode == context.mode and tools == self.registry.definitions_for_mode(context.mode))
            reason = outcome.status
        except asyncio.CancelledError:
            context.cancel_event.set()
            reason = 'cancelled'
        except Exception:
            reason = 'failed'
            await send(TurnEvent('notice', text='手动压缩未完成，原对话保留'))
        finally:
            try:
                await send(TurnEvent('turn_done', reason=reason, totals=self.usage_totals))
            finally:
                if generation is not None:
                    runtime.finish_operation(generation)
                if self._context is context:
                    self.busy, self._context = False, None

    def bind_questions(self):
        return self.questions.connect()

    def bind_approvals(self):
        return self.approvals.connect()

    def unbind_approvals(self, token):
        self.approvals.disconnect(token)

    def submit_approval(self, run_id, approval_id, choice):
        if self._context is None or self._context.run_id != run_id or self._context.cancel_event.is_set():
            return False, "审批不属于当前任务或任务已取消"
        return self.approvals.submit(run_id, approval_id, choice)

    def unbind_questions(self, token):
        self.questions.disconnect(token)

    def submit_answer(self, run_id, question_id, answer):
        if self._context is None or self._context.run_id != run_id or self._context.cancel_event.is_set():
            return False, "问题不属于当前任务或任务已取消"
        return self.questions.submit(question_id, answer)

    async def aclose(self):
        if self._close_task is None:
            self._closed = True
            async def close():
                if self._context is not None:
                    self._context.cancel_event.set()
                    self._context.consumer_closed.set()
                self.approvals.close()
                if self._task is not None:
                    await asyncio.gather(self._task, return_exceptions=True)
                self.questions.close()
                if self.context_manager is not None:
                    await self.context_manager.aclose()
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
        runtime = self.context_runtime
        keys = ()
        if runtime is not None:
            keys = tuple(slot.source.execution_key if slot.source else f'{context.run_id}:{slot.local_id}' for slot in slots)
            for slot in slots:
                answer = slot.accepted_answer
                if answer is not None and runtime.accept_answer(answer, generation=runtime.operation_generation):
                    runtime.answer_sequences[answer.answer_id] = self.conversation.reserve_human_sequence()
        self.conversation.add_tool_exchange(message, results, result_keys=keys)
        context.exchange_committed = True

    async def _drive(self, user_text, context, emit, *, application=False):
        from weizhcode import __version__
        from weizhcode.prompting import build_prompt_context, EnvironmentSnapshot
        from weizhcode.prompting.environment import finish_environment
        reason, detail, assistant, external_cancel = "internal_error", "", None, False
        async def send(kind, **kwargs):
            state = context.stream
            await emit(TurnEvent(kind, run_id=context.run_id, request_id=state.request_id if state else "",
                                 iteration=context.iteration, mode=context.mode,
                                 max_iterations=self.max_iterations, **kwargs))
        async def compact_emit(event):
            await emit(replace(event, run_id=context.run_id, iteration=context.iteration, mode=context.mode))
        async def settle(request, usage, *, trigger=''):
            if self.usage_ledger.settle(request.request_id, usage, purpose=request.purpose, trigger=trigger):
                self._settled.add(request.request_id)
                self.usage_totals = self.usage_ledger.totals
                await emit(TurnEvent('usage', run_id=context.run_id, request_id=request.request_id,
                    iteration=context.iteration, mode=context.mode, usage=usage, totals=self.usage_totals,
                    request_purpose=request.purpose, compaction_trigger=trigger))
        generation = None
        try:
            if self.context_runtime is not None:
                generation = self.context_runtime.begin_operation()
            if application:
                self.conversation.add_application_message(user_text)
            else:
                self.conversation.add_user_message(user_text)
            root = getattr(getattr(self.executor, "context", None), "project_root", None)
            model = getattr(getattr(self.provider, "config", None), "model", "unavailable")
            snapshot = EnvironmentSnapshot()
            if not context.cancel_event.is_set():
                try:
                    snapshot = await self.environment_collector.capture(project_root=root, app_version=__version__,
                        model=model, context=context, redactor=self.redactor)
                except (OSError, ValueError, TypeError):
                    snapshot = EnvironmentSnapshot(app_version=__version__, model=model)
            tools = self.registry.definitions_for_mode(context.mode)
            for iteration in range(1, self.max_iterations + 1):
                if context.cancel_event.is_set():
                    reason = "cancelled"
                    break
                context.iteration = iteration
                context.slots, context.exchange_committed, assistant = [], False, None
                await send("iteration_started")
                state = StreamState(iteration=iteration)
                context.stream = state
                prompt = build_prompt_context(self.system_prompt, snapshot, mode=context.mode,
                                              iteration=iteration, redactor=self.redactor)
                current = lambda: self.mode == context.mode and tools == self.registry.definitions_for_mode(context.mode)
                from weizhcode.compact.summary import SummaryFailure
                prepared = None
                if self.context_runtime is not None:
                    prepared = await self.context_manager.before_request(self.conversation, tools=tools, prompt=prompt,
                        cancel=context.cancel_event, emit=compact_emit, settle=settle, current=current)
                for attempt in range(2):
                    try:
                        options = {'prepared_request': prepared} if prepared is not None else {}
                        response = await self.collector.collect(self.conversation.messages(),
                            tools=tools, system_prompt="", prompt_context=prompt,
                            context=context, state=state, emit=emit, **options)
                    finally:
                        if state.request_started:
                            if prepared is not None:
                                await settle(prepared, state.usage)
                            elif state.request_id not in self._settled:
                                self._settled.add(state.request_id)
                                self.usage_totals = self.usage_totals.add(state.usage)
                                await send('usage', usage=state.usage, totals=self.usage_totals)
                    if (response is None and attempt == 0 and self.context_runtime is not None
                            and not context.cancel_event.is_set() and state.fault is not None
                            and state.fault.kind == 'context_length'):
                        outcome = await self.context_manager.compact(self.conversation, tools=tools, prompt=prompt,
                            trigger='emergency', cancel=context.cancel_event, emit=compact_emit, settle=settle, current=current)
                        if outcome.status == 'completed':
                            prepared = self.context_manager.prepare(self.conversation.messages(), tools, prompt)
                            if not self.context_manager.estimator.fits(prepared):
                                raise SummaryFailure('CONTEXT_BUDGET_EXCEEDED')
                            state = StreamState(iteration=iteration)
                            context.stream = state
                            continue
                    break
                if response is None:
                    if self.context_runtime is not None:
                        self.context_runtime.anchor = None
                    if state.completed and state.assistant_message is not None:
                        assistant = state.assistant_message
                    reason = "cancelled" if context.cancel_event.is_set() else "provider_error"
                    detail = state.error
                    if reason == "provider_error":
                        await send("error", text=detail or "模型回复未完整结束", reason=reason)
                    break
                assistant = response.assistant_message
                if self.context_runtime is not None:
                    covered = self.context_manager.prepare(self.conversation.messages()+[assistant], tools, prompt)
                    self.context_manager.estimator.observe(covered, state.usage, completed=state.completed)
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
        except Exception as exc:
            from weizhcode.compact.summary import SummaryFailure
            reason, detail = "internal_error", "任务协调失败，已停止；已有修改可能保留"
            if isinstance(exc, SummaryFailure):
                reason, detail = 'internal_error', '上下文暂时无法安全容纳请求，已保留历史并停止本轮：' + exc.code
            await send("error", text=detail, reason=reason)
        finally:
            try:
                await finish_environment(context)
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
                    if generation is not None:
                        self.context_runtime.finish_operation(generation)
                    self.busy = False
                    self._context = None
        if external_cancel:
            raise asyncio.CancelledError
