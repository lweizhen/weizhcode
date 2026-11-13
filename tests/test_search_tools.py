import json
import os

import pytest

from weizhcode.models import ToolCall, ToolContext
from weizhcode.tools.find_files import FindFilesTool
from weizhcode.tools.search_content import SearchContentTool
from weizhcode.tools.registry import ToolRegistry
from weizhcode.tools.search_utils import SearchWalk
from weizhcode.tools import search_utils


def run(tool, root, **args):
    registry = ToolRegistry()
    registry.register(tool)
    call = registry.validate(ToolCall("id", tool.definition.name, json.dumps(args)))
    assert isinstance(call, ToolCall)
    operation = tool.prepare(call, ToolContext(root))
    return operation.error or tool.execute(operation, ToolContext(root))


@pytest.fixture
def tree(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".gitignore").write_text("*.log\nignored/\n!keep.log\n")
    (tmp_path / "root.py").write_text("Foo.bar\nfoo(bar)\n")
    (tmp_path / "root.txt").write_text("needle\n")
    (tmp_path / ".hidden.py").write_text("needle\n")
    (tmp_path / "keep.log").write_text("needle\n")
    (tmp_path / "drop.log").write_text("needle\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub/.gitignore").write_text("!local.log\n*.txt\n")
    (tmp_path / "sub/local.log").write_text("needle\n")
    (tmp_path / "sub/drop.log").write_text("needle\n")
    (tmp_path / "sub/a.py").write_text("needle\n")
    (tmp_path / "sub/drop.txt").write_text("needle\n")
    (tmp_path / "ignored").mkdir()
    (tmp_path / "ignored/a.py").write_text("needle\n")
    return tmp_path


def test_search_walk_hidden_and_invalid_root(tree):
    names = {p.relative_to(tree).as_posix() for p in SearchWalk(tree).files()}
    assert ".hidden.py" not in names
    assert "root.py" in names and "sub/a.py" in names
    assert "ignored/a.py" not in names
    result = run(FindFilesTool(), tree, pattern="*", path="missing")
    assert result.is_error


def test_gitignore_scope_nested_and_ancestor(tree):
    names = {p.relative_to(tree).as_posix() for p in SearchWalk(tree).files()}
    assert "keep.log" in names and "drop.log" not in names
    assert "sub/local.log" in names and "sub/drop.log" not in names
    assert "sub/drop.txt" not in names
    names = {p.name for p in SearchWalk(tree / "sub").files()}
    assert "local.log" in names and "drop.log" not in names and "drop.txt" not in names


@pytest.mark.parametrize("hidden,ignored", [(False, False), (True, False), (False, True), (True, True)])
def test_gitignore_scope_flags_are_independent(tree, hidden, ignored):
    names = {p.relative_to(tree).as_posix() for p in SearchWalk(tree, include_hidden=hidden, include_ignored=ignored).files()}
    assert (".hidden.py" in names) is hidden
    assert ("ignored/a.py" in names) is ignored
    assert ("drop.log" in names) is ignored


def test_search_walk_symbolic_link_does_not_recurse(tree):
    try:
        (tree / "sub/loop").symlink_to(tree, target_is_directory=True)
    except OSError:
        pytest.skip("当前环境没有创建目录链接的权限")
    names = list(SearchWalk(tree).files())
    assert len(names) < 20
    assert not any("loop" in p.parts for p in names)


def test_search_walk_permission_failure_is_not_empty_success(tree, monkeypatch):
    original = search_utils.os.scandir
    def denied(path):
        if str(path).endswith("sub"):
            raise PermissionError("denied")
        return original(path)
    monkeypatch.setattr(search_utils.os, "scandir", denied)
    result = run(FindFilesTool(), tree, pattern="**/*.py")
    assert result.error_code == "SEARCH_INCOMPLETE"
    assert result.metadata["errors"]


def test_find_files_glob_root_and_recursive(tree):
    result = run(FindFilesTool(), tree, pattern="**/*.py")
    assert not result.is_error
    assert str(tree / "root.py") in result.content
    assert str(tree / "sub/a.py") in result.content
    assert "ignored" not in result.content and ".hidden.py" not in result.content


def test_find_files_empty_and_cap(tmp_path, monkeypatch):
    assert not run(FindFilesTool(), tmp_path, pattern="**/*.py").is_error
    for i in range(205):
        (tmp_path / f"{i}.py").touch()
    # 此处专测条数上限；字符预算另行验证，避免临时绝对路径长度影响断言。
    monkeypatch.setattr("weizhcode.tools.find_files.MAX_RESULT_CHARS", 100000)
    result = run(FindFilesTool(), tmp_path, pattern="**/*.py")
    assert result.metadata["count"] == 200 and result.truncated
    assert len(result.to_model_text()) <= 20000


def test_find_files_character_budget(tmp_path, monkeypatch):
    for i in range(20):
        (tmp_path / f"{i}.py").touch()
    monkeypatch.setattr("weizhcode.tools.find_files.MAX_RESULT_CHARS", 1024)
    result = run(FindFilesTool(), tmp_path, pattern="**/*.py")
    assert 0 < result.metadata["count"] < 20
    assert result.truncated and "[truncated]" in result.content
    assert len(result.to_model_text()) <= 20000


def test_search_literal_not_regex_and_case(tree):
    result = run(SearchContentTool(), tree, pattern="Foo.bar")
    assert result.metadata["count"] == 1
    assert ":1:Foo.bar" in result.content
    assert run(SearchContentTool(), tree, pattern="foo.bar").metadata["count"] == 0
    assert run(SearchContentTool(), tree, pattern="foo(bar)").metadata["count"] == 1


def test_search_literal_ignored_range(tree):
    result = run(SearchContentTool(), tree, pattern="needle", path="sub")
    assert "local.log" in result.content and "a.py" in result.content
    assert "drop.log" not in result.content and "drop.txt" not in result.content


def test_search_limits_regex_and_invalid(tree):
    result = run(SearchContentTool(), tree, pattern=r"Foo\.bar", is_regex=True)
    assert result.metadata["count"] == 1
    assert run(SearchContentTool(), tree, pattern="[", is_regex=True).error_code == "INVALID_REGEX"


def test_search_limits_binary_encoding_and_long_lines(tmp_path):
    (tmp_path / "invalid").write_bytes(b"needle\n\xff")
    (tmp_path / "binary").write_bytes(b"needle\0")
    (tmp_path / "long").write_text("x" * 100000 + "needle\n")
    result = run(SearchContentTool(), tmp_path, pattern="needle")
    assert result.metadata["skipped_files"] == 2
    assert result.metadata["long_lines"] == 1
    assert result.metadata["count"] == 0
    assert result.error_code == "SEARCH_INCOMPLETE"
    assert "未完整搜索" in result.content


def test_search_limits_hit_count_and_output(tmp_path):
    (tmp_path / "many").write_text("needle\n" * 120)
    result = run(SearchContentTool(), tmp_path, pattern="needle")
    assert result.metadata["count"] == 100
    assert result.truncated and len(result.to_model_text()) <= 20000

