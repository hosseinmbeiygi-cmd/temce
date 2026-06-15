from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.result import Result
from domain.market_data.quote import Quote
from repositories.instrument_repository import InstrumentRepository
from repositories.quote_repository import QuoteRepository

logger = get_logger(__name__)


class MarketService:
    def __init__(
        self,
        quote_repo: QuoteRepository | None = None,
        instrument_repo: InstrumentRepository | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        self.quote_repo = quote_repo or QuoteRepository(session=session)
        self.instrument_repo = instrument_repo or InstrumentRepository(session=session)

    async def get_overview(self) -> Result[dict[str, Any]]:
        return await self.quote_repo.get_market_summary()

    async def get_index_values(self) -> Result[list[dict[str, Any]]]:
        return Result.ok([])

    async def get_top_gainers(self, limit: int = 10) -> Result[list[Quote]]:
        return await self.quote_repo.get_top_gainers(limit)

    async def get_top_losers(self, limit: int = 10) -> Result[list[Quote]]:
        return await self.quote_repo.get_top_losers(limit)

    async def get_most_active(self, limit: int = 10) -> Result[list[Quote]]:
        return await self.quote_repo.get_most_active(limit)

    async def get_sector_summary(self) -> Result[list[dict[str, Any]]]:
        return Result.ok([])

    async def get_historical_quotes(self, symbol: str, start_date: str, end_date: str) -> Result[list[dict[str, Any]]]:
        return Result.ok([])

    async def get_ohlcv(
        self, symbol: str, start_date: str, end_date: str, timeframe: str = "1d"
    ) -> Result[list[dict[str, Any]]]:
        return Result.ok([])

    async def get_market_summary(self) -> Result[dict[str, Any]]:
        return await self.quote_repo.get_market_summary()

    async def calculate_indicator(
        self, symbol: str, indicator: str, params: dict[str, Any] | None = None
    ) -> Result[list[float]]:
        return Result.ok([])

    async def get_macro_data(self, indicator: str, country: str = "iran") -> Result[dict[str, Any]]:
        return Result.ok({"indicator": indicator, "country": country})
