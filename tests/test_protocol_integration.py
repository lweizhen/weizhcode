import json

import pytest

from weizhcode.conversation import Conversation
from weizhcode.models import ToolContext
from weizhcode.providers.sse import SSEEvent
from weizhcode.redaction import Redactor
from weizhcode.tools import create_default_registry
from weizhcode.tools.executor import ToolExecutor
from weizhcode.turn_runner import TurnRunner
from test_provider_tools import make_provider, tool_events


def loop_tool_events(protocol, name, args, prefix):
    packets = tool_events(protocol, raw=json.dumps(args, ensure_ascii=False))
    def transform(value, key=""):
        if isinstance(value, dict):
            return {k: transform(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [transform(v) for v in value]
        if key == "name":
            return {"read_file": name, "read_": name, "file": ""}.get(value, value)
        if key in {"id", "call_id", "item_id"} and isinstance(value, str):
            return prefix + value
        return value
    return [transform(p) for p in packets]


@pytest.mark.parametrize("protocol", ["anthropic", "openai", "qwen"])
async def test_ask_question_protocol_roundtrip(tmp_path, protocol):
    scripts = [loop_tool_events(protocol, "AskUserQuestion", {"question":"部署范围？", "options":["本地","团队"]}, "q"),
               text_events(protocol, "确认本地使用，等待 /do")]
    requests = []
    provider = make_provider(protocol, [])
    async def stream(*args, **kwargs):
        requests.append(kwargs["json_body"])
        for packet in scripts.pop(0):
            yield SSEEvent(None, packet if isinstance(packet, str) else json.dumps(packet))
    provider._stream = stream
    registry, conv = create_default_registry(), Conversation()
    runner = TurnRunner(provider, conv, registry, ToolExecutor(registry, ToolContext(tmp_path)))
    token = runner.bind_questions()
    runner.set_mode("plan")
    try:
        async for event in runner.run("计划"):
            if event.type == "question_request":
                assert runner.submit_answer(event.run_id, event.question.question_id, {"option_index":0})[0]
        assert len(requests) == 2
        assert "本地" in json.dumps(requests[-1], ensure_ascii=False)
        assert conv.messages()[-1].content == "确认本地使用，等待 /do"
        assert not list(tmp_path.iterdir())
    finally:
        runner.unbind_questions(token)
        await runner.aclose()


def add_usage(protocol, script):
    import copy
    script = copy.deepcopy(script)
    if protocol == "anthropic":
        script.insert(0, {"type": "message_start", "message": {"usage": {"input_tokens": 10, "output_tokens": 0}}})
        usage = {"type": "message_delta", "usage": {"output_tokens": 2}}
        index = len(script)-1 if script[-1].get("type") == "message_stop" else len(script)
        script[index:index] = [usage, usage]
    elif protocol == "openai":
        for item in script:
            if item.get("type") == "response.completed":
                item["response"]["usage"] = {"input_tokens": 10, "output_tokens": 2,
                    "input_tokens_details": {"cached_tokens": 5}, "output_tokens_details": {"reasoning_tokens": 1}}
    else:
        usage = {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}}
        index = len(script)-1 if script[-1] == "[DONE]" else len(script)
        script[index:index] = [usage, usage]
    return script


@pytest.mark.parametrize("protocol", ["anthropic", "openai", "qwen"])
@pytest.mark.parametrize("scenario", ["multistep", "tool_failure", "unknown", "plan_violation", "incomplete", "cancel", "usage_missing"])
async def test_loop_protocol_integration_same_scenarios(tmp_path, protocol, scenario):
    import asyncio
    (tmp_path / "fixture").write_text("actual fixture 731", encoding="utf-8")
    read = loop_tool_events(protocol, "read_file", {"path": "fixture"}, "r1")
    text = text_events(protocol, "done 731")
    scripts = {
        "multistep": [read, loop_tool_events(protocol, "write_file", {"path":"summary", "content":"summary 731"}, "r2"),
                      loop_tool_events(protocol, "read_file", {"path":"summary"}, "r3"), text],
        "tool_failure": [loop_tool_events(protocol, "read_file", {"path":"missing"}, "r1"), read, text],
        "unknown": [loop_tool_events(protocol, "not_registered", {}, f"r{i}") for i in range(3)],
        "plan_violation": [loop_tool_events(protocol, "write_file", {"path":"forbidden", "content":"bad"}, "r1"), text],
        "incomplete": [read[:-1]], "cancel": [read, "wait"], "usage_missing": [read, text],
    }[scenario]
    expected_requests = len(scripts)
    scripts.append(text_events(protocol, "next"))
    entered, source_closed, requests, workers = asyncio.Event(), asyncio.Event(), [], []
    provider = make_provider(protocol, [])
    async def stream(*args, **kwargs):
        requests.append(kwargs["json_body"])
        script = scripts.pop(0)
        if script == "wait":
            try:
                entered.set()
                await asyncio.Event().wait()
            finally:
                source_closed.set()
            return
        if scenario != "usage_missing":
            script = add_usage(protocol, script)
        for packet in script:
            yield SSEEvent(None, packet if isinstance(packet, str) else json.dumps(packet))
    provider._stream = stream
    registry, conv = create_default_registry(), Conversation()
    from weizhcode.tools.process import ManagedWorker
    def factory():
        worker = ManagedWorker()
        workers.append(worker)
        return worker
    runner = TurnRunner(provider, conv, registry, ToolExecutor(registry, ToolContext(tmp_path), worker_factory=factory))
    if scenario == "plan_violation":
        runner.set_mode("plan")
    async def consume():
        return [e async for e in runner.run("task")]
    work = asyncio.create_task(consume())
    try:
        if scenario == "cancel":
            await asyncio.wait_for(entered.wait(), 5)
            runner.cancel_current()
        events = await asyncio.wait_for(work, 15)
        expected_reason = {"unknown":"unknown_tools", "incomplete":"provider_error", "cancel":"cancelled"}.get(scenario, "completed")
        assert events[-1].reason == expected_reason
        assert len(requests) == expected_requests
        assert all(w.process is not None and w.process.returncode is not None for w in workers)
        for message in conv.messages():
            if message.tool_results:
                assert all(r.call_id is not None for r in message.tool_results)
        if scenario == "multistep":
            assert (tmp_path / "summary").read_text() == "summary 731"
            assert len(workers) == 3
            assert (runner.usage_totals.input_tokens, runner.usage_totals.output_tokens) == (40, 8)
            assert runner.usage_totals.incomplete_requests == 0
        if scenario == "plan_violation":
            assert not workers and not (tmp_path / "forbidden").exists()
            assert conv.messages()[2].tool_results[0].error_code == "TOOL_NOT_ALLOWED"
        if scenario in {"unknown", "incomplete"}:
            assert not workers
        if scenario == "usage_missing":
            assert runner.usage_totals.incomplete_requests == expected_requests
            assert runner.usage_totals.input_requests == runner.usage_totals.output_requests == 0
        if scenario == "cancel":
            assert source_closed.is_set() and conv.messages()[2].tool_results[0].status == "success"
        if scenario == "tool_failure":
            assert conv.messages()[2].tool_results[0].error_code == "FILE_NOT_FOUND"
        recovered = [e async for e in runner.run("next")]
        assert recovered[-1].reason == "completed" and conv.messages()[-1].content == "next"
        assert len(requests) == expected_requests + 1
    finally:
        await runner.aclose()


def text_events(protocol, text="done"):
    return {
        "anthropic": [{"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}},
                      {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":text}},
                      {"type":"content_block_stop","index":0},
                      {"type":"message_delta","delta":{"stop_reason":"end_turn"}},{"type":"message_stop"}],
        "openai": [{"type":"response.output_text.delta","delta":text},
                   {"type":"response.completed","response":{"status":"completed","output":[]}}],
        "qwen": [{"choices":[{"delta":{"content":text}}]},
                 {"choices":[{"delta":{},"finish_reason":"stop"}]}, "[DONE]"],
    }[protocol]


@pytest.mark.parametrize("protocol", ["anthropic", "openai", "qwen"])
@pytest.mark.parametrize("scenario", ["missing", "denied", "multiple", "final_limit", "diagnostic", "duplicate_id", "missing_id"])
async def test_protocol_integration_boundaries(tmp_path, protocol, scenario):
    (tmp_path / "中文.txt").write_text("fixture", encoding="utf-8")
    raw = '{"path":"missing"}' if scenario == "missing" else '{"path":"中文.txt"}'
    if scenario == "denied":
        raw = '{"path":"created.txt","content":"new"}'
    if scenario == "diagnostic":
        raw = '{"path":'
    first = tool_events(protocol, raw=raw, count=2 if scenario in {"multiple", "duplicate_id"} else 1)
    if scenario in {"duplicate_id", "missing_id"}:
        def modify(value):
            if isinstance(value, dict):
                return {k: (None if scenario == "missing_id" and k in {"id", "call_id"} and v == "call0" else modify(v))
                        for k, v in value.items()}
            if isinstance(value, list):
                return [modify(item) for item in value]
            return "call0" if scenario == "duplicate_id" and value == "call1" else value
        first = [modify(e) for e in first]
    if scenario == "denied":
        first = [json.loads(json.dumps(e).replace("read_file", "write_file").replace("read_", "write_"))
                 if not isinstance(e, str) else e for e in first]
    second = tool_events(protocol) if scenario == "final_limit" else text_events(protocol)
    scripts = [first, second, text_events(protocol, "next")]
    requests = []
    provider = make_provider(protocol, [])
    async def stream(*args, **kwargs):
        requests.append(kwargs["json_body"])
        for item in scripts.pop(0):
            yield SSEEvent(None, item if isinstance(item, str) else json.dumps(item, ensure_ascii=False))
    provider._stream = stream
    registry = create_default_registry()
    executor = ToolExecutor(registry, ToolContext(tmp_path))
    count = []
    original = executor.worker_factory
    def factory():
        count.append(1)
        return original()
    executor.worker_factory = factory
    conv = Conversation()
    runner = TurnRunner(provider, conv, registry, executor, Redactor(), max_iterations=2 if scenario == "final_limit" else 25)
    if scenario == "denied":
        runner.set_mode("plan")
    try:
        events = [e async for e in runner.run("test")]
        assert events[-1].type == "turn_done"
        assert len(requests) == 2
        assert not (tmp_path / "created.txt").exists()
        expected_workers = {"missing":1, "denied":0, "multiple":2, "final_limit":2, "diagnostic":0, "duplicate_id":0, "missing_id":0}[scenario]
        assert len(count) == expected_workers
        results = [e.result for e in events if e.result]
        expected = {"missing":"FILE_NOT_FOUND", "denied":"TOOL_NOT_ALLOWED", "multiple":None,
                    "final_limit":None, "diagnostic":"INVALID_JSON",
                    "duplicate_id":"DUPLICATE_CALL_ID", "missing_id":"INVALID_ARGUMENTS"}[scenario]
        assert any(r.error_code == expected for r in results)
        assert requests[1]["tool_choice"] == ({"type":"auto"} if protocol == "anthropic" else "auto")
        _ = [e async for e in runner.run("next")]
        assert len(requests) == 3 and len(count) == expected_workers
        assert conv.messages()[-1].content == "next"
        if scenario in {"diagnostic", "duplicate_id", "missing_id"}:
            assert "仅用于诊断" in json.dumps(requests[1], ensure_ascii=False)
    finally:
        await runner.aclose()
