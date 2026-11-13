import json
import os
import shlex
import sys
from pathlib import Path

import pytest

from weizhcode.models import ToolCall, ToolContext
from weizhcode.tools.registry import ToolRegistry
from weizhcode.tools.run_command import RunCommandTool
from weizhcode.tools import run_command


def python_command(source):
    if os.name == "nt":
        return "& '" + sys.executable.replace("'", "''") + "' -c '" + source.replace("'", "''") + "'"
    return shlex.quote(sys.executable) + " -c " + shlex.quote(source)


def prepare(root, command, **args):
    tool = RunCommandTool()
    registry = ToolRegistry()
    registry.register(tool)
    call = registry.validate(ToolCall("id", "run_command", json.dumps({"command": command, **args})))
    assert isinstance(call, ToolCall)
    return tool.prepare(call, ToolContext(root))


def execute(root, command, **args):
    operation = prepare(root, command, **args)
    return operation.error or RunCommandTool().execute(operation, ToolContext(root))


def test_command_prepare_default_and_explicit_directory(tmp_path):
    (tmp_path / "sub").mkdir()
    operation = prepare(tmp_path, "echo hi", cwd="sub")
    assert operation.target == str(tmp_path / "sub")
    assert operation.arguments["command"] == "echo hi"
    assert "echo hi" in operation.preview and str(tmp_path / "sub") in operation.preview
    assert not prepare(tmp_path, "echo hi").error
    assert prepare(tmp_path, "echo hi", cwd="missing").error


def test_command_prepare_no_process_or_cwd_mutation(tmp_path, monkeypatch):
    before = Path.cwd()
    def fail(*args, **kwargs):
        raise AssertionError("prepare 启动了进程")
    monkeypatch.setattr(run_command.subprocess, "Popen", fail)
    assert not prepare(tmp_path, "echo hi").error
    assert Path.cwd() == before


def test_command_output_stdout_stderr_nonzero(tmp_path):
    result = execute(tmp_path, python_command('import sys; print("你好"); print("problem", file=sys.stderr); sys.exit(7)'))
    assert result.error_code == "COMMAND_FAILED"
    assert result.metadata["exit_code"] == 7
    assert "你好" in result.content and "problem" in result.content
    assert "stdout:" in result.content and "stderr:" in result.content


def test_command_output_cwd_and_environment_do_not_persist(tmp_path):
    (tmp_path / "sub").mkdir()
    change = "Set-Location 'sub'; $env:WEIZH_UNIT_TEST_ENV='yes'" if os.name == "nt" else "cd sub; export WEIZH_UNIT_TEST_ENV=yes"
    assert not execute(tmp_path, change).is_error
    result = execute(tmp_path, python_command('import os; print(os.getcwd()); print(os.getenv("WEIZH_UNIT_TEST_ENV", "unset"))'))
    assert str(tmp_path) in result.content and "unset" in result.content


def test_command_output_large_is_bounded(tmp_path):
    result = execute(tmp_path, python_command('print("x"*200000)'))
    assert result.truncated
    assert result.metadata["stdout_chars"] > 100000
    assert len(result.to_model_text()) <= 20000

