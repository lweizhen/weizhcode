"""固定归档进程；无模型、MCP连接或任意命令执行入口。"""
from dataclasses import asdict, replace
import hashlib
import json
import sys

from weizhcode.permissions.types import RootIdentity
from .archive_fs import (ArchiveFailure, ArchiveGuard, ArchivePaths, _record_id, cleanup_owned, encode_user_pages,
    encode_view, ensure_directories, publish_exclusive, read_bounded, require_ignored, write_exclusive)
from .contracts import ArchiveRef
from .limits import CAPTURE_BYTES, CAPTURE_CHUNK_BYTES, CAPTURE_FRAME_BYTES, RECORD_METADATA_BYTES, USER_RECORD_BYTES


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _verified(guard, paths, expected):
    try:
        expected = ArchiveRef(**expected)
        if expected.session_id != paths.session_id:
            raise ValueError()
        data = json.loads(read_bounded(guard, paths.record(expected.record_id), RECORD_METADATA_BYTES))
        if data.get("reference") != asdict(expected):
            raise ValueError()
        if expected.raw_path != "/".join(paths.object(expected.record_id)) or expected.view_path != "/".join(paths.view(expected.record_id)):
            raise ValueError()
        raw = read_bounded(guard, paths.object(expected.record_id), USER_RECORD_BYTES)
        view = read_bounded(guard, paths.view(expected.record_id), USER_RECORD_BYTES * 8)
        if len(raw) != expected.safe_bytes or hashlib.sha256(raw).hexdigest() != expected.sha256 or hashlib.sha256(view).hexdigest() != expected.view_sha256:
            raise ValueError()
        proofs = data.get("proofs", {})
        for key, parts, body, sha in (("raw", paths.object(expected.record_id), raw, expected.sha256),
                                     ("view", paths.view(expected.record_id), view, expected.view_sha256)):
            with guard.pin_target(parts) as target:
                if proofs.get(key) != {"identity": list(target.identity), "safe_bytes": len(body), "sha256": sha}:
                    raise ValueError()
        return {**asdict(expected), "_proofs": proofs}
    except (ValueError, TypeError, KeyError):
        raise ArchiveFailure("ARCHIVE_CHANGED", "归档记录内容无法核验") from None


def _save(guard, paths, operation_id, args, text):
    if set(args) - {"record_id", "kind", "source_key", "complete", "facts"}:
        raise ArchiveFailure("ARCHIVE_ARGUMENT_INVALID", "归档参数无效")
    record_id = _record_id(args.get("record_id"))
    kind, source = args.get("kind"), args.get("source_key")
    if kind not in {"human", "tool"} or not isinstance(source, str) or not source or len(source) > 512 or type(args.get("complete", True)) is not bool:
        raise ArchiveFailure("ARCHIVE_ARGUMENT_INVALID", "归档参数无效")
    view = encode_view(text)
    raw_bytes = text.encode("utf-8")
    reference = ArchiveRef(paths.session_id, record_id, kind, source, hashlib.sha256(raw_bytes).hexdigest(),
        len(raw_bytes), "/".join(paths.object(record_id)), "/".join(paths.view(record_id)),
        hashlib.sha256(view.encode("utf-8")).hexdigest(), args.get("complete", True))
    metadata = _json({"reference": asdict(reference), "facts": args.get("facts", {})})
    if len(metadata.encode()) > RECORD_METADATA_BYTES:
        raise ArchiveFailure("ARCHIVE_RECORD_LIMIT", "归档元信息超过上限")
    staging = paths.pending(operation_id)
    targets = (paths.object(record_id), paths.view(record_id), paths.record(record_id))
    require_ignored(guard.root.canonical_root, [*targets, (*staging, "raw"), (*staging, "view"), (*staging, "record")])
    for directory in (staging, *(target[:-1] for target in targets)):
        ensure_directories(guard, directory)
    published = False
    try:
        saved = [write_exclusive(guard, (*staging, name), content, kind=category)
                 for name, content, category in (("raw", text, kind), ("view", view, "view"))]
        proofs = {key: {"identity": list(item.identity), "safe_bytes": item.safe_bytes, "sha256": item.sha256}
                  for key, item in zip(("raw", "view"), saved)}
        metadata = _json({"reference": asdict(reference), "facts": args.get("facts", {}), "proofs": proofs})
        saved.append(write_exclusive(guard, (*staging, "record"), metadata, kind="metadata"))
        for item, destination in zip(saved, targets):
            publish_exclusive(guard, item.parts, destination, expected=item)
            published = True
        result = _verified(guard, paths, asdict(reference))
        for item in saved:
            try:
                cleanup_owned(guard, item)
            except (ArchiveFailure, OSError):
                result["_cleanup_warning"] = "ARCHIVE_STAGING_RETAINED"
        return result
    except ArchiveFailure:
        if published:
            raise ArchiveFailure("ARCHIVE_COMMIT_UNCERTAIN", "部分归档已发布，完整提交尚未确认") from None
        raise


def _index(guard, paths, operation_id, args, text):
    if set(args) != {"start_page"} or type(args["start_page"]) is not int:
        raise ArchiveFailure("ARCHIVE_ARGUMENT_INVALID", "索引参数无效")
    try:
        records = [(item["seq"], ArchiveRef(**item["reference"])) for item in json.loads(text)]
        for _, ref in records:
            _verified(guard, paths, asdict(ref))
        pages = tuple(replace(page, number=args["start_page"] + index) for index, page in enumerate(encode_user_pages(records)))
    except (ValueError, TypeError, KeyError):
        raise ArchiveFailure("ARCHIVE_INDEX_INVALID", "原话索引来源无效") from None
    staging = paths.pending(operation_id)
    targets = [paths.user_page(page.number) for page in pages]
    require_ignored(guard.root.canonical_root, [*targets, *[(*staging, f"page-{p.number}") for p in pages]])
    ensure_directories(guard, staging)
    ensure_directories(guard, (*paths.base, "users"))
    results = []
    warning = ""
    for page, destination in zip(pages, targets):
        saved = write_exclusive(guard, (*staging, f"page-{page.number}"), page.text, kind="index")
        published = publish_exclusive(guard, saved.parts, destination, expected=saved)
        results.append({"number": page.number, "first_seq": page.first_seq, "last_seq": page.last_seq,
                        "sha256": page.sha256, "path": "/".join(destination),
                        "identity": list(published.identity), "safe_bytes": published.safe_bytes})
        try:
            cleanup_owned(guard, saved)
        except (ArchiveFailure, OSError):
            warning = "ARCHIVE_STAGING_RETAINED"
    return {"pages": results, "cleanup_warning": warning}


def main():
    host_id = ""
    def emit(kind, **data):
        raw = (_json({"version": 1, "host_id": host_id, "type": kind, **data}) + "\n").encode("utf-8")
        if len(raw) > CAPTURE_FRAME_BYTES:
            raise ArchiveFailure("ARCHIVE_IPC_LIMIT", "归档响应超过上限")
        sys.stdout.buffer.write(raw)
        sys.stdout.buffer.flush()
    def read():
        raw = sys.stdin.buffer.readline(CAPTURE_FRAME_BYTES+1)
        if not raw:
            return None
        if len(raw) > CAPTURE_FRAME_BYTES or not raw.endswith(b"\n"):
            raise ArchiveFailure("ARCHIVE_IPC_INVALID", "归档帧无效")
        value = json.loads(raw)
        if not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != 1:
            raise ArchiveFailure("ARCHIVE_IPC_INVALID", "归档帧无效")
        return value
    try:
        initial = read()
        host_id = _record_id(initial["host_id"])
        if initial.get("type") != "archive_init":
            return
        guard = ArchiveGuard(RootIdentity(**initial["root"]))
        paths = ArchivePaths(initial["session_id"])
        emit("archive_ready")
        active = None
        while (frame := read()) is not None:
            request_id = operation_id = ""
            try:
                if frame.get("host_id") != host_id:
                    raise ArchiveFailure("ARCHIVE_IPC_INVALID", "归档帧来源无效")
                request_id, operation_id = _record_id(frame.get("request_id")), _record_id(frame.get("operation_id"))
                if frame["type"] == "archive_begin":
                    if active is not None or frame.get("action") not in {"save_record", "verify_records", "publish_index", "inspect_commit"}:
                        raise ArchiveFailure("ARCHIVE_ACTION_INVALID", "归档动作无效")
                    args = frame.get("args")
                    if not isinstance(args, dict) or len(_json(args).encode()) > RECORD_METADATA_BYTES:
                        raise ArchiveFailure("ARCHIVE_ARGUMENT_INVALID", "归档参数无效")
                    active = {"request": request_id, "operation": operation_id, "action": frame["action"],
                              "args": args, "chunks": [], "bytes": 0, "seq": 0}
                    continue
                if active is None or request_id != active["request"] or operation_id != active["operation"]:
                    raise ArchiveFailure("ARCHIVE_IPC_INVALID", "归档帧关联无效")
                if frame["type"] == "archive_chunk":
                    text = frame.get("text")
                    if not isinstance(text, str) or type(frame.get("seq")) is not int or frame["seq"] != active["seq"] or len(text.encode()) > CAPTURE_CHUNK_BYTES:
                        raise ArchiveFailure("ARCHIVE_IPC_INVALID", "归档分片无效")
                    active["bytes"] += len(text.encode())
                    limit = CAPTURE_BYTES if active["action"] == "save_record" and active["args"].get("kind") == "tool" else USER_RECORD_BYTES
                    if active["bytes"] > limit:
                        raise ArchiveFailure("ARCHIVE_RECORD_LIMIT", "归档来源超过上限")
                    active["chunks"].append(text)
                    active["seq"] += 1
                    continue
                if frame["type"] != "archive_end":
                    raise ArchiveFailure("ARCHIVE_ACTION_INVALID", "归档动作无效")
                action, args, text = active["action"], active["args"], "".join(active["chunks"])
                if action == "save_record":
                    result = _save(guard, paths, operation_id, args, text)
                elif action == "publish_index":
                    result = _index(guard, paths, operation_id, args, text)
                elif action == "verify_records":
                    if text or set(args) not in ({"references"}, {"references", "pages"}) or not isinstance(args["references"], list) or len(args["references"]) > 32:
                        raise ArchiveFailure("ARCHIVE_ARGUMENT_INVALID", "核验参数无效")
                    result = {"references": [_verified(guard, paths, ref) for ref in args["references"]]}
                    pages = args.get('pages', [])
                    if not isinstance(pages, list) or len(pages) > 32:
                        raise ArchiveFailure('ARCHIVE_ARGUMENT_INVALID', '索引核验参数无效')
                    for page in pages:
                        parts = paths.user_page(page['number'])
                        if page['path'] != '/'.join(parts) or not 0 <= page['safe_bytes'] <= 256*1024:
                            raise ArchiveFailure('ARCHIVE_CHANGED', '索引身份变化')
                        with guard.pin_target(parts) as target:
                            data = read_bounded(guard, parts, 256*1024)
                            if (list(target.identity) != page['identity'] or len(data) != page['safe_bytes']
                                    or hashlib.sha256(data).hexdigest() != page['sha256']):
                                raise ArchiveFailure('ARCHIVE_CHANGED', '索引内容变化')
                    if 'pages' in args:
                        result['pages'] = pages
                else:
                    if text or set(args) != {"expected"} or not isinstance(args["expected"], dict):
                        raise ArchiveFailure("ARCHIVE_ARGUMENT_INVALID", "提交检查参数无效")
                    expected = args["expected"]
                    metadata = json.loads(read_bounded(guard, paths.record(expected.get("record_id")), RECORD_METADATA_BYTES))
                    reference = metadata.get("reference", {})
                    if any(reference.get(key) != value for key, value in expected.items()):
                        raise ArchiveFailure("ARCHIVE_CHANGED", "提交身份或内容冲突")
                    result = _verified(guard, paths, reference)
                emit("archive_result", request_id=request_id, operation_id=operation_id, status="saved", result=result)
                active = None
            except ArchiveFailure as error:
                emit("archive_result", request_id=request_id, operation_id=operation_id,
                     status="uncertain" if error.code == "ARCHIVE_COMMIT_UNCERTAIN" else "conflict" if error.code == "ARCHIVE_CONFLICT" else "known_failed", code=error.code)
                active = None
    except Exception:
        # 不打印原始帧、路径、正文或异常响应；父进程只收到安全错误。
        if host_id:
            emit("archive_result", status="known_failed", code="ARCHIVE_IPC_INVALID", request_id="", operation_id="")


if __name__ == "__main__":
    main()
