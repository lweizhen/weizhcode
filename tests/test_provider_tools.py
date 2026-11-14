from __future__ import annotations

import json

import pytest

from weizhcode.conversation import Conversation
from weizhcode.models import ChatMessage, ProviderConfig, ToolResult
from weizhcode.providers.anthropic import AnthropicProvider
from weizhcode.providers.openai import OpenAIProvider
from weizhcode.providers.qwen import QwenProvider
from weizhcode.providers.sse import SSEEvent
from weizhcode.tools import create_default_registry
from weizhcode.redaction import Redactor


@pytest.mark.parametrize("protocol", ["anthropic", "openai", "qwen"])
async def test_mixed_diagnostic_preserves_executed_facts(protocol):
    from weizhcode.models import ToolCall
    requests = []
    provider = make_provider(protocol, [], requests)
    good = ToolCall("good", "read_file", '{}')
    bad = ToolCall(None, "missing", '{')
    assistant = ChatMessage("assistant", "preamble", tool_calls=(good, bad), provider_payload={
        "execution_facts": [{"execution_started": True, "cleanup_error": ""},
                            {"execution_started": False, "cleanup_error": ""}]})
    conv = Conversation()
    conv.add_user_message("test")
    conv.add_tool_exchange(assistant, [ToolResult("good", "read_file", "actual-success secret-token"),
                                     ToolResult.failure(bad, "UNKNOWN_TOOL", "missing")])
    saved = conv.messages()
    assert saved[1].provider_payload["execution_facts"][0]["execution_started"] is True
    saved[1].provider_payload["execution_facts"][0]["execution_started"] = False
    assert conv.messages()[1].provider_payload["execution_facts"][0]["execution_started"] is True
    _ = [event async for event in provider.stream_chat(conv.messages())]
    text = json.dumps(requests[0], ensure_ascii=False)
    assert "actual-success" in text and "UNKNOWN_TOOL" in text
    assert "未执行，仅用于诊断" not in text
    assert "secret-token" not in text


def tool_events(protocol, raw='{"path":"中文.txt"}', *, count=1):
    if protocol == "anthropic":
        events = []
        for i in range(count):
            events.append({"type": "content_block_start", "index": i, "content_block": {
                "type": "tool_use", "id": f"call{i}", "name": "read_file", "input": {}}})
            for part in [raw[:4], raw[4:9], raw[9:]]:
                events.append({"type": "content_block_delta", "index": i,
                               "delta": {"type": "input_json_delta", "partial_json": part}})
            events.append({"type": "content_block_stop", "index": i})
        return events + [{"type": "message_delta", "delta": {"stop_reason": "tool_use"}}, {"type": "message_stop"}]
    if protocol == "openai":
        events, output = [], []
        for i in range(count):
            item = {"type": "function_call", "id": f"fc{i}", "call_id": f"call{i}",
                    "name": "read_file", "arguments": ""}
            events.append({"type": "response.output_item.added", "output_index": i, "item": dict(item)})
            for part in [raw[:4], raw[4:9], raw[9:]]:
                events.append({"type": "response.function_call_arguments.delta", "output_index": i,
                               "item_id": f"fc{i}", "delta": part})
            item["arguments"] = raw
            events.append({"type": "response.function_call_arguments.done", "output_index": i, "arguments": raw})
            events.append({"type": "response.output_item.done", "output_index": i, "item": dict(item)})
            output.append(item)
        return events + [{"type": "response.completed", "response": {"status": "completed", "output": output}}]
    events = []
    for i in range(count):
        events.append({"choices": [{"delta": {"tool_calls": [{"index": i, "id": f"call{i}",
                       "type": "function", "function": {"name": "read_", "arguments": raw[:4]}}]}}]})
        events.append({"choices": [{"delta": {"tool_calls": [{"index": i,
                       "function": {"name": "file", "arguments": raw[4:]}}]}}]})
    return events + [{"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}, "[DONE]"]


def make_provider(protocol, events, requests=None):
    async def stream(*args, **kwargs):
        if requests is not None:
            requests.append(kwargs["json_body"])
        for event in events:
            yield SSEEvent(None, event if isinstance(event, str) else json.dumps(event, ensure_ascii=False))
    config = ProviderConfig("test", protocol, "model", "https://example.test/v1", "secret-token", False)
    return {"anthropic": AnthropicProvider, "openai": OpenAIProvider, "qwen": QwenProvider}[protocol](config, stream)


@pytest.mark.parametrize("protocol", ["anthropic", "openai", "qwen"])
@pytest.mark.parametrize("count", [1, 2])
async def test_stream_tool_fragments_and_roundtrip(protocol, count):
    requests = []
    provider = make_provider(protocol, tool_events(protocol, count=count), requests)
    events = [e async for e in provider.stream_chat([ChatMessage("user", "read")],
              tools=create_default_registry().definitions(), system_prompt="system")]
    assert events[-1].type == "done"
    calls = [e.tool_call for e in events if e.type == "tool_call"]
    assert len(calls) == count
    assert all(c.arguments == {"path": "中文.txt"} for c in calls)
    assert len({c.local_id for c in calls}) == count
    assert len(requests[0]["tools"]) == 6
    assert requests[0]["tool_choice"] == ({"type": "auto", "disable_parallel_tool_use": True} if protocol == "anthropic" else "auto")
    conv = Conversation()
    conv.add_user_message("read")
    conv.add_tool_exchange(events[-1].assistant_message,
                           [ToolResult(c.call_id, c.name, "secret-token 内容") for c in calls])
    awaitable = provider.stream_chat(conv.messages(), tools=create_default_registry().definitions(), allow_tools=False)
    _ = [e async for e in awaitable]
    body = requests[1]
    assert "secret-token" not in json.dumps(body, ensure_ascii=False)
    assert body["tool_choice"] == ({"type": "none"} if protocol == "anthropic" else "none")
    if protocol == "anthropic":
        assert body["messages"][-1]["role"] == "user"
        assert [x["tool_use_id"] for x in body["messages"][-1]["content"]] == [c.call_id for c in calls]
    elif protocol == "openai":
        assert body["store"] is False
        assert sum(x.get("type") == "function_call_output" for x in body["input"]) == count
    else:
        assert sum(x["role"] == "tool" for x in body["messages"]) == count


@pytest.mark.parametrize("protocol", ["anthropic", "openai", "qwen"])
@pytest.mark.parametrize("cut", [1, 2])
async def test_eof_never_exposes_executable_call(protocol, cut):
    provider = make_provider(protocol, tool_events(protocol)[:-cut])
    events = [e async for e in provider.stream_chat([])]
    assert events[-1].type == "error"
    assert not any(e.type in {"done", "tool_call"} for e in events)


@pytest.mark.parametrize("protocol", ["anthropic", "openai", "qwen"])
async def test_malformed_json_preserved_for_structured_validation(protocol):
    provider = make_provider(protocol, tool_events(protocol, raw='{"path":'))
    events = [e async for e in provider.stream_chat([])]
    assert events[-1].type == "done"
    call = events[-1].assistant_message.tool_calls[0]
    assert call.arguments is None
    assert call.raw_arguments == '{"path":'
    conv = Conversation()
    conv.add_tool_exchange(events[-1].assistant_message, [ToolResult.failure(call, "INVALID_JSON", "bad json")])
    requests = []
    provider = make_provider(protocol, tool_events(protocol), requests)
    _ = [e async for e in provider.stream_chat(conv.messages())]
    data = json.dumps(requests[0], ensure_ascii=False)
    assert "仅用于诊断" in data
    assert "INVALID_JSON" in data


@pytest.mark.parametrize("protocol", ["anthropic", "openai", "qwen"])
async def test_length_limit_never_executes(protocol):
    events = tool_events(protocol)
    if protocol == "anthropic":
        events[-2]["delta"]["stop_reason"] = "max_tokens"
    elif protocol == "openai":
        events[-1] = {"type": "response.incomplete", "response": {"status": "incomplete"}}
    else:
        events[-2]["choices"][0]["finish_reason"] = "length"
    result = [e async for e in make_provider(protocol, events).stream_chat([])]
    assert result[-1].type == "error"
    assert not any(e.type == "tool_call" for e in result)


async def test_openai_preserves_encrypted_reasoning_and_rejects_final_mismatch():
    events = tool_events("openai")
    reasoning = {"id": "rs", "type": "reasoning", "summary": [], "encrypted_content": "opaque-secret-token"}
    # reasoning 在完整输出及后续请求中保留，工具索引相应偏移。
    for event in events[:-1]:
        event["output_index"] += 1
    events[-1]["response"]["output"].insert(0, reasoning)
    requests = []
    provider = make_provider("openai", events, requests)
    result = [e async for e in provider.stream_chat([])]
    assert result[-1].type == "done"
    conv = Conversation()
    call = result[-1].assistant_message.tool_calls[0]
    conv.add_tool_exchange(result[-1].assistant_message, [ToolResult(call.call_id, call.name, "ok")])
    _ = [e async for e in provider.stream_chat(conv.messages())]
    assert requests[-1]["input"][0] == reasoning
    assert not any("opaque" in e.text for e in result)
    events[-1]["response"]["output"][1]["arguments"] = '{"path":"different"}'
    bad = [e async for e in make_provider("openai", events).stream_chat([])]
    assert bad[-1].type == "error"


async def test_anthropic_preserves_thinking_signature_without_display():
    events = tool_events("anthropic")
    for event in events[:-2]:
        event["index"] += 1
    events[:0] = [
        {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "hidden"}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "signed-secret-token"}},
        {"type": "content_block_stop", "index": 0},
    ]
    result = [e async for e in make_provider("anthropic", events).stream_chat([])]
    assert result[-1].type == "done"
    assert not any(e.text for e in result)
    blocks = result[-1].assistant_message.provider_payload["anthropic_blocks"]
    assert blocks[0]["signature"] == "signed-secret-token"


def test_history_nan_is_diagnostic():
    from weizhcode.models import ToolCall
    call = ToolCall("id", "read_file", '{"path":NaN}')
    conv = Conversation()
    conv.add_tool_exchange(ChatMessage("assistant", tool_calls=(call,)), [ToolResult.failure(call, "INVALID_JSON", "bad")])
    assert conv.messages()[0].provider_payload["diagnostic"]



def test_security_pipeline_encoded_arguments_redacted():
    from weizhcode.providers.qwen import _messages_payload
    from weizhcode.providers.openai import _input_payload
    from weizhcode.models import ToolCall
    raw = '{"content":"secret\\u002dtoken"}'
    call = ToolCall("id", "write_file", raw)
    message = ChatMessage("assistant", tool_calls=(call,))
    for encode in (_messages_payload, _input_payload):
        output = json.dumps(encode([message], Redactor(["secret-token"])))
        assert "redacted" in output
        assert "secret" not in output
    assert call.raw_arguments == raw



@pytest.mark.parametrize("protocol", ["anthropic", "openai", "qwen"])
async def test_interleaved_tool_streams_share_no_buffers(protocol):
    events = tool_events(protocol, count=2)
    if protocol == "anthropic":
        first, second, ending = events[:5], events[5:10], events[10:]
        events = [first[0], second[0], first[1], second[1], first[2], second[2],
                  first[3], second[3], first[4], second[4]] + ending
    elif protocol == "openai":
        first, second, ending = events[:6], events[6:12], events[12:]
        events = [item for pair in zip(first, second) for item in pair] + ending
    else:
        events = [events[0], events[2], events[1], events[3]] + events[4:]
        events[0]["choices"][0]["delta"]["reasoning_content"] = "private thinking"
    result = [e async for e in make_provider(protocol, events).stream_chat([])]
    assert result[-1].type == "done"
    calls = result[-1].assistant_message.tool_calls
    assert [c.call_id for c in calls] == ["call0", "call1"]
    assert all(c.arguments == {"path": "中文.txt"} for c in calls)
    starts = [e.tool_call.local_id for e in result if e.type == "tool_call_start"]
    assert starts == [c.local_id for c in calls]
    assert not any("private thinking" in e.text for e in result)
