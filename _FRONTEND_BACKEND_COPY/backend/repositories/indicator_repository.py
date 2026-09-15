from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.result import PaginatedResult, Result
from domain.analytics.indicator import Indicator
from repositories.base_repository import InMemoryRepository


class IndicatorRepository:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._mem: InMemoryRepository[Indicator] | None = InMemoryRepository[Indicator]()

    async def get(self, id: str) -> Result[Indicator]:
        return await self._mem.get(id)

    async def save(self, entity: Indicator) -> Result[Indicator]:
        return await self._mem.save(entity)

    async def delete(self, id: str) -> Result[bool]:
        return await self._mem.delete(id)

    async def list(self, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[Indicator]]:
        return await self._mem.list(page, page_size)

    async def get_by_instrument(
        self, instrument_id: str, name: str = "", timeframe: str = "1d"
    ) -> Result[list[Indicator]]:
        indicators = [
            ind
            for ind in self._mem._store.values()
            if ind.instrument_id == instrument_id and (not name or ind.name == name) and ind.timeframe == timeframe
        ]
        return Result.ok(sorted(indicators, key=lambda i: (i.date, i.time)))
