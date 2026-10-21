from __future__ import annotations

import asyncio
from typing import Any

import httpx

from core.config import settings
from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


_DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

# DP-002: transient upstream failures. 4xx other than the two "try again"
# codes are the caller's fault and must not be retried.
_RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
_DEFAULT_MAX_RETRIES = 2
_DEFAULT_RETRY_BACKOFF = 0.5


class HttpClient:
    def __init__(
        self,
        base_url: str = "",
        timeout: int | None = None,
        headers: dict[str, str] | None = None,
        concurrency: int | None = None,
        max_retries: int | None = None,
        retry_backoff: float | None = None,
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
        self.max_retries = _DEFAULT_MAX_RETRIES if max_retries is None else max(0, max_retries)
        self.retry_backoff = _DEFAULT_RETRY_BACKOFF if retry_backoff is None else max(0.0, retry_backoff)

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """True for timeouts/transport errors and retryable HTTP statuses.

        A 400/401/404 means the request itself is wrong; retrying it only
        burns quota.  Timeouts, connection resets and 5xx/429 are transient.
        """
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in _RETRYABLE_STATUS
        return isinstance(exc, httpx.TransportError)

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

    async def _request(
        self, method: str, path: str, headers: dict[str, str] | None = None, **kwargs: Any
    ) -> Result[httpx.Response]:
        """Issue one request with bounded retries on transient failures."""
        async with self._semaphore:
            request_headers = {**self._headers, **(headers or {})}
            last_error = "request failed"
            for attempt in range(self.max_retries + 1):
                try:
                    client = await self._get_client()
                    send = client.get if method == "GET" else client.post
                    resp = await send(path, headers=request_headers, **kwargs)
                    resp.raise_for_status()
                    return Result.ok(resp)
                except httpx.HTTPStatusError as e:
                    last_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                    if not self._is_retryable(e) or attempt >= self.max_retries:
                        logger.error(
                            "HTTP %s for %s: %s",
                            e.response.status_code,
                            getattr(e.request, "url", path),
                            e.response.text[:500],
                        )
                        return Result.fail(last_error)
                except httpx.RequestError as e:
                    last_error = str(e)
                    if not self._is_retryable(e) or attempt >= self.max_retries:
                        logger.error("Request failed for %s: %s", path, e)
                        return Result.fail(last_error)
                if self.retry_backoff:
                    await asyncio.sleep(self.retry_backoff * (2**attempt))
            return Result.fail(last_error)

    async def get(
        self, path: str = "", params: dict[str, Any] | None = None, headers: dict[str, str] | None = None, **kwargs: Any
    ) -> Result[httpx.Response]:
        return await self._request("GET", path, headers=headers, params=params, **kwargs)

    async def post(
        self,
        path: str = "",
        json: dict[str, Any] | None = None,
        data: Any = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> Result[httpx.Response]:
        return await self._request("POST", path, headers=headers, json=json, content=data, **kwargs)

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> HttpClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
