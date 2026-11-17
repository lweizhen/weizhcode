from __future__ import annotations

import asyncio
import json
import re
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal
from uuid import uuid4

from weizhcode.permissions.types import PathStamp, PermissionMode, RootIdentity


ProtocolName = Literal["anthropic", "openai", "qwen"]
MessageRole = Literal["user", "assistant", "tool"]
ProviderEventType = Literal["start", "text_delta", "tool_call_start", "tool_call", "done", "error", "usage"]
AgentMode = PermissionMode
StopReason = Literal["completed", "empty_response", "max_iterations", "unknown_tools",
                     "cancelled", "provider_error", "internal_error"]
MAX_ITERATIONS = 25
MAX_UNKNOWN_RUN = 3
MAX_CONCURRENT_READ_TOOLS = 4
EVENT_QUEUE_SIZE = 128


@dataclass(frozen=True)
class UsageCounter:
    value: int | None = None
    availability: Literal["reported", "missing", "not_applicable"] = "missing"
    invalid: bool = False

    def __post_init__(self):
        if type(self.invalid) is not bool:
            raise ValueError("统计异常标记须为布尔值")
        if self.availability not in {"reported", "missing", "not_applicable"}:
            raise ValueError("非法统计可用性")
        if self.value is not None and (type(self.value) is not int or self.value < 0):
            raise ValueError("非法缓存计数")
        if (self.availability == "reported") != (self.value is not None):
            raise ValueError("统计值与可用性不一致")


@dataclass(frozen=True)
class CacheCounterTotals:
    known_tokens: int = 0
    reported_requests: int = 0
    not_applicable_requests: int = 0
    invalid_requests: int = 0

    def __post_init__(self):
        if any(type(v) is not int or v < 0 for v in (self.known_tokens, self.reported_requests,
               self.not_applicable_requests, self.invalid_requests)):
            raise ValueError("汇总计数须为非负整数")

    def add(self, counter: UsageCounter) -> CacheCounterTotals:
        return CacheCounterTotals(self.known_tokens + (counter.value or 0),
            self.reported_requests + (counter.availability == "reported"),
            self.not_applicable_requests + (counter.availability == "not_applicable"),
            self.invalid_requests + counter.invalid)


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    complete: bool = False
    source: str = "unknown"
    cache_read: UsageCounter = field(default_factory=UsageCounter)
    cache_write: UsageCounter = field(default_factory=UsageCounter)
    uncached_input_tokens: int | None = None

    def __post_init__(self) -> None:
        for value in (self.input_tokens, self.output_tokens, self.uncached_input_tokens):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("Token 计数须为非负整数或未知")
        if self.complete and (self.input_tokens is None or self.output_tokens is None):
            raise ValueError("完整统计必须包含输入和输出")


@dataclass(frozen=True)
class UsageTotals:
    input_tokens: int = 0
    output_tokens: int = 0
    input_requests: int = 0
    output_requests: int = 0
    request_count: int = 0
    incomplete_requests: int = 0
    cache_read: CacheCounterTotals = field(default_factory=CacheCounterTotals)
    cache_write: CacheCounterTotals = field(default_factory=CacheCounterTotals)

    def add(self, usage: TokenUsage) -> UsageTotals:
        return UsageTotals(
            self.input_tokens + (usage.input_tokens or 0),
            self.output_tokens + (usage.output_tokens or 0),
            self.input_requests + (usage.input_tokens is not None),
            self.output_requests + (usage.output_tokens is not None),
            self.request_count + 1,
            self.incomplete_requests + (not usage.complete),
            self.cache_read.add(usage.cache_read),
            self.cache_write.add(usage.cache_write),
        )


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, object]
    read_only: bool = False
    execution_kind: Literal["worker", "interactive", "external"] = "worker"

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
            and all(isinstance(call.name, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", call.name)
                    and parse_tool_arguments(call.raw_arguments) is not None for call in calls))


@dataclass(frozen=True)
class ToolResult:
    call_id: str | None
    tool_name: str
    content: str = ""
    status: Literal["success", "error", "denied", "timeout", "cancelled"] = "success"
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
        status = {"USER_DENIED": "denied", "TOOL_TIMEOUT": "timeout", "TOOL_CANCELLED": "cancelled"}.get(code, "error")
        if code in {"DANGEROUS_COMMAND", "PATH_OUTSIDE_PROJECT", "PATH_UNRESOLVED", "PERMISSION_ROOT_UNAVAILABLE",
                    "PERMISSION_TARGET_CHANGED", "PERMISSION_RULE_DENIED", "PERMISSION_UNAVAILABLE",
                    "INTERACTION_UNAVAILABLE", "TOOL_NOT_ALLOWED"}:
            status = "denied"
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
    permission_root: RootIdentity | None = None


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
    permission_stamp: PathStamp | None = None
    permission_root: RootIdentity | None = None


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
    usage: TokenUsage | None = None


@dataclass(frozen=True)
class QuestionRequest:
    question_id: str
    question: str
    options: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "options", tuple(self.options))


@dataclass(frozen=True)
class ApprovalRequest:
    approval_id: str
    tool_name: str
    friendly_name: str
    arguments_preview: str
    target_preview: str
    reason: str
    scope_hint: str


@dataclass(frozen=True)
class TurnEvent:
    type: str
    text: str = ""
    local_id: str = ""
    tool_call: ToolCall | None = None
    result: ToolResult | None = None
    run_id: str = ""
    request_id: str = ""
    iteration: int = 0
    index: int = 0
    mode: AgentMode = PermissionMode.DEFAULT
    max_iterations: int = MAX_ITERATIONS
    reason: str = ""
    usage: TokenUsage | None = None
    totals: UsageTotals | None = None
    question: QuestionRequest | None = None
    approval: ApprovalRequest | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tool_call", deepcopy(self.tool_call))
        object.__setattr__(self, "result", deepcopy(self.result))


@dataclass
class ToolSlot:
    index: int
    call: ToolCall
    local_id: str = ""
    phase: Literal["pending", "checking", "awaiting_approval", "preparing", "running", "finished"] = "pending"
    execution_started: bool = False
    result: ToolResult | None = None
    cleanup_error: str = ""

    def __post_init__(self) -> None:
        self.call = deepcopy(self.call)
        if not self.local_id:
            self.local_id = self.call.local_id


@dataclass
class StreamState:
    request_id: str = field(default_factory=lambda: uuid4().hex)
    iteration: int = 0
    assistant_message: ChatMessage | None = None
    completed: bool = False
    usage: TokenUsage = field(default_factory=TokenUsage)
    pending_ids: list[str] = field(default_factory=list)
    text: str = ""
    error: str = ""
    cancelled: bool = False
    request_started: bool = False


@dataclass(frozen=True)
class RoundResponse:
    request_id: str
    iteration: int
    assistant_message: ChatMessage
    usage: TokenUsage

    def __post_init__(self) -> None:
        object.__setattr__(self, "assistant_message", deepcopy(self.assistant_message))


@dataclass
class RunContext:
    mode: AgentMode = PermissionMode.DEFAULT
    run_id: str = field(default_factory=lambda: uuid4().hex)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    consumer_closed: asyncio.Event = field(default_factory=asyncio.Event)
    iteration: int = 0
    unknown_run: int = 0
    stream: StreamState | None = None
    slots: list[ToolSlot] = field(default_factory=list)
    exchange_committed: bool = False
    owned_tasks: set[asyncio.Task] = field(default_factory=set)
    cleanup_tasks: set[asyncio.Task] = field(default_factory=set)

    def __setattr__(self, name, value):
        if name == "mode" and hasattr(self, "mode") and "mode" in self.__dict__:
            raise AttributeError("任务模式已经冻结")
        super().__setattr__(name, value)

