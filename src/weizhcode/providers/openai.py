from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from copy import deepcopy
from dataclasses import replace
from contextlib import aclosing

from weizhcode.errors import ProviderError, StreamError, redact_secret
from weizhcode.models import ChatMessage, ProviderConfig, ProviderEvent
from weizhcode.providers.base import DEFAULT_MAX_OUTPUT_TOKENS, UsageAccumulator, diagnostic_text, make_call, safe_arguments
from weizhcode.providers.sse import SSEEvent, stream_sse
from weizhcode.redaction import Redactor

StreamFunc = Callable[..., AsyncIterator[SSEEvent]]


class OpenAIProvider:
    def __init__(self, config: ProviderConfig, stream_func: StreamFunc = stream_sse) -> None:
        self.config = config
        self._stream = stream_func

    async def stream_chat(self, messages, *, tools=(), system_prompt="", allow_tools=True):
        yield ProviderEvent(type="start")
        body = {"model": self.config.model, "input": _input_payload(messages, Redactor([self.config.api_key])),
                "stream": True, "store": False, "max_output_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
                "include": ["reasoning.encrypted_content"]}
        if system_prompt:
            body["instructions"] = system_prompt
        if tools:
            body["tools"] = [{"type": "function", "name": t.name, "description": t.description,
                             "parameters": t.parameters, "strict": False} for t in tools]
            body["parallel_tool_calls"] = False
            body["tool_choice"] = "auto" if allow_tools else "none"
        items = {}
        buffers = {}
        local_ids = {}
        parts = []
        completed = None
        usage = UsageAccumulator("openai")
        try:
            source = self._stream(
                "POST", f"{self.config.base_url}/responses",
                headers={"content-type": "application/json", "authorization": f"Bearer {self.config.api_key}"},
                json_body=body,
            )
            async with aclosing(source):
                async for event in source:
                    parsed = event.json()
                    kind = parsed.get("type") or event.event
                    index = parsed.get("output_index")
                    if kind in {"response.output_text.delta", "response.refusal.delta"}:
                        text = parsed.get("delta") or ""
                        parts.append(text)
                        if text:
                            yield ProviderEvent(type="text_delta", text=text)
                    elif kind == "response.output_item.added":
                        if not isinstance(index, int) or index in items:
                            raise StreamError("OpenAI 输出项索引错误")
                        item = deepcopy(parsed["item"])
                        items[index] = item
                        if item.get("type") == "function_call":
                            buffers[index] = item.get("arguments") or ""
                            pending = make_call(item.get("call_id"), item.get("name"), "")
                            local_ids[index] = pending.local_id
                            yield ProviderEvent(type="tool_call_start", tool_call=pending)
                    elif kind == "response.function_call_arguments.delta":
                        if index not in buffers or parsed.get("item_id") not in (None, items[index].get("id")):
                            raise StreamError("OpenAI 参数分片没有对应调用")
                        buffers[index] += parsed.get("delta") or ""
                    elif kind == "response.function_call_arguments.done":
                        if index not in buffers:
                            raise StreamError("OpenAI 参数结束没有对应调用")
                        if buffers[index] != parsed.get("arguments"):
                            raise StreamError("OpenAI 参数分片与完整参数不一致")
                    elif kind == "response.output_item.done":
                        item = deepcopy(parsed["item"])
                        if index not in items or item.get("id") != items[index].get("id"):
                            raise StreamError("OpenAI 输出项结束不匹配")
                        if index in buffers and item.get("arguments") != buffers[index]:
                            raise StreamError("OpenAI 工具参数不完整")
                        items[index] = item
                    elif kind == "response.completed":
                        response = parsed.get("response") or {}
                        if response.get("usage") is not None:
                            yield ProviderEvent("usage", usage=usage.update(response["usage"]))
                        if response.get("status") != "completed":
                            raise StreamError("OpenAI 回复状态不是 completed")
                        completed = response.get("output")
                        if not isinstance(completed, list):
                            raise StreamError("OpenAI 完整输出缺失")
                        break
                    elif kind in {"error", "response.failed", "response.incomplete"}:
                        raw_usage = (parsed.get("response") or {}).get("usage")
                        if raw_usage is not None:
                            yield ProviderEvent("usage", usage=usage.update(raw_usage))
                        raise StreamError(_error_message(parsed, "OpenAI 回复失败或被截断"))
            if completed is None:
                raise StreamError("OpenAI 流式回复未完整结束，不执行工具")
            final_calls = []
            for index, item in enumerate(completed):
                if item.get("type") == "function_call":
                    if index not in buffers:
                        raise StreamError("OpenAI 完整输出含未知工具调用")
                    original = items[index]
                    if any(item.get(k) != original.get(k) for k in ("id", "call_id", "name")) or item.get("arguments") != buffers[index]:
                        raise StreamError("OpenAI 最终工具调用与流式分片不一致")
                    final_calls.append(replace(make_call(item.get("call_id"), item.get("name"), item.get("arguments", "")),
                                               local_id=local_ids[index]))
            if len(final_calls) != len(buffers):
                raise StreamError("OpenAI 最终输出缺少工具调用")
            for call in final_calls:
                yield ProviderEvent(type="tool_call", tool_call=call)
            if usage.seen:
                yield ProviderEvent("usage", usage=usage.snapshot(complete=True))
            yield ProviderEvent(type="done", assistant_message=ChatMessage(
                "assistant", "".join(parts), tool_calls=tuple(final_calls),
                provider_payload={"openai_items": completed}))
        except (ProviderError, StreamError, ValueError, TypeError, KeyError, AttributeError) as exc:
            yield ProviderEvent(type="error", message=redact_secret(str(exc), self.config.api_key))


def _safe_item(item, safe):
    item = deepcopy(item)
    if item.get("type") == "function_call":
        item["arguments"] = safe_arguments(item.get("arguments", ""), safe)
    elif item.get("type") == "message":
        for block in item.get("content", []):
            for key in ("text", "refusal"):
                if isinstance(block.get(key), str):
                    block[key] = safe.text(block[key])
    # reasoning 的加密内容必须无损回放；不送入 UI。
    return item


def _input_payload(messages, safe=None):
    safe = safe or Redactor()
    result = []
    for message in messages:
        if message.provider_payload.get("diagnostic"):
            result.append({"role": "assistant" if message.role == "assistant" else "user",
                           "content": safe.text(diagnostic_text(message))})
        elif message.role == "tool":
            result.extend({"type": "function_call_output", "call_id": r.call_id,
                           "output": safe.text(r.to_model_text())} for r in message.tool_results)
        elif "openai_items" in message.provider_payload:
            native = message.provider_payload["openai_items"]
            result.extend(_safe_item(item, safe) for item in native)
            if not native and message.content:
                result.append({"role": message.role, "content": safe.text(message.content)})
        else:
            if message.content:
                result.append({"role": message.role, "content": safe.text(message.content)})
            result.extend({"type": "function_call", "call_id": c.call_id, "name": c.name,
                           "arguments": safe_arguments(c.raw_arguments, safe)} for c in message.tool_calls)
    return result


def _error_message(payload, fallback):
    error = payload.get("error") or (payload.get("response") or {}).get("error")
    if isinstance(error, dict):
        return error.get("message") or fallback
    return payload.get("message") or fallback
