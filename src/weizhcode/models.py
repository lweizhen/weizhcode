from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal
from uuid import uuid4


ProtocolName = Literal["anthropic", "openai", "qwen"]
MessageRole = Literal["user", "assistant", "tool"]
ProviderEventType = Literal["start", "text_delta", "tool_call_start", "tool_call", "done", "error"]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, object]
    requires_confirmation: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", deepcopy(self.parameters))


@dataclass(frozen=True)
class ToolCall:
    call_id: str | None
    name: str
    raw_arguments: str
    arguments: dict[str, object] | None = None
    local_id: str = field(default_factory=lambda: uuid4().hex)

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", deepcopy(self.arguments))


def parse_tool_arguments(raw: str) -> dict | None:
    def reject_constant(value):
        raise ValueError("非法 JSON 常量")
    try:
        value = json.loads(raw, parse_constant=reject_constant)
        return value if isinstance(value, dict) else None
    except (ValueError, TypeError, RecursionError):
        return None


def wire_calls_valid(calls) -> bool:
    ids = [call.call_id for call in calls]
    return (all(isinstance(value, str) and 0 < len(value) <= 512 for value in ids)
            and len(set(ids)) == len(ids)
            and all(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", call.name)
                    and parse_tool_arguments(call.raw_arguments) is not None for call in calls))


@dataclass(frozen=True)
class ToolResult:
    call_id: str | None
    tool_name: str
    content: str = ""
    status: Literal["success", "error", "denied", "timeout"] = "success"
    error_code: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    truncated: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", deepcopy(self.metadata))

    @property
    def is_error(self) -> bool:
        return self.status != "success"

    @classmethod
    def failure(cls, call: ToolCall, code: str, message: str, **metadata: object) -> ToolResult:
        status = {"USER_DENIED": "denied", "TOOL_TIMEOUT": "timeout"}.get(code, "error")
        return cls(call.call_id, call.name, message, status, code, metadata)  # type: ignore[arg-type]

    def to_model_text(self, max_chars: int = 20_000) -> str:
        """最终序列化结果也计入预算，不丢掉退出码等必要标量。"""
        if max_chars < 512:
            raise ValueError("结果预算不得小于 512 字符")
        data = asdict(self)
        dump = lambda: json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)
        if len(dump()) <= max_chars:
            return dump()
        data["truncated"] = True
        data["content"] = ""
        # 元数据不能绕过正文预算。标量数字/布尔值始终保留。
        metadata = data["metadata"]
        for key, value in list(metadata.items()):
            if not isinstance(value, (int, float, bool, type(None))):
                metadata[key] = str(value)[:512]
        if len(dump()) > max_chars - 64:
            data["metadata"] = {k: v for k, v in metadata.items() if isinstance(v, (int, float, bool, type(None)))}
        for key in ("call_id", "tool_name", "error_code"):
            if isinstance(data[key], str):
                data[key] = data[key][:64]
        for key in list(data["metadata"]):
            if len(dump()) <= max_chars - 64:
                break
            if key not in {"exit_code", "match_count", "next_start_line"}:
                del data["metadata"][key]
        marker = "\n[truncated]"
        low, high = 0, len(self.content)
        while low < high:
            mid = (low + high + 1) // 2
            data["content"] = self.content[:mid] + marker
            if len(dump()) <= max_chars:
                low = mid
            else:
                high = mid - 1
        data["content"] = self.content[:low] + marker
        return dump()


@dataclass(frozen=True)
class ToolContext:
    project_root: Path


@dataclass(frozen=True)
class FileSnapshot:
    original: str
    target: str
    exists: bool
    identity: tuple[int, int] | None = None
    sha256: str | None = None
    bom: bool = False
    newline: str = "\n"
    mode: int | None = None


@dataclass(frozen=True)
class PreparedOperation:
    call: ToolCall
    arguments: dict[str, object]
    target: str = ""
    preview: str = ""
    snapshot: FileSnapshot | None = None
    state: dict[str, object] = field(default_factory=dict)
    error: ToolResult | None = None
    operation_id: str = field(default_factory=lambda: uuid4().hex)


@dataclass(frozen=True)
class PreparedOperationPreview:
    operation_id: str
    target: str
    preview: str
    command: str = ""
    cwd: str = ""
    preview_truncated: bool = False
    error: ToolResult | None = None


@dataclass(frozen=True)
class ApprovalRequest:
    request_id: str
    operation_id: str
    local_id: str
    tool_name: str
    target: str
    preview: str
    command: str = ""
    cwd: str = ""
    preview_truncated: bool = False


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    protocol: ProtocolName
    model: str
    base_url: str
    api_key: str
    thinking: bool | None = None


@dataclass(frozen=True)
class AppConfig:
    default: str
    providers: list[ProviderConfig]


@dataclass(frozen=True)
class ChatMessage:
    role: MessageRole
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_results: tuple[ToolResult, ...] = ()
    provider_payload: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tool_calls", deepcopy(tuple(self.tool_calls)))
        object.__setattr__(self, "tool_results", deepcopy(tuple(self.tool_results)))
        object.__setattr__(self, "provider_payload", deepcopy(self.provider_payload))


@dataclass(frozen=True)
class ProviderEvent:
    type: ProviderEventType
    text: str = ""
    message: str = ""
    tool_call: ToolCall | None = None
    assistant_message: ChatMessage | None = None


@dataclass(frozen=True)
class TurnEvent:
    type: str
    text: str = ""
    phase: Literal["initial", "final"] = "initial"
    local_id: str = ""
    tool_call: ToolCall | None = None
    approval: ApprovalRequest | None = None
    result: ToolResult | None = None

