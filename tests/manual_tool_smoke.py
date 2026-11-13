"""手动线上冒烟验证：仅使用当前默认供应商，不修改用户配置，不打印凭证。"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from weizhcode.config import load_config, resolve_default_provider, ENV_REF_RE
from weizhcode.conversation import Conversation
from weizhcode.models import ToolContext
from weizhcode.providers import create_provider
from weizhcode.redaction import Redactor
from weizhcode.tools import create_default_registry
from weizhcode.tools.executor import ToolExecutor
from weizhcode.turn_runner import TurnRunner


async def main():
    config = load_config()
    active = resolve_default_provider(config)
    redactor = Redactor(p.api_key for p in config.providers if not ENV_REF_RE.fullmatch(p.api_key))
    print(json.dumps({"protocol": active.protocol, "model": active.model,
                      "host": urlsplit(active.base_url).hostname}, ensure_ascii=False), flush=True)
    with TemporaryDirectory(prefix="weizhcode-live-") as folder:
        root = Path(folder)
        (root / "fixture.txt").write_text("Project fruit: orange. Fixture number: 731.\n", encoding="utf-8")
        registry = create_default_registry()
        conv = Conversation()
        executor = ToolExecutor(registry, ToolContext(root), redactor)
        runner = TurnRunner(create_provider(active), conv, registry, executor, redactor)
        scenarios = [
            ("read", f"仅调用一次 read_file 读取 {root / 'fixture.txt'}，然后用中文一句话总结文件内容。"),
            ("missing", f"仅调用一次 read_file 读取 {root / 'missing.txt'}，如果失败请如实解释，不要调用其他工具。"),
            ("context", "不要使用工具。前面读取的文件中的数字是多少？只回答数字。"),
        ]
        try:
            for name, prompt in scenarios:
                async with asyncio.timeout(90):
                    events = [event async for event in runner.run(prompt)]
                errors = [e.text for e in events if e.type == "error"]
                results = [e.result for e in events if e.result]
                finals = "".join(e.text for e in events if e.type == "text_delta" and
                                 (e.phase == "final" or name == "context"))
                record = {"scenario": name, "ended": any(e.type == "turn_done" for e in events),
                          "results": [{"tool": r.tool_name, "status": r.status, "error_code": r.error_code} for r in results],
                          "final": redactor.display(finals[:500]), "errors": errors}
                print(json.dumps(record, ensure_ascii=False), flush=True)
                if errors or not record["ended"]:
                    return 1
                if name == "read" and (len(results) != 1 or results[0].is_error or "731" not in results[0].content):
                    return 1
                if name == "missing" and (len(results) != 1 or not results[0].is_error):
                    return 1
                if name == "context" and ("731" not in finals or results):
                    return 1
        finally:
            await runner.aclose()
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(asyncio.run(main()))
