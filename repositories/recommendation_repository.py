from sqlalchemy.ext.asyncio import AsyncSession

from core.result import Result
from domain.analytics.recommendation import Recommendation
from repositories.base_repository import InMemoryRepository


class RecommendationRepository:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._mem: InMemoryRepository[Recommendation] | None = InMemoryRepository[Recommendation]()

    async def get(self, id: str) -> Result[Recommendation]:
        return await self._mem.get(id)

    async def save(self, entity: Recommendation) -> Result[Recommendation]:
        return await self._mem.save(entity)

    async def delete(self, id: str) -> Result[bool]:
        return await self._mem.delete(id)

    async def list(self, page: int = 1, page_size: int = 100) -> Result[Result]:
        return await self._mem.list(page, page_size)

    async def get_active(self, instrument_id: str) -> Result[list[Recommendation]]:
        recs = [r for r in self._mem._store.values() if r.instrument_id == instrument_id]
        return Result.ok(recs)
