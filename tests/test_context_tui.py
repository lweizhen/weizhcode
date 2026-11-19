import asyncio

from test_context_integration import PreparedScriptProvider, context_runner, long_history
from weizhcode.tui import ChatInput, MessageView, WeizhCodeApp
from weizhcode.models import TurnEvent
from weizhcode.compact.contracts import CompactionNotice


async def test_ctx_t57_ctx_t58_manual_preserves_draft_focus_and_scrollback(tmp_path):
    runner = context_runner(tmp_path, PreparedScriptProvider(), long_history())
    app = WeizhCodeApp(runner.provider, runner.conversation, runner=runner,
        provider_name='offline', model='offline', project_path=str(tmp_path), version='test')
    async with app.run_test(size=(110, 35)) as pilot:
        await app._append_message('assistant', 'previous scrollback')
        entry = app.query_one(ChatInput)
        entry.text = 'unsubmitted draft'
        await app.submit_text('/compact')
        async with asyncio.timeout(30):
            while runner.busy or app.is_generating:
                await pilot.pause(.05)
        assert entry.text == 'unsubmitted draft' and entry.has_focus
        text = '\n'.join(v.message_content for v in app.query(MessageView))
        assert 'previous scrollback' in text and '手动上下文压缩：completed' in text
        assert 'SECRET-DRAFT' not in text
        count = len(runner.provider.requests)
        await app.submit_text('/not-a-command')
        assert len(runner.provider.requests) == count
        assert entry.text == 'unsubmitted draft'


async def test_ctx_t58_ctx_t59_stale_notice_and_busy_do_not_change_mode(tmp_path):
    runner = context_runner(tmp_path, PreparedScriptProvider())
    app = WeizhCodeApp(runner.provider, runner.conversation, runner=runner,
        provider_name='offline', model='offline', project_path=str(tmp_path), version='test')
    async with app.run_test() as pilot:
        app.is_generating, app._active_run_id = True, 'run'
        await app._consume_event(TurnEvent('compaction', run_id='run',
            compaction=CompactionNotice('new', 'manual', 'started', 1234)))
        await app._consume_event(TurnEvent('compaction', run_id='run',
            compaction=CompactionNotice('old', 'manual', 'completed', 1234, 100)))
        assert app._compaction_id == 'new'
        before = runner.mode
        await app.submit_text('/do')
        await app.action_cycle_permissions()
        assert runner.mode == before and not runner.provider.requests
        app.is_generating = False


def test_ctx_t57_idle_dispatch_keeps_unknown_slash_out():
    from weizhcode.commands import idle_command
    assert idle_command('/compact') == 'compact'
    assert idle_command('/oops') == 'unknown'
    assert idle_command('ordinary question') == 'message'
