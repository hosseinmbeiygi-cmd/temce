from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider
from providers.historical.tsetmc_historical.client import TsetmcHistoricalClient
from providers.historical.tsetmc_historical.mapping import TsetmcHistoricalMapping
from providers.historical.tsetmc_historical.parser import TsetmcHistoricalParser

logger = get_logger(__name__)


class TsetmcHistoricalProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="tsetmc_historical")
        self.client = TsetmcHistoricalClient()
        self.parser = TsetmcHistoricalParser()
        self.mapping = TsetmcHistoricalMapping()

    async def fetch(self, symbol: str | None = None, **kwargs: Any) -> Result[Any]:
        if not symbol:
            return Result.fail("symbol is required")
        ins_code = kwargs.get("ins_code", symbol)
        days = kwargs.get("days", 365)
        result = await self.client.get_instrument_history(ins_code, days)
        if not result.success:
            return result
        data = self.parser.parse(result.value.json() if hasattr(result.value, "json") else result.value)
        mapped = self.mapping.map_batch(data)
        return Result.ok(mapped)

    async def health(self) -> dict[str, Any]:
        result = await self.client.get_instrument_history("test", 1)
        return {"healthy": result.success, "message": "ok" if result.success else result.error}
