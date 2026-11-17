"""Bounded diagnostic projection. It never prints raw server output."""
import codecs
import logging

from weizhcode.redaction import StreamingRedactor, safe_text
from .limits import MAX_DIAGNOSTIC_CHARS, MAX_DIAGNOSTICS, MAX_STDERR_CHARS


class DiagnosticCollector:
    def __init__(self, redactor):
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self._redactor = StreamingRedactor(redactor)
        self._messages = []
        self._bytes = 0
        self.dropped_bytes = 0
        self._finished = False

    @property
    def messages(self):
        return tuple(self._messages)

    def _collect(self, text):
        text = safe_text(text)
        raw = text.encode("utf-8")
        available = max(0, MAX_STDERR_CHARS - self._bytes)
        if len(self._messages) >= MAX_DIAGNOSTICS:
            available = 0
        excerpt = raw[:available].decode("utf-8", "ignore")[:MAX_DIAGNOSTIC_CHARS]
        kept = len(excerpt.encode("utf-8"))
        self.dropped_bytes += len(raw) - kept
        if excerpt:
            self._messages.append(excerpt)
            self._bytes += kept

    def push(self, chunk):
        if self._finished:
            raise RuntimeError("Diagnostic stream already finished")
        self._collect(self._redactor.push(self._decoder.decode(chunk)))

    def finish(self):
        if not self._finished:
            self._collect(self._redactor.push(self._decoder.decode(b"", final=True), final=True))
            self._finished = True

    async def drain(self, reader):
        try:
            while chunk := await reader.read(4096):
                self.push(chunk)
        finally:
            self.finish()


class SdkDiagnosticHandler(logging.Handler):
    """SDK error messages may embed protocol data; only expose a fixed level code."""
    def __init__(self, publish):
        super().__init__()
        self.publish = publish

    def emit(self, record):
        level = "ERROR" if record.levelno >= logging.ERROR else "WARNING"
        self.publish("MCP_SDK_" + level)
