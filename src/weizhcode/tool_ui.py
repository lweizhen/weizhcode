from __future__ import annotations

import json

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from weizhcode.redaction import Redactor


def result_summary(result, redactor):
    text = redactor.display(result.content)
    if result.error_code:
        text = f"{result.error_code}: {text}"
    lines = text.splitlines()
    clipped = len(lines) > 8 or len(text) > 1000 or result.truncated
    text = "\n".join(lines[:8])[:1000]
    if clipped:
        marker = " … [truncated]"
        text = text[:1000-len(marker)] + marker
        # 标记放在末行，不额外突破行数上限。
    return text


class ToolCallView(Vertical):
    DEFAULT_CSS = """
    ToolCallView { height: auto; margin-bottom: 1; padding: 0 1; border-left: solid #726b89; }
    ToolCallView .tool-title { height: auto; color: #bda8e6; }
    ToolCallView .tool-detail { height: auto; color: #999999; }
    ToolCallView.failed .tool-detail { color: #e87979; }
    ToolCallView.succeeded .tool-detail { color: #83c9a5; }
    """

    def __init__(self, call, redactor=None):
        super().__init__()
        self.call = call
        self.redactor = redactor or Redactor()
        self.state = "Receiving…"
        self.summary = ""

    def title(self):
        args = self.call.arguments
        if args is None:
            args = self.call.raw_arguments or "接收参数中"
        elif isinstance(args, dict):
            args = {k: v for k, v in args.items() if k in {"path", "pattern", "command", "cwd", "start_line"}}
        text = self.redactor.display(args) if isinstance(args, str) else json.dumps(self.redactor.value(args), ensure_ascii=False)
        return self.redactor.display(f"● {self.call.name}({text[:220]})")

    def compose(self) -> ComposeResult:
        yield Static(self.title(), classes="tool-title", markup=False)
        yield Static(self.state, classes="tool-detail", markup=False)

    def update_call(self, call):
        self.call = call
        self.query_one(".tool-title", Static).update(self.title())

    def set_state(self, state):
        self.state = state
        self.query_one(".tool-detail", Static).update(self.redactor.display(state))

    def finish(self, result):
        self.summary = result_summary(result, self.redactor)
        self.add_class("failed" if result.is_error else "succeeded")
        label = {"success": "完成", "error": "失败", "denied": "已拒绝", "timeout": "已超时",
                 "cancelled": "已取消"}[result.status]
        self.set_state(label + ("\n" + self.summary if self.summary else ""))

    def invalidate(self):
        if self.state in {"Receiving…", "Queued…", "Preparing…", "Running…"}:
            self.set_state("已停止，状态以实际结果为准")
