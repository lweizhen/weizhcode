import asyncio
from uuid import uuid4
import pytest

from weizhcode.compact.contracts import CompactionBudget
from weizhcode.compact.prompts import SECTIONS, SUMMARY_PROMPT
from weizhcode.compact.summary import SummaryCollector, SummaryFailure, parse_summary
from weizhcode.models import ChatMessage, ProviderEvent, ToolCall
from weizhcode.providers.request import prepare_body, RequestOptions
from weizhcode.redaction import Redactor


def valid_summary():
    return '<work_draft>private draft</work_draft><summary>' + '\n'.join('## '+s+'\n事实' for s in SECTIONS) + '</summary>'


def test_ctx_t42_ctx_t43_strict_nine_sections():
    text = valid_summary()
    assert 'private draft' not in parse_summary(text)
    assert all(s in SUMMARY_PROMPT for s in SECTIONS)
    for invalid in ('', text*2, text.replace('## 当前工作', '## wrong'), text.replace('</summary>', ''),
                    text.replace('private draft', '<summary>fake</summary>'), text.replace('事实', '', 1)):
        with pytest.raises(SummaryFailure):
            parse_summary(invalid)


@pytest.mark.parametrize('tool,bad_finish', [(False, False), (True, False), (False, True)])
async def test_ctx_t43_independent_collector_never_emits_draft(tool, bad_finish):
    class Provider:
        async def stream_prepared(self, request):
            if tool:
                yield ProviderEvent('tool_call_start', tool_call=ToolCall('id', 'read_file', '{}'))
            yield ProviderEvent('text_delta', text=valid_summary())
            yield ProviderEvent('done', assistant_message=ChatMessage('assistant', valid_summary()),
                                finish_reason='max_tokens' if bad_finish else 'end_turn')
    request = prepare_body({'messages': [], 'max_tokens': 4096}, protocol='qwen', options=RequestOptions('summary', False))
    settled = []
    async def settle(req, usage): settled.append(req.request_id)
    collector = SummaryCollector(Provider(), Redactor())
    budget = CompactionBudget(uuid4().hex, asyncio.get_running_loop().time()+30)
    if tool or bad_finish:
        with pytest.raises(SummaryFailure):
            await collector.collect(request, cancel=asyncio.Event(), budget=budget, settle=settle)
    else:
        text = await collector.collect(request, cancel=asyncio.Event(), budget=budget, settle=settle)
        assert 'private draft' not in text
    assert settled == [request.request_id]


async def test_ctx_t44_shared_length_reduction_and_twelve_request_cap():
    import json
    from weizhcode.compact.contracts import HistoryEntry
    from weizhcode.compact.summary import SummaryService
    from weizhcode.errors import ProviderFault
    class Provider:
        def __init__(self): self.requests = []
        def prepare_request(self, messages, **kwargs):
            return prepare_body({'messages': [{'content': m.content} for m in messages], 'max_tokens': 4096},
                                protocol='qwen', options=RequestOptions('summary', False))
        async def stream_prepared(self, request):
            self.requests.append(request)
            yield ProviderEvent('error', fault=ProviderFault('qwen', kind='context_length'))
    groups = tuple((HistoryEntry(str(i), str(i), 'human', ChatMessage('user', 'x'*(100000 if i == 0 else 100)), i+1),)
                   for i in range(81))
    provider = Provider()
    service = SummaryService(provider, Redactor())
    usages, progress = [], []
    async def settle(request, usage): usages.append(request.request_id)
    async def report(number): progress.append(number)
    with pytest.raises(SummaryFailure) as error:
        await service.summarize(groups, (), index_text='index', trigger='manual', window=40000,
            cancel=asyncio.Event(), budget=CompactionBudget(uuid4().hex, asyncio.get_running_loop().time()+30),
            settle=settle, progress=report)
    assert error.value.code == 'SUMMARY_REQUEST_LIMIT'
    assert len(provider.requests) == len(usages) == 12
    sizes = [len(json.loads(r.body()['messages'][0]['content'])['older_history']) for r in provider.requests]
    assert sizes[:4] == [80, 79, 78, 62]
    assert progress == list(range(1, 13))


async def test_ctx_t44_non_length_failure_never_retries():
    from weizhcode.compact.contracts import HistoryEntry
    from weizhcode.compact.summary import SummaryService
    class Provider:
        def prepare_request(self, messages, **kwargs):
            return prepare_body({'messages': [], 'max_tokens': 4096}, protocol='qwen', options=RequestOptions('summary', False))
        async def stream_prepared(self, request):
            yield ProviderEvent('error', message='network')
    settled = []
    async def settle(request, usage): settled.append(request)
    async def progress(number): pass
    with pytest.raises(SummaryFailure) as error:
        await SummaryService(Provider(), Redactor()).summarize(
            ((HistoryEntry('entry', 'turn', 'human', ChatMessage('user', 'x'), 1),),), (),
            index_text='', trigger='auto', window=128000, cancel=asyncio.Event(),
            budget=CompactionBudget(uuid4().hex, asyncio.get_running_loop().time()+30), settle=settle, progress=progress)
    assert error.value.code == 'SUMMARY_PROVIDER_ERROR' and len(settled) == 1


@pytest.mark.parametrize('extra', [0, 1])
async def test_ctx_t43_summary_response_512k_boundary(extra):
    base = valid_summary()
    text = base.replace('private draft', 'x'*(512*1024 + extra - len(base.encode()) + len('private draft')))
    assert len(text.encode()) == 512*1024+extra
    class Provider:
        async def stream_prepared(self, request):
            yield ProviderEvent('text_delta', text=text)
            yield ProviderEvent('done', assistant_message=ChatMessage('assistant', text), finish_reason='stop')
    request = prepare_body({'messages': [], 'max_tokens': 4096}, protocol='qwen', options=RequestOptions('summary', False))
    async def settle(*args): pass
    operation = SummaryCollector(Provider(), Redactor()).collect(request, cancel=asyncio.Event(),
        budget=CompactionBudget(uuid4().hex, asyncio.get_running_loop().time()+30), settle=settle)
    if extra:
        with pytest.raises(SummaryFailure): await operation
    else:
        assert 'x'*100 not in await operation
