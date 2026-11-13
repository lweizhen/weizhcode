from __future__ import annotations

import re
from copy import deepcopy


_ANSI = re.compile(r"\x1b(?:\][^\x07\x1b]*(?:\x07|\x1b\\)|\[[0-?]*[ -/]*[@-~]|[@-_])")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def safe_text(text: str) -> str:
    return _CONTROL.sub("", _ANSI.sub("", text))


class Redactor:
    def __init__(self, secrets=()) -> None:
        self.secrets = tuple(sorted({s for s in secrets if isinstance(s, str) and s}, key=len, reverse=True))

    def text(self, text: str) -> str:
        for secret in self.secrets:
            text = text.replace(secret, "[redacted]")
        return text

    def value(self, value):
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, dict):
            return {self.text(str(k)): self.value(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.value(v) for v in value]
        return deepcopy(value)

    def display(self, text: str) -> str:
        return safe_text(self.text(text))


class StreamingRedactor:
    """不先输出可能属于密钥的前缀，避免分片规避脱敏。"""

    def __init__(self, redactor: Redactor) -> None:
        self.redactor = redactor
        self.pending = ""

    def push(self, text: str, *, final: bool = False) -> str:
        self.pending += text
        output: list[str] = []
        index = 0
        while index < len(self.pending):
            tail = self.pending[index:]
            match = next((s for s in self.redactor.secrets if tail.startswith(s)), None)
            if match:
                output.append("[redacted]")
                index += len(match)
            elif not final and any(s.startswith(tail) for s in self.redactor.secrets):
                break
            else:
                output.append(self.pending[index])
                index += 1
        self.pending = self.pending[index:]
        return "".join(output)

    def finish(self) -> str:
        return self.push("", final=True)
