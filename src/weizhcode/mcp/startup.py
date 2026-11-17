import json
import sys
from uuid import uuid4

from .contracts import TrustRequest


class StartupTrustPrompt:
    def __init__(self, redactor, *, ask=input, output=print, is_tty=None):
        self.redactor, self.ask, self.output = redactor, ask, output
        self.is_tty = sys.stdin.isatty() if is_tty is None else is_tty

    def choose(self, request):
        self.output(self.redactor.display(request.preview))
        self.output(request.scope_hint)
        if not self.is_tty:
            return "skip"
        try:
            answer = self.ask("1 信任并记住此配置 / 2 跳过 [默认跳过]: ").strip()
        except EOFError:
            return "skip"
        return "trust" if answer == "1" else "skip"


def request_for(config, redactor, startup_id):
    target = (json.dumps([config.command, *config.args], ensure_ascii=False) if config.transport == "stdio"
              else config.url.split("?", 1)[0])
    preview = redactor.display(f"项目MCP Server {config.name} ({config.transport})\n{target}")
    if len(preview) > 4096:
        preview = preview[:4070] + "…[truncated]"
    return TrustRequest(startup_id, uuid4().hex, config.name, preview,
                        "启动可能执行本地代码/联网发送认证；信任只绑定此项目和配置，不等于允许工具调用。")
