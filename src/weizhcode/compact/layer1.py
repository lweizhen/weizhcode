from dataclasses import replace
import hashlib

from .contracts import HistoryEntry
from .limits import SINGLE_RESULT_BYTES, MESSAGE_RESULT_BYTES, PREVIEW_BYTES, PREVIEW_LINES
from .state import ReplacementDecision


def copy_entry(entry, message):
    return HistoryEntry(entry.entry_id, entry.turn_id, entry.origin, message,
                        entry.human_seq, entry.created_at, entry.result_keys)


def preview_text(text, reference, *, partial, truncated, collected_bytes=None):
    header = ('[工具原文已归档；以下仅预览，不是完整文件]\n'
              f'原文: {reference.raw_path}\n可读视图: {reference.view_path}\n'
              f'采集字节: {collected_bytes if collected_bytes is not None else "未知"}; 安全归档字节: {reference.safe_bytes}\n'
              f'捕获不完整: {partial}; 工具采集已截断: {truncated}。需要细节请用read_file按行读取视图。\n')
    lines = (header + text).splitlines(keepends=True)[:PREVIEW_LINES]
    return ''.join(lines).encode()[:PREVIEW_BYTES].decode('utf-8', errors='ignore')


class Layer1:
    def __init__(self, runtime, redactor):
        import asyncio
        self.runtime, self.redactor = runtime, redactor
        self.lock = asyncio.Lock()

    async def apply(self, conversation, *, cancel, budget):
        async with self.lock:
            snapshot = conversation.snapshot()
            entries, changed, count = [], False, 0
            for entry in snapshot.entries:
                message = entry.message
                if not message.tool_results:
                    entries.append(entry)
                    continue
                results = list(message.tool_results)
                rows = []
                for index, result in enumerate(results):
                    key = entry.result_keys[index] if index < len(entry.result_keys) else f'legacy:{entry.entry_id}:{index}'
                    source = self.runtime.sources.get(key) if self.runtime.sources else None
                    text = source.text if source else self.redactor.text(result.content)
                    sha = hashlib.sha256(text.encode()).hexdigest()
                    decision = self.runtime.replacements.get(key)
                    if source is not None and decision is not None and sha != decision.source_digest:
                        raise ValueError('同一执行身份的安全原文冲突')
                    if decision and decision.kind == 'replaced':
                        results[index] = replace(result, content=decision.preview, truncated=True)
                    rows.append((key, text, sha, source, decision))

                async def offload(index):
                    nonlocal changed, count
                    key, text, sha, source, decision = rows[index]
                    if decision or self.runtime.store is None or cancel.is_set():
                        return False
                    saved = await self.runtime.store.save_text('tool', key, text,
                        facts={'capture_complete': bool(source and source.capture_complete),
                               'partial': not bool(source and source.capture_complete),
                               'truncated_at_source': source.truncated_at_source if source else results[index].truncated},
                        cancel=cancel, budget=budget)
                    if saved.status != 'saved':
                        return False
                    preview = preview_text(text, saved.reference, partial=not bool(source and source.capture_complete),
                        truncated=source.truncated_at_source if source else results[index].truncated,
                        collected_bytes=source.collected_bytes if source else None)
                    decision = await self.runtime.replacements.freeze(ReplacementDecision(key, sha, 'replaced', saved.reference, preview))
                    rows[index] = (key, text, sha, source, decision)
                    results[index] = replace(results[index], content=decision.preview, truncated=True)
                    changed, count = True, count + 1
                    return True

                failed = set()
                for index, row in enumerate(rows):
                    if not row[4] and len(row[1].encode()) > SINGLE_RESULT_BYTES:
                        if not await offload(index):
                            failed.add(index)
                def retained_size(index):
                    row = rows[index]
                    # 聚合阈值约束剩余原文；预览的实际开销仍进入请求总预算。
                    return 0 if row[4] and row[4].kind == 'replaced' else len(row[1].encode())
                for index in sorted(range(len(rows)), key=lambda i: (-len(rows[i][1].encode()), i)):
                    if sum(retained_size(i) for i in range(len(rows))) <= MESSAGE_RESULT_BYTES:
                        break
                    if not rows[index][4] and index not in failed and not await offload(index):
                        failed.add(index)
                for index, (key, text, sha, source, decision) in enumerate(rows):
                    if decision is None and index not in failed:
                        await self.runtime.replacements.freeze(ReplacementDecision(key, sha, 'kept'))
                updated = replace(message, tool_results=tuple(results))
                changed = changed or updated != message
                entries.append(copy_entry(entry, updated))
            if changed:
                if cancel.is_set() or not conversation.replace_if_current(snapshot.revision, tuple(entries)):
                    raise ValueError('轻量替换候选已过期')
                self.runtime.anchor = None
            # 已冻结的来源正文不再占用32MiB私有缓冲；失败来源仍可重试。
            if self.runtime.sources:
                for decision in self.runtime.replacements.snapshot():
                    await self.runtime.sources.release(decision.execution_key)
            return count
