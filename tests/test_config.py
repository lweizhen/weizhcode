from __future__ import annotations

from pathlib import Path

import pytest

from weizhcode.config import load_config, resolve_default_provider
from weizhcode.errors import ConfigError


def write_config(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def valid_config() -> str:
    return """
default: openai-main
providers:
  - name: openai-main
    protocol: openai
    model: gpt-5.6
    base_url: https://api.openai.com/v1
    api_key: ${OPENAI_API_KEY}
    thinking: false
"""


def test_loads_valid_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    config = load_config(write_config(tmp_path / "weizhcode.yaml", valid_config()))

    provider = resolve_default_provider(config)

    assert config.default == "openai-main"
    assert provider.protocol == "openai"
    assert provider.api_key == "sk-test"


def test_missing_top_level_default(tmp_path: Path) -> None:
    path = write_config(
        tmp_path / "weizhcode.yaml",
        """
providers: []
""",
    )

    with pytest.raises(ConfigError, match="default"):
        load_config(path)


def test_missing_provider_field(tmp_path: Path) -> None:
    path = write_config(
        tmp_path / "weizhcode.yaml",
        """
default: demo
providers:
  - name: demo
    protocol: openai
    model: gpt-5.6
    api_key: sk-test
    thinking: false
""",
    )

    with pytest.raises(ConfigError, match="base_url"):
        load_config(path)


def test_invalid_protocol(tmp_path: Path) -> None:
    path = write_config(
        tmp_path / "weizhcode.yaml",
        """
default: demo
providers:
  - name: demo
    protocol: other
    model: gpt-5.6
    base_url: https://example.test/v1
    api_key: sk-test
    thinking: false
""",
    )

    with pytest.raises(ConfigError, match="protocol"):
        load_config(path)


def test_default_provider_must_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    path = write_config(
        tmp_path / "weizhcode.yaml",
        valid_config().replace("default: openai-main", "default: missing"),
    )

    with pytest.raises(ConfigError, match="默认供应商"):
        load_config(path)


def test_missing_env_var_is_reported_without_secret(tmp_path: Path) -> None:
    path = write_config(tmp_path / "weizhcode.yaml", valid_config())

    with pytest.raises(ConfigError) as exc_info:
        load_config(path)

    message = str(exc_info.value)
    assert "OPENAI_API_KEY" in message
    assert "${OPENAI_API_KEY}" not in message


def test_missing_env_var_for_non_default_provider_is_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", "qwen-key")
    path = write_config(
        tmp_path / "weizhcode.yaml",
        """
default: qwen-main
providers:
  - name: anthropic-main
    protocol: anthropic
    model: claude-sonnet-5
    base_url: https://api.anthropic.com/v1
    api_key: ${ANTHROPIC_API_KEY}
    thinking: false
  - name: qwen-main
    protocol: qwen
    model: qwen-plus
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key: ${DASHSCOPE_API_KEY}
    thinking: false
""",
    )

    config = load_config(path)

    assert resolve_default_provider(config).api_key == "qwen-key"


def test_direct_api_key_is_allowed(tmp_path: Path) -> None:
    config = load_config(
        write_config(
            tmp_path / "weizhcode.yaml",
            valid_config().replace("${OPENAI_API_KEY}", "direct-key"),
        )
    )

    assert resolve_default_provider(config).api_key == "direct-key"


def test_thinking_must_be_boolean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    path = write_config(
        tmp_path / "weizhcode.yaml",
        valid_config().replace("thinking: false", "thinking: nope"),
    )

    with pytest.raises(ConfigError, match="thinking"):
        load_config(path)
