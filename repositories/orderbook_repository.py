from __future__ import annotations

import json

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.result import PaginatedResult, Result
from domain.orderbook.entities import OrderBookSnapshot
from models.orderbook import OrderbookModel
from repositories.base_repository import InMemoryRepository
from repositories.db_base import DbRepository


class OrderBookRepository:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session
        self._mem: InMemoryRepository[OrderBookSnapshot] | None = None if session else InMemoryRepository[OrderBookSnapshot]()
        self._db: _OrderBookDbRepo | None = None if not session else _OrderBookDbRepo(session)

    async def get(self, id: str) -> Result[OrderBookSnapshot]:
        if self._db:
            return await self._db.get(id)
        return await self._mem.get(id)

    async def save(self, entity: OrderBookSnapshot) -> Result[OrderBookSnapshot]:
        if self._db:
            return await self._db.save(entity)
        return await self._mem.save(entity)

    async def delete(self, id: str) -> Result[bool]:
        if self._db:
            return await self._db.delete(id)
        return await self._mem.delete(id)

    async def list(self, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[OrderBookSnapshot]]:
        if self._db:
            return await self._db.list(page, page_size)
        return await self._mem.list(page, page_size)

    async def get_by_instrument(self, instrument_id: str) -> Result[list[OrderBookSnapshot]]:
        if self._db:
            return await self._db.get_by_instrument(instrument_id)
        matches = [o for o in self._mem._store.values() if o.instrument_id == instrument_id]
        return Result.ok(matches)

    async def get_latest(self, instrument_id: str) -> Result[OrderBookSnapshot]:
        if self._db:
            return await self._db.get_latest(instrument_id)
        matches = [o for o in self._mem._store.values() if o.instrument_id == instrument_id]
        if not matches:
            return Result.fail(f"No orderbook for {instrument_id}")
        return Result.ok(sorted(matches, key=lambda o: (o.date or "", o.time or ""), reverse=True)[0])

    async def count(self) -> int:
        if self._db:
            return await self._db.count()
        return len(self._mem._store)


class _OrderBookDbRepo(DbRepository[OrderBookSnapshot, OrderbookModel]):
    model_class = OrderbookModel

    async def get_by_instrument(self, instrument_id: str) -> Result[list[OrderBookSnapshot]]:
        stmt = select(OrderbookModel).where(OrderbookModel.instrument_id == instrument_id).order_by(desc(OrderbookModel.date), desc(OrderbookModel.time))
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok([self._to_domain(r) for r in rows])

    async def get_latest(self, instrument_id: str) -> Result[OrderBookSnapshot]:
        stmt = (
            select(OrderbookModel)
            .where(OrderbookModel.instrument_id == instrument_id)
            .order_by(desc(OrderbookModel.date), desc(OrderbookModel.time))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return Result.fail(f"No orderbook for {instrument_id}")
        return Result.ok(self._to_domain(row))

    async def count(self) -> int:
        from sqlalchemy import func as sa_func

        stmt = select(sa_func.count()).select_from(OrderbookModel)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    def _to_domain(self, orm: OrderbookModel) -> OrderBookSnapshot:
        bids = []
        if orm.bids:
            try:
                bids = json.loads(orm.bids)
            except (json.JSONDecodeError, TypeError):
                pass
        asks = []
        if orm.asks:
            try:
                asks = json.loads(orm.asks)
            except (json.JSONDecodeError, TypeError):
                pass
        return OrderBookSnapshot(
            id=orm.id,
            instrument_id=orm.instrument_id,
            symbol=orm.symbol or "",
            bids=bids,
            asks=asks,
            time=orm.time or "",
            date=orm.date or "",
            created_at=orm.created_at,
        )

    def _to_orm(self, domain: OrderBookSnapshot) -> OrderbookModel:
        return OrderbookModel(
            id=domain.id,
            instrument_id=domain.instrument_id,
            symbol=domain.symbol or None,
            bids=json.dumps(domain.bids, ensure_ascii=False) if domain.bids else None,
            asks=json.dumps(domain.asks, ensure_ascii=False) if domain.asks else None,
            time=domain.time or None,
            date=domain.date or None,
            data_source="tsetmc",
            created_at=domain.created_at,
        )
