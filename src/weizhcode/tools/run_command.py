from __future__ import annotations

import base64
import codecs
import os
import shutil
import subprocess
import threading
from pathlib import Path

from weizhcode.models import PreparedOperation, ToolDefinition, ToolResult
from weizhcode.tools.base import BaseTool, TEXT, ToolFailure, schema
from weizhcode.tools.file_utils import original_path
from weizhcode.tools.limits import CHUNK_SIZE, MAX_RESULT_CHARS

output_collected = None


def shell_argv(command: str, shell: str) -> list[str]:
    if os.name == "nt":
        script = (
            "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)\n"
            "$OutputEncoding = [Console]::OutputEncoding\n" + command +
            "\n$weizhSuccess = $?\n"
            "if ($null -ne $LASTEXITCODE) { exit $LASTEXITCODE }\n"
            "if (-not $weizhSuccess) { exit 1 }\n"
        )
        encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        return [shell, "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]
    return [shell, "-c", command]


class RunCommandTool(BaseTool):
    definition = ToolDefinition("run_command", "在指定目录运行一次非交互命令，须用户批准；不保留 cd 和环境修改。",
                                schema({"command": TEXT, "cwd": TEXT}, ["command"]), requires_confirmation=True, read_only=False)

    def _prepare(self, call, context):
        args = dict(call.arguments or {})
        command = str(args["command"])
        if not command.strip() or "\0" in command:
            raise ToolFailure("INVALID_ARGUMENTS", "命令不能为空或包含空字符")
        cwd = original_path(str(args.get("cwd", ".")), context).resolve()
        if not cwd.is_dir():
            raise ToolFailure("INVALID_ARGUMENTS", "命令执行目录不存在或不是目录")
        shell = (shutil.which("pwsh") or shutil.which("powershell")) if os.name == "nt" else "/bin/sh"
        if not shell or not Path(shell).is_file():
            raise ToolFailure("IO_ERROR", "找不到当前系统的命令解释器")
        args["cwd"] = str(cwd)
        return PreparedOperation(call, args, str(cwd), f"执行目录：{cwd}\n解释器：{shell}\n完整命令：\n{command}",
                                 state={"shell": shell})

    def _execute(self, operation, context):
        environment = os.environ.copy()
        environment.setdefault("PYTHONIOENCODING", "utf-8")
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        process = subprocess.Popen(
            shell_argv(str(operation.arguments["command"]), str(operation.state["shell"])),
            cwd=operation.target, env=environment, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creationflags,
        )
        chunks = {"stdout": [], "stderr": []}
        counts = {"stdout": 0, "stderr": 0}
        retained = 0
        truncated = False
        lock = threading.Lock()
        failures = []

        def read_pipe(label, pipe):
            nonlocal retained, truncated
            decoder = codecs.getincrementaldecoder("utf-8")("replace")
            try:
                while raw := pipe.read1(CHUNK_SIZE):
                    text = decoder.decode(raw)
                    keep(label, text)
                keep(label, decoder.decode(b"", final=True))
            except OSError:
                failures.append(label)
            finally:
                pipe.close()

        def keep(label, text):
            nonlocal retained, truncated
            with lock:
                counts[label] += len(text)
                remaining = max(0, MAX_RESULT_CHARS - 1024 - retained)
                chunks[label].append(text[:remaining]) if remaining else None
                retained += min(remaining, len(text))
                truncated |= len(text) > remaining
                if output_collected and remaining and text:
                    output_collected(label, text[:remaining])

        threads = [threading.Thread(target=read_pipe, args=(label, pipe), daemon=True)
                   for label, pipe in (("stdout", process.stdout), ("stderr", process.stderr))]
        for thread in threads:
            thread.start()
        code = process.wait()
        for thread in threads:
            thread.join()
        stdout, stderr = "".join(chunks["stdout"]), "".join(chunks["stderr"])
        content = f"stdout:\n{stdout}\nstderr:\n{stderr}"
        if truncated:
            content += "\n[truncated]"
        failed = code != 0 or bool(failures)
        return ToolResult(operation.call.call_id, self.definition.name, content,
                          status="error" if failed else "success",
                          error_code="COMMAND_FAILED" if failed else None,
                          metadata={"exit_code": code, "stdout_chars": counts["stdout"], "stderr_chars": counts["stderr"],
                                    "stdout_preview": stdout[:256], "stderr_preview": stderr[:256]},
                          truncated=truncated)

