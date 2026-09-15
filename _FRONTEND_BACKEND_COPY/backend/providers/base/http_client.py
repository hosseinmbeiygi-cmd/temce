from __future__ import annotations

import asyncio
from typing import Any

import httpx

from core.config import settings
from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class HttpClient:
    def __init__(
        self,
        base_url: str = "",
        timeout: int | None = None,
        headers: dict[str, str] | None = None,
        concurrency: int | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout or settings.provider_default_timeout
        default_headers = {"User-Agent": _DEFAULT_USER_AGENT}
        self._headers = {**default_headers, **(headers or {})}
        self._client: httpx.AsyncClient | None = None
        # Concurrency per-host: previously hard-coded to 10, now derived from
        # provider_rate_limit_per_minute (≈5 req/s) but overridable per-provider.
        _conc = concurrency or max(5, min(20, settings.provider_rate_limit_per_minute // 12))
        self._semaphore = asyncio.Semaphore(_conc)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                headers=self._headers,
                follow_redirects=True,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            )
        return self._client

    async def get(
        self, path: str = "", params: dict[str, Any] | None = None, headers: dict[str, str] | None = None, **kwargs: Any
    ) -> Result[httpx.Response]:
        async with self._semaphore:
            try:
                client = await self._get_client()
                resp = await client.get(path, params=params, headers={**self._headers, **(headers or {})}, **kwargs)
                resp.raise_for_status()
                return Result.ok(resp)
            except httpx.HTTPStatusError as e:
                logger.error("HTTP %s for %s: %s", e.response.status_code, e.request.url, e.response.text[:500])
                return Result.fail(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
            except httpx.RequestError as e:
                logger.error("Request failed for %s: %s", path, e)
                return Result.fail(str(e))

    async def post(
        self,
        path: str = "",
        json: dict[str, Any] | None = None,
        data: Any = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> Result[httpx.Response]:
        async with self._semaphore:
            try:
                client = await self._get_client()
                resp = await client.post(
                    path, json=json, content=data, headers={**self._headers, **(headers or {})}, **kwargs
                )
                resp.raise_for_status()
                return Result.ok(resp)
            except httpx.HTTPStatusError as e:
                return Result.fail(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
            except httpx.RequestError as e:
                return Result.fail(str(e))

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> HttpClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
