from __future__ import annotations

import asyncio
from contextvars import ContextVar
from dataclasses import dataclass, field

from weizhcode.redaction import StreamingRedactor
from .contracts import ToolSource
from .limits import CAPTURE_BYTES, CAPTURE_CHUNK_BYTES, CAPTURE_QUEUE_SIZE, SOURCE_BUFFER_BYTES


worker_file_capture = ContextVar("weizhcode_worker_file_capture", default=None)


def result_capture_frames(result, *, operation_id, execution_key, generation):
    """首次最终结果截断前生成有界帧；原采集限制及截断事实保持。"""
    common = {"operation_id": operation_id, "execution_key": execution_key, "generation": generation}
    raw = result.content.encode("utf-8")
    text = raw[:CAPTURE_BYTES].decode("utf-8", errors="ignore")
    yield {"type": "capture_begin", **common, "collected_bytes": len(raw), "truncated": result.truncated,
           "call_id": result.call_id, "tool_name": result.tool_name}
    for seq, offset in enumerate(range(0, len(text), 4096)):
        yield {"type": "capture_chunk", **common, "seq": seq, "text": text[offset:offset+4096]}
    yield {"type": "capture_end", **common, "complete": len(text.encode("utf-8")) == len(raw)}


@dataclass
class _Incoming:
    generation: int
    stream: StreamingRedactor = field(repr=False)
    parts: list[str] = field(default_factory=list, repr=False)
    safe_bytes: int = 0
    received_bytes: int = 0
    collected_bytes: int = 0
    truncated: bool = False
    overflow: bool = False
    started: bool = False


class CaptureSink:
    def __init__(self, hub, execution_key, generation):
        self.hub, self.execution_key, self.generation = hub, execution_key, generation
        self.closed = False
        self.file_read = None

    async def begin(self, *, collected_bytes, truncated):
        return await self.hub._begin(self, collected_bytes, truncated)

    async def feed(self, text):
        if self.closed or not isinstance(text, str) or len(text.encode("utf-8")) > CAPTURE_CHUNK_BYTES:
            return False
        return await self.hub._feed(self, text)

    async def finish(self, *, complete=True):
        if self.closed:
            return self.hub.get(self.execution_key)
        self.closed = True
        return await self.hub._finish(self, complete)

    async def abort(self, *, keep_partial=False):
        if keep_partial:
            return await self.finish(complete=False)
        self.closed = True
        await self.hub.release(self.execution_key)


class CaptureHub:
    """有界的私有文本通道；不得从模型metadata创建来源。"""

    queue_limit = CAPTURE_QUEUE_SIZE

    def __init__(self, redactor, *, is_current=lambda generation: True):
        self.redactor, self.is_current = redactor, is_current
        self._incoming, self._sources = {}, {}
        self._allocated = 0
        self._lock = asyncio.Lock()
        self._queue = asyncio.Queue(maxsize=CAPTURE_QUEUE_SIZE)
        self._pump = None
        self._closed = False
        self._closing = asyncio.Event()

    async def reserve(self, execution_key, *, generation):
        async with self._lock:
            if (self._closed or not self.is_current(generation) or execution_key in self._incoming
                    or execution_key in self._sources or self._allocated + CAPTURE_BYTES > SOURCE_BUFFER_BYTES):
                return None
            self._incoming[execution_key] = _Incoming(generation, StreamingRedactor(self.redactor))
            self._allocated += CAPTURE_BYTES
            if self._pump is None:
                self._pump = asyncio.create_task(self._consume())
            return CaptureSink(self, execution_key, generation)

    def get(self, execution_key):
        return self._sources.get(execution_key)

    def _active(self, sink):
        incoming = self._incoming.get(sink.execution_key)
        if self._closed or not self.is_current(sink.generation) or incoming is None or incoming.generation != sink.generation:
            return None
        return incoming

    async def _begin(self, sink, collected_bytes, truncated):
        async with self._lock:
            incoming = self._active(sink)
            if (incoming is None or incoming.started or type(collected_bytes) is not int
                    or collected_bytes < 0 or type(truncated) is not bool):
                return False
            incoming.collected_bytes, incoming.truncated, incoming.started = collected_bytes, truncated, True
            return True

    def _append(self, incoming, text):
        data = text.encode("utf-8")
        room = CAPTURE_BYTES - incoming.safe_bytes
        if len(data) > room:
            data = data[:room]
            text = data.decode("utf-8", errors="ignore")
            data = text.encode("utf-8")
            incoming.overflow = True
        if data:
            incoming.parts.append(text)
            incoming.safe_bytes += len(data)

    async def _feed(self, sink, text):
        if self._closed:
            return False
        done = asyncio.get_running_loop().create_future()
        put = asyncio.create_task(self._queue.put((sink, text, done)))
        closed = asyncio.create_task(self._closing.wait())
        try:
            await asyncio.wait((put, closed), return_when=asyncio.FIRST_COMPLETED)
            if self._closed:
                return False
            await put
            await asyncio.wait((done, closed), return_when=asyncio.FIRST_COMPLETED)
            return done.result() if done.done() and not done.cancelled() else False
        finally:
            for task in (put, closed):
                if not task.done():
                    task.cancel()
            if not done.done() and self._closed:
                done.set_result(False)
            await asyncio.gather(put, closed, return_exceptions=True)

    async def _consume(self):
        while True:
            sink, text, done = await self._queue.get()
            accepted = False
            try:
                async with self._lock:
                    incoming = self._active(sink)
                    if incoming is not None and incoming.started:
                        size = len(text.encode("utf-8"))
                        if incoming.received_bytes + size <= incoming.collected_bytes:
                            incoming.received_bytes += size
                            self._append(incoming, incoming.stream.push(text))
                            accepted = True
            finally:
                if not done.done():
                    done.set_result(accepted)
                self._queue.task_done()

    async def _finish(self, sink, complete):
        async with self._lock:
            incoming = self._active(sink)
            if incoming is None or not incoming.started:
                original = self._incoming.pop(sink.execution_key, None)
                if original is not None:
                    self._allocated -= CAPTURE_BYTES
                return None
            self._append(incoming, incoming.stream.finish())
            source = ToolSource(sink.execution_key, "".join(incoming.parts), incoming.collected_bytes,
                incoming.safe_bytes, incoming.truncated,
                bool(complete) and incoming.received_bytes == incoming.collected_bytes and not incoming.overflow)
            self._incoming.pop(sink.execution_key)
            self._sources[sink.execution_key] = source
            self._allocated -= CAPTURE_BYTES - source.safe_bytes
            return source

    async def release(self, execution_key):
        async with self._lock:
            if self._incoming.pop(execution_key, None) is not None:
                self._allocated -= CAPTURE_BYTES
            source = self._sources.pop(execution_key, None)
            if source is not None:
                self._allocated -= source.safe_bytes

    async def aclose(self):
        self._closed = True
        self._closing.set()
        if self._pump is not None:
            self._pump.cancel()
            await asyncio.gather(self._pump, return_exceptions=True)
        while not self._queue.empty():
            _, _, future = self._queue.get_nowait()
            if not future.done():
                future.set_result(False)
            self._queue.task_done()
        async with self._lock:
            self._incoming.clear()
            self._sources.clear()
            self._allocated = 0
