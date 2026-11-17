from __future__ import annotations

from pathlib import Path

from weizhcode import __version__
from weizhcode.config import load_config, resolve_default_provider, ENV_REF_RE
from weizhcode.conversation import Conversation
from weizhcode.errors import WeizhCodeError
from weizhcode.providers import create_provider
from weizhcode.tui import StartupErrorApp, WeizhCodeApp
from weizhcode.models import ToolContext
from weizhcode.redaction import Redactor
from weizhcode.tools import create_default_registry
from weizhcode.tools.executor import ToolExecutor
from weizhcode.turn_runner import TurnRunner
from weizhcode.permissions.engine import PermissionEngine
from weizhcode.approvals import ApprovalBroker


def main() -> None:
    """Run the weizhCode terminal app."""
    try:
        config = load_config()
        provider_config = resolve_default_provider(config)
        provider = create_provider(provider_config)
    except WeizhCodeError as exc:
        StartupErrorApp(str(exc)).run()
        return

    redactor = Redactor(p.api_key for p in config.providers if not ENV_REF_RE.fullmatch(p.api_key))
    conversation = Conversation()
    registry = create_default_registry()
    permissions = PermissionEngine.load(Path.cwd())
    root = Path(permissions.root.canonical_root) if permissions.root else Path.cwd()
    if (root / ".weizhcode/mcp.yaml").exists() or (Path.home() / ".weizhcode/mcp.yaml").exists():
        from weizhcode.bootstrap import ApplicationBootstrap
        import asyncio
        try:
            bootstrap = ApplicationBootstrap(root, Path.home(), redactor)
            from weizhcode.permissions.sandbox import verify_root
            if permissions.root is None:
                raise ValueError("Project root unavailable")
            verify_root(permissions.root)
            bootstrap.root_identity = permissions.root
            bootstrap.prepare()
        except KeyboardInterrupt:
            return
        except Exception:
            print("MCP配置/信任准备失败，未启动外部Server；请检查独立mcp.yaml和本地文件。")
        else:
            async def run_connected():
                runner = None
                try:
                    manager = await bootstrap.start(registry, permissions)
                    executor = ToolExecutor(registry, ToolContext(root), bootstrap.redactor, permissions=permissions,
                                            approvals=ApprovalBroker(bootstrap.redactor))
                    executor.mcp_manager = manager
                    executor.mcp_notices = bootstrap.notices
                    runner = TurnRunner(provider, conversation, registry, executor, bootstrap.redactor)
                    app = WeizhCodeApp(provider, conversation, runner=runner, redactor=bootstrap.redactor,
                                       provider_name=provider_config.name, model=provider_config.model,
                                       project_path=str(root), version=__version__)
                    await app.run_async()
                finally:
                    if runner is not None:
                        await runner.aclose()
                    if bootstrap.manager:
                        report = await bootstrap.manager.aclose()
                        if not report.clean:
                            print("MCP进程清理无法确认：" + ", ".join(report.unconfirmed_servers))
            try:
                asyncio.run(run_connected())
            except KeyboardInterrupt:
                return
            except Exception:
                print("MCP应用未正常完成；已尝试清理自有连接，请检查配置与本地进程后重启。")
            return
    executor = ToolExecutor(registry, ToolContext(root), redactor, permissions=permissions,
                            approvals=ApprovalBroker(redactor))
    runner = TurnRunner(provider, conversation, registry, executor, redactor)
    WeizhCodeApp(
        provider,
        conversation,
        runner=runner,
        redactor=redactor,
        provider_name=provider_config.name,
        model=provider_config.model,
        project_path=str(root),
        version=__version__,
    ).run()
