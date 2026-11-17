"""Bounded YAML data loading, without file access or application schema."""
import math

import yaml


class SafeYamlError(ValueError):
    def __init__(self, kind):
        super().__init__("Invalid YAML data")
        self.kind = kind


class BoundedSafeLoader(yaml.SafeLoader):
    def __init__(self, stream):
        super().__init__(stream)
        self._depth = self._nodes = 0

    def compose_node(self, parent, index):
        self._depth += 1
        self._nodes += 1
        try:
            if self._depth > 16 or self._nodes > 32768:
                raise SafeYamlError("limit")
            return super().compose_node(parent, index)
        finally:
            self._depth -= 1

    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if type(key) is not str or key in result:
                raise SafeYamlError("invalid")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def validate_basic(value, stack=None, depth=0, budget=None):
    stack = set() if stack is None else stack
    budget = [32768] if budget is None else budget
    budget[0] -= 1
    if depth > 16 or budget[0] < 0:
        raise SafeYamlError("limit")
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) not in (list, dict) or id(value) in stack:
        raise SafeYamlError("invalid")
    stack.add(id(value))
    try:
        if isinstance(value, dict) and any(type(k) is not str for k in value):
            raise SafeYamlError("invalid")
        for entry in value.values() if isinstance(value, dict) else value:
            validate_basic(entry, stack, depth + 1, budget)
    finally:
        stack.remove(id(value))


def load_mapping(raw, *, max_bytes):
    if type(raw) is not bytes or len(raw) > max_bytes:
        raise SafeYamlError("limit")
    try:
        data = yaml.load(raw.decode("utf-8-sig"), Loader=BoundedSafeLoader)
        data = {} if data is None else data
        validate_basic(data)
        if type(data) is not dict:
            raise SafeYamlError("invalid")
        return data
    except SafeYamlError:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError, yaml.YAMLError, OverflowError):
        raise SafeYamlError("invalid") from None
