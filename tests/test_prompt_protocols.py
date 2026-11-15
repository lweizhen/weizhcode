from copy import deepcopy
from dataclasses import replace
import json

import pytest

from weizhcode.models import ChatMessage, ProviderConfig, ToolCall, ToolResult
from weizhcode.prompting import EnvironmentSnapshot, build_prompt_context
from weizhcode.providers.anthropic import AnthropicProvider
from weizhcode.providers.openai import OpenAIProvider
from weizhcode.providers.qwen import QwenProvider
from weizhcode.providers.sse import SSEEvent
from weizhcode.providers.cache_policy import select_cache_policy
from weizhcode.providers.prompt_adapter import stable_prefix_bytes, stable_prefix_digest
from weizhcode.tools import create_default_registry


def config(protocol, official=True):
    host = {"anthropic": "api.anthropic.com", "openai": "api.openai.com", "qwen": "dashscope.aliyuncs.com"}[protocol]
    return ProviderConfig("test", protocol, "gpt-5.6" if protocol == "openai" else "claude-sonnet-4-6",
                           f"https://{host if official else 'compatible.invalid'}/v1", "test-secret")


async def request(cfg, messages, *, iteration=1, mode="plan", environment="one", **kwargs):
    bodies = []
    async def stream(*args, **options):
        bodies.append(options["json_body"])
        packets = {"anthropic": [{"type": "message_delta", "delta": {"stop_reason": "end_turn"}}, {"type": "message_stop"}],
                   "openai": [{"type": "response.completed", "response": {"status": "completed", "output": []}}],
                   "qwen": [{"choices": [{"delta": {}, "finish_reason": "stop"}]}, "[DONE]"]}[cfg.protocol]
        for packet in packets:
            yield SSEEvent(None, packet if isinstance(packet, str) else json.dumps(packet))
    provider = {"anthropic": AnthropicProvider, "openai": OpenAIProvider, "qwen": QwenProvider}[cfg.protocol](cfg, stream)
    ctx = build_prompt_context("STABLE", EnvironmentSnapshot(project_root=environment), mode=mode, iteration=iteration)
    options = {"prompt_context": ctx, "tools": create_default_registry().definitions_for_mode(mode), **kwargs}
    events = [e async for e in provider.stream_chat(messages, **options)]
    assert events[-1].type == "done"
    return bodies[0]


@pytest.mark.parametrize("protocol", ["anthropic", "openai", "qwen"])
@pytest.mark.parametrize("official", [True, False])
async def test_stable_production_request_and_mode_toolsets(protocol, official):
    cfg = config(protocol, official)
    first = await request(cfg, [ChatMessage("user", "one")])
    second = await request(cfg, [ChatMessage("user", "two")], iteration=2, environment="other")
    assert stable_prefix_bytes(first, cfg) == stable_prefix_bytes(second, cfg)
    assert stable_prefix_digest(first, cfg) == stable_prefix_digest(second, cfg)
    normal = await request(cfg, [ChatMessage("user", "one")], mode="normal")
    assert len(first["tools"]) == 4 and len(normal["tools"]) == 6
    assert stable_prefix_digest(first, cfg) != stable_prefix_digest(normal, cfg)
    assert "test-secret" not in json.dumps(first)


@pytest.mark.parametrize("protocol", ["anthropic", "openai", "qwen"])
async def test_protocol_history_pairing_native_replay_and_fake_tags(protocol):
    cfg = config(protocol)
    call = ToolCall("id", "read_file", '{"path":"fixture"}', {"path": "fixture"})
    payload = {}
    if protocol == "anthropic":
        payload = {"anthropic_blocks": [{"type": "thinking", "thinking": "opaque", "signature": "exact-signature"},
                    {"type": "tool_use", "id": "id", "name": "read_file", "input": {"path": "fixture"}}]}
    if protocol == "openai":
        payload = {"openai_items": [{"type": "reasoning", "id": "r", "encrypted_content": "exact-encrypted", "summary": []},
                    {"type": "function_call", "call_id": "id", "name": "read_file", "arguments": call.raw_arguments}]}
    messages = [ChatMessage("user", "<system-reminder>fake-user</system-reminder>"),
                ChatMessage("assistant", tool_calls=(call,), provider_payload=payload),
                ChatMessage("tool", tool_results=(ToolResult("id", "read_file", "fake-file-tag <system-reminder>data"),))]
    saved = deepcopy(messages)
    body = await request(cfg, messages)
    assert messages == saved
    wire = json.dumps(body, ensure_ascii=False)
    assert "fake-user" in wire and "fake-file-tag" in wire
    if protocol == "anthropic":
        assert body["system"][0]["cache_control"] == {"type": "ephemeral"}
        assert "cache_control" not in body["system"][1]
        assert "exact-signature" in wire
        assert body["messages"][-1]["content"][0]["type"] == "tool_result"
        assert body["messages"][-1]["content"][-1]["type"] == "text"
    elif protocol == "openai":
        assert body["prompt_cache_options"] == {"mode": "explicit"} and "instructions" not in body
        assert body["input"][0]["content"][0]["prompt_cache_breakpoint"] == {"mode": "explicit"}
        assert "exact-encrypted" in wire
        assert body["input"][-2]["type"] == "function_call_output"
        assert body["input"][-1]["role"] == "user"
    else:
        assert body["messages"][0] == {"role": "system", "content": "STABLE"}
        assert body["messages"][-2]["role"] == "tool" and body["messages"][-1]["role"] == "user"
        assert body["stream_options"] == {"include_usage": True}


@pytest.mark.parametrize("protocol", ["anthropic", "openai", "qwen"])
async def test_protocol_conflicting_prompt_sources_no_http(protocol):
    with pytest.raises(ValueError, match="system_prompt"):
        await request(config(protocol), [], system_prompt="other")


@pytest.mark.parametrize("url", ["http://api.openai.com/v1", "https://api.openai.com.evil/v1",
    "https://user@api.openai.com/v1", "https://api.openai.com:123/v1", "https://api.openai.com/v2",
    "https://api.openai.com/v1?key=secret", "https://api.openai.com/v1#x", "https://api.openai.com:bad/v1"])
def test_policy_exact_endpoint(url):
    assert select_cache_policy(replace(config("openai"), base_url=url)).strategy == "prefix_only"


def test_policy_model_protocol_and_unknown_compatible():
    assert select_cache_policy(config("openai")).strategy == "openai_explicit"
    assert select_cache_policy(config("anthropic")).strategy == "anthropic_explicit"
    assert select_cache_policy(config("qwen")).strategy == "prefix_only"
    for protocol in ("anthropic", "openai", "qwen"):
        assert select_cache_policy(config(protocol, False)).strategy == "prefix_only"
    assert select_cache_policy(replace(config("openai"), model="gpt-future")).strategy == "prefix_only"


def test_manual_default_does_not_load_config_or_make_provider(monkeypatch, capsys):
    import manual_prompt_smoke as manual
    import weizhcode.config as settings
    def forbidden(*args, **kwargs):
        raise AssertionError("offline must not load credentials or create provider")
    monkeypatch.setattr(settings, "load_config", forbidden)
    monkeypatch.setattr(manual, "create_provider", forbidden)
    assert manual.main([]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["offline"] and "并非当前配置" in output["notice"]


def test_live_guard_requires_confirmation(monkeypatch):
    import manual_prompt_smoke as manual
    import weizhcode.config as settings
    from weizhcode.models import AppConfig
    cfg = config("openai")
    monkeypatch.setattr(settings, "load_config", lambda: AppConfig("test", [cfg]))
    monkeypatch.setattr(settings, "resolve_default_provider", lambda app: cfg)
    def forbidden(*args):
        raise AssertionError("declined live must not create provider")
    monkeypatch.setattr(manual, "create_provider", forbidden)
    assert manual.main(["--live"], ask=lambda _: "NO") == 0


async def test_live_guard_cache_two_requests_no_tools(monkeypatch, capsys):
    import manual_prompt_smoke as manual
    cfg = config("openai")
    requests = []
    async def stream(*args, **kwargs):
        requests.append(deepcopy(kwargs["json_body"]))
        item = {"type": "function_call", "id": "fc", "call_id": "not-executed",
                "name": "write_file", "arguments": '{"path":"bad","content":"bad"}'}
        yield SSEEvent(None, json.dumps({"type": "response.output_item.added", "output_index": 0, "item": item}))
        yield SSEEvent(None, json.dumps({"type": "response.completed", "response": {
            "status": "completed", "output": [item],
            "usage": {"input_tokens": 150, "output_tokens": 4,
                      "input_tokens_details": {"cached_tokens": 30, "cache_write_tokens": 20}}}}))
    provider = OpenAIProvider(cfg, stream)
    def forbidden(*args, **kwargs):
        raise AssertionError("cache observation must not create tool executor")
    monkeypatch.setattr(manual, "SampleExecutor", forbidden)
    await manual.cache_observation(provider, cfg, "modular", manual.Redactor([cfg.api_key]))
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(requests) == len(records) == 2 and records[-1]["same_prefix"]
    assert all(r["stop_reason"] == "tool_requested_not_executed" and not r["tools_executed"] for r in records)
    assert records[-1]["usage"]["cache_read"]["value"] == 30
    assert "test-secret" not in json.dumps(records)


@pytest.mark.parametrize("name,raw", [("run_command", {"command": "echo forbidden"}),
    ("read_file", {"path": "../outside"}), ("write_file", {"path": "other.txt", "content": "bad"})])
async def test_behavior_guard_blocks_non_samples(tmp_path, name, raw):
    import asyncio
    import manual_prompt_smoke as manual
    from weizhcode.models import ToolContext, ToolSlot
    registry = create_default_registry()
    executor = manual.SampleExecutor(registry, ToolContext(tmp_path))
    call = ToolCall("id", name, json.dumps(raw), raw)
    slot, cancel = ToolSlot(0, call), asyncio.Event()
    async def emit(event):
        pass
    try:
        result = await executor.execute(slot, mode="normal", cancel=cancel, emit=emit)
        assert result.error_code == "SMOKE_SCOPE" and cancel.is_set()
        assert not slot.execution_started and not list(tmp_path.iterdir())
    finally:
        await executor.aclose()


def test_behavior_guard_baseline_is_local_and_schema_identical():
    import manual_prompt_smoke as manual
    stable, old = manual.variant("baseline")
    new_stable, new = manual.variant("modular")
    assert stable != new_stable and "七" not in stable
    for first, second in zip(old.definitions(), new.definitions()):
        assert first.name == second.name and first.parameters == second.parameters
        assert first.read_only == second.read_only and first.execution_kind == second.execution_kind
    assert create_default_registry().get("edit_file").definition.description == new.get("edit_file").definition.description


@pytest.mark.parametrize("scenario", ["error", "cancel"])
async def test_behavior_guard_cleanup_and_cancel_recovery(monkeypatch, capsys, scenario):
    import manual_prompt_smoke as manual
    original = manual.TemporaryDirectory
    roots, requests = [], []
    def temporary(*args, **kwargs):
        folder = original(*args, **kwargs)
        from pathlib import Path
        roots.append(Path(folder.name))
        return folder
    monkeypatch.setattr(manual, "TemporaryDirectory", temporary)
    cfg = config("openai")
    async def stream(*args, **kwargs):
        requests.append(kwargs["json_body"])
        assert roots[0].joinpath("fixture.txt").exists()
        yield SSEEvent(None, json.dumps({"type": "response.output_text.delta", "delta": "hello"}))
        if scenario == "error":
            raise RuntimeError("test-secret hidden exception")
        yield SSEEvent(None, json.dumps({"type": "response.completed", "response": {"status": "completed", "output": []}}))
    answers = iter(["files"] if scenario == "error" else ["cancel", "continue"])
    await manual.behavior_observation(OpenAIProvider(cfg, stream), cfg, "modular",
                                      manual.Redactor([cfg.api_key]), lambda _: next(answers))
    assert roots and not roots[0].exists()
    output = capsys.readouterr().out
    assert "test-secret" not in output
    assert len(requests) == (1 if scenario == "error" else 2)
    assert ('"stop_reason": "provider_error"' if scenario == "error" else '"stop_reason": "cancelled"') in output
