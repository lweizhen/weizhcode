from dataclasses import asdict
from pathlib import Path

from .persist import persist_allow
from .sandbox import resolve_target
from .types import Category, PermissionFailure, PermissionTarget, RootIdentity


def handle(message, context, *, resource_created=None):
    try:
        root = RootIdentity(**message["root"])
        if Path(root.canonical_root) != context.project_root:
            raise PermissionFailure("PERMISSION_ROOT_UNAVAILABLE", "辅助进程根不一致")
        if message["type"] == "inspect_permission_path":
            return {"result": asdict(resolve_target(message["raw_path"], root))}
        data = message["target"]
        # Only the application can request this operation, never a model tool name.
        target = PermissionTarget(data["internal_name"], data["friendly_name"], Category(data["category"]),
                                  data["match_target"], data.get("command"))
        if data.get("external_identity") is not None:
            from dataclasses import replace
            from weizhcode.mcp.contracts import McpToolIdentity
            identity = McpToolIdentity(**data["external_identity"])
            if identity.full_name != target.internal_name or target.match_target != identity.full_name:
                raise ValueError()
            target = replace(target, external_identity=identity)
        destination = context.project_root / ".weizhcode/settings.local.yaml"
        stamp = resolve_target(str(destination), root)
        if Path(stamp.canonical_target) != destination:
            raise PermissionFailure("SAVE_REDIRECTED", "本地权限配置被重定向，未自动保存")
        return {"result": asdict(persist_allow(target, destination, root,
                                  resource_created=resource_created, transaction_id=message["request_id"]))}
    except PermissionFailure as exc:
        return {"error_code": exc.code, "reason": str(exc)}
    except (OSError, ValueError, TypeError, KeyError):
        return {"error_code": "PERMISSION_IO_ERROR", "reason": "权限辅助操作失败，未确认授权"}
