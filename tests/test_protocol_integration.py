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
    runner = TurnRunner(provider, conv, registry, executor, Redactor())
    async def deny(request):
        return False
    try:
        events = [e async for e in runner.run("test", approve=deny)]
        assert events[-1].type == "turn_done"
        assert len(requests) == 2
        assert not (tmp_path / "created.txt").exists()
        expected_workers = 0 if scenario in {"multiple", "diagnostic", "duplicate_id", "missing_id"} else 1
        assert len(count) == expected_workers
        results = [e.result for e in events if e.result]
        expected = {"missing":"FILE_NOT_FOUND", "denied":"USER_DENIED", "multiple":"TOO_MANY_TOOL_CALLS",
                    "final_limit":"TOOL_ROUND_LIMIT", "diagnostic":"INVALID_JSON",
                    "duplicate_id":"TOO_MANY_TOOL_CALLS", "missing_id":"INVALID_ARGUMENTS"}[scenario]
        assert any(r.error_code == expected for r in results)
        assert requests[1]["tool_choice"] == ({"type":"none"} if protocol == "anthropic" else "none")
        _ = [e async for e in runner.run("next")]
        assert len(requests) == 3 and len(count) == expected_workers
        assert conv.messages()[-1].content == "next"
        if scenario in {"diagnostic", "duplicate_id", "missing_id"}:
            assert "仅用于诊断" in json.dumps(requests[1], ensure_ascii=False)
    finally:
        await runner.aclose()
