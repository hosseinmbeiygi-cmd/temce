from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import new_id
from core.logging import get_logger
from core.result import PaginatedResult, Result

TDomain = TypeVar("TDomain")
TModel = TypeVar("TModel")

logger = get_logger(__name__)


class DbRepository(Generic[TDomain, TModel]):
    model_class: type[TModel] = None  # type: ignore

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id: str) -> Result[TDomain]:
        stmt = select(self.model_class).where(self.model_class.id == id)  # type: ignore
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return Result.fail(f"{self.model_class.__name__} {id} not found")
        return Result.ok(self._to_domain(row))

    async def save(self, entity: TDomain) -> Result[TDomain]:
        orm = self._to_orm(entity)
        self.session.add(orm)
        await self.session.flush()
        return Result.ok(self._to_domain(orm))

    async def delete(self, id: str) -> Result[bool]:
        stmt = select(self.model_class).where(self.model_class.id == id)  # type: ignore
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return Result.fail(f"{self.model_class.__name__} {id} not found")
        await self.session.delete(row)
        return Result.ok(True)

    async def list(self, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[TDomain]]:
        count_stmt = select(sa_func.count()).select_from(self.model_class)  # type: ignore
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = select(self.model_class).offset((page - 1) * page_size).limit(page_size)  # type: ignore
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok(
            PaginatedResult(
                items=[self._to_domain(r) for r in rows],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=max(1, (total + page_size - 1) // page_size),
            )
        )

    async def exists(self, id: str) -> bool:
        result = await self.get(id)
        return result.success

    def _to_domain(self, orm: TModel) -> TDomain:
        raise NotImplementedError

    def _to_orm(self, domain: TDomain) -> TModel:
        raise NotImplementedError

    @staticmethod
    def _new_id(prefix: str = "") -> str:
        return new_id(prefix)
