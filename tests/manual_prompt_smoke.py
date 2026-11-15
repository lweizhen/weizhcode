"""Opt-in manual observations. Default invocation is offline and does not load credentials."""
from __future__ import annotations

import argparse
import asyncio
from contextlib import aclosing
from dataclasses import asdict, replace
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from uuid import uuid4

from weizhcode.conversation import Conversation
from weizhcode.models import ChatMessage, ProviderConfig, TokenUsage, ToolContext, ToolResult
from weizhcode.prompting import EnvironmentSnapshot, build_prompt_context
from weizhcode.prompts import SYSTEM_PROMPT, EXECUTE_DIRECTIVE
from weizhcode.providers import create_provider
from weizhcode.providers.base import merge_usage_snapshot
from weizhcode.providers.cache_policy import select_cache_policy
from weizhcode.providers.prompt_adapter import stable_prefix_digest
from weizhcode.redaction import Redactor
from weizhcode.tools import create_default_registry
from weizhcode.tools.executor import ToolExecutor
from weizhcode.turn_runner import TurnRunner


def emit_record(data, redactor=None):
    print((redactor or Redactor()).display(json.dumps(data, ensure_ascii=False)), flush=True)


def baseline_data():
    return json.loads(Path(__file__).with_name("fixtures").joinpath("prompt_baseline.json").read_text(encoding="utf-8"))


def variant(variant_name):
    registry = create_default_registry()
    stable = SYSTEM_PROMPT
    if variant_name == "baseline":
        baseline = baseline_data()
        stable = baseline["system_prompt"]
        for definition in registry.definitions():
            tool = registry.get(definition.name)
            tool.definition = replace(tool.definition, description=baseline["descriptions"][definition.name])
    return stable, registry


class SampleExecutor(ToolExecutor):
    """Test-only restriction; not a product sandbox or permission implementation."""

    async def execute(self, slot, *, mode, cancel, emit):
        call, root = slot.call, self.context.project_root.resolve()
        allowed = call.name == "AskUserQuestion" and mode == "plan"
        if call.name in {"read_file", "write_file", "edit_file", "find_files", "search_content"}:
            args = call.arguments or {}
            raw = args.get("path", "." if call.name in {"find_files", "search_content"} else None)
            if isinstance(raw, str):
                try:
                    path = Path(raw)
                    target = (path if path.is_absolute() else root / path).resolve()
                    allowed = (target == root if call.name in {"find_files", "search_content"}
                               else target.parent == root and target.name in {"fixture.txt", "summary.txt"})
                except (ValueError, OSError):
                    allowed = False
        if not allowed:
            cancel.set()
            slot.result = ToolResult.failure(call, "SMOKE_SCOPE", "验收样本范围外或命令调用：拒绝执行，已停止观察")
            return slot.result
        return await super().execute(slot, mode=mode, cancel=cancel, emit=emit)


def observe_requests(provider, active):
    original = provider._stream
    observed = []
    async def stream(*args, **kwargs):
        observed.append(stable_prefix_digest(kwargs["json_body"], active))
        async with aclosing(original(*args, **kwargs)) as source:
            async for packet in source:
                yield packet
    provider._stream = stream
    return observed


def metadata(active, mode, variant_name):
    policy = select_cache_policy(active)
    return {"host": urlsplit(active.base_url).hostname, "protocol": active.protocol, "model": active.model,
            "mode": mode, "prompt_variant": variant_name, "strategy": policy.strategy,
            "strategy_reason": policy.reason, "rule_version": policy.version}


async def cache_observation(provider, active, variant_name, safe):
    stable, registry = variant(variant_name)
    # A controlled, non-sensitive reference dataset, confined to this opt-in observation.
    sample = "\n".join(f"样本记录{i}: 名称=item-{i}; 分类=group-{i % 7}; 数值={i * 3}; 用途=缓存验证资料。"
                       for i in range(600))
    stable += "\n\n仅本次人工缓存验证使用的合成参考数据：\n" + sample
    digests = observe_requests(provider, active)
    for index in (1, 2):
        ctx = build_prompt_context(stable, EnvironmentSnapshot(project_root=f"synthetic-environment-{index}"),
                                   mode="normal", iteration=1, redactor=safe)
        usage, done, stop = TokenUsage(), False, "incomplete"
        request_id = uuid4().hex
        stream = provider.stream_chat([ChatMessage("user", f"用一句话说明参考记录{index}的数值，不调用工具。")],
            tools=registry.definitions_for_mode("normal"), prompt_context=ctx)
        async with aclosing(stream):
            async for event in stream:
                if event.type == "usage" and event.usage:
                    usage = merge_usage_snapshot(usage, event.usage)
                if event.type == "error":
                    stop = "provider_error"
                if event.type == "done":
                    done = True
                    stop = "tool_requested_not_executed" if event.assistant_message.tool_calls else "completed"
        if not done:
            usage = replace(usage, complete=False)
        emit_record({**metadata(active, "normal", variant_name), "request_id": request_id, "iteration": 1,
            "observation_index": index, "stable_prefix_digest": digests[-1] if digests else None,
            "same_prefix": len(digests) == 2 and digests[0] == digests[1], "usage": asdict(usage),
            "stop_reason": stop, "tools_executed": False,
            "cache_read_observed": usage.cache_read.value is not None and usage.cache_read.value > 0
                                   and not usage.cache_read.invalid}, safe)


CASES = {
    "files": ("normal", "先读 fixture.txt，查找本目录txt文件并搜索 Project，再用一句话总结。"),
    "edit": ("normal", "将 fixture.txt 中 Project fruit: orange. 唯一替换成 Project fruit: apple.，确认实际结果。"),
    "clarify": ("plan", "我想改进这个样本项目，请先问我目标、范围和验收边界，再调查制定计划。"),
    "plan": ("plan", "计划将 fixture.txt 的 orange 改为 apple，只修改这一处，验收是读回确认；先调查给计划，等待 /do。"),
    "environment": ("normal", "说明本任务开始快照中的工作环境、模型、本地日期和Git状态；不可用须说明，不另行执行命令。"),
    "reminder": ("plan", "只读调查 fixture.txt，逐步确认内容和相关上下文，再给计划；不要单独回应应用补充提醒。"),
    "cancel": ("normal", "读取 fixture.txt 后说明内容。"),
}


async def behavior_observation(provider, active, variant_name, safe, ask=input):
    case = ask("选择一个场景 files/edit/clarify/plan/environment/reminder/cancel：").strip()
    if case not in CASES:
        raise ValueError("未知人工场景")
    stable, registry = variant(variant_name)
    mode, task = CASES[case]
    digests = observe_requests(provider, active)
    with TemporaryDirectory(prefix="weizhcode-prompts-") as folder:
        root = Path(folder)
        (root / "fixture.txt").write_text("Project fruit: orange.\nFixture number: 731.\n", encoding="utf-8")
        executor = SampleExecutor(registry, ToolContext(root), safe)
        runner = TurnRunner(provider, Conversation(), registry, executor, safe, system_prompt=stable)
        runner.set_mode(mode)
        token = runner.bind_questions()
        cancelled_once = False
        async def run(text, cancel_sample=False):
            nonlocal cancelled_once
            boundary = "本次仅操作工作根内 fixture.txt/summary.txt，不执行命令，不访问其他文件或目录。"
            async with asyncio.timeout(90):
                async for event in runner.run(boundary + text):
                    if cancel_sample and not cancelled_once and event.type in {"text_delta", "tool_start"}:
                        cancelled_once = True
                        runner.cancel_current()
                    if event.type == "question_request":
                        print(safe.display(event.question.question), flush=True)
                        if event.question.options:
                            print(safe.display(json.dumps(event.question.options, ensure_ascii=False)), flush=True)
                        answer = ask("自由回答（/cancel取消）：")
                        if answer.strip() == "/cancel":
                            runner.cancel_current()
                        else:
                            runner.submit_answer(event.run_id, event.question.question_id, {"text": answer})
                    if event.type == "text_delta":
                        print(safe.display(event.text), end="", flush=True)
                    if event.type == "tool_start":
                        emit_record({"tool": event.tool_call.name, "iteration": event.iteration}, safe)
                    if event.type == "tool_result":
                        emit_record({"tool": event.result.tool_name, "status": event.result.status,
                                     "error_code": event.result.error_code}, safe)
                    if event.type == "usage":
                        emit_record({**metadata(active, runner.mode, variant_name), "request_id": event.request_id,
                            "iteration": event.iteration, "stable_prefix_digest": digests[-1] if digests else None,
                            "usage": asdict(event.usage)}, safe)
                    if event.type == "turn_done":
                        emit_record({"case": case, "stop_reason": event.reason, "iterations": event.iteration}, safe)
        try:
            await run(task, cancel_sample=case == "cancel")
            if case == "plan" and ask("输入 /do 执行样本计划，其他输入结束：").strip() == "/do":
                runner.set_mode("normal")
                await run(EXECUTE_DIRECTIVE)
            if case == "cancel" and ask("输入 continue 验证取消后新任务，其他输入结束：").strip() == "continue":
                await run("请用一句话回复你好。")
            if case == "edit":
                emit_record({"sample_result": safe.display((root / "fixture.txt").read_text(encoding="utf-8"))}, safe)
        finally:
            runner.unbind_questions(token)
            await runner.aclose()


def main(argv=None, *, ask=input):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="显式允许当前默认服务的真实请求，可能收费；还需终端YES确认")
    parser.add_argument("--scenario", choices=("cache", "behavior"), default="cache")
    parser.add_argument("--prompt-variant", choices=("baseline", "modular"), default="modular")
    args = parser.parse_args(argv)
    if not args.live:
        demo = ProviderConfig("demo", "openai", "gpt-5.6", "https://api.openai.com/v1", "")
        emit_record({"offline": True, "notice": "离线演示，并非当前配置；未加载认证配置、未发请求",
                     "stable_prefix_note": "实际投影由生产请求构造产生，包含稳定系统/工具定义与模型设置；不含环境、历史或提醒。",
                     **metadata(demo, "normal", args.prompt_variant)})
        return 0
    from weizhcode.config import load_config, resolve_default_provider, ENV_REF_RE
    configuration = load_config()
    active = resolve_default_provider(configuration)
    safe = Redactor([active.api_key, *(p.api_key for p in configuration.providers if not ENV_REF_RE.fullmatch(p.api_key))])
    emit_record({**metadata(active, "normal", args.prompt_variant), "scenario": args.scenario,
                 "warning": "真实请求可能收费。cache最多两次请求；behavior单个场景每任务最多25轮，不自动评分。"}, safe)
    if ask("输入 YES 确认本次调用，其他输入取消：").strip() != "YES":
        return 0
    provider = create_provider(active)
    if args.scenario == "cache":
        asyncio.run(cache_observation(provider, active, args.prompt_variant, safe))
    else:
        asyncio.run(behavior_observation(provider, active, args.prompt_variant, safe, ask))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("人工观察已停止；已有样本副作用不代表任务完成。", flush=True)
    except Exception:
        print("人工观察未完成：配置、服务或运行失败；未输出原始异常/凭证。", flush=True)
        raise SystemExit(1)
