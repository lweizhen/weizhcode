import json
from pathlib import Path
import sys

from weizhcode.bootstrap import ApplicationBootstrap
from weizhcode.redaction import Redactor


def test_startup_prompt_authorization_no_tty(tmp_path):
    from weizhcode.mcp.startup import StartupTrustPrompt
    root, home = tmp_path / "root", tmp_path / "home"
    root.mkdir()
    home.mkdir()
    (root / ".weizhcode").mkdir()
    fixture = Path(__file__).parent / "fixtures/mcp_stdio_server.py"
    (root / ".weizhcode/mcp.yaml").write_text(json.dumps({"mcp_servers": {"demo": {"type": "stdio", "command": sys.executable, "args": [str(fixture)]}}}))
    prompt = StartupTrustPrompt(Redactor(), output=lambda text: None, is_tty=False)
    bootstrap = ApplicationBootstrap(root, home, Redactor()).prepare(prompt)
    assert not bootstrap.authorized.tickets
    assert not bootstrap.manager.hosts


def test_ctx_t61_mcp_bootstrap_cli_same_loop(monkeypatch, tmp_path):
    from weizhcode import cli
    import weizhcode.bootstrap as module
    from weizhcode.models import AppConfig, ProviderConfig
    root, home = tmp_path / "root", tmp_path / "home"
    root.mkdir()
    home.mkdir()
    (root / ".weizhcode").mkdir()
    fixture = Path(__file__).parent / "fixtures/mcp_stdio_server.py"
    (root / ".weizhcode/mcp.yaml").write_text(json.dumps({"mcp_servers": {"demo": {"type": "stdio", "command": sys.executable, "args": [str(fixture)]}}}))
    monkeypatch.chdir(root)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(cli, "load_config", lambda: AppConfig("test", [ProviderConfig("test", "qwen", "fake", "https://example.invalid", "synthetic-key")]))
    class Prompt:
        def choose(self, request):
            return "trust"
    monkeypatch.setattr(module, "StartupTrustPrompt", lambda safe: Prompt())
    captured = {}
    class App:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)
        async def run_async(self):
            runner = captured["runner"]
            assert runner.registry.external_identity("mcp__demo__echo") is not None
            assert runner.executor.mcp_manager.snapshot().servers[0].state == "ready"
            assert runner.context_runtime is runner.executor.context_runtime
            assert runner.context_manager.runtime is runner.context_runtime
            assert runner.context_runtime.store is not None
    monkeypatch.setattr(cli, "WeizhCodeApp", App)
    cli.main()
    manager = captured["runner"].executor.mcp_manager
    assert manager.hosts["demo"].process.returncode is not None


def test_manual_mcp_guards(monkeypatch, capsys):
    import manual_mcp_smoke as manual
    import weizhcode.config
    def forbidden(*args, **kwargs):
        raise AssertionError("Must not read real credentials")
    monkeypatch.setattr(weizhcode.config, "load_config", forbidden)
    assert manual.main([]) == 0
    assert "未读取凭据" in capsys.readouterr().out
    import pytest
    with pytest.raises(SystemExit):
        manual.main(["--terminal", "--live"])


def test_root_replaced_during_consent_never_authorized(tmp_path):
    import pytest
    from weizhcode.permissions.types import PermissionFailure
    root, home = tmp_path / "root", tmp_path / "home"
    root.mkdir()
    home.mkdir()
    (root / ".weizhcode").mkdir()
    (root / ".weizhcode/mcp.yaml").write_text('mcp_servers: {demo: {type: stdio, command: python}}')
    bootstrap = ApplicationBootstrap(root, home, Redactor())
    class Prompt:
        def choose(self, request):
            root.rename(tmp_path / "old-root")
            root.mkdir()
            return "trust"
    with pytest.raises(PermissionFailure):
        bootstrap.prepare(Prompt())
    assert not bootstrap.authorized.tickets and not bootstrap.manager.hosts
    assert not (root / ".weizhcode/mcp-trust.local.json").exists()
