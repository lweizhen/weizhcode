from dataclasses import replace
from pathlib import Path

import pytest

from weizhcode.permissions.persist import merge_allow, persist_allow
from weizhcode.permissions.sandbox import make_root
from weizhcode.permissions.settings import parse_settings, read_settings
from weizhcode.permissions.types import Category, PermissionFailure, PermissionTarget


def target():
    return PermissionTarget("run_command", "Bash", Category.EXEC, "echo *(hi)", "echo *(hi)")


def test_merge():
    before = parse_settings(b"default_mode: default\npermissions: {deny: [Read]}\next: {value: 3}")
    after = parse_settings(merge_allow(before, target()))
    assert after.data["ext"] == before.data["ext"]
    assert after.rules.deny == before.rules.deny
    assert merge_allow(after, target()) is None


def test_atomic(tmp_path):
    root = make_root(tmp_path)
    path = tmp_path / ".weizhcode/settings.local.yaml"
    result = persist_allow(target(), path, root)
    assert result.saved and result.committed and read_settings(path).rules.allow[0].is_exact
    assert persist_allow(target(), path, root).already_present
    assert not list(path.parent.glob("*.tmp"))


def test_failure_cleanup(tmp_path, monkeypatch):
    import weizhcode.permissions.persist as module
    path = tmp_path / "settings.yaml"
    path.write_text("ext: 4\n", encoding="utf-8")
    before = path.read_bytes()
    def fail(*args):
        raise OSError("injected")
    monkeypatch.setattr(module.os, "replace", fail)
    with pytest.raises(OSError):
        persist_allow(target(), path, make_root(tmp_path))
    assert path.read_bytes() == before and not list(tmp_path.glob("*.tmp"))
    path.write_text("permissions: wrong", encoding="utf-8")
    with pytest.raises(PermissionFailure):
        persist_allow(target(), path, make_root(tmp_path))
