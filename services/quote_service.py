from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import new_id
from core.logging import get_logger
from core.result import Result
from domain.market_data.quote import Quote
from repositories.quote_repository import QuoteRepository

logger = get_logger(__name__)


class QuoteService:
    def __init__(self, quote_repo: QuoteRepository | None = None, session: AsyncSession | None = None) -> None:
        if quote_repo is None:
            quote_repo = QuoteRepository(session=session)
        self.quote_repo = quote_repo

    async def get_latest(self, instrument_id: str) -> Result[Quote]:
        return await self.quote_repo.get_latest(instrument_id)

    async def get_history(
        self, instrument_id: str, start_date: date, end_date: date, timeframe: str = "1d"
    ) -> Result[list[Quote]]:
        return await self.quote_repo.get_range(instrument_id, start_date, end_date, timeframe)

    async def create(self, instrument_id: str, **kwargs: Any) -> Result[Quote]:
        quote = Quote(id=new_id("q"), instrument_id=instrument_id, **kwargs)
        return await self.quote_repo.save(quote)

    async def save_quote(self, quote: Quote) -> Result[Quote]:
        return await self.quote_repo.save(quote)

    async def save_quotes(self, quotes: list[Quote]) -> Result[int]:
        count = 0
        for q in quotes:
            r = await self.quote_repo.save(q)
            if r.success:
                count += 1
        return Result.ok(count)

    async def get_market_summary(self) -> Result[dict[str, Any]]:
        return await self.quote_repo.get_market_summary()
