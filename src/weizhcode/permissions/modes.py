from .types import Category, Decision, PermissionMode


def parse_mode(value: str) -> PermissionMode:
    if isinstance(value, str):
        for mode in PermissionMode:
            if mode.value.casefold() == value.casefold():
                return mode
    raise ValueError("未知权限模式")


def normalize_runtime_mode(value) -> PermissionMode:
    return PermissionMode.DEFAULT if value == "normal" else parse_mode(value)


def next_mode(mode: PermissionMode) -> PermissionMode:
    modes = tuple(PermissionMode)
    return modes[(modes.index(normalize_runtime_mode(mode)) + 1) % len(modes)]


def mode_fallback(mode: PermissionMode, category: Category) -> Decision:
    mode = normalize_runtime_mode(mode)
    if not isinstance(category, Category):
        return Decision.DENY
    if mode == PermissionMode.PLAN and category != Category.READ:
        return Decision.DENY
    if category == Category.READ or mode == PermissionMode.BYPASS:
        return Decision.ALLOW
    if mode == PermissionMode.ACCEPT_EDITS and category == Category.WRITE:
        return Decision.ALLOW
    return Decision.ASK
