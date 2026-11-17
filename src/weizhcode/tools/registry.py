from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import replace

from jsonschema import Draft202012Validator

from weizhcode.models import ToolCall, ToolDefinition, ToolResult
from weizhcode.tools.base import Tool


def _has_reference(value) -> bool:
    if isinstance(value, dict):
        return "$ref" in value or any(_has_reference(v) for v in value.values())
    return isinstance(value, list) and any(_has_reference(v) for v in value)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._external = {}

    def register(self, tool: Tool) -> None:
        definition = tool.definition
        if definition.execution_kind == "external":
            raise ValueError("外部工具必须通过可信来源注册")
        self._register(tool)

    def _register(self, tool):
        definition = tool.definition
        if definition.name in self._tools:
            raise ValueError(f"工具名称重复：{definition.name}")
        if _has_reference(definition.parameters):
            raise ValueError("工具 Schema 必须自包含，不允许引用")
        Draft202012Validator.check_schema(definition.parameters)
        self._tools[definition.name] = tool

    def register_external(self, tool, identity):
        from weizhcode.mcp.tool import McpToolAdapter
        if (not isinstance(tool, McpToolAdapter) or tool.identity != identity
                or tool.manager.identity(identity.full_name) != identity
                or tool not in tool.manager.tools):
            raise ValueError("外部工具来源无效")
        self._register(tool)
        self._external[identity.full_name] = (tool, identity)

    def external_identity(self, name):
        item = self._external.get(name)
        return item[1] if item and self.get(name) is item[0] and item[0].manager.identity(name) == item[1] else None

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def definitions(self, *, read_only: bool = False) -> list[ToolDefinition]:
        return deepcopy([tool.definition for tool in self._tools.values()
                         if not read_only or tool.definition.read_only is True])

    def is_read_only(self, name: str) -> bool:
        tool = self.get(name)
        return tool is not None and tool.definition.read_only is True

    def definitions_for_mode(self, mode):
        from weizhcode.permissions.modes import normalize_runtime_mode
        from weizhcode.permissions.rules import TOOLS
        mode = normalize_runtime_mode(mode)
        return [d for d in self.definitions() if
                (d.name in {"read_file", "find_files", "search_content", "AskUserQuestion"}
                 if mode == "plan" else d.name in TOOLS or self.external_identity(d.name) is not None)]

    def is_parallel_read(self, name):
        tool = self.get(name)
        return self.is_read_only(name) and tool.definition.execution_kind == "worker"

    def validate(self, call: ToolCall) -> ToolCall | ToolResult:
        if not isinstance(call.call_id, str) or not call.call_id or len(call.call_id) > 512:
            return ToolResult.failure(call, "INVALID_ARGUMENTS", "缺少或非法工具调用 ID")
        if not isinstance(call.name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", call.name):
            return ToolResult.failure(call, "INVALID_ARGUMENTS", "工具名称非法")
        tool = self.get(call.name)
        if tool is None:
            return ToolResult.failure(call, "UNKNOWN_TOOL", f"未知工具：{call.name}")
        if tool.definition.execution_kind == "external" and len(call.raw_arguments.encode()) > 65536:
            return ToolResult.failure(call, "INVALID_ARGUMENTS", "MCP参数超过64KiB")
        try:
            arguments = json.loads(call.raw_arguments, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError, TypeError, RecursionError):
            return ToolResult.failure(call, "INVALID_JSON", "工具参数不是完整、合法的 JSON")
        errors = list(Draft202012Validator(tool.definition.parameters).iter_errors(arguments))
        if errors:
            # 不把包含实际参数值的 ValidationError 原文直接回显。
            details = [f"{'.'.join(map(str, e.absolute_path)) or '参数对象'}：不符合 {e.validator} 约束" for e in errors[:8]]
            return ToolResult.failure(call, "INVALID_ARGUMENTS", "；".join(details))
        return replace(call, arguments=arguments)
