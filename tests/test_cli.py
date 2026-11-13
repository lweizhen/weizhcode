from pathlib import Path

from weizhcode import cli
from weizhcode.models import AppConfig, ProviderConfig
from weizhcode.errors import ConfigError
from weizhcode.config import load_config


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
