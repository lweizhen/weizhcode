from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from weizhcode.compact.limits import ERROR_BODY_BYTES
from weizhcode.errors import ProviderFault, StreamError, classify_provider_fault


@dataclass(frozen=True)
class SSEEvent:
    event: str | None
    data: str

    def json(self) -> dict[str, Any]:
        try:
            parsed = json.loads(self.data)
        except json.JSONDecodeError as exc:
            raise StreamError(f"流式响应包含无法解析的 JSON：{exc.msg}") from exc
        if not isinstance(parsed, dict):
            raise StreamError("流式响应 JSON 必须是对象。")
        return parsed


async def stream_sse(
    method: str,
    url: str,
    headers: dict[str, str],
    json_body: dict[str, Any],
    *,
    timeout: float | None = None,
    protocol: str = "unknown",
) -> AsyncIterator[SSEEvent]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                method,
                url,
                headers=headers,
                json=json_body,
            ) as response:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError:
                    payload = await _bounded_error_payload(response)
                    fault = classify_provider_fault(protocol, payload, http_status=response.status_code)
                    raise StreamError(f"HTTP {response.status_code}：{fault.message}", fault=fault) from None

                async for event in parse_sse_lines(response.aiter_lines()):
                    yield event
    except httpx.HTTPError:
        fault = ProviderFault(protocol, kind="network")
        raise StreamError(fault.message, fault=fault) from None


async def _bounded_error_payload(response):
    data = bytearray()
    async for chunk in response.aiter_bytes(chunk_size=4096):
        if len(data) + len(chunk) > ERROR_BODY_BYTES:
            return None
        data.extend(chunk)
    try:
        payload = json.loads(data)
        return payload if isinstance(payload, dict) else None
    except (ValueError, UnicodeError, RecursionError):
        return None


async def parse_sse_lines(lines: AsyncIterator[str]) -> AsyncIterator[SSEEvent]:
    event_name: str | None = None
    data_lines: list[str] = []

    async for line in lines:
        if line == "":
            if data_lines:
                yield SSEEvent(event=event_name, data="\n".join(data_lines))
            event_name = None
            data_lines = []
            continue

        if line.startswith(":"):
            continue

        field, separator, value = line.partition(":")
        if separator:
            value = value[1:] if value.startswith(" ") else value

        if field == "event":
            event_name = value
        elif field == "data":
            data_lines.append(value)

    if data_lines:
        yield SSEEvent(event=event_name, data="\n".join(data_lines))


def _extract_secret(headers: dict[str, str]) -> str | None:
    for key, value in headers.items():
        normalized = key.lower()
        if normalized in {"authorization", "x-api-key"}:
            return value.removeprefix("Bearer ").strip()
    return None

