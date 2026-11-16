from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import yaml

from .modes import parse_mode
from .rules import parse_rule
from .types import PermissionFailure, PermissionSettings, RuleSet, SettingsWarning

MAX_BYTES = 256 * 1024
MAX_RULES = 1024
MAX_DEPTH = 16


class SettingsLoader(yaml.SafeLoader):
    def __init__(self, stream):
        super().__init__(stream)
        self._depth = self._nodes = 0

    def compose_node(self, parent, index):
        self._depth += 1
        self._nodes += 1
        try:
            if self._depth > MAX_DEPTH or self._nodes > 32768:
                raise PermissionFailure("SETTINGS_LIMIT", "权限配置超出体量限制")
            return super().compose_node(parent, index)
        finally:
            self._depth -= 1

    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise PermissionFailure("SETTINGS_INVALID", "权限配置含重复或非法键")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def _basic(value, stack=None, depth=0, budget=None):
    stack = set() if stack is None else stack
    budget = [32768] if budget is None else budget
    budget[0] -= 1
    if depth > MAX_DEPTH or budget[0] < 0:
        raise ValueError()
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) not in (list, dict) or id(value) in stack:
        raise ValueError()
    stack.add(id(value))
    try:
        entries = value.values() if isinstance(value, dict) else value
        if isinstance(value, dict) and not all(type(key) is str for key in value):
            raise ValueError()
        for entry in entries:
            _basic(entry, stack, depth + 1, budget)
    finally:
        stack.remove(id(value))


def parse_settings(raw: bytes) -> PermissionSettings:
    if len(raw) > MAX_BYTES:
        raise PermissionFailure("SETTINGS_LIMIT", "权限配置超出体量限制")
    try:
        data = yaml.load(raw.decode("utf-8-sig"), Loader=SettingsLoader)
        data = {} if data is None else data
        _basic(data)
        if type(data) is not dict:
            raise ValueError()
        mode = parse_mode(data["default_mode"]) if "default_mode" in data else None
        block = data.get("permissions", {})
        if type(block) is not dict or set(block) - {"allow", "deny"}:
            raise ValueError()
        lists = [block.get(name, []) for name in ("allow", "deny")]
        if any(type(entries) is not list for entries in lists) or sum(map(len, lists)) > MAX_RULES:
            raise ValueError()
        rules = RuleSet(*(tuple(parse_rule(v) for v in entries) for entries in lists))
        encoded = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > MAX_BYTES:
            raise ValueError()
        return PermissionSettings(mode, rules, encoded, hashlib.sha256(raw).hexdigest(), "loaded")
    except PermissionFailure:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError, yaml.YAMLError, OverflowError) as exc:
        raise PermissionFailure("SETTINGS_INVALID", "权限配置格式无效，该文件未生效") from None


def read_settings(path: Path) -> PermissionSettings:
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
    except FileNotFoundError:
        return PermissionSettings()
    except OSError:
        raise PermissionFailure("SETTINGS_UNREADABLE", "权限配置不可读，该文件未生效") from None
    return parse_settings(raw)


def load_layers(root: Path, home: Path):
    paths = {"user": home / ".weizhcode/settings.yaml",
             "project": root / ".weizhcode/settings.yaml",
             "local": root / ".weizhcode/settings.local.yaml"}
    settings, warnings = {}, []
    for layer, path in paths.items():
        try:
            settings[layer] = read_settings(path)
        except PermissionFailure as exc:
            settings[layer] = PermissionSettings(status="invalid")
            warnings.append(SettingsWarning(layer, str(path), exc.code))
    return settings, tuple(warnings), paths
