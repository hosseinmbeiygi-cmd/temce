from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.realtime.brokerage.base import BaseBrokerageProvider
from providers.realtime.brokerage.mofid_client import MofidClient

logger = get_logger(__name__)


class MofidProvider(BaseBrokerageProvider):
    def __init__(self, token: str = "") -> None:
        super().__init__(name="mofid", base_url="")
        self.client = MofidClient(token=token)

    async def fetch(self, symbol: str | None = None, **kwargs: Any) -> Result[Any]:
        if symbol:
            return await self.client.get_market_data(symbol)
        return await self.client.get_portfolio()

    async def get_portfolio(self, **kwargs: Any) -> Result[Any]:
        return await self.client.get_portfolio()

    async def get_orders(self, **kwargs: Any) -> Result[Any]:
        return await self.client.get_orders()

    async def place_order(self, order: dict[str, Any], **kwargs: Any) -> Result[Any]:
        return await self.client.place_order(order)

    async def get_balances(self, **kwargs: Any) -> Result[Any]:
        return await self.client.get_balances()

    async def health(self) -> dict[str, Any]:
        result = await self.client.get_market_data("test")
        return {"healthy": result.success, "message": "ok" if result.success else result.error}
