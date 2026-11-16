from __future__ import annotations

import os

from .types import Category, Decision, PermissionFailure, PermissionTarget, Rule, RuleSet

TOOLS = {
    "read_file": ("Read", Category.READ),
    "write_file": ("Write", Category.WRITE),
    "edit_file": ("Edit", Category.WRITE),
    "run_command": ("Bash", Category.EXEC),
    "find_files": ("Glob", Category.READ),
    "search_content": ("Grep", Category.READ),
}
FRIENDLY = frozenset(name for name, _ in TOOLS.values())


def parse_rule(value: str) -> Rule:
    def invalid():
        raise PermissionFailure("INVALID_RULE", "权限规则格式无效")
    if not isinstance(value, str) or not value.strip() or len(value) > 8192:
        invalid()
    text = value.strip()
    if text in FRIENDLY:
        return Rule(text, original=text, all_targets=True)
    start = text.find("(")
    if start < 1 or text[:start] not in FRIENDLY or not text.endswith(")"):
        invalid()
    name, pattern = text[:start], text[start + 1:-1]
    if not pattern:
        invalid()
    tokens, i, depth = [], 0, 0
    while i < len(pattern):
        char = pattern[i]
        if char == "\\" and i + 1 < len(pattern) and pattern[i + 1] in "\\*()":
            i += 1
            tokens.append(("literal", pattern[i]))
        elif char == "*":
            count = 1
            while i + 1 < len(pattern) and pattern[i + 1] == "*":
                i += 1
                count += 1
            tokens.append(("star", "**" if count > 1 else "*"))
        else:
            if char == "\\" and name != "Bash":
                invalid()
            depth += (1 if char == "(" else -1 if char == ")" else 0)
            if depth < 0:
                invalid()
            tokens.append(("literal", char))
        i += 1
    if depth:
        invalid()
    if name != "Bash":
        decoded = "".join(v for _, v in tokens)
        if decoded != "." and (decoded.startswith("/") or ":" in decoded
                               or any(s in {"", ".", ".."} for s in decoded.split("/"))):
            invalid()
    return Rule(name, tuple(tokens), not any(k == "star" for k, _ in tokens), text)


def _match(tokens, text):
    # Greedy wildcard matching, with no regex backtracking or recursive expansion.
    p = t = 0
    star = -1
    restart = 0
    while t < len(text):
        if p < len(tokens) and tokens[p][0] == "literal" and tokens[p][1] == text[t]:
            p += 1
            t += 1
        elif p < len(tokens) and tokens[p][0] == "star":
            star, restart = p, t
            p += 1
        elif star >= 0:
            restart += 1
            t, p = restart, star + 1
        else:
            return False
    return all(kind == "star" for kind, _ in tokens[p:])


def matches(rule: Rule, friendly: str, target: str) -> bool:
    if rule.friendly_name != friendly:
        return False
    if rule.all_targets:
        return True
    if friendly == "Bash":
        return _match(rule.tokens, target)
    tokens = tuple((k, v.lower() if os.name == "nt" else v) for k, v in rule.tokens)
    segments = [[]]
    for token in tokens:
        if token == ("literal", "/"):
            segments.append([])
        else:
            segments[-1].append(token)
    parts = os.path.normcase(target).replace("\\", "/").split("/")
    # Iterative dynamic programming avoids a recursion limit on deep paths.
    positions = {0}
    for segment in segments:
        if segment == [("star", "**")]:
            positions = set(range(min(positions), len(parts) + 1)) if positions else set()
        else:
            positions = {i + 1 for i in positions if i < len(parts) and _match(segment, parts[i])}
    return len(parts) in positions


def match_rules(rules: RuleSet, friendly: str, target: str):
    for decision, entries in ((Decision.DENY, rules.deny), (Decision.ALLOW, rules.allow)):
        for rule in entries:
            if matches(rule, friendly, target):
                return decision, rule
    return None


def exact_rule(target: PermissionTarget) -> Rule:
    value = target.match_target
    escaped = "".join("\\" + c if c in "\\*()" else c for c in value)
    rule = parse_rule(f"{target.friendly_name}({escaped})")
    if not rule.is_exact:
        raise PermissionFailure("INVALID_RULE", "不能生成精确授权")
    return rule


def rule_key(rule: Rule):
    tokens = rule.tokens
    if rule.friendly_name != "Bash":
        tokens = tuple((k, os.path.normcase(v)) for k, v in tokens)
    return rule.friendly_name, rule.all_targets, tokens
