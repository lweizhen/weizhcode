import pytest

from weizhcode.redaction import Redactor, StreamingRedactor, safe_text


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
