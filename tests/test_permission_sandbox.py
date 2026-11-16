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


@pytest.mark.skipif(os.name != "nt", reason="Windows 路径原生分支")
def test_windows(tmp_path):
    root = make_root(tmp_path)
    assert resolve_target(str(tmp_path / "x"), root).project_relative == "x"
    assert resolve_target("\\\\?\\" + str(tmp_path / "x"), root).project_relative == "x"
    for path in (r"\\.\PhysicalDrive0", str(tmp_path / "x") + ":stream", "C:relative", "NUL"):
        with pytest.raises(PermissionFailure):
            resolve_target(path, root)
    for path in ("Z:\\outside", r"\\nonexistent-permission-test\share\outside"):
        with pytest.raises(PermissionFailure):
            resolve_target(path, root)


@pytest.mark.skipif(os.name != "nt", reason="Windows junction 原生分支")
def test_windows_junction_resolution(tmp_path):
    import subprocess
    root, outside = tmp_path / "root", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    link = root / "link"
    assert link.parent.resolve() == root.resolve() and outside.parent.resolve() == tmp_path.resolve()
    created = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)],
                             capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    if created.returncode:
        pytest.skip("本机不能创建 junction")
    for path in ("link/a", "link/../a", "missing/../link/a"):
        with pytest.raises(PermissionFailure):
            resolve_target(path, make_root(root))


def test_root_changed(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    identity = make_root(root)
    root.rename(tmp_path / "old")
    root.mkdir()
    with pytest.raises(PermissionFailure):
        resolve_target("file", identity)
