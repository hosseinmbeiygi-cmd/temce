from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.result import PaginatedResult, Result
from domain.common.base_entity import BaseEntity
from models.trade import TradeModel
from repositories.base_repository import InMemoryRepository
from repositories.db_base import DbRepository


class Trade(BaseEntity):
    def __init__(
        self,
        id: str,
        instrument_id: str,
        symbol: str = "",
        price: float = 0.0,
        volume: int = 0,
        value: float = 0.0,
        side: str = "",
        time: str = "",
        date: str = "",
        data_source: str = "tsetmc",
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.symbol = symbol
        self.price = price
        self.volume = volume
        self.value = value
        self.side = side
        self.time = time
        self.date = date
        self.data_source = data_source


class TradeRepository:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session
        self._mem: InMemoryRepository[Trade] | None = None if session else InMemoryRepository[Trade]()
        self._db: _TradeDbRepo | None = None if not session else _TradeDbRepo(session)

    async def get(self, id: str) -> Result[Trade]:
        if self._db:
            return await self._db.get(id)
        return await self._mem.get(id)

    async def save(self, entity: Trade) -> Result[Trade]:
        if self._db:
            return await self._db.save(entity)
        return await self._mem.save(entity)

    async def delete(self, id: str) -> Result[bool]:
        if self._db:
            return await self._db.delete(id)
        return await self._mem.delete(id)

    async def list(self, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[Trade]]:
        if self._db:
            return await self._db.list(page, page_size)
        return await self._mem.list(page, page_size)

    async def get_by_instrument(self, instrument_id: str, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[Trade]]:
        if self._db:
            return await self._db.get_by_instrument(instrument_id, page, page_size)
        matches = [t for t in self._mem._store.values() if t.instrument_id == instrument_id]
        total = len(matches)
        start = (page - 1) * page_size
        return Result.ok(
            PaginatedResult(
                items=sorted(matches, key=lambda t: t.date or "", reverse=True)[start : start + page_size],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=max(1, (total + page_size - 1) // page_size),
            )
        )

    async def get_by_date_range(self, start_date: str, end_date: str, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[Trade]]:
        if self._db:
            return await self._db.get_by_date_range(start_date, end_date, page, page_size)
        matches = [t for t in self._mem._store.values() if t.date and start_date <= t.date <= end_date]
        total = len(matches)
        start = (page - 1) * page_size
        return Result.ok(
            PaginatedResult(
                items=sorted(matches, key=lambda t: t.date or "", reverse=True)[start : start + page_size],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=max(1, (total + page_size - 1) // page_size),
            )
        )

    async def get_by_symbol(self, symbol: str, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[Trade]]:
        if self._db:
            return await self._db.get_by_symbol(symbol, page, page_size)
        matches = [t for t in self._mem._store.values() if t.symbol == symbol]
        total = len(matches)
        start = (page - 1) * page_size
        return Result.ok(
            PaginatedResult(
                items=sorted(matches, key=lambda t: t.date or "", reverse=True)[start : start + page_size],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=max(1, (total + page_size - 1) // page_size),
            )
        )

    async def count(self) -> int:
        if self._db:
            return await self._db.count()
        return len(self._mem._store)


class _TradeDbRepo(DbRepository[Trade, TradeModel]):
    model_class = TradeModel

    async def get_by_instrument(self, instrument_id: str, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[Trade]]:
        from sqlalchemy import func as sa_func

        count_stmt = select(sa_func.count()).select_from(TradeModel).where(TradeModel.instrument_id == instrument_id)
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = (
            select(TradeModel)
            .where(TradeModel.instrument_id == instrument_id)
            .order_by(desc(TradeModel.date))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
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

    async def get_by_date_range(self, start_date: str, end_date: str, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[Trade]]:
        from sqlalchemy import func as sa_func

        count_stmt = (
            select(sa_func.count()).select_from(TradeModel).where(TradeModel.date >= start_date, TradeModel.date <= end_date)
        )
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = (
            select(TradeModel)
            .where(TradeModel.date >= start_date, TradeModel.date <= end_date)
            .order_by(desc(TradeModel.date))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
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

    async def get_by_symbol(self, symbol: str, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[Trade]]:
        from sqlalchemy import func as sa_func

        count_stmt = select(sa_func.count()).select_from(TradeModel).where(TradeModel.symbol == symbol)
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = (
            select(TradeModel)
            .where(TradeModel.symbol == symbol)
            .order_by(desc(TradeModel.date))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
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

    async def count(self) -> int:
        from sqlalchemy import func as sa_func

        stmt = select(sa_func.count()).select_from(TradeModel)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    def _to_domain(self, orm: TradeModel) -> Trade:
        return Trade(
            id=orm.id,
            instrument_id=orm.instrument_id,
            symbol=orm.symbol or "",
            price=orm.price or 0.0,
            volume=orm.volume or 0,
            value=orm.value or 0.0,
            side=orm.side or "",
            time=orm.time or "",
            date=orm.date or "",
            data_source=orm.data_source or "tsetmc",
            created_at=orm.created_at,
        )

    def _to_orm(self, domain: Trade) -> TradeModel:
        return TradeModel(
            id=domain.id,
            instrument_id=domain.instrument_id,
            symbol=domain.symbol or None,
            price=domain.price or None,
            volume=domain.volume or None,
            value=domain.value or None,
            side=domain.side or None,
            time=domain.time or None,
            date=domain.date or None,
            data_source=domain.data_source or "tsetmc",
            created_at=domain.created_at,
        )
