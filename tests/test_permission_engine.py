import pytest

from weizhcode.permissions.modes import mode_fallback, next_mode, normalize_runtime_mode, parse_mode
from weizhcode.permissions.types import Category, Decision, PermissionMode, Rule, RuleSet


def test_mode_contract():
    mode = PermissionMode.DEFAULT
    observed = []
    for _ in range(4):
        observed.append(mode)
        mode = next_mode(mode)
    assert observed == list(PermissionMode) and mode == PermissionMode.DEFAULT
    assert normalize_runtime_mode("normal") == PermissionMode.DEFAULT
    assert parse_mode("ACCEPTEDITS") == PermissionMode.ACCEPT_EDITS
    for value in ("normal", "bad", None, True):
        with pytest.raises(ValueError):
            parse_mode(value)


def test_contract():
    items = [Rule("Read")]
    rules = RuleSet(items)
    items.clear()
    assert len(rules.allow) == 1


@pytest.mark.parametrize("mode", list(PermissionMode))
@pytest.mark.parametrize("category", list(Category))
def test_mode_matrix(mode, category):
    actual = mode_fallback(mode, category)
    if mode == PermissionMode.PLAN and category != Category.READ:
        assert actual == Decision.DENY
    elif category == Category.READ or mode == PermissionMode.BYPASS or (mode == PermissionMode.ACCEPT_EDITS and category == Category.WRITE):
        assert actual == Decision.ALLOW
    else:
        assert actual == Decision.ASK
