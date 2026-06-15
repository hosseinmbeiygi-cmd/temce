from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider
from providers.realtime.tsetmc.client import TsetmcClient

logger = get_logger(__name__)


class TsetmcQuotesProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="tsetmc_quotes")
        self.client = TsetmcClient()

    async def fetch(self, symbol: str | None = None, **kwargs: Any) -> Result[Any]:
        if symbol:
            return await self.client.get_quote(symbol)
        return await self.client.get_market_watch()

    async def health(self) -> dict[str, Any]:
        result = await self.client.get_instruments()
        return {"healthy": result.success, "message": "ok" if result.success else result.error}
