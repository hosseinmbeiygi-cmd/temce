from __future__ import annotations

from typing import Any

from core.result import Result
from providers.base.http_client import HttpClient

MARKETWATCH_BASE = "https://www.marketwatch.com/investing"


class MarketWatchClient(HttpClient):
    def __init__(self) -> None:
        super().__init__(base_url=MARKETWATCH_BASE, timeout=15)
        self._headers.update({"User-Agent": "Mozilla/5.0"})

    async def get_stock_data(self, symbol: str) -> Result[Any]:
        return await self.get(f"/stock/{symbol}")

    async def get_index_data(self, index: str) -> Result[Any]:
        return await self.get(f"/index/{index}")

    async def get_commodity_data(self, symbol: str) -> Result[Any]:
        return await self.get(f"/future/{symbol}")

    async def get_currency_data(self, pair: str) -> Result[Any]:
        return await self.get(f"/currency/{pair}")
