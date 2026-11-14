from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from time import monotonic
from uuid import uuid4

from weizhcode.models import ApprovalRequest, ToolCall, ToolContext, ToolResult, TurnEvent
from weizhcode.redaction import Redactor
from weizhcode.tools.base import failure
from weizhcode.tools.limits import MAX_RESULT_CHARS, TOOL_TIMEOUT_SECONDS
from weizhcode.tools.process import ManagedWorker


class ToolExecutor:
    def __init__(self, registry, context: ToolContext, redactor: Redactor | None = None, *,
                 timeout=TOOL_TIMEOUT_SECONDS, worker_factory=ManagedWorker):
        self.registry, self.context = registry, context
        self.redactor = redactor or Redactor()
        self.timeout, self.worker_factory = timeout, worker_factory
        self._active = set()
        self._closed = False

    async def execute(self, slot, *, mode, cancel, emit):
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
        try:
            worker = self.worker_factory()
        except Exception as exc:
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
                await worker.start(self.context)
                preview = await worker.prepare(call)
                if preview.error:
                    save(preview.error)
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

    async def run(self, call: ToolCall, *, approve=None):
        if self._closed:
            yield self._result_event(call, ToolResult.failure(call, "USER_DENIED", "应用已退出，未执行工具"))
            return
        validated = self.registry.validate(call)
        if isinstance(validated, ToolResult):
            yield self._result_event(call, validated)
            return
        call = validated
        try:
            worker = self.worker_factory()
        except Exception as exc:
            yield self._result_event(call, failure(call, exc))
            return
        self._active.add(worker)
        remaining = self.timeout
        try:
            yield TurnEvent("tool_preparing", local_id=call.local_id)
            started = monotonic()
            async with asyncio.timeout(remaining):
                await worker.start(self.context)
                preview = await worker.prepare(call)
            remaining -= monotonic() - started
            if preview.error:
                result = preview.error
            else:
                allowed = True
                if self.registry.get(call.name).definition.requires_confirmation:
                    request = ApprovalRequest(uuid4().hex, preview.operation_id, call.local_id, call.name,
                                              self.redactor.display(preview.target), self.redactor.display(preview.preview),
                                              self.redactor.display(preview.command), self.redactor.display(preview.cwd),
                                              preview.preview_truncated)
                    yield TurnEvent("approval_required", local_id=call.local_id, approval=request)
                    allowed = (await approve(request)) is True if approve else False
                if not allowed:
                    result = ToolResult.failure(call, "USER_DENIED", "用户拒绝本次操作，未执行")
                else:
                    yield TurnEvent("tool_running", local_id=call.local_id)
                    async with asyncio.timeout(max(0, remaining)):
                        result = await worker.execute(preview.operation_id)
        except TimeoutError:
            content = "工具实际计算超过时间预算，已终止受管进程；已有副作用不会自动回滚"
            if worker.partial["stdout"] or worker.partial["stderr"]:
                content += f"\nstdout:\n{worker.partial['stdout']}\nstderr:\n{worker.partial['stderr']}"
            result = ToolResult.failure(call, "TOOL_TIMEOUT", content, exit_code=None)
        except Exception as exc:
            result = failure(call, exc)
        finally:
            try:
                cleanup = asyncio.create_task(worker.aclose())
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                await cleanup
                raise
            except Exception:
                result = ToolResult.failure(call, "PROCESS_CONTROL_FAILED", "工具资源收尾失败，不能确认全部进程已终止")
            finally:
                self._active.discard(worker)
        yield self._result_event(call, result)

    def _result_event(self, call, result):
        safe = replace(result, content=self.redactor.text(result.content), metadata=self.redactor.value(result.metadata))
        # 通过统一序列化预算归一化，保存的结果与发给模型的内容一致。
        import json
        safe = ToolResult(**json.loads(safe.to_model_text(MAX_RESULT_CHARS)))
        safe = replace(safe, call_id=call.call_id, tool_name=call.name)
        return TurnEvent("tool_result", local_id=call.local_id, result=safe)

    async def aclose(self):
        self._closed = True
        await asyncio.gather(*(worker.aclose() for worker in tuple(self._active)))

