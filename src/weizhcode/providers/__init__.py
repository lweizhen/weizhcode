from __future__ import annotations

from weizhcode.errors import ProviderError
from weizhcode.models import ProviderConfig
from weizhcode.providers.anthropic import AnthropicProvider
from weizhcode.providers.base import Provider
from weizhcode.providers.openai import OpenAIProvider
from weizhcode.providers.qwen import QwenProvider


def create_provider(config: ProviderConfig) -> Provider:
    if config.protocol == "anthropic":
        return AnthropicProvider(config)
    if config.protocol == "openai":
        return OpenAIProvider(config)
    if config.protocol == "qwen":
        return QwenProvider(config)
    raise ProviderError(f"未知 Provider 协议：{config.protocol}")


__all__ = [
    "AnthropicProvider",
    "OpenAIProvider",
    "Provider",
    "QwenProvider",
    "create_provider",
]

