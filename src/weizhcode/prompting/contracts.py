from dataclasses import dataclass, field
from typing import Literal


_APP_ORIGIN = object()


@dataclass(frozen=True)
class PromptModule:
    key: str
    priority: int
    content: str

    def __post_init__(self):
        if not self.key or type(self.priority) is not int or not isinstance(self.content, str):
            raise ValueError("非法提示模块")


@dataclass(frozen=True)
class GitSummary:
    status: str = "unavailable"
    staged: int | None = None
    unstaged: int | None = None
    untracked: int | None = None
    conflicted: int | None = None
    truncated: bool = False

    def __post_init__(self):
        if self.status not in {"available", "not_repository", "unavailable", "timeout"}:
            raise ValueError("非法 Git 状态")
        for value in (self.staged, self.unstaged, self.untracked, self.conflicted):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("非法 Git 计数")


@dataclass(frozen=True)
class EnvironmentSnapshot:
    project_root: str = "unavailable"
    platform: str = "unavailable"
    local_date: str = "unavailable"
    git: GitSummary = field(default_factory=GitSummary)
    app_version: str = "unavailable"
    model: str = "unavailable"


@dataclass(frozen=True)
class RuntimeSupplement:
    kind: Literal["plan"]
    text: str
    _origin: object = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self._origin is not _APP_ORIGIN or self.kind != "plan" or not isinstance(self.text, str):
            raise ValueError("补充上下文必须由应用工厂生成")


@dataclass(frozen=True)
class PromptContext:
    stable_text: str
    environment_text: str = ""
    supplements: tuple[RuntimeSupplement, ...] = ()

    def __post_init__(self):
        if not isinstance(self.stable_text, str) or not isinstance(self.environment_text, str):
            raise ValueError("提示正文必须为文本")
        object.__setattr__(self, "supplements", tuple(self.supplements))
        if any(not isinstance(s, RuntimeSupplement) or s._origin is not _APP_ORIGIN
               for s in self.supplements):
            raise ValueError("非法补充上下文来源")
