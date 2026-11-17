from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml
from weizhcode.yaml_utils import BoundedSafeLoader, SafeYamlError, validate_basic

from .modes import parse_mode
from .rules import parse_rule
from .types import PermissionFailure, PermissionSettings, RuleSet, SettingsWarning

MAX_BYTES = 256 * 1024
MAX_RULES = 1024
MAX_DEPTH = 16


SettingsLoader = BoundedSafeLoader
_basic = validate_basic


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
    except SafeYamlError as exc:
        raise PermissionFailure("SETTINGS_LIMIT" if exc.kind == "limit" else "SETTINGS_INVALID",
                                "权限配置格式无效，该文件未生效") from None
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
