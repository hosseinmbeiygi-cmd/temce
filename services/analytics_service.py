from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import new_id
from core.logging import get_logger
from core.result import Result
from domain.analytics.indicator import Indicator
from repositories.indicator_repository import IndicatorRepository

logger = get_logger(__name__)


class AnalyticsService:
    def __init__(self, indicator_repo: IndicatorRepository | None = None, session: AsyncSession | None = None) -> None:
        self.indicator_repo = indicator_repo or IndicatorRepository(session=session)

    async def create(self, instrument_id: str, name: str, **kwargs: Any) -> Result[Indicator]:
        indicator = Indicator(id=new_id("ind"), instrument_id=instrument_id, name=name, **kwargs)
        return await self.indicator_repo.save(indicator)

    async def compute_indicator(
        self, instrument_id: str, name: str, params: dict[str, Any] | None = None
    ) -> Result[Indicator]:
        return Result.fail("Not implemented")

    async def get_indicator(self, instrument_id: str, name: str, timeframe: str = "1d") -> Result[list[Indicator]]:
        return await self.indicator_repo.get_by_instrument(instrument_id, name, timeframe)

    async def save_indicator(self, indicator: Indicator) -> Result[Indicator]:
        return await self.indicator_repo.save(indicator)

    async def batch_save(self, indicators: list[Indicator]) -> Result[int]:
        count = 0
        for ind in indicators:
            r = await self.indicator_repo.save(ind)
            if r.success:
                count += 1
        return Result.ok(count)
