import json
from dataclasses import replace
from pathlib import Path

import pytest

from weizhcode.models import ToolCall, ToolContext
from weizhcode.tools import file_utils
from weizhcode.tools.edit_file import EditFileTool
from weizhcode.tools.read_file import ReadFileTool
from weizhcode.tools.registry import ToolRegistry
from weizhcode.tools.write_file import WriteFileTool


def prepare(tool, root, **args):
    registry = ToolRegistry()
    registry.register(tool)
    call = registry.validate(ToolCall("call-1", tool.definition.name, json.dumps(args)))
    assert isinstance(call, ToolCall), call
    return tool.prepare(call, ToolContext(root))


@pytest.mark.parametrize("raw,bom,newline", [
    (b"abc\n", False, "\n"), (b"\xef\xbb\xbfabc\r\n", True, "\r\n"),
    (b"a\rb\r", False, "\r"), (b"a\r\nb\n", False, "\r\n"), (b"", False, "\n"),
])
def test_text_format_snapshot(tmp_path, raw, bom, newline):
    path = tmp_path / "a"
    path.write_bytes(raw)
    info, _, _ = file_utils.scan_file(path)
    assert info.bom is bom
    assert info.newline == newline
    assert info.exists and info.sha256


def test_text_format_multibyte_chunks(tmp_path, monkeypatch):
    monkeypatch.setattr(file_utils, "CHUNK_SIZE", 5)
    path = tmp_path / "a"
    path.write_bytes("\ufeff你好\r\n世界\n".encode())
    info, count, position = file_utils.scan_file(path, "好\r\n世".encode())
    assert info.bom and count == 1 and position == len("你".encode())


@pytest.mark.parametrize("raw,code", [(b"\xff", "UNSUPPORTED_ENCODING"), (b"a\0b", "BINARY_FILE")])
def test_text_format_invalid_does_not_replace(tmp_path, raw, code):
    path = tmp_path / "a"
    path.write_bytes(raw)
    operation = prepare(WriteFileTool(), tmp_path, path="a", content="new")
    assert operation.error.error_code == code
    assert path.read_bytes() == raw


def test_read_file_pagination_and_eof(tmp_path):
    path = tmp_path / "a"
    path.write_bytes("".join(f"line-{n}\r\n" for n in range(1, 402)).encode())
    tool = ReadFileTool()
    result = tool.execute(prepare(tool, tmp_path, path="a"), ToolContext(tmp_path))
    assert result.metadata["lines"] == 200 and result.truncated
    assert result.metadata["next_start_line"] == 201
    assert "line-201" not in result.content
    result = tool.execute(prepare(tool, tmp_path, path="a", start_line=201, line_count=2), ToolContext(tmp_path))
    assert "201\tline-201" in result.content and "202\tline-202" in result.content
    assert result.metadata["newline"] == "\r\n"
    result = tool.execute(prepare(tool, tmp_path, path="a", start_line=999), ToolContext(tmp_path))
    assert result.content == "" and not result.is_error


def test_read_file_errors_and_large_line(tmp_path):
    tool = ReadFileTool()
    assert prepare(tool, tmp_path, path="missing").error.error_code == "FILE_NOT_FOUND"
    assert prepare(tool, tmp_path, path=".").error.error_code == "NOT_A_FILE"
    (tmp_path / "a").write_bytes(b"x" * 150000 + b"\nend\n")
    result = tool.execute(prepare(tool, tmp_path, path="a"), ToolContext(tmp_path))
    assert result.truncated and len(result.to_model_text()) <= 20000


@pytest.mark.parametrize("args", [{"start_line": 0}, {"line_count": 201}, {"line_count": True}])
def test_read_file_invalid_range(tmp_path, args):
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    call = registry.validate(ToolCall("id", "read_file", json.dumps({"path": "a", **args})))
    assert call.is_error


def test_file_snapshot_content_and_existence_changes(tmp_path):
    path = tmp_path / "a"
    snapshot, _, _ = file_utils.scan_file(path)
    path.write_bytes(b"x")
    with pytest.raises(file_utils.ToolFailure, match="失效"):
        file_utils.verify_snapshot(snapshot)
    snapshot, _, _ = file_utils.scan_file(path)
    path.write_bytes(b"y")
    with pytest.raises(file_utils.ToolFailure):
        file_utils.verify_snapshot(snapshot)


@pytest.mark.parametrize("content", ["", "中文\nsecond\n"])
def test_write_prepare_no_side_effects(tmp_path, content):
    operation = prepare(WriteFileTool(), tmp_path, path="a/b/c", content=content)
    assert not operation.error
    assert not (tmp_path / "a").exists()
    assert operation.state["temp_path"]
    assert str(tmp_path / "a/b/c") in operation.preview


@pytest.mark.parametrize("initial", [None, b"old\n", b"\xef\xbb\xbfold\r\n"])
def test_write_execute_create_overwrite_format(tmp_path, initial):
    path = tmp_path / "a/b"
    if initial is not None:
        path.parent.mkdir()
        path.write_bytes(initial)
    tool = WriteFileTool()
    result = tool.execute(prepare(tool, tmp_path, path="a/b", content="new\nnext\n"), ToolContext(tmp_path))
    assert not result.is_error
    expected = b"\xef\xbb\xbfnew\r\nnext\r\n" if initial and initial.startswith(file_utils.BOM) else b"new\nnext\n"
    assert path.read_bytes() == expected
    assert not list(path.parent.glob(".weizhcode-*.tmp"))


def test_write_execute_stale_does_not_overwrite(tmp_path):
    path = tmp_path / "a"
    path.write_bytes(b"old")
    tool = WriteFileTool()
    operation = prepare(tool, tmp_path, path="a", content="new")
    path.write_bytes(b"external")
    result = tool.execute(operation, ToolContext(tmp_path))
    assert result.error_code == "PREVIEW_STALE"
    assert path.read_bytes() == b"external"


def test_atomic_write_failure_preserves_target(tmp_path, monkeypatch):
    path = tmp_path / "a"
    path.write_bytes(b"old")
    tool = WriteFileTool()
    operation = prepare(tool, tmp_path, path="a", content="new")
    def fail(*args):
        raise PermissionError("locked")
    monkeypatch.setattr(file_utils.os, "replace", fail)
    result = tool.execute(operation, ToolContext(tmp_path))
    assert result.is_error and path.read_bytes() == b"old"
    assert not Path(operation.state["temp_path"]).exists()


def test_atomic_write_does_not_delete_existing_temp(tmp_path):
    tool = WriteFileTool()
    operation = prepare(tool, tmp_path, path="a", content="new")
    temp = Path(operation.state["temp_path"])
    temp.write_bytes(b"user")
    result = tool.execute(operation, ToolContext(tmp_path))
    assert result.is_error
    assert temp.read_bytes() == b"user"
    assert not (tmp_path / "a").exists()


@pytest.mark.parametrize("text,old,count", [("abc", "x", 0), ("abc", "b", 1), ("abcabcabc", "abc", 3)])
def test_exact_scan_count_across_chunks(tmp_path, monkeypatch, text, old, count):
    monkeypatch.setattr(file_utils, "CHUNK_SIZE", 5)
    path = tmp_path / "a"
    path.write_bytes(text.encode())
    _, actual, _ = file_utils.scan_file(path, old.encode())
    assert actual == count


@pytest.mark.parametrize("old,expected", [("missing", 0), ("same", 3)])
def test_edit_prepare_reports_actual_match_count(tmp_path, old, expected):
    path = tmp_path / "a"
    path.write_bytes(b"same same same")
    operation = prepare(EditFileTool(), tmp_path, path="a", old_text=old, new_text="new")
    assert operation.error.error_code == "MATCH_COUNT_ERROR"
    assert operation.error.metadata["match_count"] == expected
    assert path.read_bytes() == b"same same same"


def test_edit_prepare_precise_and_readonly(tmp_path):
    path = tmp_path / "a"
    path.write_bytes(b"aa\r\nbb\r\n")
    assert prepare(EditFileTool(), tmp_path, path="a", old_text="aa\nbb", new_text="c").error
    operation = prepare(EditFileTool(), tmp_path, path="a", old_text="aa\r\nbb", new_text="")
    assert not operation.error and path.read_bytes() == b"aa\r\nbb\r\n"
    assert "aa" in operation.preview


@pytest.mark.parametrize("new", ["new\nline", ""])
def test_edit_execute_bom_and_unchanged_mixed_newlines(tmp_path, new):
    path = tmp_path / "a"
    initial = file_utils.BOM + b"aa\r\nold\r\nlast\n"
    path.write_bytes(initial)
    tool = EditFileTool()
    result = tool.execute(prepare(tool, tmp_path, path="a", old_text="old", new_text=new), ToolContext(tmp_path))
    assert not result.is_error
    assert path.read_bytes() == file_utils.BOM + b"aa\r\n" + new.replace("\n", "\r\n").encode() + b"\r\nlast\n"


def test_edit_execute_stale_and_empty_original(tmp_path):
    path = tmp_path / "a"
    path.write_bytes(b"old")
    tool = EditFileTool()
    operation = prepare(tool, tmp_path, path="a", old_text="old", new_text="new")
    path.write_bytes(b"changed")
    assert tool.execute(operation, ToolContext(tmp_path)).error_code == "PREVIEW_STALE"
    direct = ToolCall("id", "edit_file", "{}", {"path": "a", "old_text": "", "new_text": "x"})
    assert tool.prepare(direct, ToolContext(tmp_path)).error.error_code == "INVALID_ARGUMENTS"
    assert path.read_bytes() == b"changed"



@pytest.mark.parametrize("raw,expected", [(b"bad\0file", "BINARY_FILE"), (b"bad\xff", "UNSUPPORTED_ENCODING")])
def test_read_file_rejects_binary_and_encoding(tmp_path, raw, expected):
    (tmp_path / "a").write_bytes(raw)
    tool = ReadFileTool()
    result = tool.execute(prepare(tool, tmp_path, path="a"), ToolContext(tmp_path))
    assert result.error_code == expected
    assert (tmp_path / "a").read_bytes() == raw


def test_read_file_permission_failure_structured(tmp_path, monkeypatch):
    (tmp_path / "a").write_text("unchanged", encoding="utf-8")
    tool = ReadFileTool()
    operation = prepare(tool, tmp_path, path="a")
    original = Path.open
    def denied(self, *args, **kwargs):
        if self == tmp_path / "a":
            raise PermissionError(13, "Permission denied")
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Path, "open", denied)
    assert tool.execute(operation, ToolContext(tmp_path)).error_code == "IO_ERROR"

