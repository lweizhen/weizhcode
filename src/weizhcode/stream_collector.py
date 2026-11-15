from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import replace

from weizhcode.models import RoundResponse, TurnEvent
from weizhcode.redaction import Redactor, StreamingRedactor, safe_text
from weizhcode.providers.base import merge_usage_snapshot


class StreamCollector:
    def __init__(self, provider, redactor=None):
        self.provider = provider
        self.redactor = redactor or Redactor()

    async def collect(self, messages, *, tools, system_prompt, context, state, emit, prompt_context=None):
        options = {"prompt_context": prompt_context} if prompt_context is not None else {}
        stream = self.provider.stream_chat(messages, tools=tools, system_prompt=system_prompt,
                                           allow_tools=True, **options)
        cancelled = asyncio.create_task(context.cancel_event.wait())
        context.owned_tasks.add(cancelled)
        pending = None
        redactor = StreamingRedactor(self.redactor)
        invalid_usage = False

        async def send(kind, **kwargs):
            await emit(TurnEvent(kind, run_id=context.run_id, request_id=state.request_id,
                                 iteration=state.iteration, mode=context.mode, **kwargs))

        async def text(raw):
            visible = safe_text(redactor.push(raw))
            if visible:
                await send("text_delta", text=visible)

        try:
            while not context.cancel_event.is_set():
                state.request_started = True
                pending = asyncio.create_task(anext(stream))
                context.owned_tasks.add(pending)
                done, _ = await asyncio.wait((pending, cancelled), return_when=asyncio.FIRST_COMPLETED)
                event = None
                if pending in done:
                    try:
                        event = pending.result()
                    except StopAsyncIteration:
                        state.error = "模型回复未完整结束，本次内容未保存"
                        break
                    finally:
                        context.owned_tasks.discard(pending)
                if event is not None:
                    if event.type == "usage" and event.usage is not None:
                        previous, current = state.usage, event.usage
                        for old, new in ((previous.input_tokens, current.input_tokens),
                                         (previous.output_tokens, current.output_tokens),
                                         (previous.uncached_input_tokens, current.uncached_input_tokens)):
                            if old is not None and new is not None and new < old:
                                invalid_usage = True
                        merged = merge_usage_snapshot(previous, current)
                        state.usage = replace(merged, complete=merged.complete and not invalid_usage,
                                              source=self.redactor.display(current.source))
                    elif event.type == "done":
                        message = event.assistant_message
                        if message is None or message.role != "assistant":
                            state.error = "模型未提供完整助手响应，不执行工具"
                            break
                        if not message.content.startswith(state.text):
                            state.error = "模型完整正文与流式正文不一致，不执行工具"
                            break
                        remainder = message.content[len(state.text):]
                        state.text = message.content
                        await text(remainder)
                        state.assistant_message = deepcopy(message)
                        state.completed = True
                    elif event.type == "error":
                        state.error = self.redactor.display(event.message or "模型请求失败")
                        break
                    elif event.type == "text_delta" and not context.cancel_event.is_set():
                        state.text += event.text
                        await text(event.text)
                    elif event.type == "tool_call_start" and event.tool_call is not None and not context.cancel_event.is_set():
                        call = event.tool_call
                        state.pending_ids.append(call.local_id)
                        display = replace(call, name=self.redactor.display(call.name),
                                          raw_arguments=self.redactor.display(call.raw_arguments),
                                          arguments=self.redactor.value(call.arguments))
                        await send("tool_pending", local_id=call.local_id, tool_call=display)
                if context.cancel_event.is_set():
                    state.cancelled = True
                    break
                if state.completed:
                    return RoundResponse(state.request_id, state.iteration,
                                         state.assistant_message, state.usage)
            if context.cancel_event.is_set():
                state.cancelled = True
            return None
        except asyncio.CancelledError:
            context.cancel_event.set()
            state.cancelled = True
            raise
        except Exception:
            # 不回显未知异常原文，避免认证头/密钥随第三方异常泄露。
            state.error = "模型响应收集失败，本次内容未保存"
            return None
        finally:
            for task in (pending, cancelled):
                if task is not None and not task.done():
                    task.cancel()
            await asyncio.gather(*(t for t in (pending, cancelled) if t is not None),
                                 return_exceptions=True)
            for task in (pending, cancelled):
                context.owned_tasks.discard(task)
            await stream.aclose()
            tail = safe_text(redactor.finish())
            if tail:
                await send("text_delta", text=tail)
            if not state.completed or state.cancelled or state.error:
                state.usage = replace(state.usage, complete=False)
