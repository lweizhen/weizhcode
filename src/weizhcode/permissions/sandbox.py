"""File-tool path fence, not an OS sandbox. Command file access is not constrained."""
from __future__ import annotations

import os
from pathlib import Path, PureWindowsPath
import stat

from .types import PathStamp, PermissionFailure, RootIdentity


def _identity(path):
    info = path.stat()
    return (info.st_dev, info.st_ino) if info.st_ino else None


def _canonical_key(path):
    value = str(path)
    if os.name == "nt":
        if value.startswith("\\\\?\\UNC\\"):
            value = "\\\\" + value[8:]
        elif value.startswith("\\\\?\\"):
            value = value[4:]
    return os.path.normcase(value)


def make_root(root: Path) -> RootIdentity:
    try:
        target = root.expanduser().resolve(strict=True)
        if not target.is_dir():
            raise OSError()
        return RootIdentity(str(root), str(target), _identity(target))
    except (OSError, ValueError, RuntimeError):
        raise PermissionFailure("PERMISSION_ROOT_UNAVAILABLE", "项目根不可确认，工具未执行") from None


def verify_root(root: RootIdentity):
    try:
        target = Path(root.original_root).expanduser().resolve(strict=True)
        if (_canonical_key(target) != _canonical_key(root.canonical_root) or not target.is_dir()
                or (root.identity is not None and _identity(target) != root.identity)):
            raise OSError()
    except (OSError, ValueError, RuntimeError):
        raise PermissionFailure("PERMISSION_ROOT_UNAVAILABLE", "项目根已改变或不可访问，工具未执行") from None


def _validate_form(value):
    if not isinstance(value, str) or not value or "\0" in value:
        raise PermissionFailure("PATH_UNRESOLVED", "无法解析文件路径，安全拒绝")
    if os.name == "nt":
        win = PureWindowsPath(value)
        if (value.startswith(("\\\\.\\", "\\\\?\\", "//./", "//?/"))
                or (win.drive and not win.root) or (win.root and not win.drive)
                or any(":" in part for part in win.parts[1:])
                or (os.path.isreserved(value) if hasattr(os.path, "isreserved") else win.is_reserved())):
            raise PermissionFailure("PATH_UNRESOLVED", "不支持的 Windows 文件路径形式")


def resolve_target(raw: str, root: RootIdentity) -> PathStamp:
    verify_root(root)
    _validate_form(raw)
    try:
        requested = Path(raw).expanduser()
        requested = requested if requested.is_absolute() else Path(root.canonical_root) / requested
        current = Path(requested.anchor)
        # Resolve existing components before interpreting the next '..'.
        for part in requested.parts[1:]:
            if part == "..":
                current = current.parent
                continue
            if part == ".":
                continue
            current = current / part
            try:
                info = current.lstat()
            except FileNotFoundError:
                continue
            reparse = getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)
            if reparse:
                tag = getattr(info, "st_reparse_tag", None)
                if tag not in {getattr(stat, "IO_REPARSE_TAG_SYMLINK", 0xA000000C),
                               getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003)}:
                    raise PermissionFailure("PATH_UNRESOLVED", "不支持的文件重定向")
            if stat.S_ISLNK(info.st_mode) or reparse:
                current = current.resolve(strict=True)
        root_key, target_key = _canonical_key(root.canonical_root), _canonical_key(current)
        try:
            contained = os.path.commonpath([root_key, target_key]) == root_key
        except ValueError:
            contained = False
        if not contained:
            raise PermissionFailure("PATH_OUTSIDE_PROJECT", "路径在项目目录之外，工具未执行")
        ancestor = current
        exists = True
        while True:
            try:
                ancestor.lstat()
                break
            except FileNotFoundError:
                exists = False
                ancestor = ancestor.parent
        relative = os.path.relpath(current, root.canonical_root).replace(os.sep, "/")
        return PathStamp(raw, str(current), relative, exists, str(ancestor), _identity(ancestor))
    except PermissionFailure:
        raise
    except (OSError, RuntimeError, ValueError):
        raise PermissionFailure("PATH_UNRESOLVED", "无法确认文件真实路径，安全拒绝") from None


def recheck(stamp: PathStamp, root: RootIdentity) -> PathStamp:
    current = resolve_target(stamp.original, root)
    if _canonical_key(current.canonical_target) != _canonical_key(stamp.canonical_target):
        raise PermissionFailure("PERMISSION_TARGET_CHANGED", "目标已变化，请重新发起工具调用")
    return current
