from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from ingestion.http_client import HttpClient, RateLimiter

from .base import DataSource, FetchResult, SourcePayload

logger = get_logger(__name__)

IFB_BASE = "https://api.ifb.ir/api/v1"


class IFBSource(DataSource):
    def __init__(self, http: HttpClient) -> None:
        self._http = http
        self._rate_limiter = RateLimiter(max_calls=10, period=1.0)

    @property
    def name(self) -> str:
        return "ifb"

    async def fetch(self, context: dict[str, Any] | None = None) -> FetchResult:
        url = f"{IFB_BASE}/market/trades"
        await self._rate_limiter.acquire()
        raw = await self._http.fetch(url)
        payload = SourcePayload(
            source=self.name,
            endpoint="/market/trades",
            raw_data=raw,
            content_type="application/json",
            fetch_time=datetime.now(UTC),
        )
        return FetchResult(payloads=[payload])

    async def health_check(self) -> bool:
        try:
            await self._http.fetch(f"{IFB_BASE}/market/status", method="HEAD")
            return True
        except Exception:
            return False
