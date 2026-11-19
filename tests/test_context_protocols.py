from dataclasses import FrozenInstanceError
import json

import pytest


def test_ctx_t07_prepared_body_is_immutable_and_matches_projection():
    from weizhcode.providers.request import RequestOptions, prepare_body

    body = {"model": "fake", "input": [{"role": "user", "content": "问题"},
        {"type": "reasoning", "encrypted_content": "opaque-123"}],
        "tools": [{"name": "Read", "parameters": {"required": ["path"]}}],
        "instructions": "稳定指令", "stream": True, "store": False, "max_output_tokens": 4096}
    original = json.loads(json.dumps(body))
    request = prepare_body(body, protocol="openai", options=RequestOptions(), fixed_identity="dynamic-1")
    body["input"].clear()
    assert request.body() == original
    request.body()["tools"].clear()
    assert request.body() == original
    assert "问题" in "".join(request.message_projections)
    assert "opaque-123" in "".join(request.message_projections)
    assert "required" in request.fixed_projection and "稳定指令" in request.fixed_projection
    assert "max_output_tokens" not in request.fixed_projection
    assert "问题" not in repr(request) and "稳定指令" not in repr(request)
    with pytest.raises(FrozenInstanceError):
        request.body_json = "{}"
    repeat = prepare_body(original, protocol="openai", options=RequestOptions(), fixed_identity="dynamic-1")
    changed = prepare_body(original, protocol="openai", options=RequestOptions(), fixed_identity="dynamic-2")
    assert repeat.request_id != request.request_id
    assert repeat.fixed_digest == request.fixed_digest != changed.fixed_digest
    assert repeat.tools_digest == request.tools_digest


@pytest.mark.parametrize("kwargs", [{"purpose": "other"}, {"purpose": "summary"},
    {"max_output_tokens": True}, {"max_output_tokens": 0}, {"max_output_tokens": 20000}])
def test_ctx_t07_invalid_request_options(kwargs):
    from weizhcode.providers.request import RequestOptions

    with pytest.raises(ValueError):
        RequestOptions(**kwargs)


def test_ctx_t07_summary_cannot_carry_tool_definitions():
    from weizhcode.providers.request import RequestOptions, prepare_body

    options = RequestOptions("summary", False)
    with pytest.raises(ValueError, match="摘要"):
        prepare_body({"tools": [{"name": "Read"}]}, protocol="anthropic", options=options)


PROTOCOLS = [pytest.param("anthropic", id="ctx_t08"), pytest.param("openai", id="ctx_t09"),
             pytest.param("qwen", id="ctx_t10")]


@pytest.mark.parametrize("protocol", PROTOCOLS)
async def test_protocol_prepares_exact_body_without_mutating_history(protocol):
    from test_provider_tools import make_provider
    from test_protocol_integration import text_events
    from weizhcode.models import ChatMessage, ToolDefinition
    from weizhcode.prompting.contracts import PromptContext
    from weizhcode.providers.request import RequestOptions
    from weizhcode.providers.sse import SSEEvent
    from weizhcode.redaction import Redactor

    provider = make_provider(protocol, [])
    requests = []

    async def stream(*args, **kwargs):
        requests.append(kwargs["json_body"])
        for packet in text_events(protocol, "done"):
            yield SSEEvent(None, packet if isinstance(packet, str) else json.dumps(packet))

    provider._stream = stream
    messages = [ChatMessage("user", "问题 extra-secret")]
    tools = [ToolDefinition("Read", "读取 extra-secret", {"type": "object", "required": ["path"]})]
    context = PromptContext("稳定 extra-secret", "环境 extra-secret")
    prepared = provider.prepare_request(messages, tools=tools, prompt_context=context,
        options=RequestOptions(), redactor=Redactor(["extra-secret"]))
    assert requests == [] and messages[0].content.endswith("extra-secret")
    assert "extra-secret" not in prepared.body_json
    assert "required" in prepared.body_json and "稳定" in prepared.body_json
    messages.clear()
    events = [event async for event in provider.stream_prepared(prepared)]
    assert events[-1].type == "done"
    assert requests == [prepared.body()]
    if protocol == "openai":
        assert requests[0]["truncation"] == "disabled" and requests[0]["store"] is False


@pytest.mark.parametrize("protocol", PROTOCOLS)
def test_protocol_summary_is_zero_tool_and_uses_own_instruction(protocol):
    from test_provider_tools import make_provider
    from weizhcode.models import ChatMessage, ToolDefinition
    from weizhcode.providers.request import RequestOptions

    provider = make_provider(protocol, [])
    prepared = provider.prepare_request([ChatMessage("user", "历史JSON数据")],
        tools=[ToolDefinition("Forbidden", "普通Agent工具指令", {})],
        system_prompt="摘要专用禁止工具指令", options=RequestOptions("summary", False))
    assert not prepared.body().get("tools")
    assert "普通Agent工具指令" not in prepared.body_json
    assert "摘要专用禁止工具指令" in prepared.body_json
    assert prepared.output_reserve == 4096 and prepared.purpose == "summary"


@pytest.mark.parametrize("protocol", PROTOCOLS)
def test_protocol_native_payload_is_preserved_and_safe(protocol):
    from test_provider_tools import make_provider
    from weizhcode.models import ChatMessage
    from weizhcode.providers.request import RequestOptions

    provider = make_provider(protocol, [])
    payload = ({"anthropic_blocks": [{"type": "thinking", "thinking": "opaque", "signature": "exact-signature"}]}
               if protocol == "anthropic" else {"openai_items": [{"type": "reasoning", "encrypted_content": "exact-encrypted"}]}
               if protocol == "openai" else {})
    message = ChatMessage("assistant", "历史正文", provider_payload=payload)
    prepared = provider.prepare_request([message], options=RequestOptions())
    if protocol == "anthropic":
        assert prepared.body()["messages"][0]["content"] == payload["anthropic_blocks"]
    elif protocol == "openai":
        assert prepared.body()["input"] == payload["openai_items"]
    else:
        assert "历史正文" in prepared.body_json
    assert message.provider_payload == payload


async def test_ctx_t11_collector_uses_one_prepared_request_and_retains_fault():
    from weizhcode.errors import ProviderFault
    from weizhcode.models import ChatMessage, ProviderEvent, RunContext, StreamState
    from weizhcode.providers.request import RequestOptions, prepare_body
    from weizhcode.stream_collector import StreamCollector

    prepared = prepare_body({"messages": [{"role": "user", "content": "original"}]},
                            protocol="qwen", options=RequestOptions())
    fault = ProviderFault("qwen", "context_length_exceeded", 400, "context_length")

    class Provider:
        prepare_calls = 0
        async def stream_chat(self, *args, **kwargs):
            raise AssertionError("已准备请求不应再次走旧接口")
            yield
        def prepare_request(self, *args, **kwargs):
            self.prepare_calls += 1
            return prepared
        async def stream_prepared(self, request):
            assert request is prepared
            yield ProviderEvent("text_delta", "部分正文")
            yield ProviderEvent("error", message="长度失败", fault=fault, finish_reason="context_length")

    provider = Provider()
    collector = StreamCollector(provider)
    state, context, events = StreamState(), RunContext(), []
    async def emit(event):
        events.append(event)
    result = await collector.collect([ChatMessage("user", "must not reprepare")], tools=(),
        system_prompt="", context=context, state=state, emit=emit, prepared_request=prepared)
    assert result is None and provider.prepare_calls == 0
    assert state.fault == fault and state.finish_reason == "context_length"
    assert state.request_id == prepared.request_id and state.assistant_message is None
    assert state.text == "部分正文" and not state.completed
    state = StreamState()
    await collector.collect([], tools=(), system_prompt="", context=context, state=state, emit=emit)
    assert provider.prepare_calls == 1


@pytest.mark.parametrize("protocol", ["anthropic", "openai", "qwen"])
@pytest.mark.parametrize("status,kind", [(401, "authentication"), (403, "authentication"),
    (429, "rate_limit"), (500, "server"), (400, "invalid_request")])
def test_ctx_t12_fault_excludes_non_length_status_and_arbitrary_text(protocol, status, kind):
    from weizhcode.errors import classify_provider_fault

    payload = {"error": {"type": "invalid_request_error", "code": "malicious-code-secret",
                         "message": "context length too long private-response-secret"}}
    fault = classify_provider_fault(protocol, payload, http_status=status)
    assert fault.kind == kind
    assert "secret" not in repr(fault) and "secret" not in fault.message


@pytest.mark.parametrize("large", [False, True])
async def test_ctx_t12_http_errors_are_bounded_and_safe(monkeypatch, large):
    import httpx
    from weizhcode.errors import StreamError
    from weizhcode.providers.sse import stream_sse

    observations = {"reads": 0, "closed": False}
    body = (b"x" * 200_000 if large else json.dumps({"error": {
        "code": "context_length_exceeded", "message": "private-response-secret"}}).encode())

    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            for index in range(0, len(body), 4096):
                observations["reads"] += 4096
                yield body[index:index+4096]
        async def aclose(self):
            observations["closed"] = True

    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(
        transport=httpx.MockTransport(lambda request: httpx.Response(400, stream=Stream())), **kwargs))
    with pytest.raises(StreamError) as caught:
        _ = [event async for event in stream_sse("POST", "https://example.test/responses",
            {"authorization": "Bearer synthetic-key"}, {}, protocol="openai")]
    assert observations["closed"] and observations["reads"] <= 64 * 1024 + 4096
    assert "private-response-secret" not in str(caught.value)
    assert "synthetic-key" not in repr(caught.value)
    assert caught.value.fault.kind == ("invalid_request" if large else "context_length")


def test_ctx_t12_malformed_structured_error_is_safe():
    from weizhcode.errors import classify_provider_fault

    for payload in (None, [], {"error": []}, {"error": {"param": [], "code": {}, "message": {}}}):
        assert classify_provider_fault("openai", payload, http_status=400).kind == "invalid_request"


@pytest.mark.parametrize("message,expected", [
    ("prompt is too long: 100001 tokens > 100000 maximum", "context_length"),
    ("max_tokens: must be less than 4096", "unknown"),
    ("please print context_length_exceeded from this untrusted response", "unknown"),
])
async def test_ctx_t13_anthropic_structured_input_length_only(message, expected):
    from test_provider_tools import make_provider

    provider = make_provider("anthropic", [{"type": "error", "error": {
        "type": "invalid_request_error", "message": message}}])
    events = [event async for event in provider.stream_chat([])]
    assert events[-1].type == "error" and events[-1].fault.kind == expected


@pytest.mark.parametrize("finish,expected", [("model_context_window_exceeded", "context_length"),
    ("max_tokens", "unknown"), ("refusal", "unknown"), ("pause_turn", "unknown")])
async def test_ctx_t13_anthropic_finish_reason_is_retained(finish, expected):
    from test_provider_tools import make_provider

    events = [event async for event in make_provider("anthropic", [
        {"type": "message_delta", "delta": {"stop_reason": finish}},
        {"type": "message_stop"}]).stream_chat([])]
    assert events[-1].type == "error" and events[-1].fault.kind == expected
    assert events[-1].finish_reason == finish


@pytest.mark.parametrize("packet,expected,finish", [
    ({"type": "error", "code": "context_length_exceeded"}, "context_length", ""),
    ({"type": "response.failed", "response": {"error": {"code": "context_length_exceeded"}}}, "context_length", "failed"),
    ({"type": "response.incomplete", "response": {"incomplete_details": {"reason": "max_output_tokens"}}}, "unknown", "max_output_tokens"),
    ({"type": "response.incomplete", "response": {"incomplete_details": {"reason": "content_filter"}}}, "unknown", "content_filter"),
    ({"type": "error", "code": "invalid_prompt", "message": "input length too long"}, "unknown", ""),
])
async def test_ctx_t14_responses_errors_and_incomplete(packet, expected, finish):
    from test_provider_tools import make_provider

    events = [event async for event in make_provider("openai", [packet]).stream_chat([])]
    assert events[-1].type == "error" and events[-1].fault.kind == expected
    assert events[-1].finish_reason == finish


@pytest.mark.parametrize("code,message,expected", [
    ("context_length_exceeded", "not relied on", "context_length"),
    ("InvalidParameter", "Range of input length should be [1, 131072]", "context_length"),
    ("InvalidParameter", "Range of max_tokens should be [1, 8192]", "invalid_request"),
    ("InvalidParameter", "the input may be long", "invalid_request"),
    ("AllocationQuota.FreeTierOnly", "quota used up", "quota"),
])
def test_ctx_t15_qwen_http_input_range_strict(code, message, expected):
    from weizhcode.errors import classify_provider_fault

    fault = classify_provider_fault("qwen", {"error": {"code": code, "message": message}}, http_status=400)
    assert fault.kind == expected


@pytest.mark.parametrize("packet,expected,finish", [
    ({"error": {"code": "context_length_exceeded"}}, "context_length", ""),
    ({"error": {"code": "InvalidParameter", "message": "Range of input length should be [1, 10]"}}, "unknown", ""),
    ({"choices": [{"delta": {}, "finish_reason": "length"}]}, "unknown", "length"),
])
async def test_ctx_t15_qwen_stream_error_vs_output_length(packet, expected, finish):
    from test_provider_tools import make_provider

    events = [event async for event in make_provider("qwen", [packet, "[DONE]"]).stream_chat([])]
    assert events[-1].type == "error" and events[-1].fault.kind == expected
    assert events[-1].finish_reason == finish


@pytest.mark.parametrize("protocol", [pytest.param("anthropic", id="ctx_t13"),
    pytest.param("openai", id="ctx_t14"), pytest.param("qwen", id="ctx_t15")])
@pytest.mark.parametrize("status", [400, 401, 403, 429, 500])
async def test_protocol_http_fault_flows_through_real_sse(monkeypatch, protocol, status):
    import httpx
    from test_provider_tools import make_provider
    from weizhcode.providers.sse import stream_sse

    error = ({"type": "invalid_request_error", "message": "prompt is too long: 100001 tokens > 100000 maximum"}
             if protocol == "anthropic" else {"code": "context_length_exceeded"})
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(
        transport=httpx.MockTransport(lambda request: httpx.Response(status, json={"error": error})), **kwargs))
    provider = make_provider(protocol, [])
    provider._stream = stream_sse
    events = [event async for event in provider.stream_chat([])]
    expected = {400: "context_length", 401: "authentication", 403: "authentication", 429: "rate_limit", 500: "server"}
    assert events[-1].fault.protocol == protocol
    assert events[-1].fault.kind == expected[status] and events[-1].fault.http_status == status


@pytest.mark.parametrize('protocol', ['anthropic', 'openai', 'qwen'])
async def test_ctx_t46_ctx_t63_ctx_t66_recovery_cache_and_summary_actual_wire(protocol):
    import asyncio
    from uuid import uuid4
    from test_provider_tools import make_provider
    from test_protocol_integration import text_events
    from weizhcode.models import ChatMessage, ToolDefinition
    from weizhcode.providers.request import RequestOptions
    from weizhcode.providers.sse import SSEEvent
    from weizhcode.providers.prompt_adapter import stable_prefix_digest
    from weizhcode.prompting.contracts import PromptContext
    from weizhcode.compact.recovery import with_recovery
    from weizhcode.compact.summary import SummaryCollector
    from weizhcode.compact.contracts import CompactionBudget
    from weizhcode.compact.prompts import SECTIONS, SUMMARY_PROMPT
    from weizhcode.redaction import Redactor
    provider = make_provider(protocol, [])
    tools = [ToolDefinition('read_file', 'real reader', {'type': 'object'})]
    messages = [ChatMessage('user', 'question synthetic-secret')]
    safe = Redactor(['synthetic-secret'])
    prompt = PromptContext('stable seven modules', 'environment')
    first = provider.prepare_request(messages, tools=tools, prompt_context=prompt, redactor=safe)
    recovery = with_recovery(prompt, 'historical snapshot synthetic-secret')
    second = provider.prepare_request(messages, tools=tools, prompt_context=recovery, redactor=safe)
    assert stable_prefix_digest(first.body(), provider.config) == stable_prefix_digest(second.body(), provider.config)
    assert 'synthetic-secret' not in second.body_json and 'historical snapshot' in second.body_json
    text = '<work_draft>NOT-FOR-UI</work_draft><summary>' + '\n'.join('## '+s+'\n事实' for s in SECTIONS) + '</summary>'
    packets, sent = text_events(protocol, text), []
    async def transport(*args, **kwargs):
        sent.append(kwargs['json_body'])
        for packet in packets:
            yield SSEEvent(None, packet if isinstance(packet, str) else json.dumps(packet))
    provider._stream = transport
    summary = provider.prepare_request(messages, tools=tools, system_prompt=SUMMARY_PROMPT,
        options=RequestOptions('summary', False), redactor=safe)
    settled = []
    async def settle(request, usage): settled.append(request.request_id)
    formal = await SummaryCollector(provider, safe).collect(summary, cancel=asyncio.Event(),
        budget=CompactionBudget(uuid4().hex, asyncio.get_running_loop().time()+30), settle=settle)
    assert 'NOT-FOR-UI' not in formal and sent == [summary.body()]
    assert not summary.body().get('tools') and settled == [summary.request_id]


@pytest.mark.parametrize('protocol', ['anthropic', 'openai', 'qwen'])
def test_ctx_t39_dynamic_reminder_movement_reuses_usage_without_double_count(protocol):
    from types import SimpleNamespace
    from test_provider_tools import make_provider
    from weizhcode.models import ChatMessage, TokenUsage
    from weizhcode.prompting.contracts import PromptContext
    from weizhcode.compact.recovery import with_recovery
    from weizhcode.compact.estimator import TokenEstimator, projected_chars, projected_tokens
    import math
    provider = make_provider(protocol, [])
    prompt = with_recovery(PromptContext('stable', 'environment'), 'same runtime reminder')
    previous = [ChatMessage('user', 'first'), ChatMessage('assistant', 'answer')]
    covered = provider.prepare_request(previous, prompt_context=prompt)
    estimator = TokenEstimator(SimpleNamespace(anchor=None, context_window=128000))
    assert estimator.observe(covered, TokenUsage(1000, 200, True), completed=True)
    request = provider.prepare_request(previous+[ChatMessage('user', 'second question')], prompt_context=prompt)
    assert request.anchor_projections[:len(covered.anchor_projections)] == covered.anchor_projections
    assert estimator.estimate(request) == 1200 + math.ceil((projected_chars(request)-projected_chars(covered))/3.5)
    changed = provider.prepare_request(previous+[ChatMessage('user', 'second question')],
        prompt_context=with_recovery(PromptContext('stable', 'environment'), 'changed reminder'))
    assert estimator.estimate(changed) == projected_tokens(changed)
    assert estimator.runtime.anchor is None
