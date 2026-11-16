from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json


class PermissionMode(str, Enum):
    DEFAULT = "default"
    ACCEPT_EDITS = "acceptEdits"
    PLAN = "plan"
    BYPASS = "bypassPermissions"


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class Category(str, Enum):
    READ = "read"
    WRITE = "write"
    EXEC = "exec"


class ApprovalChoice(str, Enum):
    ONCE = "once"
    SESSION = "session"
    PERMANENT = "permanent"
    DENY = "deny"


class PermissionFailure(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RootIdentity:
    original_root: str
    canonical_root: str
    identity: tuple[int, int] | None = None

    def __post_init__(self):
        if self.identity is not None:
            object.__setattr__(self, "identity", tuple(self.identity))


@dataclass(frozen=True)
class PathStamp:
    original: str
    canonical_target: str
    project_relative: str
    target_exists: bool
    nearest_existing: str
    ancestor_identity: tuple[int, int] | None = None

    def __post_init__(self):
        if self.ancestor_identity is not None:
            object.__setattr__(self, "ancestor_identity", tuple(self.ancestor_identity))


@dataclass(frozen=True)
class PermissionTarget:
    internal_name: str
    friendly_name: str
    category: Category
    match_target: str
    command: str | None = None
    path: PathStamp | None = None


@dataclass(frozen=True)
class Rule:
    friendly_name: str
    tokens: tuple[tuple[str, str], ...] = ()
    is_exact: bool = False
    original: str = ""
    all_targets: bool = False

    def __post_init__(self):
        object.__setattr__(self, "tokens", tuple(tuple(t) for t in self.tokens))


@dataclass(frozen=True)
class RuleSet:
    allow: tuple[Rule, ...] = ()
    deny: tuple[Rule, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "allow", tuple(self.allow))
        object.__setattr__(self, "deny", tuple(self.deny))


@dataclass(frozen=True)
class PermissionCheck:
    decision: Decision
    source: str
    reason: str
    target: PermissionTarget | None = None
    matched_layer: str | None = None
    matched_rule: str | None = None
    code: str = ""


@dataclass(frozen=True)
class PermissionSettings:
    default_mode: PermissionMode | None = None
    rules: RuleSet = RuleSet()
    raw_data: str = "{}"
    fingerprint: str | None = None
    status: str = "missing"

    @property
    def data(self):
        # The stored snapshot is immutable; callers receive their own copy.
        return json.loads(self.raw_data)


@dataclass(frozen=True)
class SettingsWarning:
    layer: str
    path: str
    code: str


@dataclass(frozen=True)
class SaveResult:
    saved: bool = False
    already_present: bool = False
    warning_code: str = ""
    committed: bool | None = False
