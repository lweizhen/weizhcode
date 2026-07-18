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
    redacted = text
    if secret:
        redacted = redacted.replace(secret, "[redacted]")
    for marker in ("sk-", "sk_"):
        if marker in redacted:
            prefix, _, suffix = redacted.partition(marker)
            tail = suffix.split()[0] if suffix else ""
            redacted = redacted.replace(f"{marker}{tail}", "[redacted]")
    return redacted

