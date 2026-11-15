from __future__ import annotations

import asyncio
from datetime import datetime
import os
import platform
from dataclasses import replace

from .contracts import EnvironmentSnapshot, GitSummary


GIT_ARGV = ("git", "--no-optional-locks", "-c", "core.fsmonitor=false", "status",
            "--porcelain=v1", "-z", "--untracked-files=normal")


def parse_git_status(raw: bytes, *, truncated=False) -> GitSummary:
    unknown = GitSummary("available", truncated=True)
    if truncated or (raw and not raw.endswith(b"\0")):
        return unknown
    records = raw.split(b"\0")[:-1]
    counts = dict(staged=0, unstaged=0, untracked=0, conflicted=0)
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if len(record) < 4 or record[2:3] != b" ":
            return unknown
        xy = record[:2]
        if xy == b"??":
            counts["untracked"] += 1
            continue
        if any(c not in b" MADRCUT" for c in xy):
            return unknown
        if xy in {b"DD", b"AU", b"UD", b"UA", b"DU", b"AA", b"UU"}:
            counts["conflicted"] += 1
        counts["staged"] += xy[0] != 32
        counts["unstaged"] += xy[1] != 32
        if b"R" in xy or b"C" in xy:
            if index >= len(records) or not records[index]:
                return unknown
            index += 1
    return GitSummary("available", **counts)


async def _drain(reader, limit):
    retained = bytearray()
    truncated = False
    while chunk := await reader.read(8192):
        remaining = limit - len(retained)
        retained.extend(chunk[:remaining])
        truncated |= len(chunk) > remaining
    return bytes(retained), truncated


class EnvironmentCollector:
    def __init__(self, *, timeout=2.0, spawn=None):
        self.timeout = min(2.0, max(0.001, timeout))
        self.spawn = spawn or asyncio.create_subprocess_exec

    async def _git(self, root):
        process = None
        readers = []
        creating = asyncio.create_task(self.spawn(*GIT_ARGV, cwd=root,
                                                  stdout=asyncio.subprocess.PIPE,
                                                  stderr=asyncio.subprocess.PIPE))
        try:
            process = await asyncio.shield(creating)
            readers = [asyncio.create_task(_drain(process.stdout, 65536)),
                       asyncio.create_task(_drain(process.stderr, 4096))]
            (out, truncated), (err, _) = await asyncio.gather(*readers)
            code = await process.wait()
            if code:
                return GitSummary("not_repository" if b"not a git repository" in err else "unavailable")
            return parse_git_status(out, truncated=truncated)
        except (OSError, ValueError):
            return GitSummary()
        finally:
            # Cancellation of creation must not discard the eventual process handle.
            if process is None:
                try:
                    process = await asyncio.shield(creating)
                except (OSError, ValueError):
                    pass
            if process is not None:
                if process.returncode is None:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                if not readers:
                    readers = [asyncio.create_task(_drain(process.stdout, 65536)),
                               asyncio.create_task(_drain(process.stderr, 4096))]
                # Existing readers may have been cancelled by gather; drain remaining pipes.
                await asyncio.gather(*readers, return_exceptions=True)
                await asyncio.gather(_drain(process.stdout, 0), _drain(process.stderr, 0))
                await process.wait()

    async def capture(self, *, project_root, app_version, model, context, redactor=None):
        try:
            root = os.path.abspath(os.fspath(project_root)) if project_root is not None else "unavailable"
        except (TypeError, ValueError, OSError):
            root = "unavailable"
        snapshot = EnvironmentSnapshot(root, f"{platform.system()} / {platform.python_implementation()}",
                                       datetime.now().astimezone().date().isoformat(),
                                       app_version=app_version, model=model)
        if root == "unavailable" or context.cancel_event.is_set():
            return snapshot
        work = asyncio.create_task(self._git(root))
        cancelled = asyncio.create_task(context.cancel_event.wait())
        context.owned_tasks.update((work, cancelled))
        try:
            done, _ = await asyncio.wait((work, cancelled), timeout=self.timeout,
                                         return_when=asyncio.FIRST_COMPLETED)
            if work in done and not context.cancel_event.is_set():
                return replace(snapshot, git=work.result())
            return replace(snapshot, git=GitSummary("unavailable" if cancelled in done else "timeout"))
        finally:
            cancelled.cancel()
            await asyncio.gather(cancelled, return_exceptions=True)
            context.owned_tasks.discard(cancelled)
            if not work.done():
                work.cancel()
                context.cleanup_tasks.add(work)
            else:
                # Observe any error even if cancellation won the result race.
                await asyncio.gather(work, return_exceptions=True)
                context.owned_tasks.discard(work)


async def finish_environment(context):
    tasks = tuple(context.cleanup_tasks)
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
        context.owned_tasks.difference_update(tasks)
        context.cleanup_tasks.difference_update(tasks)
