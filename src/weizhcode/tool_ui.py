from __future__ import annotations

import json

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Static

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
    ToolCallView .tool-preview { height: auto; max-height: 18; overflow-y: auto; color: #a8a8a8; }
    ToolCallView .tool-buttons { height: auto; }
    ToolCallView Button { min-width: 12; width: auto; margin: 0 1 0 0; }
    ToolCallView.failed .tool-detail { color: #e87979; }
    ToolCallView.succeeded .tool-detail { color: #83c9a5; }
    """

    class Decision(Message):
        def __init__(self, request_id, operation_id, allowed):
            super().__init__()
            self.request_id = request_id
            self.operation_id = operation_id
            self.allowed = allowed

    def __init__(self, call, redactor=None):
        super().__init__()
        self.call = call
        self.redactor = redactor or Redactor()
        self.state = "Receiving…"
        self.request = None
        self.decided = False
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
        preview = Static("", classes="tool-preview", markup=False)
        preview.display = False
        yield preview
        row = Horizontal(classes="tool-buttons")
        row.display = False
        with row:
            yield Button("允许本次", id="allow", variant="success")
            yield Button("拒绝本次", id="deny", variant="default")

    def update_call(self, call):
        self.call = call
        self.query_one(".tool-title", Static).update(self.title())

    def set_state(self, state):
        self.state = state
        self.query_one(".tool-detail", Static).update(self.redactor.display(state))

    def show_approval(self, request):
        self.request = request
        self.set_state("等待确认（默认拒绝）")
        if request.command:
            text = f"执行目录: {request.cwd}\n完整命令:\n{request.command}"
        else:
            text = f"实际目标: {request.target}\n变更预览:\n{request.preview}"
            if request.preview_truncated:
                text += "\n[预览已截断；批准绑定完整操作]"
        preview = self.query_one(".tool-preview", Static)
        preview.update(self.redactor.display(text))
        preview.display = True
        self.query_one(".tool-buttons").display = True
        self.query_one("#deny", Button).focus()

    def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        if self.request is None or self.decided:
            return
        self.decided = True
        for button in self.query(Button):
            button.disabled = True
        allowed = event.button.id == "allow"
        self.set_state("已允许本次" if allowed else "已拒绝本次")
        self.post_message(self.Decision(self.request.request_id, self.request.operation_id, allowed))

    def finish(self, result):
        self.summary = result_summary(result, self.redactor)
        self.add_class("failed" if result.is_error else "succeeded")
        label = {"success": "完成", "error": "失败", "denied": "已拒绝", "timeout": "已超时"}[result.status]
        self.set_state(label + ("\n" + self.summary if self.summary else ""))
        self.query_one(".tool-buttons").display = False

    def invalidate(self):
        self.decided = True
        for button in self.query(Button):
            button.disabled = True
