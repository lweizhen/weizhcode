import pytest

from weizhcode.permissions.rules import exact_rule, matches, parse_rule, rule_key
from weizhcode.permissions.types import Category, PermissionFailure, PermissionTarget


@pytest.mark.parametrize("text", ["", "Nope(x)", "Bash()", "Read(../x)", "Write(/x)", "Edit(C:/x)", "Bash((x)"])
def test_parse_invalid(text):
    with pytest.raises(PermissionFailure):
        parse_rule(text)


@pytest.mark.parametrize("text,name,target,expected", [
    ("Bash(git status)", "Bash", "git status", True),
    ("Bash(git status)", "Bash", "git status ", False),
    ("Bash(git *)", "Bash", "git status; echo other", True),
    ("Bash(git *)", "Bash", "git\nstatus", False),
    ("Bash(git*)", "Bash", "git\nstatus", True),
    ("Bash", "Bash", "anything", True),
    ("Bash( x )", "Bash", "x", False),
])
def test_command_match(text, name, target, expected):
    assert matches(parse_rule(text), name, target) is expected


@pytest.mark.parametrize("pattern,target,expected", [
    ("src/*", "src/a", True), ("src/*", "src/a/b", False),
    ("src/**", "src", True), ("src/**", "src/a/b", True),
    ("**/a.py", "a.py", True), ("**/a.py", "x/y/a.py", True),
    ("src/**", "src-other/a", False), (".", ".", True),
])
def test_path_match(pattern, target, expected):
    assert matches(parse_rule(f"Write({pattern})"), "Write", target) is expected


@pytest.mark.parametrize("name,category,value", [
    ("Bash", Category.EXEC, r"echo *(a) C:\temp\file"),
    ("Write", Category.WRITE, "src/a*(b)[x]?.txt"),
    ("Glob", Category.READ, "."),
])
def test_exact_roundtrip(name, category, value):
    target = PermissionTarget("test", name, category, value)
    rule = exact_rule(target)
    assert rule.is_exact and matches(rule, name, value)
    assert rule_key(parse_rule(rule.original)) == rule_key(rule)
    assert not matches(rule, name, value + "other")
    assert not matches(rule, "Read" if name != "Read" else "Edit", value)
