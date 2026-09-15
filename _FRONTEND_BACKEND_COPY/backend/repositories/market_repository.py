from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.result import PaginatedResult, Result
from domain.common.base_entity import BaseEntity
from models.market import MarketModel
from repositories.base_repository import InMemoryRepository
from repositories.db_base import DbRepository


class Market(BaseEntity):
    def __init__(
        self,
        id: str,
        name: str,
        market_type: str = "",
        exchange_code: str = "",
        country: str = "IR",
        timezone: str = "Asia/Tehran",
        open_time: str = "09:00",
        close_time: str = "12:30",
        status: str = "active",
        description: str = "",
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.market_type = market_type
        self.exchange_code = exchange_code
        self.country = country
        self.timezone = timezone
        self.open_time = open_time
        self.close_time = close_time
        self.status = status
        self.description = description


class MarketRepository:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session
        self._mem: InMemoryRepository[Market] | None = None if session else InMemoryRepository[Market]()
        self._db: _MarketDbRepo | None = None if not session else _MarketDbRepo(session)

    async def get(self, id: str) -> Result[Market]:
        if self._db:
            return await self._db.get(id)
        return await self._mem.get(id)

    async def save(self, entity: Market) -> Result[Market]:
        if self._db:
            return await self._db.save(entity)
        return await self._mem.save(entity)

    async def delete(self, id: str) -> Result[bool]:
        if self._db:
            return await self._db.delete(id)
        return await self._mem.delete(id)

    async def list(self, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[Market]]:
        if self._db:
            return await self._db.list(page, page_size)
        return await self._mem.list(page, page_size)

    async def get_by_type(self, market_type: str) -> Result[list[Market]]:
        if self._db:
            return await self._db.get_by_type(market_type)
        matches = [m for m in self._mem._store.values() if m.market_type == market_type]
        return Result.ok(matches)

    async def get_by_exchange(self, exchange_code: str) -> Result[list[Market]]:
        if self._db:
            return await self._db.get_by_exchange(exchange_code)
        matches = [m for m in self._mem._store.values() if m.exchange_code == exchange_code]
        return Result.ok(matches)

    async def count(self) -> int:
        if self._db:
            return await self._db.count()
        return len(self._mem._store)


class _MarketDbRepo(DbRepository[Market, MarketModel]):
    model_class = MarketModel

    async def get_by_type(self, market_type: str) -> Result[list[Market]]:
        stmt = select(MarketModel).where(MarketModel.market_type == market_type)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok([self._to_domain(r) for r in rows])

    async def get_by_exchange(self, exchange_code: str) -> Result[list[Market]]:
        stmt = select(MarketModel).where(MarketModel.exchange_code == exchange_code)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok([self._to_domain(r) for r in rows])

    async def count(self) -> int:
        from sqlalchemy import func as sa_func

        stmt = select(sa_func.count()).select_from(MarketModel)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    def _to_domain(self, orm: MarketModel) -> Market:
        return Market(
            id=orm.id,
            name=orm.name,
            market_type=orm.market_type or "",
            exchange_code=orm.exchange_code or "",
            country=orm.country or "IR",
            timezone=orm.timezone or "Asia/Tehran",
            open_time=orm.open_time or "09:00",
            close_time=orm.close_time or "12:30",
            status=orm.status or "active",
            description=orm.description or "",
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    def _to_orm(self, domain: Market) -> MarketModel:
        return MarketModel(
            id=domain.id,
            name=domain.name,
            market_type=domain.market_type or None,
            exchange_code=domain.exchange_code or None,
            country=domain.country or "IR",
            timezone=domain.timezone or "Asia/Tehran",
            open_time=domain.open_time or "09:00",
            close_time=domain.close_time or "12:30",
            status=domain.status or "active",
            description=domain.description or None,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
        )
