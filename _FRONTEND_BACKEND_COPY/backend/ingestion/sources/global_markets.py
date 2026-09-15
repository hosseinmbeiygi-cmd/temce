from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

from ..http_client import HttpClient, RateLimiter
from .base import DataSource, FetchResult, SourcePayload

logger = get_logger(__name__)


class ConfiguredMarketSource(DataSource):
    """Adapter for a configured JSON endpoint (XAU/USD, USD index, FX, etc.)."""

    def __init__(
        self,
        http: HttpClient,
        *,
        source_name: str,
        url: str,
        instrument: str,
        asset_class: str = "global",
        currency: str = "USD",
        price_paths: tuple[str, ...] = ("price", "close", "rate", "data.price"),
        max_calls: int = 1,
        period: float = 5.0,
    ) -> None:
        self._http = http
        self._source_name = source_name
        self._url = url
        self._instrument = instrument
        self._asset_class = asset_class
        self._currency = currency
        self._price_paths = price_paths
        self._rate_limiter = RateLimiter(max_calls=max_calls, period=period)

    @property
    def name(self) -> str:
        return self._source_name

    async def fetch(self, context: dict[str, Any] | None = None) -> FetchResult:
        await self._rate_limiter.acquire()
        raw = await self._http.fetch(self._url)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("%s returned non-JSON payload", self.name)
            payload = {}
        record = {
            "instrument": self._instrument,
            "asset_class": self._asset_class,
            "observed_at": datetime.now(UTC).isoformat(),
            "price": self._find_price(payload),
            "currency": self._currency,
            "metadata": {"url": self._url},
        }
        envelope = json.dumps({"source": self.name, "records": [record]}, default=str).encode("utf-8")
        return FetchResult(
            payloads=[
                SourcePayload(
                    source=self.name,
                    endpoint=self._url,
                    raw_data=envelope,
                    content_type="application/json",
                    fetch_time=datetime.now(UTC),
                )
            ]
        )

    def _find_price(self, payload: Any) -> Any:
        for path in self._price_paths:
            current = payload
            for part in path.split("."):
                if not isinstance(current, dict) or part not in current:
                    current = None
                    break
                current = current[part]
            if current not in (None, ""):
                return current
        return None

    async def health_check(self) -> bool:
        try:
            await self.fetch()
            return True
        except Exception:
            logger.exception("%s health check failed", self.name)
            return False
