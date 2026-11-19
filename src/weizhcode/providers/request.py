from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RequestOptions:
    purpose: Literal["chat", "summary"] = "chat"
    allow_tools: bool = True
    max_output_tokens: int = 4096

    def __post_init__(self):
        if self.purpose not in {"chat", "summary"} or type(self.allow_tools) is not bool:
            raise ValueError("请求目的或工具开关无效")
        if self.purpose == "summary" and self.allow_tools:
            raise ValueError("摘要请求禁止工具调用")
        if type(self.max_output_tokens) is not int or not 1 <= self.max_output_tokens <= 4096:
            raise ValueError("输出预算必须在1到4096之间")


@dataclass(frozen=True)
class PreparedRequest:
    request_id: str
    purpose: str
    protocol: str
    body_json: str = field(repr=False)
    message_projections: tuple[str, ...] = field(repr=False)
    fixed_projection: str = field(repr=False)
    fixed_digest: str
    tools_digest: str
    output_reserve: int
    anchor_projections: tuple[str, ...] | None = field(default=None, repr=False)

    def __post_init__(self):
        object.__setattr__(self, "message_projections", tuple(self.message_projections))
        object.__setattr__(self, 'anchor_projections', tuple(self.message_projections if self.anchor_projections is None
                                                            else self.anchor_projections))

    def body(self):
        # 发送方得到私有副本，无法修改保存的出站投影。
        return json.loads(self.body_json)


def prepare_body(body, *, protocol, options: RequestOptions, fixed_identity="", history_items=None):
    """仅规范化已经适配、脱敏的真实body；不做网络、历史或认证操作。"""
    if protocol not in {"anthropic", "openai", "qwen"}:
        raise ValueError("请求协议无效")
    body = deepcopy(body)
    if options.purpose == "summary" and body.get("tools"):
        raise ValueError("摘要请求不能携带工具定义")
    key = "input" if protocol == "openai" else "messages"
    messages = body.get(key, [])
    if not isinstance(messages, list):
        raise ValueError("出站消息投影必须是列表")
    # 输出预算/传输开关不充作输入正文；原生签名/工具Schema等仍保留。
    excluded = {key, "model", "stream", "store", "max_tokens", "max_output_tokens", "stream_options"}
    fixed = {k: v for k, v in body.items() if k not in excluded}
    actual_output = body.get("max_output_tokens", body.get("max_tokens", options.max_output_tokens))
    if actual_output != options.max_output_tokens:
        raise ValueError("出站输出预算与准备选项不一致")
    return PreparedRequest(
        uuid4().hex, options.purpose, protocol, canonical(body), tuple(canonical(m) for m in messages),
        canonical(fixed), digest({"fixed": fixed, "dynamic_identity": fixed_identity}),
        digest(body.get("tools", [])), options.max_output_tokens,
        tuple(canonical(m) for m in history_items) if history_items is not None else None,
    )


def prompt_identity(system_prompt, prompt_context, safe):
    if prompt_context is None:
        return safe.text(system_prompt)
    return {"stable": safe.text(prompt_context.stable_text),
            "environment": safe.text(prompt_context.environment_text),
            "supplements": [(s.kind, safe.text(s.text)) for s in prompt_context.supplements]}


def request_redactor(config, redactor=None):
    from weizhcode.redaction import Redactor

    return Redactor((config.api_key, *(redactor.secrets if redactor is not None else ())))


def stream_options(stream_func, protocol):
    from .sse import stream_sse

    # 保持旧四参数stream_func替身兼容；真实传输获得明确协议而非猜测URL。
    return {"protocol": protocol} if stream_func is stream_sse else {}


def redact_request_body(value, safe, _path=()):
    """普通数据脱敏；仅协议原生位置的签名/加密项保持无损，不把任意type标签当豁免。"""
    if isinstance(value, dict):
        native_position = ((len(_path) == 2 and _path[0] == "input")
                           or (len(_path) == 4 and _path[0] == "messages" and _path[2] == "content"))
        if native_position and value.get("type") in {"thinking", "redacted_thinking", "reasoning"}:
            return deepcopy(value)
        return {safe.text(str(k)): redact_request_body(v, safe, (*_path, k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_request_body(v, safe, (*_path, index)) for index, v in enumerate(value)]
    return safe.text(value) if isinstance(value, str) else deepcopy(value)
