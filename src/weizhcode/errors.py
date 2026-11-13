from __future__ import annotations


class WeizhCodeError(Exception):
    """Base class for user-facing weizhCode errors."""


class ConfigError(WeizhCodeError):
    """Raised when configuration is missing or invalid."""


class ProviderError(WeizhCodeError):
    """Raised when a provider cannot be created or used."""


class StreamError(ProviderError):
    """Raised when a streaming response fails."""


def redact_secret(text: str, secret: str | None = None) -> str:
    """Remove obvious secret values from text before showing it to users."""
    import re
    from weizhcode.redaction import Redactor

    redacted = Redactor((secret,)).text(text)
    return re.sub(r"sk[-_][^\s\"'<>]+", "[redacted]", redacted)

