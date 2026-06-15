from __future__ import annotations

from typing import Any

from core.config import settings
from core.result import Result
from providers.base.http_client import HttpClient


class TsetmcClient(HttpClient):
    def __init__(self) -> None:
        super().__init__(
            base_url=settings.tsetmc_base_url,
            timeout=settings.provider_default_timeout,
        )

    async def get_instruments(self) -> Result[Any]:
        return await self.get("/api/Instrument")

    async def get_quote(self, symbol: str) -> Result[Any]:
        return await self.get(f"/api/Quote/{symbol}")

    async def get_history(self, symbol: str, days: int = 365) -> Result[Any]:
        return await self.get(f"/api/History/{symbol}", params={"days": days})

    async def get_orderbook(self, symbol: str) -> Result[Any]:
        return await self.get(f"/api/OrderBook/{symbol}")

    async def get_trades(self, symbol: str) -> Result[Any]:
        return await self.get(f"/api/Trades/{symbol}")

    async def get_market_watch(self) -> Result[Any]:
        return await self.get("/api/MarketWatch")
