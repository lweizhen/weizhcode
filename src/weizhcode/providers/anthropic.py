from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from copy import deepcopy
from dataclasses import replace
from contextlib import aclosing

from weizhcode.errors import ProviderError, StreamError, redact_secret
from weizhcode.models import ChatMessage, ProviderConfig, ProviderEvent
from weizhcode.providers.base import DEFAULT_MAX_OUTPUT_TOKENS, UsageAccumulator, diagnostic_text, make_call
from weizhcode.providers.sse import SSEEvent, stream_sse
from weizhcode.redaction import Redactor

StreamFunc = Callable[..., AsyncIterator[SSEEvent]]


class AnthropicProvider:
    def __init__(self, config: ProviderConfig, stream_func: StreamFunc = stream_sse) -> None:
        self.config = config
        self._stream = stream_func

    async def stream_chat(self, messages, *, tools=(), system_prompt="", allow_tools=True):
        yield ProviderEvent(type="start")
        body = {"model": self.config.model, "max_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
                "messages": _messages_payload(messages, Redactor([self.config.api_key])), "stream": True}
        if system_prompt:
            body["system"] = system_prompt
        if tools:
            body["tools"] = [{"name": t.name, "description": t.description, "input_schema": t.parameters} for t in tools]
            body["tool_choice"] = {"type": "auto"} if allow_tools else {"type": "none"}
        blocks = {}
        closed = set()
        text_parts = []
        stop_reason = None
        complete = False
        usage = UsageAccumulator("anthropic")
        try:
            source = self._stream(
                "POST", f"{self.config.base_url}/messages",
                headers={"content-type": "application/json", "x-api-key": self.config.api_key,
                         "anthropic-version": "2023-06-01"}, json_body=body,
            )
            async with aclosing(source):
                async for event in source:
                    parsed = event.json()
                    kind = parsed.get("type") or event.event
                    index = parsed.get("index", 0)
                    if kind == "message_start":
                        raw_usage = (parsed.get("message") or {}).get("usage")
                        if raw_usage is not None:
                            yield ProviderEvent("usage", usage=usage.update(raw_usage))
                    elif kind == "content_block_start":
                        if index in blocks:
                            raise StreamError("重复的内容块")
                        block = deepcopy(parsed["content_block"])
                        if block.get("type") == "tool_use":
                            block["_raw"] = ""
                            pending = make_call(block.get("id"), block.get("name"), "")
                            block["_local_id"] = pending.local_id
                            yield ProviderEvent(type="tool_call_start", tool_call=pending)
                        blocks[index] = block
                        if block.get("type") == "text" and block.get("text"):
                            text_parts.append(block["text"])
                            yield ProviderEvent("text_delta", text=block["text"])
                    elif kind == "content_block_delta":
                        if index in closed:
                            raise StreamError("已结束的内容块仍有增量")
                        delta = parsed.get("delta") or {}
                        dtype = delta.get("type")
                        block = blocks.setdefault(index, {"type": "text", "text": ""})
                        if dtype == "text_delta":
                            text = delta.get("text") or ""
                            block["text"] = block.get("text", "") + text
                            text_parts.append(text)
                            if text:
                                yield ProviderEvent(type="text_delta", text=text)
                        elif dtype == "input_json_delta":
                            if block.get("type") != "tool_use":
                                raise StreamError("工具参数不属于工具块")
                            block["_raw"] += delta.get("partial_json") or ""
                        elif dtype == "thinking_delta":
                            block["thinking"] = block.get("thinking", "") + (delta.get("thinking") or "")
                        elif dtype == "signature_delta":
                            block["signature"] = block.get("signature", "") + (delta.get("signature") or "")
                    elif kind == "content_block_stop":
                        if index not in blocks or index in closed:
                            raise StreamError("内容块结束顺序错误")
                        closed.add(index)
                    elif kind == "message_delta":
                        stop_reason = (parsed.get("delta") or {}).get("stop_reason", stop_reason)
                        if parsed.get("usage") is not None:
                            yield ProviderEvent("usage", usage=usage.update(parsed["usage"]))
                    elif kind == "message_stop":
                        complete = True
                        break
                    elif kind == "error":
                        raise StreamError(_error_message(parsed, "Claude 请求失败"))
            if not complete or stop_reason not in {"end_turn", "tool_use", "stop_sequence"}:
                raise StreamError("Claude 流式回复未完整结束，不执行工具")
            if set(blocks) != closed:
                raise StreamError("Claude 内容块不完整，不执行工具")
            assembled = []
            replay = []
            for _, block in sorted(blocks.items()):
                block = deepcopy(block)
                if block.get("type") == "tool_use":
                    raw = block.pop("_raw", "")
                    if not raw:
                        raw = json.dumps(block.get("input", {}), ensure_ascii=False)
                    call = make_call(block.get("id"), block.get("name"), raw)
                    call = replace(call, local_id=block.pop("_local_id"))
                    assembled.append(call)
                    block["input"] = call.arguments if call.arguments is not None else {}
                replay.append(block)
            if bool(assembled) != (stop_reason == "tool_use"):
                raise StreamError("工具调用与回复结束原因不一致")
            for call in assembled:
                yield ProviderEvent(type="tool_call", tool_call=call)
            if usage.seen:
                yield ProviderEvent("usage", usage=usage.snapshot(complete=True))
            yield ProviderEvent(type="done", assistant_message=ChatMessage(
                "assistant", "".join(text_parts), tool_calls=tuple(assembled),
                provider_payload={"anthropic_blocks": replay}))
        except (ProviderError, StreamError, ValueError, TypeError, KeyError, AttributeError) as exc:
            yield ProviderEvent(type="error", message=redact_secret(str(exc), self.config.api_key))


def _messages_payload(messages, safe=None):
    safe = safe or Redactor()
    result = []
    for message in messages:
        if message.provider_payload.get("diagnostic"):
            item = {"role": "assistant" if message.role == "assistant" else "user",
                    "content": safe.text(diagnostic_text(message))}
        elif message.role == "tool":
            item = {"role": "user", "content": [{"type": "tool_result", "tool_use_id": r.call_id,
                    "content": safe.text(r.to_model_text()), "is_error": r.is_error} for r in message.tool_results]}
        else:
            blocks = deepcopy(message.provider_payload.get("anthropic_blocks"))
            if blocks is None and message.tool_calls:
                blocks = ([{"type": "text", "text": message.content}] if message.content else []) + [
                    {"type": "tool_use", "id": c.call_id, "name": c.name, "input": c.arguments}
                    for c in message.tool_calls]
            if blocks is not None:
                for block in blocks:
                    # 签名与加密块原样保留，绝不显示或改写。
                    if block.get("type") == "text":
                        block["text"] = safe.text(block["text"])
                    elif block.get("type") == "tool_use":
                        block["input"] = safe.value(block["input"])
            item = {"role": message.role, "content": blocks if blocks is not None else safe.text(message.content)}
        if result and result[-1]["role"] == item["role"]:
            def as_blocks(value):
                return value if isinstance(value, list) else [{"type": "text", "text": value}]
            result[-1]["content"] = as_blocks(result[-1]["content"]) + as_blocks(item["content"])
        else:
            result.append(item)
    return result


def _error_message(payload, fallback):
    error = payload.get("error")
    return error.get("message", fallback) if isinstance(error, dict) else fallback
