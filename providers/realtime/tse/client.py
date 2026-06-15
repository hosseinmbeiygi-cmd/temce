from __future__ import annotations

from typing import Any

from core.config import settings
from core.result import Result
from providers.base.http_client import HttpClient

TSE_REALTIME_BASE = "https://tse.ir/json"


class TseRealtimeClient(HttpClient):
    def __init__(self) -> None:
        super().__init__(base_url=TSE_REALTIME_BASE, timeout=settings.provider_default_timeout)

    async def get_market_overview(self) -> Result[Any]:
        return await self.get("/marketOverview")

    async def get_index_data(self) -> Result[Any]:
        return await self.get("/index")

    async def get_symbol_data(self, symbol: str) -> Result[Any]:
        return await self.get(f"/symbol/{symbol}")

    async def get_orderbook(self, symbol: str) -> Result[Any]:
        return await self.get(f"/orderbook/{symbol}")

    async def get_trades(self, symbol: str) -> Result[Any]:
        return await self.get(f"/trades/{symbol}")

    async def get_market_map(self) -> Result[Any]:
        return await self.get("/marketMap")
