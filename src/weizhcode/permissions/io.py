from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path

from weizhcode.models import ToolContext
from weizhcode.tools.process import ManagedWorker
from .types import PathStamp, PermissionFailure, SaveResult


class PermissionIO:
    def __init__(self, *, timeout=5.0, worker_factory=ManagedWorker):
        self.timeout = timeout
        self.worker_factory = worker_factory
        self._active = set()
        self._closed = False

    async def _run(self, action, payload, root, cancel):
        if self._closed or cancel.is_set():
            raise asyncio.CancelledError()
        worker = self.worker_factory(purpose="permission")
        self._active.add(worker)
        async def operation():
            async with asyncio.timeout(self.timeout):
                await worker.start(ToolContext(Path(root.canonical_root)))
                return await worker.permission_operation(action, {"root": asdict(root), **payload})
        work = asyncio.create_task(operation())
        cancelled = asyncio.create_task(cancel.wait())
        interrupted = False
        response = None
        error = None
        try:
            done, _ = await asyncio.wait((work, cancelled), return_when=asyncio.FIRST_COMPLETED)
            if work in done:
                response = await work
            else:
                interrupted = True
        except asyncio.CancelledError:
            cancel.set()
            interrupted = True
        except Exception as exc:
            error = exc
        finally:
            for task in (work, cancelled):
                if not task.done():
                    task.cancel()
            async def finish():
                await asyncio.gather(work, cancelled, return_exceptions=True)
                await worker.aclose()
            cleanup = asyncio.create_task(finish())
            try:
                while not cleanup.done():
                    try:
                        await asyncio.shield(cleanup)
                    except asyncio.CancelledError:
                        cancel.set()
                        interrupted = True
                cleanup.result()
            except Exception:
                raise PermissionFailure("PROCESS_CONTROL_FAILED", "权限辅助进程收尾失败") from None
            finally:
                self._active.discard(worker)
        if interrupted or error is not None:
            if action == "persist_permission_allow":
                return {"result": asdict(SaveResult(warning_code="SAVE_UNCERTAIN", committed=None))}
            if interrupted:
                raise asyncio.CancelledError()
            raise PermissionFailure("PATH_UNRESOLVED", "路径检查失败或超时，安全拒绝") from None
        if not isinstance(response, dict):
            raise PermissionFailure("PERMISSION_IO_ERROR", "权限辅助响应无效")
        if "error_code" in response:
            raise PermissionFailure(str(response["error_code"]), str(response.get("reason", "权限检查失败")))
        return response

    async def inspect_path(self, raw_path, root, *, cancel):
        response = await self._run("inspect_permission_path", {"raw_path": raw_path}, root, cancel)
        try:
            data = response["result"]
            if (not isinstance(data, dict) or type(data.get("target_exists")) is not bool
                    or any(not isinstance(data.get(key), str) for key in
                           ("original", "canonical_target", "project_relative", "nearest_existing"))
                    or data["original"] != raw_path):
                raise ValueError()
            return PathStamp(**data)
        except (ValueError, TypeError, KeyError):
            raise PermissionFailure("PATH_UNRESOLVED", "路径辅助响应无效") from None

    async def persist_allow(self, target, settings_path, root, *, cancel):
        if Path(settings_path) != Path(root.canonical_root) / ".weizhcode/settings.local.yaml":
            raise PermissionFailure("SAVE_PATH", "权限保存位置无效")
        response = await self._run("persist_permission_allow", {"target": asdict(target)}, root, cancel)
        try:
            result = SaveResult(**response["result"])
            if (type(result.saved) is not bool or type(result.already_present) is not bool
                    or result.committed not in (None, True, False) or not isinstance(result.warning_code, str)):
                raise ValueError()
            return result
        except (ValueError, TypeError, KeyError):
            return SaveResult(warning_code="SAVE_UNCERTAIN", committed=None)

    async def aclose(self):
        self._closed = True
        await asyncio.gather(*(worker.aclose() for worker in tuple(self._active)))
