"""权限观察：默认离线说明；--terminal 为 fake 模型 TUI；--live 另需 YES，可能收费。"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from weizhcode.conversation import Conversation
from weizhcode.models import ChatMessage, ProviderEvent, ToolCall, ToolContext, ToolResult, parse_tool_arguments
from weizhcode.permissions.engine import PermissionEngine
from weizhcode.permissions.types import ApprovalChoice
from weizhcode.redaction import Redactor
from weizhcode.tools import create_default_registry
from weizhcode.tools.executor import ToolExecutor
from weizhcode.turn_runner import TurnRunner


class SampleExecutor(ToolExecutor):
    def __init__(self, *args, native_demo=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.native_demo = native_demo

    async def execute(self, slot, *, mode, cancel, emit, run_id=""):
        args = parse_tool_arguments(slot.call.raw_arguments)
        if args is not None:
            name = slot.call.name
            allowed = name == "AskUserQuestion" and mode == "plan"
            if name == "run_command":
                allowed = (self.native_demo and args.get("command") == "echo weizhCode-permission-demo"
                           and args.get("cwd", ".") == ".")
            elif name in {"read_file", "write_file", "edit_file", "find_files", "search_content"}:
                raw = args.get("path", "." if name in {"find_files", "search_content"} else "")
                # Let the real fence reject ../outside. Everything else stays in fixed sample files.
                allowed = raw in {"fixture.txt", "sample.txt", "other.txt", "../outside", "."}
            if not allowed:
                slot.result = ToolResult.failure(slot.call, "PERMISSION_RULE_DENIED", "手动样本范围外，未执行")
                slot.phase = "finished"
                return slot.result
        return await super().execute(slot, mode=mode, cancel=cancel, emit=emit, run_id=run_id)


class DemoProvider:
    """Deterministic messages, not a model/API or safety evaluator."""
    async def stream_chat(self, messages, **kwargs):
        if messages[-1].role == "tool":
            result = messages[-1].tool_results[0]
            if result.error_code == "PATH_OUTSIDE_PROJECT":
                args, name = {"path": "sample.txt", "content": "合法目标\n"}, "write_file"
            else:
                yield ProviderEvent("text_delta", text="离线样本已结束；以工具的真实结果为准。")
                yield ProviderEvent("done", assistant_message=ChatMessage("assistant", "离线样本已结束；以工具的真实结果为准。"))
                return
        else:
            text = messages[-1].content
            if "危险" in text:
                from weizhcode.permissions.blacklist import hits_blacklist
                output = "纯判定（未执行）：rm -rf / → " + str(hits_blacklist("rm -rf /"))
                yield ProviderEvent("text_delta", text=output)
                yield ProviderEvent("done", assistant_message=ChatMessage("assistant", output))
                return
            if "提问" in text:
                name, args = "AskUserQuestion", {"question": "本次样本的范围？", "options": ["仅当前项目", "仅生成计划"]}
            elif "命令" in text:
                name, args = "run_command", {"command": "echo weizhCode-permission-demo"}
            elif "读取" in text:
                name, args = "read_file", {"path": "fixture.txt"}
            else:
                name = "write_file"
                args = {"path": "../outside" if "项目外" in text else "other.txt" if "另一" in text else "sample.txt",
                        "content": "weizhCode permission sample\n"}
        call = ToolCall("demo-call", name, json.dumps(args, ensure_ascii=False))
        yield ProviderEvent("done", assistant_message=ChatMessage("assistant", tool_calls=(call,)))


def make_runner(root, home, provider, *, safe=None, native_demo=False):
    safe = safe or Redactor()
    engine = PermissionEngine.load(root, user_home=home)
    registry = create_default_registry()
    executor = SampleExecutor(registry, ToolContext(root), safe, permissions=engine, native_demo=native_demo)
    return TurnRunner(provider, Conversation(), registry, executor, safe, max_iterations=5)


def terminal_observation(*, ask=input):
    from weizhcode.tui import WeizhCodeApp
    with TemporaryDirectory(prefix="weizhcode-permissions-") as directory:
        root = Path(directory)
        home = root / ".sample-home"
        (root / "fixture.txt").write_text("permission fixture 731\n", encoding="utf-8")
        while True:
            print("离线 fake 模型：可输入 写入 / 另一文件 / 项目外 / 命令 / 读取 / 提问 / 危险判定。")
            print("/plan、/do、Shift+Tab 和审批均使用生产路径；只有固定 echo 样本可能执行。")
            print("样本目录：" + str(root))
            runner = make_runner(root, home, DemoProvider(), native_demo=True)
            WeizhCodeApp(runner.provider, runner.conversation, runner=runner, provider_name="offline-demo",
                         model="fake-no-api", project_path=str(root), version="permission-demo").run()
            local = root / ".weizhcode/settings.local.yaml"
            print("样本本地配置：" + (local.read_text(encoding="utf-8") if local.exists() else "尚未保存"))
            if ask("输入 restart 在同一临时项目重启，其他输入结束并清理：").strip() != "restart":
                break


async def live_observation(provider, safe, *, ask=input):
    with TemporaryDirectory(prefix="weizhcode-permission-live-") as directory:
        root = Path(directory)
        (root / "fixture.txt").write_text("permission fixture 731\n", encoding="utf-8")
        runner = make_runner(root, root / ".sample-home", provider, safe=safe)
        token = runner.bind_approvals()
        choices = tuple(ApprovalChoice)
        prompt = ask("输入本次样本任务（回车：创建 sample.txt 并总结；输入拒绝场景可要求先写 ../outside）：").strip()
        prompt = prompt or "创建 sample.txt 写入 hello，再总结工具结果。"
        boundary = "仅操作工作根下 fixture.txt/sample.txt/other.txt，禁止命令；每次按真实结果决定，权限拒绝可调整或解释。"
        try:
            async with asyncio.timeout(90):
                async for event in runner.run(boundary + prompt):
                    if event.type == "approval_request":
                        print(safe.display(event.approval.arguments_preview))
                        answer = ask("1本次 / 2本会话 / 3永久 / 4拒绝，其他输入取消：").strip()
                        if answer not in {"1", "2", "3", "4"}:
                            runner.cancel_current()
                        else:
                            runner.submit_approval(event.run_id, event.approval.approval_id, choices[int(answer)-1])
                    elif event.type == "text_delta":
                        print(safe.display(event.text), end="", flush=True)
                    elif event.type == "tool_result":
                        print(safe.display(json.dumps({"tool": event.result.tool_name, "status": event.result.status,
                            "error_code": event.result.error_code}, ensure_ascii=False)))
                    elif event.type in {"notice", "turn_done"}:
                        print(safe.display(event.text or event.reason))
        finally:
            runner.unbind_approvals(token)
            await runner.aclose()


def main(argv=None, *, ask=input):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--terminal", action="store_true", help="离线 fake 模型真实终端观察")
    mode.add_argument("--live", action="store_true", help="真实模型，可能收费且需要 YES")
    args = parser.parse_args(argv)
    if args.terminal:
        terminal_observation(ask=ask)
        return 0
    if not args.live:
        print("离线说明：未加载凭据、未发请求、未运行工具。--terminal 为离线真实 TUI；--live 另需 YES。")
        print("审批：1允许本次 / 2允许本会话 / 3永久允许 / 4拒绝本次；危险样例永不执行。")
        return 0
    from urllib.parse import urlsplit
    from weizhcode.config import load_config, resolve_default_provider, ENV_REF_RE
    from weizhcode.providers import create_provider
    configuration = load_config()
    active = resolve_default_provider(configuration)
    safe = Redactor([p.api_key for p in configuration.providers if not ENV_REF_RE.fullmatch(p.api_key)])
    print(safe.display(json.dumps({"host": urlsplit(active.base_url).hostname, "model": active.model,
        "protocol": active.protocol, "warning": "真实调用可能收费：仅一任务，最多5轮模型请求；异步90秒，终端输入等待需手动结束。"}, ensure_ascii=False)))
    if ask("输入 YES 同意本次费用与样本范围，其他输入取消：").strip() != "YES":
        return 0
    asyncio.run(live_observation(create_provider(active), safe, ask=ask))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("样本观察已取消；已有副作用不保证回滚。")
    except Exception:
        print("观察未完成：配置、服务或运行失败，未输出原始异常或凭据。")
        raise SystemExit(1)
