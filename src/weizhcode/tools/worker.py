from __future__ import annotations

import json
import sys
import threading
import re
from dataclasses import asdict, replace
from pathlib import Path

from weizhcode.models import PreparedOperationPreview, ToolCall, ToolContext, ToolResult
from weizhcode.tools import create_default_registry
from weizhcode.tools import file_utils, run_command
from weizhcode.permissions.types import PathStamp, PermissionFailure, RootIdentity

_output_lock = threading.Lock()


def emit(message):
    with _output_lock:
        print(json.dumps(message, ensure_ascii=False), flush=True)


def main():
    registry = create_default_registry()
    context = None
    operation = None
    state = "waiting"
    purpose = "tools"
    request_id = ""
    file_utils.resource_created = lambda path, identity: emit({"type": "resource", "path": str(path), "identity": identity})
    run_command.output_collected = lambda label, text: emit({"type": "output", "label": label, "text": text})
    for line in sys.stdin:
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                raise ValueError()
            kind = message.get("type")
            if kind == "abort":
                return
            if state == "waiting" and kind == "start":
                purpose = message.get("purpose", "tools")
                request_id = message.get("request_id", "")
                if purpose not in {"tools", "permission"} or not isinstance(request_id, str) or not re.fullmatch(r"[a-f0-9]{32}", request_id):
                    raise ValueError()
                root_data = message.get("permission_root")
                context = ToolContext(Path(message["project_root"]).resolve(), RootIdentity(**root_data) if root_data else None)
                state = "ready"
                emit({"type": "ready"})
            elif state == "ready" and purpose == "permission" and kind in {"inspect_permission_path", "persist_permission_allow"}:
                from weizhcode.permissions.worker_ops import handle
                if message.get("request_id") != request_id:
                    raise ValueError()
                state = "done"
                emit({"type": "permission_result", "request_id": request_id,
                      **handle(message, context, resource_created=file_utils.resource_created)})
            elif state == "ready" and purpose == "tools" and kind == "prepare":
                call = ToolCall(**message["call"])
                validated = registry.validate(call)
                if isinstance(validated, ToolResult):
                    preview = PreparedOperationPreview("", "", "", error=validated)
                    state = "failed"
                else:
                    tool = registry.get(validated.name)
                    from weizhcode.permissions.rules import TOOLS
                    from weizhcode.permissions.sandbox import recheck
                    from weizhcode.tools.base import failure
                    from weizhcode.models import PreparedOperation
                    try:
                        if validated.name in TOOLS and validated.name != "run_command":
                            if context.permission_root is None or not message.get("permission_stamp"):
                                raise PermissionFailure("PERMISSION_UNAVAILABLE", "文件操作缺少批准印记")
                            recheck(PathStamp(**message["permission_stamp"]), context.permission_root)
                        operation = tool.prepare(validated, context)
                        proof = message.get("archive_read_proof")
                        if proof is not None:
                            if validated.name != "read_file" or not isinstance(proof, dict):
                                raise PermissionFailure("ARCHIVE_CHANGED", "归档读取凭据无效")
                            operation = replace(operation, state={**operation.state, "archive_read_proof": proof})
                        if not operation.error and message.get("permission_stamp") and operation.target != message["permission_stamp"]["canonical_target"]:
                            raise PermissionFailure("PERMISSION_TARGET_CHANGED", "文件准备目标已变化")
                    except PermissionFailure as exc:
                        operation = PreparedOperation(validated, validated.arguments, error=failure(validated, exc))
                    preview = PreparedOperationPreview(
                        operation.operation_id, operation.target, operation.preview,
                        command=str(operation.arguments.get("command", "")),
                        cwd=str(operation.arguments.get("cwd", "")),
                        preview_truncated="[truncated]" in operation.preview, error=operation.error,
                    )
                    state = "prepared" if not operation.error else "failed"
                emit({"type": "prepared", "preview": asdict(preview)})
            elif state == "prepared" and kind == "execute" and message.get("operation_id") == operation.operation_id:
                state = "done"
                capture = message.get("capture")
                if capture is not None:
                    if (not isinstance(capture, dict) or set(capture) != {"execution_key", "generation"}
                            or not isinstance(capture["execution_key"], str)
                            or not re.fullmatch(r"[A-Za-z0-9:_-]{1,256}", capture["execution_key"])
                            or type(capture["generation"]) is not int or capture["generation"] < 0):
                        raise ValueError()
                from weizhcode.compact.capture import worker_file_capture
                file_capture = {} if capture is not None and operation.call.name == "read_file" else None
                token = worker_file_capture.set(file_capture)
                try:
                    result = registry.get(operation.call.name).execute(operation, context)
                finally:
                    worker_file_capture.reset(token)
                if capture is not None:
                    if file_capture and not result.is_error:
                        emit({"type": "file_capture", "operation_id": operation.operation_id,
                              **capture, **file_capture})
                    from weizhcode.compact.capture import result_capture_frames
                    for frame in result_capture_frames(result, operation_id=operation.operation_id, **capture):
                        if len(json.dumps(frame, ensure_ascii=False).encode()) > 128*1024:
                            raise ValueError()
                        emit(frame)
                # 公开DTO仍有原最终预算；捕获不混入metadata或provider_payload。
                emit({"type": "result", "result": json.loads(result.to_model_text())})
            else:
                state = "failed"
                emit({"type": "error", "message": "非法指令、错误操作 ID 或重复执行"})
        except Exception:
            state = "failed"
            emit({"type": "error", "message": "工具工作进程协议错误"})


if __name__ == "__main__":
    main()

