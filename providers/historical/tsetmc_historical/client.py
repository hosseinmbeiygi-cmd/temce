from __future__ import annotations

from typing import Any

from core.config import settings
from core.result import Result
from providers.base.http_client import HttpClient


class TsetmcHistoricalClient(HttpClient):
    def __init__(self) -> None:
        super().__init__(
            base_url=settings.tsetmc_base_url,
            timeout=settings.provider_default_timeout,
        )

    async def get_instrument_history(self, ins_code: str, days: int = 365) -> Result[Any]:
        return await self.get("/api/InstrumentHistory", params={"insCode": ins_code, "days": days})

    async def get_daily_data(self, ins_code: str, date: str) -> Result[Any]:
        return await self.get("/api/DailyData", params={"insCode": ins_code, "date": date})

    async def get_closing_prices(self, ins_code: str, days: int = 365) -> Result[Any]:
        return await self.get("/api/ClosingPrices", params={"insCode": ins_code, "days": days})

    async def get_adjusted_prices(self, ins_code: str) -> Result[Any]:
        return await self.get("/api/AdjustedPrices", params={"insCode": ins_code})
