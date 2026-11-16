from __future__ import annotations

import os
import stat
from pathlib import Path

from pathspec import GitIgnoreSpec
from wcmatch import glob

from weizhcode.tools.base import ToolFailure
from weizhcode.permissions.sandbox import make_root, resolve_target
from weizhcode.permissions.types import PermissionFailure
from weizhcode.tools.file_utils import active_root


class SearchWalk:
    def __init__(self, root: Path, *, project_root: Path, include_hidden=False, include_ignored=False):
        self.permission_root = active_root.get() or make_root(project_root)
        self.root = Path(resolve_target(str(root), self.permission_root).canonical_target)
        self.include_hidden = include_hidden
        self.include_ignored = include_ignored
        self.errors: list[str] = []
        self.skipped_files = 0
        self.long_lines = 0
        self.sandbox_skipped = 0
        if not self.root.is_dir():
            raise ToolFailure("IO_ERROR" if self.root.exists() else "FILE_NOT_FOUND", "搜索范围必须是存在的可读目录")
        self.ancestors: list[tuple[Path, GitIgnoreSpec]] = []
        if not include_ignored:
            boundary = Path(self.permission_root.canonical_root)
            dirs = []
            current = self.root.parent
            while current != boundary.parent and current != self.root and boundary in (current, *current.parents):
                dirs.append(current)
                if current == boundary:
                    break
                current = current.parent
            for directory in reversed(dirs):
                self.ancestors = self.load_rules(directory, self.ancestors)

    def error(self, path: Path, exc: Exception):
        if len(self.errors) < 8:
            self.errors.append(f"{path}：{type(exc).__name__}")

    def load_rules(self, directory, rules):
        ignore = directory / ".gitignore"
        if self.include_ignored:
            return rules
        try:
            target = Path(resolve_target(str(ignore), self.permission_root).canonical_target)
            if not target.is_file():
                return rules
            return [*rules, (directory, GitIgnoreSpec.from_lines(target.read_text(encoding="utf-8-sig").splitlines()))]
        except PermissionFailure as exc:
            self.sandbox_skipped += 1
            if exc.code != "PATH_OUTSIDE_PROJECT":
                self.error(ignore, exc)
            return rules
        except (OSError, UnicodeError) as exc:
            self.error(ignore, exc)
            return rules

    def ignored(self, path, is_directory, rules):
        if self.include_ignored:
            return False
        ignored = False
        for base, spec in rules:
            try:
                relative = path.relative_to(base).as_posix() + ("/" if is_directory else "")
            except ValueError:
                continue
            result = spec.check_file(relative).include
            if result is not None:
                ignored = result
        return ignored

    def files(self):
        if self.ignored(self.root, True, self.ancestors):
            return
        yield from self._walk(self.root, self.ancestors)

    def _walk(self, directory, inherited):
        try:
            resolve_target(str(directory), self.permission_root)
        except PermissionFailure as exc:
            self.sandbox_skipped += 1
            if exc.code != "PATH_OUTSIDE_PROJECT":
                self.error(directory, exc)
            return
        rules = self.load_rules(directory, inherited)
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    path = Path(entry.path)
                    try:
                        info = entry.stat(follow_symlinks=False)
                        attributes = getattr(info, "st_file_attributes", 0)
                        hidden = entry.name.startswith(".") or bool(attributes & getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 2))
                        if hidden and not self.include_hidden:
                            continue
                        is_dir = entry.is_dir(follow_symlinks=False)
                        reparse = bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024))
                        if (entry.is_symlink() or reparse) and entry.is_dir(follow_symlinks=True):
                            self.sandbox_skipped += 1
                            continue
                        try:
                            resolve_target(str(path), self.permission_root)
                        except PermissionFailure as exc:
                            self.sandbox_skipped += 1
                            if exc.code != "PATH_OUTSIDE_PROJECT":
                                self.error(path, exc)
                            continue
                        if self.ignored(path, is_dir, rules):
                            continue
                        if is_dir:
                            yield from self._walk(path, rules)
                        elif entry.is_file(follow_symlinks=True):
                            yield path
                    except OSError as exc:
                        self.error(path, exc)
        except OSError as exc:
            self.error(directory, exc)


def match_glob(relative: str, pattern: str) -> bool:
    flags = glob.GLOBSTAR | glob.FORCEUNIX | glob.DOTMATCH
    if os.name == "nt":
        flags |= glob.IGNORECASE
    return glob.globmatch(relative, pattern.replace("\\", "/"), flags=flags)

