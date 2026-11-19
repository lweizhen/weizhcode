from __future__ import annotations

import json
from dataclasses import replace
from contextlib import aclosing
from collections.abc import AsyncIterator, Callable

from weizhcode.errors import (ProviderError, ProviderFault, StreamError, classify_provider_fault,
                             redact_secret, safe_finish_reason)
from weizhcode.models import ChatMessage, ProviderConfig, ProviderEvent
from weizhcode.providers.base import DEFAULT_MAX_OUTPUT_TOKENS, UsageAccumulator, diagnostic_text, make_call, safe_arguments
from weizhcode.providers.sse import SSEEvent, stream_sse
from weizhcode.providers.prompt_adapter import apply_prompt
from weizhcode.providers.request import (RequestOptions, prepare_body, prompt_identity,
                                         redact_request_body, request_redactor, stream_options)
from weizhcode.redaction import Redactor

StreamFunc = Callable[..., AsyncIterator[SSEEvent]]


class QwenProvider:
    def __init__(self, config: ProviderConfig, stream_func: StreamFunc = stream_sse) -> None:
        self.config = config
        self._stream = stream_func

    def prepare_request(self, messages, *, tools=(), system_prompt="", prompt_context=None,
                        options=RequestOptions(), redactor=None):
        if options.purpose == "summary":
            tools = ()
            if prompt_context is not None:
                raise ValueError("摘要不能沿用普通Agent提示上下文")
        safe = request_redactor(self.config, redactor)
        body = {
            "model": self.config.model, "messages": _messages_payload(messages, safe),
            "stream": True, "max_tokens": options.max_output_tokens,
            "stream_options": {"include_usage": True},
        }
        history = redact_request_body({'messages': body['messages']}, safe)['messages']
        if system_prompt:
            body["messages"].insert(0, {"role": "system", "content": system_prompt})
        if tools:
            body["tools"] = [{"type": "function", "function": {
                "name": t.name, "description": t.description, "parameters": t.parameters,
            }} for t in tools]
            body["tool_choice"] = "auto" if options.allow_tools else "none"
        body = apply_prompt(body, self.config, system_prompt=system_prompt, prompt_context=prompt_context, redactor=safe)
        return prepare_body(redact_request_body(body, safe), protocol="qwen", options=options,
                            fixed_identity=prompt_identity(system_prompt, prompt_context, safe), history_items=history)

    async def stream_chat(self, messages, *, tools=(), system_prompt="", allow_tools=True, prompt_context=None):
        request = self.prepare_request(messages, tools=tools, system_prompt=system_prompt,
                                       prompt_context=prompt_context, options=RequestOptions(allow_tools=allow_tools))
        async with aclosing(self.stream_prepared(request)) as stream:
            async for event in stream:
                yield event

    async def stream_prepared(self, request):
        if request.protocol != "qwen":
            raise ValueError("已准备请求与Provider协议不一致")
        body = request.body()
        yield ProviderEvent(type="start")
        calls = {}
        parts = []
        finish = None
        completed = False
        usage = UsageAccumulator("qwen")
        try:
            source = self._stream(
                "POST", f"{self.config.base_url}/chat/completions",
                headers={"content-type": "application/json", "authorization": f"Bearer {self.config.api_key}"},
                json_body=body,
                **stream_options(self._stream, "qwen"),
            )
            async with aclosing(source):
                async for event in source:
                    if event.data == "[DONE]":
                        completed = True
                        break
                    parsed = event.json()
                    if parsed.get("error"):
                        fault = classify_provider_fault("qwen", parsed)
                        raise StreamError(fault.message, fault=fault)
                    if parsed.get("usage") is not None:
                        yield ProviderEvent("usage", usage=usage.update(parsed["usage"]))
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
            if usage.seen:
                yield ProviderEvent("usage", usage=usage.snapshot(complete=True))
            yield ProviderEvent(type="done", assistant_message=ChatMessage(
                "assistant", "".join(parts), tool_calls=assembled), finish_reason=safe_finish_reason("qwen", finish))
        except (ProviderError, StreamError, ValueError, TypeError, KeyError, AttributeError) as exc:
            fault = getattr(exc, "fault", None)
            fault = fault if isinstance(fault, ProviderFault) else ProviderFault("qwen")
            yield ProviderEvent(type="error", message=redact_secret(str(exc), self.config.api_key),
                                fault=fault, finish_reason=safe_finish_reason("qwen", finish))


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
                    "function": {"name": c.name, "arguments": safe_arguments(c.raw_arguments, safe)}}
                    for c in message.tool_calls]
            result.append(item)
    return result
