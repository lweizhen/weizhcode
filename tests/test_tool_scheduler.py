import asyncio
import json

from weizhcode.models import ChatMessage, RunContext, ToolCall, ToolResult, TurnEvent
from weizhcode.tool_scheduler import ToolScheduler
from weizhcode.tools import create_default_registry


def call(index, name="read_file", **args):
    defaults = {"read_file": {"path": "a"}, "write_file": {"path": "a", "content": "x"},
                "edit_file": {"path": "a", "old_text": "x", "new_text": "y"},
                "run_command": {"command": "echo hi"}}
    return ToolCall(str(index), name, json.dumps(args or defaults.get(name, {})))


class FakeExecutor:
    def __init__(self, gates=None, callback=None):
        self.gates, self.callback = gates or {}, callback
        self.started, self.active, self.peak, self.log = [], set(), 0, []
    async def execute(self, slot, *, mode, cancel, emit):
        i = slot.index
        self.started.append(i)
        self.active.add(i)
        self.peak = max(self.peak, len(self.active))
        self.log.append(("start", i))
        slot.execution_started = True
        try:
            await emit(TurnEvent("tool_running", local_id=slot.local_id, index=i))
            if i in self.gates:
                await self.gates[i].wait()
            await asyncio.sleep(0)
            if self.callback:
                self.callback(slot)
            slot.result = ToolResult(slot.call.call_id, slot.call.name, str(i))
            return slot.result
        finally:
            self.active.remove(i)
            self.log.append(("end", i))


async def wait_until(predicate):
    async def spin():
        while not predicate():
            await asyncio.sleep(0)
    await asyncio.wait_for(spin(), 2)


def schedule(calls, executor, context=None):
    context, events = context or RunContext(), []
    async def emit(event):
        events.append(event)
    work = asyncio.create_task(ToolScheduler(create_default_registry(), executor).execute(
        ChatMessage("assistant", tool_calls=tuple(calls)), context=context, emit=emit))
    return work, context, events


async def test_scheduler_preflight_rejects_conflicts_only():
    calls = [call("dup"), call("dup"), ToolCall(None, "read_file", '{}'),
             ToolCall("bad", "read_file", '{'), call("unknown", "missing"), call("valid")]
    executor = FakeExecutor()
    work, context, events = schedule(calls, executor)
    results = await work
    assert [r.error_code for r in results] == ["DUPLICATE_CALL_ID", "DUPLICATE_CALL_ID",
        "INVALID_ARGUMENTS", "INVALID_JSON", "UNKNOWN_TOOL", None]
    assert executor.started == [5]
    assert [r.call_id for r in results] == [c.call_id for c in calls]
    assert len(set(s.local_id for s in context.slots)) == len(calls)
    assert not context.owned_tasks


async def test_readonly_batch_overlap_and_batch_event_order():
    gates = {0: asyncio.Event(), 1: asyncio.Event()}
    executor = FakeExecutor(gates)
    work, context, events = schedule([call(0), call(1)], executor)
    await wait_until(lambda: len(executor.active) == 2)
    assert [e.index for e in events if e.type == "tool_start"] == [0, 1]
    gates[1].set()
    await wait_until(lambda: 1 not in executor.active)
    assert not any(e.type == "tool_result" for e in events)
    gates[0].set()
    results = await work
    assert [r.content for r in results] == ["0", "1"] and executor.peak == 2
    assert [e.index for e in events if e.type == "tool_result"] == [0, 1]
    assert all(e.local_id == context.slots[e.index].local_id for e in events if e.type.startswith("tool_"))


async def test_readonly_concurrency_limit_and_cancel_waiters():
    gate = asyncio.Event()
    executor = FakeExecutor({i: gate for i in range(6)})
    work, context, _ = schedule([call(i) for i in range(6)], executor)
    await wait_until(lambda: executor.peak == 4)
    assert executor.started == [0, 1, 2, 3]
    context.cancel_event.set()
    results = await work
    gate.set()
    await asyncio.sleep(0)
    assert executor.peak == 4 and executor.started == [0, 1, 2, 3]
    assert len(results) == 6 and all(r.status == "cancelled" for r in results)
    assert not context.slots[4].execution_started and not context.owned_tasks


async def test_readonly_concurrency_limit_wait_time_excluded_from_tool_budget(tmp_path):
    from weizhcode.models import ToolContext
    from weizhcode.tools.executor import ToolExecutor
    from test_tool_executor import LoopWorker
    workers = []
    def factory():
        worker = LoopWorker(prepare_delay=.12)
        workers.append(worker)
        return worker
    registry = create_default_registry()
    executor = ToolExecutor(registry, ToolContext(tmp_path), timeout=.2, worker_factory=factory)
    context, events = RunContext(), []
    async def emit(event):
        events.append(event)
    results = await ToolScheduler(registry, executor).execute(
        ChatMessage("assistant", tool_calls=tuple(call(i) for i in range(6))), context=context, emit=emit)
    assert len(workers) == 6 and all(w.closed for w in workers)
    assert all(r.status == "success" for r in results)


async def test_side_effect_batch_barriers_actual_visibility(tmp_path):
    marker = tmp_path / "marker"
    def side_effect(slot):
        if slot.index == 2:
            marker.write_text("written")
        if slot.index >= 3:
            assert marker.read_text() == "written"
    executor = FakeExecutor(callback=side_effect)
    calls = [call(0), call(1), call(2, "write_file"), call(3), call(4, "edit_file"), call(5, "run_command")]
    work, _, _ = schedule(calls, executor)
    results = await work
    assert all(not r.is_error for r in results)
    log = executor.log
    assert log.index(("start", 2)) > max(log.index(("end", 0)), log.index(("end", 1)))
    for i in (3, 4, 5):
        assert log.index(("start", i)) > log.index(("end", i-1))


async def test_side_effect_batch_barriers_unknown_and_invalid_separate_reads():
    executor = FakeExecutor()
    work, _, events = schedule([call(0), call(1, "missing"), call(2), ToolCall("3", "read_file", '{'), call(4)], executor)
    results = await work
    assert executor.peak == 1 and executor.started == [0, 2, 4]
    assert [e.index for e in events if e.type == "tool_result"] == list(range(5))
    assert results[1].error_code == "UNKNOWN_TOOL" and results[3].error_code == "INVALID_JSON"


async def test_batch_cancellation_results_preserve_success_and_block_next_batch():
    gate = asyncio.Event()
    executor = FakeExecutor({1: gate})
    work, context, events = schedule([call(0), call(1), call(2, "write_file")], executor)
    await wait_until(lambda: ("end", 0) in executor.log and 1 in executor.active)
    context.cancel_event.set()
    results = await work
    assert results[0].status == "success"
    assert results[1].status == results[2].status == "cancelled"
    assert executor.started == [0, 1]
    assert [e.index for e in events if e.type == "tool_result"] == [0, 1, 2]
    assert not context.slots[2].execution_started and not context.owned_tasks
