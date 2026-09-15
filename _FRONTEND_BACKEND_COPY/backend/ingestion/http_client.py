from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import aiohttp

from core.logging import get_logger

from .config import IngestionConfig
from .retry import retry_async

logger = get_logger(__name__)


class HttpClient:
    def __init__(self, config: IngestionConfig) -> None:
        self._config = config
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()
        self._cleanup_callbacks: list[Callable[[], Any]] = []

    async def start(self) -> None:
        async with self._lock:
            if self._session is not None:
                return
            connector = aiohttp.TCPConnector(
                limit=self._config.connection_pool_size,
                ttl_dns_cache=300,
                force_close=True,
            )
            timeout = aiohttp.ClientTimeout(total=self._config.request_timeout)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={"User-Agent": "MarketIngestion/1.0"},
            )

    async def stop(self) -> None:
        async with self._lock:
            if self._session is not None:
                await self._session.close()
                self._session = None
        for cb in self._cleanup_callbacks:
            if asyncio.iscoroutinefunction(cb):
                await cb()
            else:
                cb()

    def add_cleanup(self, cb: Callable[[], Any]) -> None:
        self._cleanup_callbacks.append(cb)

    async def fetch(
        self,
        url: str,
        method: str = "GET",
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        data: Any = None,
    ) -> bytes:
        if self._session is None:
            raise RuntimeError("HttpClient not started")

        return await retry_async(
            self._do_fetch,
            url,
            method=method,
            params=params,
            headers=headers,
            data=data,
            max_retries=self._config.max_retries,
            backoff_base=self._config.retry_backoff_base,
            max_delay=self._config.retry_max_delay,
        )

    async def _do_fetch(
        self,
        url: str,
        method: str = "GET",
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        data: Any = None,
    ) -> bytes:
        assert self._session is not None
        async with self._session.request(
            method,
            url,
            params=params,
            headers=headers,
            data=data,
        ) as resp:
            resp.raise_for_status()
            return await resp.read()


class RateLimiter:
    def __init__(self, max_calls: int, period: float) -> None:
        self._max_calls = max_calls
        self._period = period
        self._tokens = 0.0
        self._last_refill = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_refill
            self._tokens = min(float(self._max_calls), self._tokens + elapsed * (self._max_calls / self._period))
            self._last_refill = now

            if self._tokens < 1:
                wait = (1 - self._tokens) * (self._period / self._max_calls)
                await asyncio.sleep(wait)
                self._tokens = 0.0
                self._last_refill = asyncio.get_event_loop().time()
            else:
                self._tokens -= 1.0
