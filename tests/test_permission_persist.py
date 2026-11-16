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


def test_atomic_existing_temporary_is_not_overwritten(tmp_path):
    path = tmp_path / "settings.yaml"
    temporary = tmp_path / ".settings.local.fixed.tmp"
    temporary.write_text("not ours", encoding="utf-8")
    with pytest.raises(FileExistsError):
        persist_allow(target(), path, make_root(tmp_path), transaction_id="fixed")
    assert temporary.read_text() == "not ours" and not path.exists()


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


def test_atomic_conflict(tmp_path, monkeypatch):
    import weizhcode.permissions.persist as module
    path = tmp_path / "settings.yaml"
    path.write_text("ext: 1\n", encoding="utf-8")
    original_fsync = module.os.fsync
    def update(fd):
        original_fsync(fd)
        path.write_text("ext: 2\n", encoding="utf-8")
    monkeypatch.setattr(module.os, "fsync", update)
    with pytest.raises(PermissionFailure) as exc:
        persist_allow(target(), path, make_root(tmp_path))
    assert exc.value.code == "SAVE_CONFLICT" and path.read_text() == "ext: 2\n"
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("stage", ["open", "write", "fsync", "replace"])
def test_failure_cleanup_stages(tmp_path, monkeypatch, stage):
    import weizhcode.permissions.persist as module
    path = tmp_path / "settings.yaml"
    path.write_text("ext: 4\n", encoding="utf-8")
    before = path.read_bytes()
    def fail(*args, **kwargs):
        raise OSError("injected")
    if stage == "write":
        original = module.os.fdopen
        class BadStream:
            def __init__(self, *args, **kwargs):
                self.stream = original(*args, **kwargs)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.stream.close()
            def __getattr__(self, key):
                return getattr(self.stream, key)
            def write(self, value):
                fail()
        monkeypatch.setattr(module.os, "fdopen", BadStream)
    else:
        monkeypatch.setattr(module.os, stage, fail)
    with pytest.raises(OSError):
        persist_allow(target(), path, make_root(tmp_path))
    assert path.read_bytes() == before and not list(tmp_path.glob("*.tmp"))
