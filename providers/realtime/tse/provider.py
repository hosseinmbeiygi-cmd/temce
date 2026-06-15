from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.realtime import RealtimeDataProvider
from providers.realtime.tse.client import TseRealtimeClient
from providers.realtime.tse.mapping import TseRealtimeMapping
from providers.realtime.tse.parser import TseRealtimeParser

logger = get_logger(__name__)


class TseRealtimeProvider(RealtimeDataProvider):
    def __init__(self) -> None:
        super().__init__(name="tse_realtime")
        self.client = TseRealtimeClient()
        self.parser = TseRealtimeParser()
        self.mapping = TseRealtimeMapping()

    async def fetch(self, symbol: str | None = None, **kwargs: Any) -> Result[Any]:
        if symbol:
            result = await self.client.get_symbol_data(symbol)
        else:
            result = await self.client.get_market_overview()
        if not result.success:
            return result
        raw = result.value.json() if hasattr(result.value, "json") else result.value
        parsed = self.parser.parse(raw)
        mapped = self.mapping.map(parsed)
        return Result.ok(mapped)

    async def get_quote(self, symbol: str, **kwargs: Any) -> Result[dict[str, Any]]:
        return await self.fetch(symbol)

    async def get_orderbook(self, symbol: str, **kwargs: Any) -> Result[dict[str, Any]]:
        result = await self.client.get_orderbook(symbol)
        if result.success:
            raw = result.value.json() if hasattr(result.value, "json") else result.value
            return Result.ok(raw)
        return result

    async def get_trades(self, symbol: str, limit: int = 100, **kwargs: Any) -> Result[list[dict[str, Any]]]:
        result = await self.client.get_trades(symbol)
        if result.success:
            raw = result.value.json() if hasattr(result.value, "json") else result.value
            data = raw if isinstance(raw, list) else raw.get("trades", [])
            return Result.ok(data[:limit])
        return Result.fail(result.error or "Unknown error")

    async def subscribe(self, symbol: str, callback: Any, **kwargs: Any) -> Result[bool]:
        return Result.fail("Subscriptions not supported via HTTP")

    async def unsubscribe(self, symbol: str) -> Result[bool]:
        return Result.fail("Subscriptions not supported via HTTP")

    async def health(self) -> dict[str, Any]:
        result = await self.client.get_market_overview()
        return {"healthy": result.success, "message": "ok" if result.success else result.error}
