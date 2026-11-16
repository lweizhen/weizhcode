from pathlib import Path

import pytest

from weizhcode.permissions.settings import MAX_BYTES, load_layers, parse_settings
from weizhcode.permissions.types import PermissionFailure, PermissionMode


@pytest.mark.parametrize("text", [
    "[]", "permissions: []", "default_mode: normal", "default_mode: unknown",
    "permissions:\n  allow: [Nope(x)]", "permissions:\n  allow: [Bash]\n  allow: []",
    "permissions:\n  deny: [3]", "extra: &loop [*loop]", "x: !!python/object:builtins.object {}",
])
def test_safe_load_invalid(text):
    with pytest.raises(PermissionFailure):
        parse_settings(text.encode())


def test_safe_load_limits():
    for raw in (b" " * (MAX_BYTES + 1), ("permissions:\n  allow:\n" + "    - Bash\n" * 1025).encode(),
                ("x: " + "[" * 20 + "0" + "]" * 20).encode()):
        with pytest.raises(PermissionFailure):
            parse_settings(raw)
    settings = parse_settings(b"default_mode: default\npermissions:\n  allow: ['Bash(git *)']\next: {a: 1}")
    data = settings.data
    data["ext"]["a"] = 9
    assert settings.data["ext"]["a"] == 1


def test_layers(tmp_path):
    root, home = tmp_path / "root", tmp_path / "home"
    root.mkdir()
    home.mkdir()
    settings, warnings, paths = load_layers(root, home)
    assert not warnings and all(s.status == "missing" for s in settings.values())
    for layer, text in (("user", "default_mode: default"), ("project", "default_mode: bypassPermissions"),
                        ("local", "default_mode: bad\npermissions: {deny: [Bash]}")):
        paths[layer].parent.mkdir(parents=True, exist_ok=True)
        paths[layer].write_text(text, encoding="utf-8")
    settings, warnings, _ = load_layers(root, home)
    assert settings["project"].default_mode == PermissionMode.BYPASS
    assert settings["local"].rules.deny == () and warnings[0].layer == "local"


def test_safe_load_exact_limits():
    assert parse_settings(b" " * MAX_BYTES).data == {}
    raw = ("permissions:\n  allow:\n" + "    - Bash\n" * 1024).encode()
    assert len(parse_settings(raw).rules.allow) == 1024
    value = "Bash(" + "x" * (8192 - 6) + ")"
    assert len(value) == 8192
    assert len(parse_settings(("permissions:\n  allow:\n    - " + value).encode()).rules.allow) == 1
    with pytest.raises(PermissionFailure):
        parse_settings(("permissions:\n  allow:\n    - " + value[:-1] + "x)").encode())
    assert parse_settings(("x: " + "[" * 14 + "0" + "]" * 14).encode()).data
    with pytest.raises(PermissionFailure):
        parse_settings(("x: " + "[" * 15 + "0" + "]" * 15).encode())
