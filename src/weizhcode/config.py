from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, cast

import yaml

from weizhcode.errors import ConfigError
from weizhcode.models import AppConfig, ProtocolName, ProviderConfig


REQUIRED_PROVIDER_FIELDS = {
    "name",
    "protocol",
    "model",
    "base_url",
    "api_key",
    "thinking",
}
VALID_PROTOCOLS = {"anthropic", "openai", "qwen"}
ENV_REF_RE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


def load_config(path: Path = Path("weizhcode.yaml")) -> AppConfig:
    if not path.exists():
        raise ConfigError(f"配置文件不存在：{path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"配置文件不是合法 YAML：{exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("配置文件顶层必须是对象，包含 default 和 providers。")

    default = raw.get("default")
    if not isinstance(default, str) or not default.strip():
        raise ConfigError("配置缺少有效的 default 字段。")

    providers_raw = raw.get("providers")
    if not isinstance(providers_raw, list) or not providers_raw:
        raise ConfigError("配置缺少有效的 providers 列表。")

    providers = [_parse_provider(item, index) for index, item in enumerate(providers_raw)]
    config = AppConfig(default=default, providers=providers)
    resolve_default_provider(config)
    return config


def resolve_default_provider(config: AppConfig) -> ProviderConfig:
    for provider in config.providers:
        if provider.name == config.default:
            return provider
    raise ConfigError(f"默认供应商 {config.default!r} 不存在于 providers 列表中。")


def _parse_provider(raw: Any, index: int) -> ProviderConfig:
    if not isinstance(raw, dict):
        raise ConfigError(f"providers[{index}] 必须是对象。")

    missing = sorted(REQUIRED_PROVIDER_FIELDS - set(raw))
    if missing:
        raise ConfigError(f"providers[{index}] 缺少字段：{', '.join(missing)}。")

    name = _require_text(raw, "name", index)
    protocol_raw = _require_text(raw, "protocol", index)
    if protocol_raw not in VALID_PROTOCOLS:
        raise ConfigError(
            f"providers[{index}].protocol 只能是 anthropic、openai 或 qwen。"
        )
    protocol = cast(ProtocolName, protocol_raw)

    model = _require_text(raw, "model", index)
    base_url = _require_text(raw, "base_url", index).rstrip("/")
    api_key = _resolve_api_key(_require_text(raw, "api_key", index))

    thinking = raw.get("thinking")
    if not isinstance(thinking, bool):
        raise ConfigError(f"providers[{index}].thinking 必须是 true 或 false。")

    return ProviderConfig(
        name=name,
        protocol=protocol,
        model=model,
        base_url=base_url,
        api_key=api_key,
        thinking=thinking,
    )


def _require_text(raw: dict[str, Any], field: str, index: int) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"providers[{index}].{field} 必须是非空字符串。")
    return value.strip()


def _resolve_api_key(value: str) -> str:
    match = ENV_REF_RE.match(value)
    if not match:
        return value

    env_name = match.group(1)
    env_value = os.environ.get(env_name)
    if not env_value:
        raise ConfigError(f"环境变量 {env_name} 未设置，无法读取 api_key。")
    return env_value

