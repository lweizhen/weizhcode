import pytest
from textual.widgets import Static

from test_mcp_integration import rig, call
from test_turn_runner import reply
from test_tool_tui import wait_for
from weizhcode.tui import WeizhCodeApp, ChatInput


@pytest.mark.parametrize("key,expected", [("1", "success"), ("2", "success"), ("3", "success"), ("4", "denied"), ("escape", "cancelled")])
async def test_mcp_interaction_status(tmp_path, key, expected):
    runner = await rig(tmp_path, [reply("", (call(),)), reply("done")])
    app = WeizhCodeApp(runner.provider, runner.conversation, runner=runner, redactor=runner.redactor,
                       provider_name="test", model="fake", project_path=str(tmp_path), version="test")
    async with app.run_test() as pilot:
        assert "Connected to 1 MCP server(s)" in str(app.query_one("#status", Static).render())
        await app.submit_text("echo")
        app.query_one(ChatInput).text = "draft"
        await wait_for(pilot, lambda: app._pending_approval is not None)
        await pilot.press(key)
        await wait_for(pilot, lambda: not app.is_generating)
        results = [m for m in runner.conversation.messages() if m.role == "tool"]
        assert results[-1].tool_results[0].status == expected
        assert app.query_one(ChatInput).text == "draft"
        assert not app.query_one(ChatInput).disabled
