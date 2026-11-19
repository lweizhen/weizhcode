from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, replace
import math
import re

from weizhcode.models import ChatMessage, TokenUsage
from weizhcode.providers.base import merge_usage_snapshot
from weizhcode.providers.request import RequestOptions, canonical
from .estimator import projected_tokens
from .prompts import SECTIONS, SUMMARY_PROMPT


class SummaryFailure(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def parse_summary(text):
    match = re.fullmatch(r'\s*<work_draft>(.*?)</work_draft>\s*<summary>(.*?)</summary>\s*', text, re.S)
    if match is None or any(tag in part for part in match.groups()
                            for tag in ('<work_draft', '</work_draft', '<summary', '</summary')):
        raise SummaryFailure('SUMMARY_FORMAT')
    summary = match[2].strip()
    headings = re.findall(r'^## (.+?)\s*$', summary, re.M)
    if headings != list(SECTIONS):
        raise SummaryFailure('SUMMARY_SECTIONS')
    chunks = re.split(r'^## .+?\s*$', summary, flags=re.M)[1:]
    if not all(chunk.strip() for chunk in chunks):
        raise SummaryFailure('SUMMARY_EMPTY_SECTION')
    return summary


@dataclass(frozen=True)
class SummaryResult:
    text: str
    requests: int
    omitted: tuple


class SummaryCollector:
    def __init__(self, provider, redactor):
        self.provider, self.redactor = provider, redactor

    async def collect(self, request, *, cancel, budget, settle, on_started=None):
        stream = self.provider.stream_prepared(request)
        usage, complete, text, received = TokenUsage(), False, '', 0
        cancellation = asyncio.create_task(cancel.wait())
        pending = None
        started = False
        try:
            async with asyncio.timeout_at(budget.deadline - 2):
                while True:
                    if cancel.is_set():
                        raise asyncio.CancelledError()
                    if not started:
                        started = True
                        if on_started is not None:
                            on_started()
                    pending = asyncio.create_task(anext(stream))
                    done, _ = await asyncio.wait((pending, cancellation), return_when=asyncio.FIRST_COMPLETED)
                    if cancellation in done:
                        raise asyncio.CancelledError()
                    try:
                        event = pending.result()
                    except StopAsyncIteration:
                        raise SummaryFailure('SUMMARY_INCOMPLETE') from None
                    if event.usage is not None:
                        usage = merge_usage_snapshot(usage, event.usage)
                    if event.fault is not None and event.fault.kind == 'context_length':
                        raise SummaryFailure('CONTEXT_LENGTH')
                    if event.type == 'error':
                        raise SummaryFailure('SUMMARY_PROVIDER_ERROR')
                    if event.type in {'tool_call_start', 'tool_call_delta', 'tool_call'} or event.tool_call is not None:
                        raise SummaryFailure('SUMMARY_TOOL_FORBIDDEN')
                    if event.type == 'text_delta':
                        received += len(event.text.encode())
                        if received > 512*1024:
                            raise SummaryFailure('SUMMARY_RESPONSE_LIMIT')
                        text += event.text
                    if event.type == 'done':
                        message = event.assistant_message
                        if (message is None or message.tool_calls or not message.content.startswith(text)
                                or len(message.content.encode()) > 512*1024
                                or event.finish_reason in {'max_tokens', 'max_output_tokens', 'incomplete', 'length', 'content_filter'}):
                            raise SummaryFailure('SUMMARY_INCOMPLETE')
                        complete = True
                        # 唯一可公开产物是通过结构校验并脱敏的正式摘要。
                        return self.redactor.text(parse_summary(message.content))
        finally:
            for task in (pending, cancellation):
                if task is not None and not task.done():
                    task.cancel()
            await asyncio.gather(*(t for t in (pending, cancellation) if t is not None), return_exceptions=True)
            try:
                async with asyncio.timeout(2):
                    await stream.aclose()
            finally:
                if started:
                    await settle(request, replace(usage, complete=usage.complete and complete))


class SummaryService:
    def __init__(self, provider, redactor):
        self.provider, self.redactor = provider, redactor
        self.collector = SummaryCollector(provider, redactor)
        self.requests = 0

    async def summarize(self, groups, recent, *, index_text, trigger, window, cancel, budget, settle, progress):
        groups, omitted, steps, requests = list(groups), [], 0, 0
        self.requests = 0
        while groups:
            if cancel.is_set():
                raise asyncio.CancelledError()
            if asyncio.get_running_loop().time() >= budget.deadline-2:
                raise SummaryFailure('COMPACTION_TIMEOUT')
            data = {'older_history': [asdict(e.message) for group in groups for e in group],
                    'recent_history': [asdict(e.message) for e in recent],
                    'user_original_index': index_text, 'omitted_turn_ranges': omitted}
            request = self.provider.prepare_request([ChatMessage('user', canonical(data))], tools=(),
                system_prompt=SUMMARY_PROMPT, options=RequestOptions('summary', False), redactor=self.redactor)
            margin = 13000 if trigger == 'auto' else 3000
            too_long = projected_tokens(request) + 20000 + margin > window
            if not too_long:
                if requests >= budget.max_summary_requests:
                    raise SummaryFailure('SUMMARY_REQUEST_LIMIT')
                requests += 1
                await progress(requests)
                def started():
                    self.requests += 1
                try:
                    text = await self.collector.collect(request, cancel=cancel, budget=budget, settle=settle, on_started=started)
                    return SummaryResult(text, self.requests, tuple(omitted))
                except SummaryFailure as exc:
                    if exc.code != 'CONTEXT_LENGTH':
                        raise
            drop = 1 if steps < 3 else max(1, math.ceil(len(groups)*.2))
            removed, groups = groups[:drop], groups[drop:]
            omitted.append((removed[0][0].turn_id, removed[-1][-1].turn_id))
            steps += 1
        raise SummaryFailure('SUMMARY_NO_REMOVABLE_HISTORY')
