import json

import httpx

from .limits import MAX_HTTP_RESPONSE_BYTES


def origin(url):
    return url.scheme, url.host, url.port


class LimitedStream(httpx.AsyncByteStream):
    def __init__(self, response):
        self.response = response

    async def __aiter__(self):
        count = 0
        try:
            async for chunk in self.response.aiter_bytes():
                count += len(chunk)
                if count > MAX_HTTP_RESPONSE_BYTES:
                    raise ValueError("MCP_HTTP_LIMIT")
                yield chunk
        finally:
            await self.response.aclose()

    async def aclose(self):
        await self.response.aclose()


class McpHttpTransport(httpx.AsyncBaseTransport):
    def __init__(self, url, inner=None):
        self.endpoint = httpx.URL(url)
        self.inner = inner or httpx.AsyncHTTPTransport(retries=0)
        self.sent = {}

    async def handle_async_request(self, request):
        if origin(request.url) != origin(self.endpoint):
            raise ValueError("MCP_HTTP_ORIGIN")
        if request.method == "GET":
            return httpx.Response(405, request=request)
        if request.method not in {"POST", "DELETE"}:
            raise ValueError("MCP_HTTP_METHOD")
        key = None
        if request.method == "POST":
            # HTTPX redirects rebuild a streaming request even for an original JSON body.
            payload = json.loads(await request.aread())
            if "method" in payload and "id" in payload:
                key = (type(payload["id"]).__name__, str(payload["id"]))
                previous = self.sent.get(key)
                if previous is not None and (previous[0] != str(request.url) or previous[1] >= 3):
                    raise ValueError("MCP_HTTP_REPLAY")
                self.sent[key] = (None, 0 if previous is None else previous[1] + 1)
        response = await self.inner.handle_async_request(request)
        if key is not None and response.status_code in {307, 308} and "location" in response.headers:
            target = request.url.join(response.headers["location"])
            if origin(target) != origin(self.endpoint):
                await response.aclose()
                raise ValueError("MCP_HTTP_ORIGIN")
            self.sent[key] = (str(target), self.sent[key][1])
        headers = [(k, v) for k, v in response.headers.multi_items() if k.lower() not in {"content-encoding", "content-length"}]
        return httpx.Response(response.status_code, headers=headers, stream=LimitedStream(response),
                              extensions=response.extensions, request=request)

    async def aclose(self):
        await self.inner.aclose()
