"""MCP smoke: default offline; --terminal uses local fixtures; --live needs explicit fee approval."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from weizhcode.bootstrap import ApplicationBootstrap
from weizhcode.conversation import Conversation
from weizhcode.models import ChatMessage, ProviderEvent, ToolCall, ToolContext, ToolResult
from weizhcode.permissions.engine import PermissionEngine
from weizhcode.redaction import Redactor
from weizhcode.tools import create_default_registry
from weizhcode.tools.executor import ToolExecutor
from weizhcode.turn_runner import TurnRunner


class DemoProvider:
    async def stream_chat(self, messages, **kwargs):
        if messages[-1].role == "tool":
            result = messages[-1].tool_results[0]
            text = f"本地MCP样本结束：{result.status}；{result.content[:300]}"
            yield ProviderEvent("text_delta", text=text)
            yield ProviderEvent("done", assistant_message=ChatMessage("assistant", text))
            return
        text = messages[-1].content
        if not any(t.name == "mcp__demo__echo" for t in kwargs.get("tools", ())) and "提问" not in text:
            answer = "本地离线聊天正常；当前模式未提供MCP工具。"
            yield ProviderEvent("text_delta", text=answer)
            yield ProviderEvent("done", assistant_message=ChatMessage("assistant", answer))
            return
        if "提问" in text and any(t.name == "AskUserQuestion" for t in kwargs.get("tools", ())):
            call = ToolCall("demo-q", "AskUserQuestion", json.dumps({"question": "本次调查范围？", "options": ["仅本地样本", "只输出计划"]}))
        else:
            call = ToolCall("demo-call", "mcp__demo__echo", json.dumps({"text": "slow" if "慢" in text else "error" if "错误" in text else text}))
        yield ProviderEvent("done", assistant_message=ChatMessage("assistant", tool_calls=(call,)))


class SampleExecutor(ToolExecutor):
    async def execute(self, slot, *, mode, cancel, emit, run_id=""):
        if self.registry.external_identity(slot.call.name) is None and not (slot.call.name == "AskUserQuestion" and mode == "plan"):
            slot.result = ToolResult.failure(slot.call, "PERMISSION_RULE_DENIED", "观察样本只允许本地MCP和计划提问，不执行内置文件/命令工具")
            return slot.result
        return await super().execute(slot, mode=mode, cancel=cancel, emit=emit, run_id=run_id)


async def run_app(bootstrap, provider):
    from weizhcode.tui import WeizhCodeApp
    registry = create_default_registry()
    engine = PermissionEngine.load(bootstrap.root, user_home=bootstrap.home)
    manager = await bootstrap.start(registry, engine)
    executor = SampleExecutor(registry, ToolContext(bootstrap.root), bootstrap.redactor, permissions=engine)
    executor.mcp_manager, executor.mcp_notices = manager, bootstrap.notices
    from weizhcode.compact.factory import NoopContextManager
    options = {'context_manager': NoopContextManager()} if not hasattr(provider, 'prepare_request') else {}
    runner = TurnRunner(provider, Conversation(), registry, executor, bootstrap.redactor, max_iterations=5, **options)
    try:
        await WeizhCodeApp(provider, runner.conversation, runner=runner, redactor=bootstrap.redactor,
                           provider_name="mcp-smoke", model="fake-local" if isinstance(provider, DemoProvider) else "live-approved",
                           project_path=str(bootstrap.root), version="mcp-smoke").run_async()
    finally:
        await runner.aclose()
        report = await manager.aclose()
        print("本地连接清理：" + ("已确认" if report.clean else "无法确认，请检查"))


def main(argv=None, *, ask=input):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--terminal", action="store_true")
    group.add_argument("--live", action="store_true")
    options = parser.parse_args(argv)
    if not options.terminal and not options.live:
        print("离线说明：未读取凭据/真实MCP配置，未启动Server、未调用API。")
        print("--terminal: 本地Server+fake模型；--live: 真实模型，费用另需YES确认。")
        return 0
    provider, safe = DemoProvider(), Redactor()
    if options.live:
        from weizhcode.config import load_config, resolve_default_provider
        from weizhcode.providers import create_provider
        config = resolve_default_provider(load_config())
        print(json.dumps({"host": urlsplit(config.base_url).hostname, "protocol": config.protocol, "model": config.model,
                          "scope": "仅临时本地MCP echo样本，不连接生产MCP，不允许文件/命令；每任务最多5次LLM请求",
                          "fees": "真实API可能收费；输入等待不算硬时限，请主动退出"}, ensure_ascii=False))
        if ask("输入 YES 同意本次模型费用，其他输入取消：").strip() != "YES":
            return 0
        safe = Redactor([config.api_key])
        provider = create_provider(config)
    fixture = Path(__file__).parent / "fixtures/mcp_stdio_server.py"
    from contextlib import ExitStack
    with TemporaryDirectory(prefix="weizhcode-mcp-smoke-") as directory, ExitStack() as contexts:
        root = Path(directory).resolve()
        home = root / ".sample-home"
        home.mkdir(mode=0o700)
        (root / ".weizhcode").mkdir()
        mode = ask("本地传输 stdio / http / none [stdio]：").strip() or "stdio"
        if mode not in {"stdio", "http", "none"}:
            return 0
        server = {"type": "stdio", "command": sys.executable, "args": [str(fixture)]}
        if mode == "http":
            from fixtures.mcp_http_server import local_http
            url, _ = contexts.enter_context(local_http(sse=True))
            server = {"type": "http", "url": url}
        cfg = root / ".weizhcode/mcp.yaml"
        if mode != "none":
            cfg.write_text(json.dumps({"mcp_servers": {"demo": server}}), encoding="utf-8")
        while True:
            print("样本目录：" + str(root))
            print("可输入任意回声、错误、慢（可Esc取消）、/plan后提问、/do；所有模型工具仅限本地样本。")
            bootstrap = ApplicationBootstrap(root, home, safe).prepare()
            asyncio.run(run_app(bootstrap, provider))
            answer = ask("restart 同项目重启 / change 修改配置后重启 / 其他结束：").strip()
            if answer not in {"restart", "change"}:
                break
            if answer == "change" and mode != "none":
                if mode == "stdio":
                    server["args"] = [str(fixture), "--changed"]
                else:
                    server["headers"] = {"X-Smoke": "changed"}
                cfg.write_text(json.dumps({"mcp_servers": {"demo": server}}), encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("观察已取消；已完成远端副作用不会自动回滚。")
    except Exception:
        print("观察未完成；未输出原始异常或认证信息。")
        raise SystemExit(1)
