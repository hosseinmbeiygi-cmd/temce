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

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Perform one request and retry only transient failures.

        Permanent 4xx responses are caller/data errors and must not be retried;
        429 and 5xx responses may be transient upstream failures.
        """
        url = f"{self.base_url}{path}"
        client = await self._get_client()
        attempts = max(1, self.max_retries)
        retryable_statuses = {408, 425, 429, 500, 502, 503, 504}

        for attempt in range(attempts):
            try:
                resp = await client.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status not in retryable_statuses or attempt == attempts - 1:
                    raise
                logger.warning(
                    "%s %s failed with HTTP %s (attempt %d/%d)",
                    method,
                    url,
                    status,
                    attempt + 1,
                    attempts,
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt == attempts - 1:
                    raise
                logger.warning(
                    "%s %s failed (attempt %d/%d): %s",
                    method,
                    url,
                    attempt + 1,
                    attempts,
                    exc,
                )
            await asyncio.sleep(2**attempt)

        raise RuntimeError(f"Request failed after {attempts} attempts")  # pragma: no cover

    async def get(self, path: str, params: dict[str, Any] | None = None, **kwargs: Any) -> httpx.Response:
        return await self._request("GET", path, params=params, **kwargs)

    async def post(self, path: str, json: dict[str, Any] | None = None, **kwargs: Any) -> httpx.Response:
        return await self._request("POST", path, json=json, **kwargs)
