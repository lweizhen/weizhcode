from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

from weizhcode.models import parse_tool_arguments
from .blacklist import hits_blacklist
from .io import PermissionIO
from .modes import mode_fallback, normalize_runtime_mode
from .rules import TOOLS, exact_rule, match_rules, rule_key
from .sandbox import make_root
from .settings import load_layers
from .types import (ApprovalChoice, Category, Decision, PermissionCheck, PermissionFailure,
                    PermissionMode, PermissionTarget, RuleSet, SaveResult)


class PermissionEngine:
    def __init__(self, root, settings, warnings, paths, *, io=None):
        self.root = root
        self.settings = settings
        self.warnings = warnings
        self.paths = paths
        self.io = io or PermissionIO()
        self.session = RuleSet()
        self.start_mode = next((settings[layer].default_mode for layer in ("local", "project", "user")
                                if settings[layer].default_mode is not None), PermissionMode.DEFAULT)
        self._asks = {}

    @classmethod
    def load(cls, project_root, *, user_home=None, io=None):
        root_path = Path(project_root)
        try:
            root = make_root(root_path)
        except PermissionFailure:
            root = None
        settings, warnings, paths = load_layers(Path(root.canonical_root) if root else root_path,
                                               Path.home() if user_home is None else Path(user_home))
        return cls(root, settings, warnings, paths, io=io)

    def _deny(self, code, reason, source="invalid", target=None):
        return PermissionCheck(Decision.DENY, source, reason, target, code=code)

    async def check(self, call, *, mode, cancel):
        mode = normalize_runtime_mode(mode)
        identity = TOOLS.get(call.name)
        args = parse_tool_arguments(call.raw_arguments)
        if identity is None or args is None:
            return self._deny("PERMISSION_UNAVAILABLE", "不能确认工具身份或参数，安全拒绝")
        friendly, category = identity
        if mode == PermissionMode.PLAN and category != Category.READ:
            return self._deny("TOOL_NOT_ALLOWED", "计划模式禁止写文件、改文件和执行命令", "plan")
        if self.root is None:
            return self._deny("PERMISSION_ROOT_UNAVAILABLE", "项目根不可用，工具未执行", "sandbox")
        if cancel.is_set():
            raise asyncio.CancelledError()
        if category == Category.EXEC:
            command = args.get("command")
            if not isinstance(command, str) or not command.strip() or "\0" in command:
                return self._deny("PERMISSION_UNAVAILABLE", "命令参数无效")
            target = PermissionTarget(call.name, friendly, category, command, command)
            hit = hits_blacklist(command)
            if hit:
                return self._deny("DANGEROUS_COMMAND", f"命中危险命令黑名单：{hit}", "blacklist", target)
        else:
            raw_path = args.get("path", "." if call.name in {"find_files", "search_content"} else None)
            if not isinstance(raw_path, str) or not raw_path:
                return self._deny("PATH_UNRESOLVED", "无法解析文件路径，安全拒绝", "sandbox")
            try:
                stamp = await self.io.inspect_path(raw_path, self.root, cancel=cancel)
            except PermissionFailure as exc:
                if exc.code == "PROCESS_CONTROL_FAILED":
                    raise
                return self._deny(exc.code, str(exc), "sandbox")
            target = PermissionTarget(call.name, friendly, category, stamp.project_relative, path=stamp)
        for layer, rules in (("session", self.session), *((name, self.settings[name].rules)
                                                     for name in ("local", "project", "user"))):
            hit = match_rules(rules, friendly, target.match_target)
            if hit is not None:
                decision, rule = hit
                return PermissionCheck(decision, "rule", f"匹配 {layer} {decision.value} 规则", target,
                                       layer, rule.original, "PERMISSION_RULE_DENIED" if decision == Decision.DENY else "")
        decision = mode_fallback(mode, category)
        result = PermissionCheck(decision, "mode", f"{mode.value} 模式下 {category.value} 类操作需确认"
                                 if decision == Decision.ASK else "", target)
        if decision == Decision.ASK:
            self._asks[id(result)] = result
        return result

    async def recheck(self, checked, *, cancel):
        if cancel.is_set():
            raise asyncio.CancelledError()
        target = checked.target
        if target is None:
            raise PermissionFailure("PERMISSION_UNAVAILABLE", "授权目标无效")
        if target.path is not None:
            current = await self.io.inspect_path(target.path.original, self.root, cancel=cancel)
            if Path(current.canonical_target) != Path(target.path.canonical_target):
                raise PermissionFailure("PERMISSION_TARGET_CHANGED", "目标已变化，请重新发起工具调用")
        return target

    async def accept(self, checked, choice, *, cancel):
        if self._asks.pop(id(checked), None) is not checked or not isinstance(choice, ApprovalChoice):
            raise PermissionFailure("PERMISSION_UNAVAILABLE", "审批不属于当前有效请求")
        target = await self.recheck(checked, cancel=cancel)
        if choice == ApprovalChoice.SESSION:
            try:
                rule = exact_rule(target)
            except PermissionFailure:
                return SaveResult(warning_code="SESSION_NOT_SAVED")
            if not any(rule_key(r) == rule_key(rule) for r in self.session.allow):
                self.session = RuleSet((*self.session.allow, rule))
        elif choice == ApprovalChoice.PERMANENT:
            try:
                result = await self.io.persist_allow(target, self.paths["local"], self.root, cancel=cancel)
                if result.saved:
                    rule = exact_rule(target)
                    local = self.settings["local"]
                    if not any(rule_key(r) == rule_key(rule) for r in local.rules.allow):
                        self.settings["local"] = replace(local, rules=RuleSet((*local.rules.allow, rule), local.rules.deny))
                return result
            except PermissionFailure as exc:
                if exc.code == "PROCESS_CONTROL_FAILED":
                    raise
                return SaveResult(warning_code=exc.code)
        return SaveResult()

    def forget(self, checked):
        self._asks.pop(id(checked), None)

    async def aclose(self):
        self._asks.clear()
        await self.io.aclose()
