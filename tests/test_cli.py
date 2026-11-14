from pathlib import Path

from weizhcode import cli
from weizhcode.models import AppConfig, ProviderConfig
from weizhcode.errors import ConfigError
from weizhcode.config import load_config


def test_loop_startup_wiring_new_components_share_dependencies(monkeypatch, tmp_path):
    from weizhcode.turn_runner import TurnRunner
    monkeypatch.setattr(cli, "TurnRunner", TurnRunner)
    providers = [ProviderConfig("active", "qwen", "model", "https://example.test", "active-key", False),
                 ProviderConfig("inactive", "openai", "model", "https://example.test", "${MISSING_OTHER_KEY}", False)]
    monkeypatch.setattr(cli, "load_config", lambda: AppConfig("active", providers))
    captured = {}
    class App:
        def __init__(self, provider, conversation, **kwargs):
            captured.update(kwargs)
            captured["provider"] = provider
        def run(self):
            pass
    monkeypatch.setattr(cli, "WeizhCodeApp", App)
    cli.main()
    runner = captured["runner"]
    assert runner.collector.provider is captured["provider"]
    assert runner.scheduler.executor is runner.executor
    assert runner.scheduler.registry is runner.registry
    assert runner.redactor.secrets == ("active-key",)
    assert runner.mode == "normal" and runner.max_iterations == 25


async def test_manual_smoke_scope_rejects_outside_without_worker(tmp_path):
    import asyncio
    from manual_tool_smoke import SmokeExecutor
    from weizhcode.models import ToolCall, ToolContext, ToolSlot
    from weizhcode.tools import create_default_registry
    executor = SmokeExecutor(create_default_registry(), ToolContext(tmp_path))
    executor.allowed, executor.allowed_paths = {"write_file"}, {"allowed"}
    call = ToolCall("a", "write_file", '{"path":"../outside","content":"bad"}')
    slot, cancel = ToolSlot(0, call), asyncio.Event()
    async def emit(event):
        pass
    result = await executor.execute(slot, mode="normal", cancel=cancel, emit=emit)
    assert result.error_code == "SMOKE_SCOPE" and cancel.is_set() and executor.scope_error
    assert not executor._active and not slot.execution_started


async def test_manual_smoke_scope_allows_readonly_check_inside_root(tmp_path):
    import asyncio
    from manual_tool_smoke import SmokeExecutor
    from weizhcode.models import ToolCall, ToolContext, ToolSlot
    from weizhcode.tools import create_default_registry
    executor = SmokeExecutor(create_default_registry(), ToolContext(tmp_path))
    executor.allowed = {"find_files"}
    slot = ToolSlot(0, ToolCall("a", "find_files", '{"pattern":"planned.txt"}'))
    async def emit(event):
        pass
    result = await executor.execute(slot, mode="normal", cancel=asyncio.Event(), emit=emit)
    assert not result.is_error and not executor.scope_error and slot.execution_started


def test_startup_tools_cli_constructs_all_components(monkeypatch, tmp_path):
    providers = [
        ProviderConfig("active", "qwen", "model", "https://example.test", "active-key", False),
        ProviderConfig("inactive", "openai", "model", "https://example.test", "${MISSING_OTHER_KEY}", False),
    ]
    monkeypatch.setattr(cli, "load_config", lambda: AppConfig("active", providers))
    captured = {}
    class App:
        def __init__(self, provider, conversation, **kwargs):
            captured.update(kwargs)
            captured["conversation"] = conversation
        def run(self):
            captured["ran"] = True
    monkeypatch.setattr(cli, "WeizhCodeApp", App)
    cli.main()
    assert captured["ran"]
    assert len(captured["runner"].registry.definitions()) == 6
    assert captured["runner"].conversation is captured["conversation"]
    assert captured["redactor"].secrets == ("active-key",)


def test_startup_tools_config_failure_uses_error_app(monkeypatch):
    def fail():
        raise ConfigError("环境变量未设置")
    monkeypatch.setattr(cli, "load_config", fail)
    captured = []
    class App:
        def __init__(self, text):
            captured.append(text)
        def run(self):
            captured.append("ran")
    monkeypatch.setattr(cli, "StartupErrorApp", App)
    cli.main()
    assert captured == ["环境变量未设置", "ran"]


def test_security_pipeline_yaml_error_never_quotes_secret(tmp_path):
    import pytest
    path = tmp_path / "bad.yaml"
    path.write_text('api_key: [secret-token\nnext: ]:', encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        load_config(path)
    assert "secret-token" not in str(exc.value)
