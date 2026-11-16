from __future__ import annotations

import os
from pathlib import Path
import stat
from uuid import uuid4

import yaml

from .rules import exact_rule, rule_key
from .sandbox import recheck, resolve_target
from .settings import parse_settings, read_settings
from .types import PermissionFailure, SaveResult


def merge_allow(settings, target):
    rule = exact_rule(target)
    if any(rule_key(entry) == rule_key(rule) for entry in settings.rules.allow):
        return None
    data = settings.data
    block = data.setdefault("permissions", {})
    block.setdefault("allow", []).append(rule.original)
    raw = yaml.safe_dump(data, allow_unicode=True, sort_keys=False).encode("utf-8")
    parsed = parse_settings(raw)
    if parsed.data != data:
        raise PermissionFailure("SAVE_ROUNDTRIP", "配置不能安全往返，未保存")
    return raw


def persist_allow(target, path: Path, root, *, resource_created=None, transaction_id=None):
    """Synchronous transaction. Only called inside an owned permission process."""
    stamp = resolve_target(str(path), root)
    destination = Path(stamp.canonical_target)
    settings = read_settings(destination)  # Never replace an invalid file with empty settings.
    raw = merge_allow(settings, target)
    if raw is None:
        return SaveResult(True, True, committed=True)
    temp = destination.with_name(f".settings.local.{transaction_id or uuid4().hex}.tmp")
    identity = None
    try:
        recheck(stamp, root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        recheck(stamp, root)
        resolve_target(str(temp), root)
        mode = stat.S_IMODE(destination.stat().st_mode) if settings.status == "loaded" else 0o600
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        with os.fdopen(fd, "wb") as stream:
            info = os.fstat(stream.fileno())
            identity = (info.st_dev, info.st_ino)
            if resource_created:
                resource_created(temp, identity)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        recheck(stamp, root)
        current = read_settings(destination)
        if current.fingerprint != settings.fingerprint:
            raise PermissionFailure("SAVE_CONFLICT", "本地权限文件已改变，未覆盖")
        os.replace(temp, destination)
        return SaveResult(True, committed=True)
    finally:
        if identity is not None:
            try:
                info = temp.lstat()
                if not stat.S_ISLNK(info.st_mode) and (info.st_dev, info.st_ino) == identity:
                    temp.unlink()
            except FileNotFoundError:
                pass
