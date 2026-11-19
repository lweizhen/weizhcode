from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
from uuid import uuid4

from weizhcode.mcp.process import OwnedProcess
from .archive_fs import ArchivePaths, encode_user_pages
from .contracts import ArchiveRef
from .limits import CAPTURE_BYTES, CLEANUP_SECONDS, IO_SECONDS, USER_RECORD_BYTES


@dataclass(frozen=True)
class StoreResult:
    status: str
    reference: ArchiveRef | None = None
    code: str = ""


@dataclass(frozen=True)
class ArchiveReadProof:
    canonical_path: str
    identity: tuple[int, int]
    sha256: str
    safe_bytes: int
    session_id: str
    record_id: str


@dataclass(frozen=True)
class UserIndexRef:
    pages: tuple[dict, ...]
    first_seq: int
    last_seq: int


class SessionStore:
    def __init__(self, root, session_id, redactor, *, process_factory=OwnedProcess):
        self.root, self.session_id, self.redactor = root, session_id, redactor
        self.paths = ArchivePaths(session_id) if root is not None and session_id else None
        self._process_factory = process_factory
        self._process = None
        self._lock = asyncio.Lock()
        self._closed = False
        self._close_task = None
        self._operations = set()
        self._records, self._sources, self._proofs, self._pending = {}, {}, {}, {}
        self._next_page = 1
        self.cleanup_warning = ""

    async def _close_process(self):
        process, self._process = self._process, None
        if process is not None:
            try:
                async with asyncio.timeout(CLEANUP_SECONDS):
                    await process.aclose()
            except Exception:
                self.cleanup_warning = "ARCHIVE_CLEANUP_UNCERTAIN"

    async def _request(self, action, args, text, operation_id):
        if self._process is None:
            process = self._process_factory("weizhcode.compact.archive_worker")
            self._process = process
            await process.start()
            await process.send("archive_init", root=asdict(self.root), session_id=self.session_id)
            ready = await process.receive()
            if ready.get("type") != "archive_ready":
                raise ValueError("ARCHIVE_IPC_INVALID")
        process = self._process
        request_id = uuid4().hex
        await process.send("archive_begin", request_id=request_id, operation_id=operation_id, action=action, args=args)
        for seq, offset in enumerate(range(0, len(text), 4096)):
            await process.send("archive_chunk", request_id=request_id, operation_id=operation_id,
                               seq=seq, text=text[offset:offset+4096])
        await process.send("archive_end", request_id=request_id, operation_id=operation_id)
        response = await process.receive()
        if (response.get("type") != "archive_result" or response.get("request_id") != request_id
                or response.get("operation_id") != operation_id or response.get("status") not in
                {"saved", "known_failed", "uncertain", "conflict"}):
            raise ValueError("ARCHIVE_IPC_INVALID")
        return response

    async def _run(self, action, args, text, *, cancel, budget):
        if self._closed or self.paths is None:
            return {"status": "known_failed", "code": "ARCHIVE_UNAVAILABLE"}
        if cancel.is_set():
            raise asyncio.CancelledError()
        duration = min(IO_SECONDS, budget.deadline - asyncio.get_running_loop().time() - CLEANUP_SECONDS)
        if duration <= 0:
            return {"status": "known_failed", "code": "ARCHIVE_DEADLINE"}
        work = cancelled = acquire = None
        acquired = False
        try:
            async with asyncio.timeout(duration):
                acquire = asyncio.create_task(self._lock.acquire())
                cancelled = asyncio.create_task(cancel.wait())
                await asyncio.wait((acquire, cancelled), return_when=asyncio.FIRST_COMPLETED)
                if cancel.is_set():
                    raise asyncio.CancelledError()
                await acquire
                acquired = True
                if self._closed:
                    return {"status": "known_failed", "code": "ARCHIVE_UNAVAILABLE"}
                work = asyncio.create_task(self._request(action, args, text, uuid4().hex))
                self._operations.add(work)
                await asyncio.wait((work, cancelled), return_when=asyncio.FIRST_COMPLETED)
                if cancel.is_set():
                    raise asyncio.CancelledError()
                return await work
        except asyncio.CancelledError:
            if work is not None:
                work.cancel()
            if acquired:
                await self._close_process()
            raise
        except Exception:
            if work is not None:
                work.cancel()
            if acquired:
                await self._close_process()
            return {"status": "uncertain", "code": "ARCHIVE_IO_UNCERTAIN"}
        finally:
            pending = [task for task in (work, cancelled, acquire) if task is not None]
            for task in pending:
                if not task.done():
                    task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            if work is not None:
                self._operations.discard(work)
            if acquire is not None and not acquire.cancelled() and acquire.done() and acquire.exception() is None:
                acquired = acquired or acquire.result()
            if acquired:
                self._lock.release()

    def _register(self, payload, expected):
        proof_data = payload.get("_proofs")
        reference = ArchiveRef(**{key: value for key, value in payload.items() if key not in {"_proofs", "_cleanup_warning"}})
        if (any(getattr(reference, key) != value for key, value in expected.items())
                or reference.session_id != self.session_id
                or reference.raw_path != "/".join(self.paths.object(reference.record_id))
                or reference.view_path != "/".join(self.paths.view(reference.record_id))
                or re.fullmatch(r"[a-f0-9]{64}", reference.view_sha256) is None):
            raise ValueError("ARCHIVE_REFERENCE_INVALID")
        proofs = {}
        for kind, path, sha in (("raw", reference.raw_path, reference.sha256), ("view", reference.view_path, reference.view_sha256)):
            item = proof_data[kind]
            identity = item["identity"]
            if (not isinstance(identity, list) or len(identity) != 2 or any(type(n) is not int for n in identity)
                    or item["sha256"] != sha or type(item["safe_bytes"]) is not int or item["safe_bytes"] < 0):
                raise ValueError("ARCHIVE_PROOF_INVALID")
            canonical = os.path.normcase(str(Path(self.root.canonical_root).joinpath(path)))
            proofs[canonical] = ArchiveReadProof(canonical, tuple(identity), sha, item["safe_bytes"], self.session_id, reference.record_id)
        if proofs[os.path.normcase(str(Path(self.root.canonical_root) / reference.raw_path))].safe_bytes != reference.safe_bytes:
            raise ValueError("ARCHIVE_PROOF_INVALID")
        self._records[reference.record_id] = reference
        self._sources[(reference.kind, reference.source_key)] = reference
        self._proofs.update(proofs)
        if payload.get("_cleanup_warning"):
            self.cleanup_warning = "ARCHIVE_STAGING_RETAINED"
        return reference

    async def save_text(self, kind, source_key, safe_text, *, facts=None, cancel, budget):
        if kind not in {"human", "tool"} or not isinstance(safe_text, str) or not isinstance(source_key, str) or not source_key:
            return StoreResult("known_failed", code="ARCHIVE_RECORD_INVALID")
        text = self.redactor.text(safe_text)
        source_key = self.redactor.text(source_key)
        raw = text.encode("utf-8")
        if len(raw) > (CAPTURE_BYTES if kind == "tool" else USER_RECORD_BYTES):
            return StoreResult("known_failed", code="ARCHIVE_RECORD_LIMIT")
        sha = hashlib.sha256(raw).hexdigest()
        existing = self._sources.get((kind, source_key))
        if existing is not None:
            if existing.sha256 != sha:
                return StoreResult("conflict", code="ARCHIVE_CONFLICT")
            if await self.verify_refs([existing], cancel=cancel, budget=budget):
                return StoreResult("saved", existing)
            return StoreResult("known_failed", code="ARCHIVE_CHANGED")
        expected = self._pending.get((kind, source_key))
        if expected is not None:
            if expected["sha256"] != sha:
                return StoreResult("conflict", code="ARCHIVE_CONFLICT")
            inspection = await self._run("inspect_commit", {"expected": expected}, "", cancel=cancel, budget=budget)
            if inspection["status"] == "saved":
                try:
                    return StoreResult("saved", self._register(inspection["result"], expected))
                except (ValueError, TypeError, KeyError):
                    return StoreResult("uncertain", code="ARCHIVE_REFERENCE_INVALID")
        expected = {"record_id": uuid4().hex, "kind": kind, "source_key": source_key, "sha256": sha,
                    "safe_bytes": len(raw), "complete": not bool((facts or {}).get("partial", False))}
        self._pending[(kind, source_key)] = expected
        args = {key: value for key, value in expected.items() if key not in {"sha256", "safe_bytes"}}
        args["facts"] = self.redactor.value(facts or {})
        response = await self._run("save_record", args, text, cancel=cancel, budget=budget)
        if response["status"] != "saved":
            return StoreResult(response["status"], code=response.get("code", "ARCHIVE_IO_ERROR"))
        try:
            ref = self._register(response["result"], expected)
            self._pending.pop((kind, source_key), None)
            return StoreResult("saved", ref)
        except (ValueError, TypeError, KeyError):
            return StoreResult("uncertain", code="ARCHIVE_REFERENCE_INVALID")

    async def verify_refs(self, refs, *, cancel, budget):
        refs = tuple(refs)
        if any(not isinstance(ref, ArchiveRef) or self._records.get(ref.record_id) != ref for ref in refs):
            return False
        for index in range(0, len(refs), 32):
            batch = refs[index:index+32]
            response = await self._run("verify_records", {"references": [asdict(ref) for ref in batch]}, "", cancel=cancel, budget=budget)
            if response["status"] != "saved":
                return False
            try:
                values = response["result"]["references"]
                if len(values) != len(batch):
                    return False
                for ref, value in zip(batch, values):
                    if {key: item for key, item in value.items() if key != "_proofs"} != asdict(ref):
                        return False
                    for kind, path in (("raw", ref.raw_path), ("view", ref.view_path)):
                        known = self.proof_for_registered_path(Path(self.root.canonical_root) / path)
                        actual = value["_proofs"][kind]
                        if known is None or actual != {"identity": list(known.identity), "safe_bytes": known.safe_bytes, "sha256": known.sha256}:
                            return False
            except (ValueError, TypeError, KeyError):
                return False
        return True

    async def publish_user_index(self, records, *, cancel, budget):
        records = tuple(records)
        if not await self.verify_refs([ref for _, ref in records], cancel=cancel, budget=budget):
            return None
        text = json.dumps([{"seq": seq, "reference": asdict(ref)} for seq, ref in records], ensure_ascii=False)
        if len(text.encode()) > USER_RECORD_BYTES:
            return None
        expected_pages = encode_user_pages(records)
        start = self._next_page
        self._next_page += max(1, len(expected_pages))  # 未确认提交也不复用可能已落盘的页号。
        response = await self._run("publish_index", {"start_page": start}, text, cancel=cancel, budget=budget)
        if response["status"] != "saved":
            return None
        if response["result"].get("cleanup_warning"):
            self.cleanup_warning = "ARCHIVE_STAGING_RETAINED"
        pages = response["result"]["pages"]
        if len(pages) != len(expected_pages):
            return None
        if not pages:
            return UserIndexRef((), 0, 0)
        proofs = {}
        for index, (page, expected) in enumerate(zip(pages, expected_pages), start):
            if (page["number"] != index or page["path"] != "/".join(self.paths.user_page(index))
                    or page["sha256"] != expected.sha256 or page["safe_bytes"] != len(expected.text.encode())
                    or not isinstance(page["identity"], list) or len(page["identity"]) != 2
                    or any(type(n) is not int for n in page["identity"])):
                return None
            canonical = os.path.normcase(str(Path(self.root.canonical_root) / page["path"]))
            proofs[canonical] = ArchiveReadProof(canonical, tuple(page["identity"]), page["sha256"],
                page["safe_bytes"], self.session_id, f"index-{index}")
        self._proofs.update(proofs)
        return UserIndexRef(tuple(pages), pages[0]["first_seq"], pages[-1]["last_seq"])

    def proof_for_registered_path(self, canonical_path):
        if self.root is None:
            return None
        path = Path(canonical_path)
        if not path.is_absolute():
            path = Path(self.root.canonical_root) / path
        # 只规范文字路径，不重新读盘；同时识别原登记位置被重定向的情况。
        from weizhcode.permissions.sandbox import _canonical_key
        return self._proofs.get(_canonical_key(os.path.abspath(path)))

    async def verify_index(self, index, *, cancel, budget):
        for offset in range(0, len(index.pages), 32):
            pages = list(index.pages[offset:offset+32])
            for page in pages:
                proof = self.proof_for_registered_path(page['path'])
                if (proof is None or tuple(page['identity']) != proof.identity
                        or page['sha256'] != proof.sha256 or page['safe_bytes'] != proof.safe_bytes):
                    return False
            result = await self._run('verify_records', {'references': [], 'pages': pages}, '', cancel=cancel, budget=budget)
            if result['status'] != 'saved' or result['result'].get('pages') != pages:
                return False
        return True

    async def aclose(self):
        if self._close_task is None:
            self._closed = True
            async def close():
                for task in tuple(self._operations):
                    task.cancel()
                await asyncio.gather(*tuple(self._operations), return_exceptions=True)
                await self._close_process()
            self._close_task = asyncio.create_task(close())
        await asyncio.shield(self._close_task)
