from __future__ import annotations

from typing import Any

from core.result import Result
from providers.base.http_client import HttpClient

AGAH_BASE_URL = "https://api.agah.com/v1"


class AgahClient(HttpClient):
    def __init__(self, api_key: str = "") -> None:
        super().__init__(base_url=AGAH_BASE_URL)
        self._api_key = api_key

    async def get_quotes(self, symbols: list[str]) -> Result[Any]:
        return await self.get("/quotes", params={"symbols": ",".join(symbols)})

    async def get_orderbook(self, symbol: str) -> Result[Any]:
        return await self.get(f"/orderbook/{symbol}")

    async def get_trades(self, symbol: str) -> Result[Any]:
        return await self.get(f"/trades/{symbol}")

    async def get_portfolio(self) -> Result[Any]:
        return await self.get("/portfolio")

    async def get_orders(self) -> Result[Any]:
        return await self.get("/orders")

    async def place_order(self, order: dict[str, Any]) -> Result[Any]:
        return await self.post("/orders", json=order)

    async def get_balances(self) -> Result[Any]:
        return await self.get("/balances")
