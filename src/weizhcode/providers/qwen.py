from __future__ import annotations

import json
from dataclasses import replace
from collections.abc import AsyncIterator, Callable

from weizhcode.errors import ProviderError, StreamError, redact_secret
from weizhcode.models import ChatMessage, ProviderConfig, ProviderEvent
from weizhcode.providers.base import DEFAULT_MAX_OUTPUT_TOKENS, diagnostic_text, make_call
from weizhcode.providers.sse import SSEEvent, stream_sse
from weizhcode.redaction import Redactor

StreamFunc = Callable[..., AsyncIterator[SSEEvent]]


class QwenProvider:
    def __init__(self, config: ProviderConfig, stream_func: StreamFunc = stream_sse) -> None:
        self.config = config
        self._stream = stream_func

    async def stream_chat(self, messages, *, tools=(), system_prompt="", allow_tools=True):
        yield ProviderEvent(type="start")
        safe = Redactor([self.config.api_key])
        body = {
            "model": self.config.model, "messages": _messages_payload(messages, safe),
            "stream": True, "max_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
        }
        if system_prompt:
            body["messages"].insert(0, {"role": "system", "content": system_prompt})
        if tools:
            body["tools"] = [{"type": "function", "function": {
                "name": t.name, "description": t.description, "parameters": t.parameters,
            }} for t in tools]
            body["tool_choice"] = "auto" if allow_tools else "none"
        calls = {}
        parts = []
        finish = None
        completed = False
        try:
            async for event in self._stream(
                "POST", f"{self.config.base_url}/chat/completions",
                headers={"content-type": "application/json", "authorization": f"Bearer {self.config.api_key}"},
                json_body=body,
            ):
                if event.data == "[DONE]":
                    completed = True
                    break
                parsed = event.json()
                if parsed.get("error"):
                    raise StreamError("通义千问请求失败：" + str(parsed["error"]))
                choices = parsed.get("choices", [])
                if not choices:
                    continue
                choice = choices[0]
                if choice.get("index", 0) != 0:
                    raise StreamError("不支持多候选回复")
                delta = choice.get("delta") or {}
                text = delta.get("content")
                if isinstance(text, str) and text:
                    parts.append(text)
                    yield ProviderEvent(type="text_delta", text=text)
                for fragment in delta.get("tool_calls") or []:
                    index = fragment.get("index")
                    if not isinstance(index, int) or index < 0 or finish is not None:
                        raise StreamError("工具调用流索引或顺序错误")
                    first = index not in calls
                    item = calls.setdefault(index, {"id": None, "name": "", "arguments": ""})
                    if fragment.get("id"):
                        if item["id"] not in (None, fragment["id"]):
                            raise StreamError("工具调用 ID 在流中改变")
                        item["id"] = fragment["id"]
                    function = fragment.get("function") or {}
                    item["name"] += function.get("name") or ""
                    item["arguments"] += function.get("arguments") or ""
                    if first:
                        pending = make_call(item["id"], item["name"], "")
                        item["local_id"] = pending.local_id
                        yield ProviderEvent(type="tool_call_start", tool_call=pending)
                reason = choice.get("finish_reason")
                if reason is not None:
                    if finish is not None:
                        raise StreamError("重复的回复结束标记")
                    finish = reason
            if not completed or finish not in {"stop", "tool_calls"}:
                raise StreamError("通义千问流式回复未完整结束，不执行工具")
            if bool(calls) != (finish == "tool_calls"):
                raise StreamError("工具调用与回复结束原因不一致")
            assembled = tuple(replace(make_call(item["id"], item["name"], item["arguments"]), local_id=item["local_id"])
                              for _, item in sorted(calls.items()))
            for call in assembled:
                yield ProviderEvent(type="tool_call", tool_call=call)
            yield ProviderEvent(type="done", assistant_message=ChatMessage(
                "assistant", "".join(parts), tool_calls=assembled))
        except (ProviderError, StreamError, ValueError, TypeError, KeyError, AttributeError) as exc:
            yield ProviderEvent(type="error", message=redact_secret(str(exc), self.config.api_key))


def _messages_payload(messages, safe=None):
    safe = safe or Redactor()
    result = []
    for message in messages:
        if message.provider_payload.get("diagnostic"):
            result.append({"role": "assistant" if message.role == "assistant" else "user",
                           "content": safe.text(diagnostic_text(message))})
        elif message.role == "tool":
            result.extend({"role": "tool", "tool_call_id": r.call_id,
                           "content": safe.text(r.to_model_text())} for r in message.tool_results)
        else:
            item = {"role": message.role, "content": safe.text(message.content)}
            if message.tool_calls:
                item["tool_calls"] = [{"id": c.call_id, "type": "function",
                    "function": {"name": c.name, "arguments": safe.text(c.raw_arguments)}}
                    for c in message.tool_calls]
            result.append(item)
    return result
