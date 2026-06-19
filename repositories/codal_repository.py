from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.result import PaginatedResult, Result
from domain.codal.disclosure import Disclosure
from repositories.base_repository import InMemoryRepository


class CodalRepository:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._mem: InMemoryRepository[Disclosure] | None = None if session else InMemoryRepository[Disclosure]()

    async def get(self, id: str) -> Result[Disclosure]:
        return await self._mem.get(id)

    async def save(self, entity: Disclosure) -> Result[Disclosure]:
        return await self._mem.save(entity)

    async def delete(self, id: str) -> Result[bool]:
        return await self._mem.delete(id)

    async def list(self, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[Disclosure]]:
        return await self._mem.list(page, page_size)

    async def get_by_instrument(
        self, instrument_id: str, page: int = 1, page_size: int = 50
    ) -> Result[PaginatedResult[Disclosure]]:
        items = [d for d in self._mem._store.values() if d.instrument_id == instrument_id]
        total = len(items)
        start = (page - 1) * page_size
        return Result.ok(
            PaginatedResult(
                items=sorted(items, key=lambda d: d.publish_date or "", reverse=True)[start : start + page_size],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=max(1, (total + page_size - 1) // page_size),
            )
        )
