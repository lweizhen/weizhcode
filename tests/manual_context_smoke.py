"""上下文观察：默认仅说明；terminal离线，live必须独立确认费用。"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys
from tempfile import mkdtemp
from urllib.parse import urlsplit


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    group = result.add_mutually_exclusive_group()
    group.add_argument('--terminal', action='store_true', help='临时项目+离线模型+本地工具/回环MCP的真实TUI')
    group.add_argument('--live', action='store_true', help='另需YES确认，真实模型只做临时历史摘要')
    result.add_argument('--protocol', choices=('anthropic', 'openai', 'qwen'))
    result.add_argument('--model')
    result.add_argument('--base-url')
    return result


def history():
    from weizhcode.conversation import Conversation
    result = Conversation()
    for index in range(12):
        result.add_user_message(f'离线原话{index}: ' + 'synthetic history '*500)
        result.add_assistant_message('历史事实 '*1500)
    return result


class DemoProvider:
    def __init__(self):
        from weizhcode.models import ProviderConfig
        from weizhcode.providers.qwen import QwenProvider
        self.config = ProviderConfig('offline', 'qwen', 'fake-no-api', 'https://offline.invalid/v1', '', context_window=100000)
        self.adapter = QwenProvider(self.config)
        self.last_messages = {}

    def prepare_request(self, messages, **kwargs):
        request = self.adapter.prepare_request(messages, **kwargs)
        self.last_messages[request.request_id] = messages
        return request

    async def stream_prepared(self, request):
        import json
        from weizhcode.models import ChatMessage, ProviderEvent, TokenUsage, ToolCall
        from weizhcode.compact.prompts import SECTIONS
        if request.purpose == 'summary':
            # 便于人工观察取消与忙碌路由，不连接任何模型。
            for _ in range(100):
                await asyncio.sleep(.1)
            text = '<work_draft>不应出现在界面的草稿</work_draft><summary>' + '\n'.join('## '+s+'\n离线样本事实' for s in SECTIONS) + '</summary>'
        else:
            messages = self.last_messages.pop(request.request_id)
            last = messages[-1]
            text = '离线样本完成；请以真实工具结果为准。可输入 读取、MCP、写入、提问，或 /compact。'
            if last.role == 'user' and not last.content.startswith('[应用生成'):
                available = {t['function']['name'] for t in request.body().get('tools', [])}
                name, args = '', {}
                if '提问' in last.content and 'AskUserQuestion' in available:
                    name, args = 'AskUserQuestion', {'question': '确认本次样本范围？', 'options': ['只读调查', '仅本地临时目录']}
                elif 'MCP' in last.content and 'mcp__demo__echo' in available:
                    name, args = 'mcp__demo__echo', {'text': 'large'}
                elif '写入' in last.content:
                    name, args = 'write_file', {'path': 'sample.txt', 'content': 'temporary demo\n'}
                elif '读取' in last.content:
                    name, args = 'read_file', {'path': 'fixture.txt'}
                if name and name in available:
                    yield ProviderEvent('done', assistant_message=ChatMessage('assistant', tool_calls=(
                        ToolCall('demo', name, json.dumps(args)),)), finish_reason='tool_calls')
                    return
            for char in text:
                await asyncio.sleep(.01)
                yield ProviderEvent('text_delta', text=char)
        yield ProviderEvent('usage', usage=TokenUsage(100, 40, True, 'offline-synthetic'))
        yield ProviderEvent('done', assistant_message=ChatMessage('assistant', text), finish_reason='stop')


async def terminal(root):
    from weizhcode.compact.factory import build_context_runtime
    from weizhcode.models import ToolContext
    from weizhcode.permissions.engine import PermissionEngine
    from weizhcode.redaction import Redactor
    from weizhcode.tools import create_default_registry
    from weizhcode.tools.executor import ToolExecutor
    from weizhcode.turn_runner import TurnRunner
    from weizhcode.tui import WeizhCodeApp
    from weizhcode.mcp.manager import McpManager
    from weizhcode.mcp.contracts import McpServerConfig, AuthorizedServers

    safe, registry = Redactor(), create_default_registry()
    engine = PermissionEngine.load(root, user_home=root/'.sample-home')
    runtime = build_context_runtime(root_identity=engine.root, context_window=100000, redactor=safe)
    manager = McpManager(root)
    cfg = McpServerConfig('demo', 'user', 'stdio', sys.executable,
        (str(Path(__file__).parent/'fixtures/mcp_stdio_server.py'), '--context-large'),
        env_json='{"PYTHONIOENCODING":"utf-8","PYTHONUTF8":"1"}')
    await manager.start(AuthorizedServers((manager.authorize(cfg),)), cancel=asyncio.Event())
    for tool in manager.tools:
        registry.register_external(tool, tool.identity)
    engine.external_identity = registry.external_identity
    executor = ToolExecutor(registry, ToolContext(root), safe, permissions=engine, context_runtime=runtime)
    executor.mcp_manager = manager
    provider = DemoProvider()
    runner = TurnRunner(provider, history(), registry, executor, safe, context_runtime=runtime)
    try:
        await WeizhCodeApp(provider, runner.conversation, runner=runner, provider_name='offline',
            model='fake-no-api', project_path=str(root), version='context-smoke').run_async()
    finally:
        await runner.aclose()
        report = getattr(executor, 'mcp_shutdown_report', None)
        print('自有MCP进程收尾：', '已确认' if report and report.clean else '无法确认，请检查')
        print('自有Host退出码：', manager.hosts['demo'].process.returncode)
        if runtime.store.cleanup_warning:
            print('归档收尾提示：', runtime.store.cleanup_warning)


async def live(root, args):
    # 只有main收到真实YES之后才进入；不自动批跑多个后端或使用真实MCP。
    from weizhcode.config import load_config, resolve_default_provider, effective_context_window
    from weizhcode.providers import create_provider
    from weizhcode.compact.factory import build_context_runtime
    from weizhcode.compact.manager import ContextManager
    from weizhcode.permissions.sandbox import make_root
    from weizhcode.prompting.contracts import PromptContext
    from weizhcode.redaction import Redactor
    from weizhcode.providers.base import RequestUsageLedger

    config = resolve_default_provider(load_config())
    if (config.protocol, config.model, config.base_url.rstrip('/')) != (args.protocol, args.model, args.base_url.rstrip('/')):
        raise ValueError('实际默认供应商与确认的协议/模型/地址不一致，未发请求')
    safe, provider = Redactor([config.api_key]), create_provider(config)
    runtime = build_context_runtime(root_identity=make_root(root), context_window=effective_context_window(config), redactor=safe)
    runtime.begin_operation()
    manager, ledger = ContextManager(runtime, provider, safe), RequestUsageLedger()
    async def emit(event):
        if event.compaction:
            print('压缩阶段：', event.compaction.phase, event.compaction.code)
    async def settle(request, usage, **kwargs):
        ledger.settle(request.request_id, usage, purpose=request.purpose, trigger='manual')
    try:
        outcome = await manager.compact(history(), tools=(), prompt=PromptContext('只处理合成历史。'), trigger='manual',
            cancel=asyncio.Event(), emit=emit, settle=settle, current=lambda: True)
        print('结果：', outcome.status, outcome.code, '实际摘要请求：', len(ledger.records()))
        print('服务报告用量（缺失不当0）：', ledger.totals)
    finally:
        await manager.aclose()


def main(argv=None, *, ask=input):
    arguments = parser()
    args = arguments.parse_args(argv)
    if not args.live and any((args.protocol, args.model, args.base_url)):
        arguments.error('服务参数只用于--live的明确确认')
    if not args.terminal and not args.live:
        print('默认不读取配置、不联网、不建资料。--terminal观察临时离线TUI；--live另需明确YES确认费用。')
        return 0
    if args.live:
        if not all((args.protocol, args.model, args.base_url)) or urlsplit(args.base_url).scheme != 'https':
            arguments.error('--live须明确--protocol、--model、https --base-url')
        print(f'真实服务：{urlsplit(args.base_url).hostname}；协议：{args.protocol}；模型：{args.model}')
        print('仅临时合成历史摘要，无业务工具/MCP；最多12次摘要请求，共120秒，输出每次4096 tokens。可能产生费用，失败/取消不撤销费用。')
        if ask('确认这些真实调用和费用？输入YES继续：').strip() != 'YES':
            print('未确认；未加载凭据或发请求。')
            return 0
    root = Path(mkdtemp(prefix='weizhcode-context-'))
    print('本观察自有临时目录：', root)
    print('结束后资料保留，不自动恢复会话；确认不再需要后可手动删除此目录。')
    (root/'fixture.txt').write_text(('🙂'*800+'\n')*30, encoding='utf-8')
    asyncio.run(live(root, args) if args.live else terminal(root))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
