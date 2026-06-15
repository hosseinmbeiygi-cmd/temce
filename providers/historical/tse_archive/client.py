from __future__ import annotations

from typing import Any

from core.config import settings
from core.result import Result
from providers.base.http_client import HttpClient

TSE_ARCHIVE_BASE = "https://old.tsetmc.com/tsev2"


class TseArchiveClient(HttpClient):
    def __init__(self) -> None:
        super().__init__(
            base_url=TSE_ARCHIVE_BASE,
            timeout=settings.provider_default_timeout,
        )

    async def get_ticker_data(self, ticker_id: str, year: int) -> Result[Any]:
        return await self.get("/data/TickerData.aspx", params={"ticker": ticker_id, "year": year})

    async def get_price_history(self, ticker_id: str, days: int = 365) -> Result[Any]:
        return await self.get("/data/PriceHistory.aspx", params={"ticker": ticker_id, "days": days})

    async def get_shareholder_data(self, ticker_id: str) -> Result[Any]:
        return await self.get("/data/Shareholder.aspx", params={"ticker": ticker_id})

    async def get_corporate_events(self, ticker_id: str) -> Result[Any]:
        return await self.get("/data/CorporateEvents.aspx", params={"ticker": ticker_id})
