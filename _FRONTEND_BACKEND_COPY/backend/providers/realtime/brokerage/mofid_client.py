from __future__ import annotations

from typing import Any

from core.result import Result
from providers.base.http_client import HttpClient

MOFID_BASE_URL = "https://api.mofidonline.com/v1"


class MofidClient(HttpClient):
    def __init__(self, token: str = "") -> None:
        super().__init__(base_url=MOFID_BASE_URL)
        self._token = token

    async def get_market_data(self, symbol: str) -> Result[Any]:
        return await self.get(f"/marketdata/{symbol}")

    async def get_orderbook(self, symbol: str) -> Result[Any]:
        return await self.get(f"/orderbook/{symbol}")

    async def get_portfolio(self) -> Result[Any]:
        return await self.get("/portfolio")

    async def get_orders(self) -> Result[Any]:
        return await self.get("/orders")

    async def place_order(self, order: dict[str, Any]) -> Result[Any]:
        return await self.post("/orders", json=order)

    async def get_balances(self) -> Result[Any]:
        return await self.get("/balances")

    async def get_trades(self, symbol: str) -> Result[Any]:
        return await self.get(f"/trades/{symbol}")
