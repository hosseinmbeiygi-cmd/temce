from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from ingestion.http_client import HttpClient, RateLimiter

from .base import DataSource, FetchResult, SourcePayload

logger = get_logger(__name__)

TSETMC_BASE = "http://cdn.tsetmc.com/api"


class TsetmcInstrumentSource(DataSource):
    def __init__(self, http: HttpClient) -> None:
        self._http = http
        self._instruments: list[dict[str, Any]] | None = None
        self._rate_limiter = RateLimiter(max_calls=10, period=1.0)

    @property
    def name(self) -> str:
        return "tsetmc_instruments"

    async def fetch(self, context: dict[str, Any] | None = None) -> FetchResult:
        url = f"{TSETMC_BASE}/Instrument/GetInstrumentList"
        await self._rate_limiter.acquire()
        raw = await self._http.fetch(url)
        payload = SourcePayload(
            source=self.name,
            endpoint="/Instrument/GetInstrumentList",
            raw_data=raw,
            content_type="application/json",
            fetch_time=datetime.now(UTC),
        )
        return FetchResult(payloads=[payload])

    async def health_check(self) -> bool:
        try:
            await self._http.fetch(f"{TSETMC_BASE}/Instrument/GetInstrumentList", method="HEAD")
            return True
        except Exception:
            return False

    async def get_instrument_ids(self) -> list[str]:
        if self._instruments is not None:
            return [inst["insCode"] for inst in self._instruments]

        import json

        try:
            result = await self.fetch()
            data = json.loads(result.payloads[0].raw_data)
            self._instruments = data if isinstance(data, list) else data.get("instrument", [])
        except Exception:
            logger.exception("Failed to fetch instrument list")
            return []
        return [inst["insCode"] for inst in self._instruments]


class TsetmcMarketWatchSource(DataSource):
    def __init__(self, http: HttpClient) -> None:
        self._http = http
        self._rate_limiter = RateLimiter(max_calls=10, period=1.0)

    @property
    def name(self) -> str:
        return "tsetmc_marketwatch"

    async def fetch(self, context: dict[str, Any] | None = None) -> FetchResult:
        url = f"{TSETMC_BASE}/MarketData/MarketData"
        await self._rate_limiter.acquire()
        raw = await self._http.fetch(url)
        payload = SourcePayload(
            source=self.name,
            endpoint="/MarketData/MarketData",
            raw_data=raw,
            content_type="application/json",
            fetch_time=datetime.now(UTC),
        )
        return FetchResult(payloads=[payload])

    async def health_check(self) -> bool:
        try:
            await self._http.fetch(f"{TSETMC_BASE}/MarketData/MarketData", method="HEAD")
            return True
        except Exception:
            return False


class TsetmcTradeSource(DataSource):
    def __init__(self, http: HttpClient) -> None:
        self._http = http
        self._rate_limiter = RateLimiter(max_calls=5, period=1.0)

    @property
    def name(self) -> str:
        return "tsetmc_trades"

    async def fetch(self, context: dict[str, Any] | None = None) -> FetchResult:
        ins_id = (context or {}).get("instrument_id")
        if not ins_id:
            return FetchResult(payloads=[])

        url = f"{TSETMC_BASE}/ClosingPrice/GetClosingPriceHistory/{ins_id}"
        await self._rate_limiter.acquire()
        raw = await self._http.fetch(url)
        payload = SourcePayload(
            source=self.name,
            endpoint=f"/ClosingPrice/GetClosingPriceHistory/{ins_id}",
            raw_data=raw,
            content_type="application/json",
            fetch_time=datetime.now(UTC),
            metadata={"instrument_id": ins_id},
        )
        return FetchResult(payloads=[payload])

    async def health_check(self) -> bool:
        try:
            await self._http.fetch(f"{TSETMC_BASE}/ClosingPrice/MarketData", method="HEAD")
            return True
        except Exception:
            return False


class TsetmcOrderBookSource(DataSource):
    def __init__(self, http: HttpClient) -> None:
        self._http = http
        self._rate_limiter = RateLimiter(max_calls=5, period=1.0)

    @property
    def name(self) -> str:
        return "tsetmc_orderbook"

    async def fetch(self, context: dict[str, Any] | None = None) -> FetchResult:
        ins_id = (context or {}).get("instrument_id")
        if not ins_id:
            return FetchResult(payloads=[])

        url = f"{TSETMC_BASE}/OrderBook/GetOrderBook/{ins_id}"
        await self._rate_limiter.acquire()
        raw = await self._http.fetch(url)
        payload = SourcePayload(
            source=self.name,
            endpoint=f"/OrderBook/GetOrderBook/{ins_id}",
            raw_data=raw,
            content_type="application/json",
            fetch_time=datetime.now(UTC),
            metadata={"instrument_id": ins_id},
        )
        return FetchResult(payloads=[payload])

    async def health_check(self) -> bool:
        try:
            await self._http.fetch(f"{TSETMC_BASE}/OrderBook/MarketData", method="HEAD")
            return True
        except Exception:
            return False
