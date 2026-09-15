from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.realtime import RealtimeDataProvider
from providers.realtime.tsetmc.client import TsetmcClient
from providers.realtime.tsetmc.mapping import TsetmcMapping
from providers.realtime.tsetmc.parser import TsetmcParser

logger = get_logger(__name__)


class TsetmcRealtimeProvider(RealtimeDataProvider):
    def __init__(self) -> None:
        super().__init__(name="tsetmc_realtime")
        self.client = TsetmcClient()
        self.parser = TsetmcParser()
        self.mapping = TsetmcMapping()

    async def fetch(self, symbol: str | None = None, **kwargs: Any) -> Result[Any]:
        if symbol:
            result = await self.client.get_quote(symbol)
        else:
            result = await self.client.get_market_watch()
        if not result.success:
            return result
        raw = result.value.json() if hasattr(result.value, "json") else result.value
        parsed = self.parser.parse(raw)
        mapped = self.mapping.map_quote(parsed)
        return Result.ok(mapped)

    async def get_quote(self, symbol: str, **kwargs: Any) -> Result[dict[str, Any]]:
        return await self.fetch(symbol)

    async def get_orderbook(self, symbol: str, **kwargs: Any) -> Result[dict[str, Any]]:
        result = await self.client.get_orderbook(symbol)
        if result.success:
            raw = result.value.json() if hasattr(result.value, "json") else result.value
            mapped = self.mapping.map_orderbook(raw if isinstance(raw, dict) else {})
            return Result.ok(mapped)
        return result

    async def get_trades(self, symbol: str, limit: int = 100, **kwargs: Any) -> Result[list[dict[str, Any]]]:
        result = await self.client.get_trades(symbol)
        if result.success:
            raw = result.value.json() if hasattr(result.value, "json") else result.value
            trades = raw if isinstance(raw, list) else raw.get("trades", [])
            return Result.ok(trades[:limit])
        return Result.fail(result.error or "Unknown error")

    async def subscribe(self, symbol: str, callback: Any, **kwargs: Any) -> Result[bool]:
        return Result.fail("Use WebSocket provider for subscriptions")

    async def unsubscribe(self, symbol: str) -> Result[bool]:
        return Result.fail("Use WebSocket provider for subscriptions")

    async def health(self) -> dict[str, Any]:
        result = await self.client.get_instruments()
        return {"healthy": result.success, "message": "ok" if result.success else result.error}
