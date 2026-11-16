from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

from weizhcode.models import ToolCall, ToolContext, ToolResult, TurnEvent
from weizhcode.redaction import Redactor
from weizhcode.tools.base import failure
from weizhcode.tools.limits import MAX_RESULT_CHARS, TOOL_TIMEOUT_SECONDS
from weizhcode.tools.process import ManagedWorker
from weizhcode.permissions.modes import normalize_runtime_mode
from weizhcode.permissions.types import ApprovalChoice, Decision, PermissionFailure


class ToolExecutor:
    def __init__(self, registry, context: ToolContext, redactor: Redactor | None = None, *,
                 timeout=TOOL_TIMEOUT_SECONDS, worker_factory=ManagedWorker, questions=None,
                 permissions=None, approvals=None):
        self.registry, self.context = registry, context
        self.redactor = redactor or Redactor()
        self.timeout, self.worker_factory = timeout, worker_factory
        self._active = set()
        self._closed = False
        self.questions = questions
        self.permissions, self.approvals = permissions, approvals

    async def execute(self, slot, *, mode, cancel, emit, run_id=""):
        mode = normalize_runtime_mode(mode)
        call = slot.call

        def save(result):
            slot.result = self._result_event(call, result).result
            return slot.result

        def cancelled_result():
            message = ("工具已停止，结果未确认，已有副作用可能保留" if slot.execution_started
                       else "已取消，未开始执行工具")
            return ToolResult.failure(call, "TOOL_CANCELLED", message,
                                      execution_started=slot.execution_started)

        if self._closed or cancel.is_set():
            slot.phase = "finished"
            return save(cancelled_result())
        validated = self.registry.validate(call)
        if isinstance(validated, ToolResult):
            slot.phase = "finished"
            return save(validated)
        if mode == "plan" and not self.registry.is_read_only(call.name):
            slot.phase = "finished"
            return save(ToolResult.failure(call, "TOOL_NOT_ALLOWED", "计划模式只允许读文件、找文件和搜索内容"))
        call = validated
        slot.call = validated
        if self.registry.get(call.name).definition.execution_kind == "interactive":
            if mode != "plan":
                slot.phase = "finished"
                return save(ToolResult.failure(call, "TOOL_NOT_ALLOWED", "用户提问仅限计划模式"))
            try:
                if self.questions is None:
                    return save(ToolResult.failure(call, "INTERACTION_UNAVAILABLE", "没有用户交互通道"))
                return save(await self.questions.ask(slot, cancel=cancel, emit=emit))
            finally:
                slot.phase = "finished"
        if self.permissions is None:
            slot.phase = "finished"
            return save(ToolResult.failure(call, "PERMISSION_UNAVAILABLE", "权限引擎未接入，未执行工具"))
        checked = None
        try:
            slot.phase = "checking"
            await emit(TurnEvent("tool_checking", local_id=slot.local_id, index=slot.index))
            checked = await self.permissions.check(call, mode=mode, cancel=cancel)
            if checked.decision == Decision.DENY:
                return save(ToolResult.failure(call, checked.code or "PERMISSION_RULE_DENIED", checked.reason,
                    permission_source=checked.source, layer=checked.matched_layer,
                    rule=checked.matched_rule, execution_started=False))
            if checked.decision == Decision.ASK:
                slot.phase = "awaiting_approval"
                choice = (await self.approvals.request(slot, checked, run_id=run_id, cancel=cancel, emit=emit)
                          if self.approvals is not None else None)
                if cancel.is_set():
                    return save(cancelled_result())
                if choice is None:
                    return save(ToolResult.failure(call, "INTERACTION_UNAVAILABLE", "没有可用审批通道，未执行工具"))
                if choice == ApprovalChoice.DENY:
                    return save(ToolResult.failure(call, "USER_DENIED", "用户拒绝本次操作", permission_source="user", execution_started=False))
                if choice == ApprovalChoice.PERMANENT:
                    await emit(TurnEvent("notice", text="正在保存精确授权…"))
                result = await self.permissions.accept(checked, choice, cancel=cancel)
                if choice == ApprovalChoice.SESSION and result.warning_code:
                    await emit(TurnEvent("notice", text="仅本次允许，未记住本会话授权"))
                if choice == ApprovalChoice.PERMANENT:
                    text = ("精确永久授权已保存" if result.saved else
                            "永久授权保存结果不确定，授权可能已保存，请检查本地配置；本轮不继续执行"
                            if result.committed is None else "仅本次允许，未保存永久授权")
                    await emit(TurnEvent("notice", text=text))
                    if result.committed is None:
                        cancel.set()
                        return save(ToolResult.failure(call, "PERMISSION_UNAVAILABLE", text))
            await self.permissions.recheck(checked, cancel=cancel)
            if cancel.is_set():
                return save(cancelled_result())
        except asyncio.CancelledError:
            if not cancel.is_set():
                cancel.set()
            return save(cancelled_result())
        except PermissionFailure as exc:
            if exc.code == "PROCESS_CONTROL_FAILED":
                slot.cleanup_error = str(exc)
            return save(ToolResult.failure(call, exc.code, str(exc), execution_started=False))
        finally:
            if checked is not None:
                self.permissions.forget(checked)
            if slot.result is not None:
                slot.phase = "finished"
        try:
            worker = self.worker_factory()
        except Exception as exc:
            slot.cleanup_error = "INTERNAL_ERROR：工具执行器初始化失败，任务已停止"
            slot.phase = "finished"
            return save(failure(call, exc))
        self._active.add(worker)

        async def operation():
            # 一个 timeout 同时包住启动、准备和执行，不按阶段重置。
            async with asyncio.timeout(self.timeout):
                slot.phase = "preparing"
                await emit(TurnEvent("tool_preparing", local_id=slot.local_id, index=slot.index))
                if cancel.is_set():
                    return
                await worker.start(replace(self.context, permission_root=self.permissions.root))
                if checked.target.path is not None:
                    preview = await worker.prepare(call, permission_stamp=checked.target.path)
                else:
                    preview = await worker.prepare(call)
                if preview.error:
                    save(preview.error)
                    return
                if checked.target.path is not None and Path(preview.target) != Path(checked.target.path.canonical_target):
                    save(ToolResult.failure(call, "PERMISSION_TARGET_CHANGED", "准备目标与批准目标不同，未执行"))
                    return
                if cancel.is_set():
                    return
                slot.phase = "running"
                await emit(TurnEvent("tool_running", local_id=slot.local_id, index=slot.index))
                if cancel.is_set():
                    return
                slot.execution_started = True
                result = await worker.execute(preview.operation_id)
                # 必须在任何后续 await（尤其清理）之前保存已确认结果。
                save(result)

        work = asyncio.create_task(operation())
        cancelled = asyncio.create_task(cancel.wait())
        propagate_cancel = False
        try:
            done, _ = await asyncio.wait((work, cancelled), return_when=asyncio.FIRST_COMPLETED)
            if work in done:
                await work
            else:
                work.cancel()
                await asyncio.gather(work, return_exceptions=True)
        except TimeoutError:
            partial = getattr(worker, "partial", {})
            content = "工具超过准备与执行共享预算，已停止受管进程；已有副作用不会自动回滚"
            if partial.get("stdout") or partial.get("stderr"):
                content += f"\nstdout:\n{partial.get('stdout', '')}\nstderr:\n{partial.get('stderr', '')}"
            save(ToolResult.failure(call, "TOOL_TIMEOUT", content, exit_code=None))
        except asyncio.CancelledError:
            propagate_cancel = not cancel.is_set()
            cancel.set()
        except Exception as exc:
            slot.cleanup_error = "INTERNAL_ERROR：工具执行基础设施异常，任务已停止"
            save(failure(call, exc))
        finally:
            for task in (work, cancelled):
                if not task.done():
                    task.cancel()
            async def finish_owned():
                await asyncio.gather(work, cancelled, return_exceptions=True)
                await worker.aclose()
            cleanup = asyncio.create_task(finish_owned())
            try:
                while not cleanup.done():
                    try:
                        await asyncio.shield(cleanup)
                    except asyncio.CancelledError:
                        if not cancel.is_set():
                            propagate_cancel = True
                        cancel.set()
                cleanup.result()
            except Exception:
                slot.cleanup_error = "PROCESS_CONTROL_FAILED：工具资源收尾失败，不能确认全部进程已终止"
                if slot.result is None:
                    save(ToolResult.failure(call, "PROCESS_CONTROL_FAILED", slot.cleanup_error))
            finally:
                self._active.discard(worker)
                slot.phase = "finished"
        if slot.result is None:
            save(cancelled_result())
        if propagate_cancel:
            raise asyncio.CancelledError
        return slot.result

    def _result_event(self, call, result):
        safe = replace(result, content=self.redactor.text(result.content), metadata=self.redactor.value(result.metadata))
        # 通过统一序列化预算归一化，保存的结果与发给模型的内容一致。
        import json
        safe = ToolResult(**json.loads(safe.to_model_text(MAX_RESULT_CHARS)))
        safe = replace(safe, call_id=call.call_id, tool_name=call.name)
        return TurnEvent("tool_result", local_id=call.local_id, result=safe)

    async def aclose(self):
        self._closed = True
        if self.questions is not None:
            self.questions.close()
        if self.approvals is not None:
            self.approvals.close()
        if self.permissions is not None:
            await self.permissions.aclose()
        await asyncio.gather(*(worker.aclose() for worker in tuple(self._active)))

