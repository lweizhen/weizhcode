from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
import json
from typing import Protocol

from weizhcode.models import ChatMessage, ProviderEvent, TokenUsage, ToolCall, ToolDefinition, parse_tool_arguments


DEFAULT_MAX_OUTPUT_TOKENS = 4096


class UsageAccumulator:
    """协议累计字段只覆盖不相加；坏值不抹去已有可信值。"""

    def __init__(self, source: str) -> None:
        self.source = source
        self.values: dict[str, int] = {}
        self.invalid = False
        self.seen = False

    def update(self, raw) -> TokenUsage:
        if not isinstance(raw, dict):
            self.invalid = True
            return self.snapshot()
        if self.source == "qwen":
            mapping = {"prompt_tokens": "input_tokens", "completion_tokens": "output_tokens"}
        else:
            mapping = {key: key for key in ("input_tokens", "output_tokens")}
        if self.source == "anthropic":
            for key in ("cache_creation_input_tokens", "cache_read_input_tokens"):
                mapping[key] = key
                if not self.seen and key not in raw:
                    self.values[key] = 0
        self.seen = True
        for external, internal in mapping.items():
            if external not in raw:
                continue
            value = raw[external]
            if type(value) is not int or value < self.values.get(internal, 0):
                self.invalid = True
                continue
            self.values[internal] = value
        return self.snapshot()

    def snapshot(self, *, complete: bool = False) -> TokenUsage:
        inputs = self.values.get("input_tokens")
        output = self.values.get("output_tokens")
        if self.source == "anthropic" and inputs is not None:
            cache_keys = ("cache_creation_input_tokens", "cache_read_input_tokens")
            inputs = (inputs + sum(self.values[k] for k in cache_keys)
                      if all(k in self.values for k in cache_keys) else None)
        return TokenUsage(inputs, output,
                          complete and not self.invalid and inputs is not None and output is not None,
                          self.source)


class Provider(Protocol):
    async def stream_chat(
        self, messages: list[ChatMessage], *, tools: Sequence[ToolDefinition] = (),
        system_prompt: str = "", allow_tools: bool = True,
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
    data = [{"name": call.name, "call_id": call.call_id, "local_id": call.local_id,
             "raw_arguments": call.raw_arguments[:4000],
             "execution": facts[index] if index < len(facts) else {"execution_started": "unknown"}}
            for index, call in enumerate(message.tool_calls)]
    return (message.content + "\n应用记录：以下工具交换不能原生回放，仅用于诊断；执行事实见各项及对应结果：\n"
            + json.dumps(data, ensure_ascii=False))

