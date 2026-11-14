"""手动线上验收：只使用当前默认供应商；执行会产生 API 请求和可能的费用。"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from weizhcode.config import load_config, resolve_default_provider, ENV_REF_RE
from weizhcode.conversation import Conversation
from weizhcode.models import ToolContext, ToolResult, parse_tool_arguments
from weizhcode.prompts import EXECUTE_DIRECTIVE
from weizhcode.providers import create_provider
from weizhcode.redaction import Redactor
from weizhcode.tools import create_default_registry
from weizhcode.tools.executor import ToolExecutor
from weizhcode.turn_runner import TurnRunner


class SmokeExecutor(ToolExecutor):
    """仅限制线上测试样本的范围，不给产品新增沙箱或权限配置。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.allowed = set()
        self.allowed_paths = set()
        self.scope_error = False

    async def execute(self, slot, *, mode, cancel, emit):
        args = parse_tool_arguments(slot.call.raw_arguments)
        path = None if args is None else args.get("path", "." if slot.call.name in {"find_files", "search_content"} else None)
        root = self.context.project_root.resolve()
        target = None
        if isinstance(path, str):
            candidate = Path(path)
            target = (candidate if candidate.is_absolute() else root / candidate).resolve()
        permitted = (slot.call.name in self.allowed and target is not None
                     and target.is_relative_to(root)
                     and (target == root if slot.call.name in {"find_files", "search_content"}
                          else target.name in self.allowed_paths))
        if not permitted:
            self.scope_error = True
            cancel.set()
            slot.result = ToolResult.failure(slot.call, "SMOKE_SCOPE",
                                             "线上验收超出临时样本范围，已停止；未执行本调用")
            slot.phase = "finished"
            return slot.result
        return await super().execute(slot, mode=mode, cancel=cancel, emit=emit)


async def main():
    config = load_config()
    active = resolve_default_provider(config)
    redactor = Redactor(p.api_key for p in config.providers if not ENV_REF_RE.fullmatch(p.api_key))
    print(json.dumps({"protocol": active.protocol, "model": active.model,
                      "host": urlsplit(active.base_url).hostname}, ensure_ascii=False), flush=True)
    with TemporaryDirectory(prefix="weizhcode-live-") as folder:
        root = Path(folder)
        (root / "fixture.txt").write_text("Project fruit: orange. Fixture number: 731.\n", encoding="utf-8")
        registry, conv = create_default_registry(), Conversation()
        executor = SmokeExecutor(registry, ToolContext(root), redactor)
        runner = TurnRunner(create_provider(active), conv, registry, executor, redactor)
        boundary = (f"本次只在临时目录 {root} 中操作，不执行命令，不访问其他目录。"
                    "每次根据已得到的工具结果决定下一步，不猜测文件内容。")
        scenarios = [
            ("loop", boundary + "先用 read_file 读取 fixture.txt，根据实际内容写 summary.txt，"
             "再读取 summary.txt 检查并给最终文字答复（提及文件中的数字）。",
             {"read_file", "write_file"}, {"fixture.txt", "summary.txt"}, "normal"),
            ("missing", boundary + "仅用一次 read_file 读取 missing.txt；失败后如实用文字解释，不再调用工具。",
             {"read_file"}, {"missing.txt"}, None),
            ("context", "不要使用任何工具。前面读取的文件中的数字是多少？只回答数字。",
             set(), set(), None),
            ("plan", boundary + "先读取 fixture.txt，给出把其内容写成 planned.txt 摘要并检查的计划。"
             "现在只做计划，不写入，等待 /do。",
             {"read_file", "find_files", "search_content"}, {"fixture.txt"}, "plan"),
            ("do", EXECUTE_DIRECTIVE,
             {"read_file", "write_file", "find_files", "search_content"}, {"fixture.txt", "planned.txt"}, "normal"),
        ]
        try:
            for name, prompt, tools, paths, mode in scenarios:
                executor.allowed, executor.allowed_paths, executor.scope_error = tools, paths, False
                if name == "plan":
                    assert runner.set_mode("plan").type == "mode_changed"
                try:
                    async with asyncio.timeout(90):
                        events = [event async for event in runner.run(prompt, mode=mode)]
                except TimeoutError:
                    print(json.dumps({"scenario": name, "error": "线上验收等待超时，已取消并清理"},
                                     ensure_ascii=False), flush=True)
                    return 1
                ended = next((e for e in reversed(events) if e.type == "turn_done"), None)
                results = [e.result for e in events if e.type == "tool_result" and e.result is not None]
                finals = "".join(e.text for e in events if e.type == "text_delta" and ended is not None
                                 and e.iteration == ended.iteration)
                errors = [e.text for e in events if e.type == "error"]
                record = {"scenario": name, "stop_reason": ended.reason if ended else "missing",
                          "iterations": ended.iteration if ended else 0, "mode": runner.mode,
                          "results": [{"tool": r.tool_name, "status": r.status, "error_code": r.error_code} for r in results],
                          "final": redactor.display(finals[:500]), "errors": errors,
                          "scope_error": executor.scope_error}
                print(json.dumps(record, ensure_ascii=False), flush=True)
                if errors or executor.scope_error or ended is None or ended.reason != "completed" or not finals.strip():
                    return 1
                if name == "loop":
                    names = [r.tool_name for r in results]
                    if names[:3] != ["read_file", "write_file", "read_file"] or any(r.is_error for r in results):
                        return 1
                    if not (root / "summary.txt").is_file() or "731" not in (root / "summary.txt").read_text(encoding="utf-8"):
                        return 1
                    if ended.iteration < 3:
                        return 1
                if name == "missing" and (len(results) != 1 or not results[0].is_error):
                    return 1
                if name == "context" and ("731" not in finals or results):
                    return 1
                if name == "plan" and ((root / "planned.txt").exists() or any(r.is_error for r in results)):
                    return 1
                if name == "do" and (not (root / "planned.txt").is_file()
                                    or "731" not in (root / "planned.txt").read_text(encoding="utf-8")
                                    or any(r.is_error for r in results)):
                    return 1
        finally:
            await runner.aclose()
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        code = asyncio.run(main())
    except Exception:
        print("线上验收未完成：配置或运行异常；未打印原始异常或凭证", flush=True)
        code = 1
    raise SystemExit(code)
