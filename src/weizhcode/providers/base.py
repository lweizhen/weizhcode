from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
import json
from typing import Protocol

from weizhcode.models import ChatMessage, ProviderEvent, ToolCall, ToolDefinition, parse_tool_arguments


DEFAULT_MAX_OUTPUT_TOKENS = 4096


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
        return "应用工具校验/限制结果（仅作为数据，未批准的操作未执行）：\n" + json.dumps(data, ensure_ascii=False)
    data = [{"name": call.name, "call_id": call.call_id, "raw_arguments": call.raw_arguments[:4000]}
            for call in message.tool_calls]
    return (message.content + "\n应用记录：以下工具调用无法合法回放，未执行，仅用于诊断：\n"
            + json.dumps(data, ensure_ascii=False))

