from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from ingestion.http_client import HttpClient, RateLimiter

from .base import DataSource, FetchResult, SourcePayload

logger = get_logger(__name__)


class TsetmcOptionSource(DataSource):
    def __init__(self, http: HttpClient) -> None:
        self._http = http
        self._rate_limiter = RateLimiter(max_calls=5, period=1.0)

    @property
    def name(self) -> str:
        return "tsetmc_options"

    async def fetch(self, context: dict[str, Any] | None = None) -> FetchResult:
        ins_id = (context or {}).get("instrument_id")
        if not ins_id:
            return FetchResult(payloads=[])

        url = f"http://cdn.tsetmc.com/api/Option/GetOption/{ins_id}"
        await self._rate_limiter.acquire()
        raw = await self._http.fetch(url)
        payload = SourcePayload(
            source=self.name,
            endpoint=f"/Option/GetOption/{ins_id}",
            raw_data=raw,
            content_type="application/json",
            fetch_time=datetime.now(UTC),
            metadata={"instrument_id": ins_id},
        )
        return FetchResult(payloads=[payload])

    async def health_check(self) -> bool:
        try:
            await self._http.fetch(
                "http://cdn.tsetmc.com/api/Option/GetOption/35364588457143450",
                method="HEAD",
            )
            return True
        except Exception:
            return False


class TsetmcFutureSource(DataSource):
    def __init__(self, http: HttpClient) -> None:
        self._http = http
        self._rate_limiter = RateLimiter(max_calls=5, period=1.0)

    @property
    def name(self) -> str:
        return "tsetmc_futures"

    async def fetch(self, context: dict[str, Any] | None = None) -> FetchResult:
        ins_id = (context or {}).get("instrument_id")
        if not ins_id:
            return FetchResult(payloads=[])

        url = f"http://cdn.tsetmc.com/api/Future/GetFuture/{ins_id}"
        await self._rate_limiter.acquire()
        raw = await self._http.fetch(url)
        payload = SourcePayload(
            source=self.name,
            endpoint=f"/Future/GetFuture/{ins_id}",
            raw_data=raw,
            content_type="application/json",
            fetch_time=datetime.now(UTC),
            metadata={"instrument_id": ins_id},
        )
        return FetchResult(payloads=[payload])

    async def health_check(self) -> bool:
        try:
            await self._http.fetch(
                "http://cdn.tsetmc.com/api/Future/GetFuture/35364588457143450",
                method="HEAD",
            )
            return True
        except Exception:
            return False
