import asyncio
from pathlib import Path
from dataclasses import replace
import os

import pytest

from weizhcode.mcp.control import McpControl
from weizhcode.mcp.contracts import McpServerConfig
from weizhcode.mcp.trust import read_bytes, atomic, git_safe, get_key, remember, inspect_trust


def roots(tmp_path):
    root, home = tmp_path / "project", tmp_path / "home"
    root.mkdir()
    home.mkdir(mode=0o700)
    return root.resolve(), home.resolve()


async def test_control_config_store_windows_key_native(tmp_path):
    root, home = roots(tmp_path)
    (root / ".weizhcode").mkdir()
    (root / ".weizhcode/mcp.yaml").write_text("mcp_servers:\n  demo:\n    type: stdio\n    command: python\n", encoding="utf-8")
    control = McpControl(root, home)
    try:
        snapshot = await control.load()
        assert len(snapshot.servers) == 1 and snapshot.servers[0].source == "project"
        config = snapshot.servers[0]
        assert not await control.inspect([config])
        result = await control.remember(config)
        assert result.saved and result.committed
        assert await control.inspect([config]) == ("demo",)
        assert not await control.inspect([replace(config, args=("changed",))])
        raw = (root / ".weizhcode/mcp-trust.local.json").read_text()
        assert "python" not in raw
        assert not control.active
    finally:
        await control.aclose()


def test_fingerprint_forgery_secret_changes(tmp_path):
    root, home = roots(tmp_path)
    config = McpServerConfig("demo", "project", "http", url="https://example.invalid/mcp", headers_json='{"authorization":"Bearer synthetic-secret"}')
    remember(root, home, config)
    assert inspect_trust(root, home, [config]) == ["demo"]
    assert inspect_trust(root, home, [replace(config, headers_json='{"authorization":"changed"}')]) == []
    record = root / ".weizhcode/mcp-trust.local.json"
    assert "synthetic-secret" not in record.read_text()
    record.write_text('{"body":{"version":1,"entries":{"demo":"fake"}},"signature":"fake"}')
    with pytest.raises(ValueError):
        inspect_trust(root, home, [config])


def test_atomic_conflict_preserves_file(tmp_path):
    (tmp_path / "a").write_bytes(b"original")
    with pytest.raises(ValueError):
        atomic(tmp_path.resolve(), "a", b"replacement", b"wrong expected")
    assert (tmp_path / "a").read_bytes() == b"original"
    assert not list(tmp_path.glob("*.tmp"))


def test_git_guard(tmp_path):
    import subprocess
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    path = tmp_path / ".weizhcode/mcp-trust.local.json"
    assert not git_safe(path)
    (tmp_path / ".gitignore").write_text(".weizhcode/mcp-trust.local.json\n.weizhcode/.mcp-trust.*.tmp\n")
    assert git_safe(path)


@pytest.mark.skipif(os.name == "nt", reason="POSIX native permission branch")
def test_posix_key(tmp_path):
    root, home = roots(tmp_path)
    assert len(get_key(home, create=True)) == 32
    (home / ".weizhcode/mcp-trust.key").chmod(0o644)
    with pytest.raises(ValueError):
        get_key(home)
