from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal


@dataclass(frozen=True)
class ProviderFault:
    """只保留结构化安全事实；不保存响应全文或认证头。"""

    protocol: str
    safe_code: str = ""
    http_status: int | None = None
    kind: Literal["context_length", "authentication", "quota", "rate_limit", "network",
                  "server", "invalid_request", "unknown"] = "unknown"
    param: str = ""

    @property
    def message(self) -> str:
        return {"context_length": "模型请求超过上下文窗口", "authentication": "模型认证失败",
                "quota": "模型额度不足", "rate_limit": "模型请求受限", "network": "模型网络请求失败",
                "server": "模型服务异常", "invalid_request": "模型请求参数无效"}.get(self.kind, "模型请求失败")


class WeizhCodeError(Exception):
    """Base class for user-facing weizhCode errors."""


class ConfigError(WeizhCodeError):
    """Raised when configuration is missing or invalid."""


class ProviderError(WeizhCodeError):
    """Raised when a provider cannot be created or used."""


class StreamError(ProviderError):
    """Raised when a streaming response fails."""

    def __init__(self, message: str, *, fault: ProviderFault | None = None):
        super().__init__(message)
        self.fault = fault


def classify_provider_fault(protocol, payload=None, *, http_status=None, finish_reason="") -> ProviderFault:
    """只认结构化来源和严格长度信号，返回值不保留原始正文。"""
    if http_status in {401, 403}:
        return ProviderFault(protocol, f"http_{http_status}", http_status, "authentication")
    if http_status == 429:
        return ProviderFault(protocol, "http_429", http_status, "rate_limit")
    if isinstance(http_status, int) and http_status >= 500:
        return ProviderFault(protocol, "http_server_error", http_status, "server")
    payload = payload if isinstance(payload, dict) else {}
    response = payload.get("response")
    container = response if isinstance(response, dict) else payload
    error = container.get("error")
    error = error if isinstance(error, dict) else container
    code, error_type = error.get("code"), error.get("type")
    message = error.get("message", "")
    message = message if isinstance(message, str) else ""
    param = error.get("param")
    param = param if isinstance(param, str) and param in {"input", "messages", "max_tokens", "max_output_tokens"} else ""
    allowed = {"context_length_exceeded", "invalid_request_error", "invalid_prompt", "InvalidParameter",
               "invalid_parameter_error", "insufficient_quota", "AllocationQuota.FreeTierOnly"}
    safe_code = code if isinstance(code, str) and code in allowed else ""
    if not safe_code and isinstance(error_type, str) and error_type in allowed:
        safe_code = error_type
    if safe_code in {"insufficient_quota", "AllocationQuota.FreeTierOnly"}:
        return ProviderFault(protocol, safe_code, http_status, "quota", param)
    length = False
    if http_status in {None, 400}:
        if protocol in {"openai", "qwen"} and code == "context_length_exceeded":
            length = True
        elif protocol == "anthropic":
            length = (finish_reason == "model_context_window_exceeded" or
                (error_type == "invalid_request_error" and re.fullmatch(
                    r"prompt is too long: [0-9]+ tokens > [0-9]+ maximum\.?", message) is not None))
        elif protocol == "qwen" and http_status == 400:
            # 官方输入长度格式；max_tokens范围错误不匹配此模式。
            length = (safe_code in {"InvalidParameter", "invalid_parameter_error"} and
                re.fullmatch(r"Range of input length should be \[1,\s*[1-9][0-9]*\]\.?", message) is not None)
    kind = "context_length" if length else "invalid_request" if http_status == 400 else "unknown"
    return ProviderFault(protocol, safe_code, http_status, kind, param)


def safe_finish_reason(protocol, value):
    allowed = {"anthropic": {"end_turn", "tool_use", "stop_sequence", "max_tokens", "refusal", "pause_turn",
                              "model_context_window_exceeded"},
               "openai": {"completed", "failed", "incomplete", "max_output_tokens", "content_filter"},
               "qwen": {"stop", "tool_calls", "length", "content_filter"}}
    if value is None or value == "":
        return ""
    return value if isinstance(value, str) and value in allowed.get(protocol, set()) else "unknown"


def redact_secret(text: str, secret: str | None = None) -> str:
    """Remove obvious secret values from text before showing it to users."""
    import re
    from weizhcode.redaction import Redactor

    redacted = Redactor((secret,)).text(text)
    return re.sub(r"sk[-_][^\s\"'<>]+", "[redacted]", redacted)

