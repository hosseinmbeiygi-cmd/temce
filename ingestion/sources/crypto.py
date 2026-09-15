from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

from ..http_client import HttpClient, RateLimiter
from ..market_data import AssetClass, parse_decimal
from .base import DataSource, FetchResult, SourcePayload

logger = get_logger(__name__)


class CryptoExchangeSource(DataSource):
    """Common order-book/ticker adapter for Iranian crypto exchanges."""

    def __init__(
        self,
        http: HttpClient,
        *,
        source_name: str,
        base_url: str,
        symbol: str = "USDTIRT",
        path: str = "/v2/orderbook/{symbol}",
        max_calls: int = 5,
        period: float = 1.0,
    ) -> None:
        self._http = http
        self._source_name = source_name
        self._base_url = base_url.rstrip("/")
        self._symbol = symbol
        self._path = path
        self._rate_limiter = RateLimiter(max_calls=max_calls, period=period)

    @property
    def name(self) -> str:
        return self._source_name

    async def fetch(self, context: dict[str, Any] | None = None) -> FetchResult:
        ctx = context or {}
        symbol = str(ctx.get("symbol", self._symbol))
        endpoint = self._path.format(symbol=symbol)
        await self._rate_limiter.acquire()
        raw = await self._http.fetch(f"{self._base_url}{endpoint}")
        records = self._normalize(raw, symbol)
        envelope = json.dumps(
            {"source": self.name, "records": records},
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
        return FetchResult(
            payloads=[
                SourcePayload(
                    source=self.name,
                    endpoint=endpoint,
                    raw_data=envelope,
                    content_type="application/json",
                    fetch_time=datetime.now(UTC),
                    metadata={"symbol": symbol, "upstream_bytes": len(raw)},
                )
            ]
        )

    def _normalize(self, raw: bytes, symbol: str) -> list[dict[str, Any]]:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("%s returned non-JSON payload", self.name)
            return []
        body = payload.get("data", payload) if isinstance(payload, dict) else payload
        bids = body.get("bids", []) if isinstance(body, dict) else []
        asks = body.get("asks", []) if isinstance(body, dict) else []
        best_bid = self._level_price(bids[0]) if bids else None
        best_ask = self._level_price(asks[0]) if asks else None
        price = parse_decimal(body.get("lastTradePrice") if isinstance(body, dict) else None)
        if price is None:
            price = (best_bid + best_ask) / 2 if best_bid and best_ask else best_bid or best_ask
        if price is None or price <= 0:
            return []
        return [
            {
                "instrument": f"{symbol.upper()}",
                "asset_class": AssetClass.CRYPTO.value,
                "observed_at": datetime.now(UTC).isoformat(),
                "price": str(price),
                "bid": str(best_bid) if best_bid else None,
                "ask": str(best_ask) if best_ask else None,
                "currency": "IRR",
                "metadata": {"exchange": self.name},
            }
        ]

    @staticmethod
    def _level_price(level: Any):
        if isinstance(level, (list, tuple)) and level:
            return parse_decimal(level[0])
        if isinstance(level, dict):
            return parse_decimal(level.get("price") or level.get("p"))
        return parse_decimal(level)

    async def health_check(self) -> bool:
        try:
            await self.fetch()
            return True
        except Exception:
            logger.exception("%s health check failed", self.name)
            return False


class NobitexSource(CryptoExchangeSource):
    def __init__(self, http: HttpClient) -> None:
        super().__init__(http, source_name="nobitex_usdt", base_url="https://api.nobitex.ir")


class WallexSource(CryptoExchangeSource):
    def __init__(self, http: HttpClient) -> None:
        super().__init__(
            http,
            source_name="wallex_usdt",
            base_url="https://api.wallex.ir",
            path="/v1/depth/{symbol}",
        )


class RamzinexSource(CryptoExchangeSource):
    def __init__(self, http: HttpClient) -> None:
        super().__init__(
            http,
            source_name="ramzinex_usdt",
            base_url="https://api.ramzinex.com",
            path="/exchange/orderbook/{symbol}",
        )
