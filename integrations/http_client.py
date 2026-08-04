from __future__ import annotations

import asyncio
from typing import Any

import httpx

from core.logging import get_logger

logger = get_logger(__name__)


class HttpClient:
    """Async HTTP client with connection reuse and retry.

    A single persistent ``httpx.AsyncClient`` is lazily created and reused
    across calls (connection pooling), avoiding the per-request client
    creation cost of the original implementation.
    """

    def __init__(self, base_url: str = "", timeout: float = 30.0, max_retries: int = 3) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> HttpClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def get(self, path: str, params: dict[str, Any] | None = None, **kwargs: Any) -> httpx.Response:
        url = f"{self.base_url}{path}"
        client = await self._get_client()
        for attempt in range(self.max_retries):
            try:
                resp = await client.get(url, params=params, **kwargs)
                resp.raise_for_status()
                return resp
            except Exception as e:
                logger.warning("GET %s failed (attempt %d/%d): %s", url, attempt + 1, self.max_retries, e)
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2**attempt)
        raise Exception(f"Request failed after {self.max_retries} retries")  # pragma: no cover

    async def post(self, path: str, json: dict[str, Any] | None = None, **kwargs: Any) -> httpx.Response:
        url = f"{self.base_url}{path}"
        client = await self._get_client()
        for attempt in range(self.max_retries):
            try:
                resp = await client.post(url, json=json, **kwargs)
                resp.raise_for_status()
                return resp
            except Exception as e:
                logger.warning("POST %s failed (attempt %d/%d): %s", url, attempt + 1, self.max_retries, e)
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2**attempt)
        raise Exception(f"Request failed after {self.max_retries} retries")  # pragma: no cover
