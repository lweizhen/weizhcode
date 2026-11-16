import os
from pathlib import Path

import pytest

from weizhcode.permissions.sandbox import make_root, recheck, resolve_target
from weizhcode.permissions.types import PermissionFailure


def test_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    identity = make_root(root)
    assert resolve_target("a/b/c", identity).project_relative == "a/b/c"
    for target in (str(tmp_path / "root-other/a"), "../outside"):
        with pytest.raises(PermissionFailure, match="项目目录之外"):
            resolve_target(target, identity)
    with pytest.raises(PermissionFailure):
        make_root(root / "missing")


def test_resolution(tmp_path):
    root, outside = tmp_path / "root", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    link = root / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("当前环境不能创建原生目录链接")
    identity = make_root(root)
    for path in ("link/file", "link/../file", "missing/../link/file"):
        with pytest.raises(PermissionFailure):
            resolve_target(path, identity)


def test_resolution_recheck(tmp_path):
    identity = make_root(tmp_path)
    stamp = resolve_target("a/b.txt", identity)
    (tmp_path / "a").mkdir()
    assert recheck(stamp, identity).canonical_target == stamp.canonical_target
    with pytest.raises(PermissionFailure):
        resolve_target("x\0y", identity)
