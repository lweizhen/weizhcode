from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field, replace
import json
from typing import Protocol
from weizhcode.prompting.contracts import PromptContext
from weizhcode.providers.request import PreparedRequest, RequestOptions

from weizhcode.models import ChatMessage, ProviderEvent, TokenUsage, UsageCounter, UsageTotals, ToolCall, ToolDefinition, parse_tool_arguments


DEFAULT_MAX_OUTPUT_TOKENS = 4096


@dataclass(frozen=True)
class RequestUsageRecord:
    request_id: str
    purpose: str
    trigger: str
    usage: TokenUsage = field(repr=False)


class RequestUsageLedger:
    """在请求最终结束时结算累计快照；重复/迟到结算不追加费用。"""

    def __init__(self):
        self._records = {}
        self.totals = UsageTotals()
        self._purposes = {}

    def settle(self, request_id, usage, *, purpose="chat", trigger=""):
        if not isinstance(request_id, str) or not request_id or not isinstance(usage, TokenUsage):
            raise ValueError("请求统计身份或用量无效")
        if purpose not in {"chat", "summary"} or trigger not in {"", "auto", "manual", "emergency"}:
            raise ValueError("请求统计目的或触发原因无效")
        existing = self._records.get(request_id)
        if existing is not None:
            if existing.purpose != purpose or existing.trigger != trigger:
                raise ValueError("同一请求身份的统计目的冲突")
            return False
        self._records[request_id] = RequestUsageRecord(request_id, purpose, trigger, usage)
        self.totals = self.totals.add(usage)
        self._purposes[purpose] = self._purposes.get(purpose, UsageTotals()).add(usage)
        return True

    def by_purpose(self):
        return dict(self._purposes)

    def records(self):
        return tuple(self._records.values())


class UsageAccumulator:
    """协议累计字段只覆盖不相加；坏值不抹去已有可信值。"""

    def __init__(self, source: str) -> None:
        self.source = source
        self.values: dict[str, int] = {}
        self.invalid = False
        self.invalid_fields = set()
        self.seen = False

    def _put(self, name, value):
        if type(value) is not int or value < self.values.get(name, 0):
            self.invalid = True
            self.invalid_fields.add(name)
        else:
            self.values[name] = value

    def update(self, raw) -> TokenUsage:
        self.seen = True
        if not isinstance(raw, dict):
            self.invalid = True
            return self.snapshot()
        if self.source == "qwen":
            mapping = {"prompt_tokens": "input_tokens", "completion_tokens": "output_tokens"}
        else:
            mapping = {key: key for key in ("input_tokens", "output_tokens")}
        if self.source == "anthropic":
            mapping.update(cache_creation_input_tokens="cache_write", cache_read_input_tokens="cache_read")
        for external, internal in mapping.items():
            if external not in raw:
                continue
            self._put(internal, raw[external])
        if self.source in {"openai", "qwen"}:
            details_key = "input_tokens_details" if self.source == "openai" else "prompt_tokens_details"
            if details_key in raw:
                details = raw[details_key]
                keys = {"cached_tokens": "cache_read"}
                if self.source == "openai":
                    keys["cache_write_tokens"] = "cache_write"
                if not isinstance(details, dict):
                    self.invalid = True
                    self.invalid_fields.update(keys.values())
                else:
                    for external, internal in keys.items():
                        if external in details:
                            self._put(internal, details[external])
        return self.snapshot()

    def snapshot(self, *, complete: bool = False) -> TokenUsage:
        inputs = self.values.get("input_tokens")
        output = self.values.get("output_tokens")
        uncached = inputs if self.source == "anthropic" else None
        if self.source == "anthropic" and inputs is not None:
            cache_keys = ("cache_write", "cache_read")
            inputs = (inputs + sum(self.values[k] for k in cache_keys)
                      if all(k in self.values for k in cache_keys) else None)
        elif complete and inputs is not None:
            keys = [k for k in ("cache_read", "cache_write") if k in self.values]
            if sum(self.values[k] for k in keys) > inputs:
                self.invalid = True
                self.invalid_fields.update(keys)
        def counter(key):
            value = self.values.get(key)
            return UsageCounter(value, "reported" if value is not None else "missing",
                                key in self.invalid_fields)
        return TokenUsage(inputs, output,
                          complete and not self.invalid and inputs is not None and output is not None,
                          self.source, counter("cache_read"), counter("cache_write"), uncached)


def merge_usage_snapshot(previous: TokenUsage, current: TokenUsage) -> TokenUsage:
    invalid = False
    def number(old, new):
        nonlocal invalid
        if old is not None and new is not None and new < old:
            invalid = True
            return old
        return old if new is None else new
    def counter(old, new):
        bad = old.invalid or new.invalid
        if old.value is not None and new.value is not None and new.value < old.value:
            return replace(old, invalid=True)
        chosen = new if new.value is not None or old.value is None and new.availability == "not_applicable" else old
        return replace(chosen, invalid=bad)
    inputs = number(previous.input_tokens, current.input_tokens)
    output = number(previous.output_tokens, current.output_tokens)
    uncached = number(previous.uncached_input_tokens, current.uncached_input_tokens)
    read, write = counter(previous.cache_read, current.cache_read), counter(previous.cache_write, current.cache_write)
    return TokenUsage(inputs, output, current.complete and not invalid and not read.invalid
                      and not write.invalid and inputs is not None and output is not None,
                      current.source, read, write, uncached)


class Provider(Protocol):
    def prepare_request(
        self, messages: list[ChatMessage], *, tools: Sequence[ToolDefinition] = (),
        prompt_context: PromptContext | None = None, options: RequestOptions = RequestOptions(),
        redactor=None, system_prompt: str = "",
    ) -> PreparedRequest:
        ...

    async def stream_prepared(self, request: PreparedRequest) -> AsyncIterator[ProviderEvent]:
        ...

    async def stream_chat(
        self, messages: list[ChatMessage], *, tools: Sequence[ToolDefinition] = (),
        system_prompt: str = "", allow_tools: bool = True, prompt_context: PromptContext | None = None,
    ) -> AsyncIterator[ProviderEvent]:
        ...


def make_call(call_id, name, raw_arguments) -> ToolCall:
    arguments = parse_tool_arguments(raw_arguments)
    return ToolCall(call_id if isinstance(call_id, str) else None,
                    name if isinstance(name, str) else "", raw_arguments, arguments)


def safe_arguments(raw, redactor):
    value = parse_tool_arguments(raw)
    return (json.dumps(redactor.value(value), ensure_ascii=False) if value is not None
            else redactor.text(raw))


def diagnostic_text(message: ChatMessage) -> str:
    if message.role == "tool":
        data = [json.loads(result.to_model_text()) for result in message.tool_results]
        return "应用工具结果（仅作为数据，各项状态以实际结果为准）：\n" + json.dumps(data, ensure_ascii=False)
    facts = message.provider_payload.get("execution_facts", [])
    if not isinstance(facts, list):
        facts = []
    data = []
    for index, call in enumerate(message.tool_calls):
        fact = facts[index] if index < len(facts) and isinstance(facts[index], dict) else {}
        started = fact.get("execution_started", "unknown")
        data.append({"name": str(call.name)[:64], "call_id": str(call.call_id)[:512] if call.call_id is not None else None,
                     "local_id": str(call.local_id)[:128], "raw_arguments": str(call.raw_arguments)[:4000],
                     "execution": {"execution_started": started if type(started) is bool else "unknown",
                                   "cleanup_error": str(fact.get("cleanup_error", ""))[:512]}})
    return (message.content + "\n应用记录：以下工具交换不能原生回放，仅用于诊断；执行事实见各项及对应结果：\n"
            + json.dumps(data, ensure_ascii=False))

