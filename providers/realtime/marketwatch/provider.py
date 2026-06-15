from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.realtime import RealtimeDataProvider
from providers.realtime.marketwatch.client import MarketWatchClient
from providers.realtime.marketwatch.mapping import MarketWatchMapping
from providers.realtime.marketwatch.parser import MarketWatchParser

logger = get_logger(__name__)


class MarketWatchProvider(RealtimeDataProvider):
    def __init__(self) -> None:
        super().__init__(name="marketwatch")
        self.client = MarketWatchClient()
        self.parser = MarketWatchParser()
        self.mapping = MarketWatchMapping()

    async def fetch(self, symbol: str | None = None, **kwargs: Any) -> Result[Any]:
        if not symbol:
            return Result.fail("symbol is required")
        result = await self.client.get_stock_data(symbol)
        if result.success:
            raw = result.value.text if hasattr(result.value, "text") else result.value
            parsed = self.parser.parse(raw)
            mapped = self.mapping.map(parsed)
            return Result.ok(mapped)
        return result

    async def get_quote(self, symbol: str, **kwargs: Any) -> Result[dict[str, Any]]:
        return await self.fetch(symbol)

    async def get_orderbook(self, symbol: str, **kwargs: Any) -> Result[dict[str, Any]]:
        return Result.fail("Orderbook not available from MarketWatch")

    async def get_trades(self, symbol: str, limit: int = 100, **kwargs: Any) -> Result[list[dict[str, Any]]]:
        return Result.fail("Trades not available from MarketWatch")

    async def subscribe(self, symbol: str, callback: Any, **kwargs: Any) -> Result[bool]:
        return Result.fail("Subscriptions not supported")

    async def unsubscribe(self, symbol: str) -> Result[bool]:
        return Result.fail("Subscriptions not supported")

    async def health(self) -> dict[str, Any]:
        result = await self.client.get_stock_data("AAPL")
        return {"healthy": result.success, "message": "ok" if result.success else result.error}
