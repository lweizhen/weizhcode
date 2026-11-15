from copy import deepcopy
import hashlib
import json
from urllib.parse import urlsplit

from weizhcode.prompting.contracts import PromptContext
from weizhcode.redaction import Redactor
from .cache_policy import select_cache_policy


def apply_prompt(body, config, *, system_prompt="", prompt_context=None):
    if prompt_context is None:
        return body
    if system_prompt:
        raise ValueError("system_prompt 与 prompt_context 不能同时提供")
    if not isinstance(prompt_context, PromptContext):
        raise ValueError("非法结构化提示")
    # Constructing a context again validates factory provenance without parsing text tags.
    ctx = PromptContext(prompt_context.stable_text, prompt_context.environment_text, prompt_context.supplements)
    safe = Redactor([config.api_key])
    stable, environment = safe.text(ctx.stable_text), safe.text(ctx.environment_text)
    reminder = "\n".join("<system-reminder>\n" + safe.text(s.text) + "\n</system-reminder>"
                         for s in ctx.supplements)
    policy = select_cache_policy(config)
    body = deepcopy(body)
    if config.protocol == "anthropic":
        system = [{"type": "text", "text": stable}] if stable else []
        if system and policy.strategy == "anthropic_explicit":
            system[0]["cache_control"] = {"type": "ephemeral"}
        if environment:
            system.append({"type": "text", "text": environment})
        if system:
            body["system"] = system
        messages = body["messages"]
        if reminder:
            block = {"type": "text", "text": reminder}
            if messages and messages[-1]["role"] == "user":
                if isinstance(messages[-1]["content"], str):
                    messages[-1]["content"] = [{"type": "text", "text": messages[-1]["content"]}]
                messages[-1]["content"].append(block)
            else:
                messages.append({"role": "user", "content": [block]})
    elif config.protocol == "openai":
        prefix = []
        if policy.strategy == "openai_explicit" and stable:
            body.pop("instructions", None)
            prefix.append({"role": "developer", "content": [{"type": "input_text", "text": stable,
                "prompt_cache_breakpoint": {"mode": "explicit"}}]})
            body["prompt_cache_options"] = {"mode": "explicit"}
        elif stable:
            body["instructions"] = stable
        if environment:
            role = "developer" if policy.strategy == "openai_explicit" else "user"
            prefix.append({"role": role, "content": [{"type": "input_text", "text": environment}]})
        body["input"] = prefix + body["input"]
        if reminder:
            body["input"].append({"role": "user", "content": [{"type": "input_text", "text": reminder}]})
    else:
        prefix = [{"role": "system", "content": stable}] if stable else []
        if environment:
            prefix.append({"role": "user", "content": environment})
        body["messages"] = prefix + body["messages"]
        if reminder:
            body["messages"].append({"role": "user", "content": reminder})
    return body


def stable_prefix_projection(body, config):
    policy = select_cache_policy(config)
    try:
        url = urlsplit(config.base_url)
        endpoint = (url.scheme, url.hostname, url.port or (443 if url.scheme == "https" else 80), url.path.rstrip("/"))
    except ValueError:
        endpoint = ("invalid",)
    if config.protocol == "anthropic":
        system = body.get("system", "")
        stable = system[:1] if isinstance(system, list) else system
    elif config.protocol == "openai":
        stable = (body.get("input", [])[:1] if policy.strategy == "openai_explicit"
                  else body.get("instructions", ""))
    else:
        messages = body.get("messages", [])
        stable = messages[:1] if messages and messages[0]["role"] == "system" else []
    return {"endpoint": endpoint, "protocol": config.protocol, "model": config.model,
            "strategy": policy.strategy, "rule_version": policy.version, "stable": deepcopy(stable),
            "tools": deepcopy(body.get("tools", [])), "settings": {key: deepcopy(body[key])
                for key in ("tool_choice", "parallel_tool_calls", "reasoning", "text", "prompt_cache_options")
                if key in body}}


def stable_prefix_bytes(body, config):
    return json.dumps(stable_prefix_projection(body, config), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def stable_prefix_digest(body, config):
    return hashlib.sha256(stable_prefix_bytes(body, config)).hexdigest()
