from dataclasses import dataclass
from urllib.parse import urlsplit


CACHE_RULE_VERSION = "2026-11-15.1"
OPENAI_EXPLICIT_MODELS = frozenset({"gpt-5.6", "gpt-6.1-sol", "gpt-6.1-terra"})


@dataclass(frozen=True)
class CachePolicy:
    strategy: str
    reason: str
    version: str = CACHE_RULE_VERSION


def select_cache_policy(config):
    fallback = CachePolicy("prefix_only", "端点或模型的显式缓存能力未确认")
    try:
        url = urlsplit(config.base_url)
        if (url.scheme != "https" or url.port not in {None, 443} or url.username is not None
                or url.password is not None or url.path.rstrip("/") != "/v1"
                or url.query or url.fragment):
            return fallback
        if config.protocol == "anthropic" and url.hostname == "api.anthropic.com" and config.model.startswith("claude-"):
            return CachePolicy("anthropic_explicit", "官方 Claude 稳定 system 内容块边界")
        if config.protocol == "openai" and url.hostname == "api.openai.com" and config.model in OPENAI_EXPLICIT_MODELS:
            return CachePolicy("openai_explicit", "官方 Responses 已核对精确模型")
    except (ValueError, TypeError, AttributeError):
        pass
    return fallback
