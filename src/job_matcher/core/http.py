from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from job_matcher.core.config import Settings


class CircuitOpenError(RuntimeError):
    pass


class ResilientHttpClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = httpx.AsyncClient(
            timeout=settings.request_timeout_seconds,
            headers={"User-Agent": settings.http_user_agent},
            follow_redirects=True,
        )
        self._failure_counts: dict[str, int] = defaultdict(int)
        self._cooldowns: dict[str, datetime] = {}

    async def close(self) -> None:
        await self._client.aclose()

    async def get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        response = await self._request("GET", url, params=params, headers=headers)
        return response.json()

    async def get_text(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        response = await self._request("GET", url, params=params, headers=headers)
        return response.text

    async def get_bytes(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> bytes:
        response = await self._request("GET", url, params=params, headers=headers)
        return response.content

    async def _request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        host = httpx.URL(url).host or "unknown"
        cooldown_until = self._cooldowns.get(host)
        now = datetime.now(tz=UTC)
        if cooldown_until and cooldown_until > now:
            raise CircuitOpenError(f"circuit open for host {host} until {cooldown_until.isoformat()}")

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.settings.request_retries),
            wait=wait_exponential(
                multiplier=self.settings.request_backoff_seconds,
                min=self.settings.request_backoff_seconds,
                max=10,
            ),
            retry=retry_if_exception_type((httpx.HTTPError, CircuitOpenError)),
            reraise=True,
        ):
            with attempt:
                try:
                    await asyncio.sleep(0.2)
                    response = await self._client.request(
                        method=method, url=url, params=params, headers=headers
                    )
                    response.raise_for_status()
                except httpx.HTTPError:
                    self._failure_counts[host] += 1
                    if self._failure_counts[host] >= 4:
                        self._cooldowns[host] = now + timedelta(minutes=5)
                    raise
                else:
                    self._failure_counts[host] = 0
                    self._cooldowns.pop(host, None)
                    return response

        raise RuntimeError("unreachable")
