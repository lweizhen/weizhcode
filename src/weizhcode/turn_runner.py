from __future__ import annotations

import asyncio
from contextlib import aclosing
from dataclasses import replace

from weizhcode.models import ChatMessage, ToolResult, TurnEvent
from weizhcode.prompts import SYSTEM_PROMPT, FINAL_PROMPT
from weizhcode.redaction import Redactor, StreamingRedactor, safe_text


class TurnRunner:
    def __init__(self, provider, conversation, registry, executor, redactor=None, *, system_prompt=SYSTEM_PROMPT):
        self.provider = provider
        self.conversation = conversation
        self.registry = registry
        self.executor = executor
        self.redactor = redactor or Redactor()
        self.system_prompt = system_prompt
        self.busy = False
        self._closed = False
        self._task = None

    def run(self, user_text, *, approve=None):
        # 在返回迭代器之前占用，避免两个提交同时进入。
        if self.busy or self._closed:
            async def rejected():
                yield TurnEvent("error", text="当前回合尚未结束或应用已退出")
            return rejected()
        self.busy = True
        return self._run(user_text, approve)

    async def _request(self, phase, state):
        redactor = StreamingRedactor(self.redactor)
        parts = []
        prompt = self.system_prompt + ("\n" + FINAL_PROMPT if phase == "final" else "")
        stream = self.provider.stream_chat(self.conversation.messages(), tools=self.registry.definitions(),
                                          system_prompt=prompt, allow_tools=phase == "initial")
        async with aclosing(stream):
            async for event in stream:
                if event.type == "text_delta":
                    parts.append(event.text)
                    text = safe_text(redactor.push(event.text))
                    if text:
                        yield TurnEvent("text_delta", text=text, phase=phase)
                elif event.type == "tool_call_start":
                    # 接收态不能被当成已批准或可执行调用。
                    yield TurnEvent("tool_pending", phase=phase,
                                    local_id=event.tool_call.local_id, tool_call=event.tool_call)
                elif event.type == "error":
                    yield TurnEvent("error", text=self.redactor.display(event.message), phase=phase)
                    return
                elif event.type == "done":
                    tail = safe_text(redactor.finish())
                    if tail:
                        yield TurnEvent("text_delta", text=tail, phase=phase)
                    message = event.assistant_message or ChatMessage("assistant", "".join(parts))
                    state["message"] = replace(message, content=self.redactor.text(message.content))
                    return
        yield TurnEvent("error", text="模型回复未完整结束，本次内容未保存", phase=phase)

    async def _run(self, user_text, approve):
        self._task = asyncio.current_task()
        try:
            self.conversation.add_user_message(user_text)
            initial = {}
            async for event in self._request("initial", initial):
                yield event
            assistant = initial.get("message")
            if assistant is None or self._closed:
                return
            calls = assistant.tool_calls
            if not calls:
                self.conversation.add_assistant_turn(assistant)
                yield TurnEvent("turn_done")
                return
            results = []
            if len(calls) > 1:
                for call in calls:
                    result = ToolResult.failure(call, "TOO_MANY_TOOL_CALLS", "本回合只允许一个工具；本批调用全部未执行")
                    results.append(result)
                    yield TurnEvent("tool_result", local_id=call.local_id, tool_call=call, result=result)
            else:
                call = calls[0]
                # 同一完整调用更新接收态；展示层始终自行脱敏，不改执行参数。
                yield TurnEvent("tool_pending", local_id=call.local_id, tool_call=call)
                async for event in self.executor.run(call, approve=approve):
                    if event.result:
                        results.append(event.result)
                    yield event
            if self._closed:
                return
            if len(results) != len(calls):
                raise RuntimeError("工具执行器未返回对应结果")
            self.conversation.add_tool_exchange(assistant, results)
            final = {}
            async for event in self._request("final", final):
                yield event
            message = final.get("message")
            if message is None or self._closed:
                return
            if message.tool_calls:
                results = [ToolResult.failure(c, "TOOL_ROUND_LIMIT", "单轮工具阶段已结束，此调用未执行")
                           for c in message.tool_calls]
                self.conversation.add_tool_exchange(message, results)
                for call, result in zip(message.tool_calls, results):
                    yield TurnEvent("tool_result", phase="final", local_id=call.local_id, tool_call=call, result=result)
                yield TurnEvent("text_delta", phase="final", text="\n已达到单轮工具上限，未执行后续调用。")
            else:
                self.conversation.add_assistant_turn(message)
            yield TurnEvent("turn_done", phase="final")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            yield TurnEvent("error", text=self.redactor.display(str(exc)))
        finally:
            self.busy = False
            self._task = None

    async def aclose(self):
        self._closed = True
        task = self._task
        if task is not None and task is not asyncio.current_task() and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await self.executor.aclose()
