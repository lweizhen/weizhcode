import pytest

from weizhcode.redaction import Redactor, StreamingRedactor, safe_text


@pytest.mark.parametrize("name", ["write_file", "run_command"])
async def test_loop_security_pipeline_events_safe_actual_bytes_preserved(tmp_path, name):
    import json
    from dataclasses import asdict
    from weizhcode.conversation import Conversation
    from weizhcode.models import ToolCall, ToolContext
    from weizhcode.tools import create_default_registry
    from weizhcode.tools.executor import ToolExecutor
    from weizhcode.turn_runner import TurnRunner
    from test_turn_runner import FakeProvider, reply
    from test_command_tool import python_command
    secret = "fake-secret-token"
    if name == "write_file":
        args = {"path": "marker", "content": secret}
    else:
        code = f"from pathlib import Path; Path('marker').write_text({secret!r}); print({secret!r})"
        args = {"command": python_command(code)}
    call = ToolCall("a", name, json.dumps(args))
    provider = FakeProvider([reply("before", (call,)), reply("done " + secret)])
    registry, safe, conv = create_default_registry(), Redactor([secret]), Conversation()
    runner = TurnRunner(provider, conv, registry, ToolExecutor(registry, ToolContext(tmp_path), safe), safe)
    events = [e async for e in runner.run("act")]
    assert events[-1].reason == "completed"
    assert secret not in json.dumps([asdict(e) for e in events])
    assert (tmp_path / "marker").read_text() == secret
    assert all(secret not in r.to_model_text() for m in conv.messages() for r in m.tool_results)


def test_redact_batch_copies_without_mutating_actual_parameters():
    source = {"command": "echo secret-123", "nested": ["secret-123 secret-123"]}
    safe = Redactor(("secret-123",)).value(source)
    assert "secret-123" not in str(safe)
    assert source["command"] == "echo secret-123"
    assert safe_text("a\x1b[31mb\x1b[0m\x1b]0;bad\x07\x00c") == "abc"
    assert safe_text("[bold]literal[/bold]\n") == "[bold]literal[/bold]\n"


@pytest.mark.parametrize("cut", range(1, 19))
def test_redact_stream_every_split(cut):
    secret = "a-secret-1234567890"
    redactor = StreamingRedactor(Redactor((secret,)))
    visible = redactor.push("prefix " + secret[:cut])
    if cut > 7:
        assert secret[:cut] not in visible
    visible += redactor.push(secret[cut:] + " suffix")
    visible += redactor.finish()
    assert visible == "prefix [redacted] suffix"


def test_redact_stream_overlapping_secrets_and_plain_tail():
    stream = StreamingRedactor(Redactor(("abcde", "deX")))
    text = stream.push("abcde") + stream.finish()
    assert text == "[redacted]"
    stream = StreamingRedactor(Redactor(("abcdef",)))
    assert stream.push("plain abc") + stream.finish() == "plain abc"
