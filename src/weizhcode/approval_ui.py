from textual import events
from textual.message import Message
from textual.widgets import Static

from weizhcode.permissions.types import ApprovalChoice


CHOICES = (ApprovalChoice.ONCE, ApprovalChoice.SESSION, ApprovalChoice.PERMANENT, ApprovalChoice.DENY)
LABELS = ("允许本次", "允许本会话（精确目标）", "永久允许（写入本地配置）", "拒绝本次")


class ApprovalView(Static):
    can_focus = True
    DEFAULT_CSS = "ApprovalView { height: auto; margin-bottom: 1; padding: 1; border-left: solid #e5bb68; color: #dccbaa; }"

    class Chosen(Message):
        def __init__(self, view, choice):
            self.view, self.choice = view, choice
            super().__init__()

    def __init__(self, request):
        self.request = request
        self.cursor = 0
        self.active = True
        self.outcome = ""
        super().__init__(self.body(), markup=False)

    def body(self):
        req = self.request
        lines = [f"● {req.friendly_name} — 等待批准", req.arguments_preview, f"目标：{req.target_preview}",
                 req.reason, req.scope_hint]
        if self.active:
            lines += [("› " if i == self.cursor else "  ") + f"{i+1}. {label}" for i, label in enumerate(LABELS)]
            lines.append("↑↓ 选择 · 回车确认 · 1–4 直选 · Esc 取消")
        else:
            lines.append(self.outcome or "审批已结束")
        return "\n".join(lines)

    def finish(self, outcome="审批已结束"):
        self.active = False
        self.outcome = outcome
        self.update(self.body())

    def on_key(self, event: events.Key):
        if not self.active:
            return
        if event.key in {"up", "down", "enter", "1", "2", "3", "4"}:
            event.stop()
            event.prevent_default()
            if event.key in {"up", "down"}:
                self.cursor = (self.cursor + (1 if event.key == "down" else -1)) % 4
                self.update(self.body())
            else:
                index = self.cursor if event.key == "enter" else int(event.key) - 1
                self.post_message(self.Chosen(self, CHOICES[index]))
