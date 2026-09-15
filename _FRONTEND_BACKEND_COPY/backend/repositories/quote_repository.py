from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.result import Result
from domain.market_data.quote import Quote
from models.quote import QuoteModel
from repositories.base_repository import InMemoryRepository
from repositories.db_base import DbRepository


class QuoteRepository:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session
        self._mem: InMemoryRepository[Quote] | None = None if session else InMemoryRepository[Quote]()
        self._db: _QuoteDbRepo | None = None if not session else _QuoteDbRepo(session)

    async def get(self, id: str) -> Result[Quote]:
        if self._db:
            return await self._db.get(id)
        return await self._mem.get(id)

    async def save(self, entity: Quote) -> Result[Quote]:
        if self._db:
            return await self._db.save(entity)
        return await self._mem.save(entity)

    async def delete(self, id: str) -> Result[bool]:
        if self._db:
            return await self._db.delete(id)
        return await self._mem.delete(id)

    async def get_all(self) -> Result[list[Quote]]:
        if self._db:
            stmt = select(QuoteModel)
            result = await self._session.execute(stmt)
            rows = result.scalars().all()
            return Result.ok([self._db._to_domain(r) for r in rows])
        return Result.ok(list(self._mem._store.values()))

    async def get_latest(self, instrument_id: str) -> Result[Quote]:
        if self._db:
            return await self._db.get_latest(instrument_id)
        quotes = [q for q in self._mem._store.values() if q.instrument_id == instrument_id]
        if not quotes:
            return Result.fail(f"No quotes for {instrument_id}")
        sorted_q = sorted(quotes, key=lambda q: (q.date, q.time), reverse=True)
        return Result.ok(sorted_q[0])

    async def get_range(
        self, instrument_id: str, start_date: date, end_date: date, timeframe: str = "1d"
    ) -> Result[list[Quote]]:
        if self._db:
            return await self._db.get_range(instrument_id, start_date, end_date, timeframe)
        quotes = [
            q
            for q in self._mem._store.values()
            if q.instrument_id == instrument_id and q.date >= start_date.isoformat() and q.date <= end_date.isoformat()
        ]
        return Result.ok(sorted(quotes, key=lambda q: (q.date, q.time)))

    async def get_by_instrument(self, instrument_id: str) -> Result[list[Quote]]:
        """Get all quotes for a given instrument (used for upsert matching)."""
        if self._db:
            return await self._db.get_by_instrument(instrument_id)
        quotes = [q for q in self._mem._store.values() if q.instrument_id == instrument_id]
        return Result.ok(quotes)

    async def get_by_date(self, instrument_id: str, date_str: str) -> Result[Quote | None]:
        """Find a single quote by instrument + exact date."""
        if self._db:
            return await self._db.get_by_date(instrument_id, date_str)
        for q in self._mem._store.values():
            if q.instrument_id == instrument_id and q.date == date_str:
                return Result.ok(q)
        return Result.ok(None)

    async def get_market_summary(self) -> Result[dict[str, Any]]:
        if self._db:
            return await self._db.get_market_summary()
        return Result.ok(
            {
                "total_instruments": len({q.instrument_id for q in self._mem._store.values()}),
                "total_quotes": len(self._mem._store),
            }
        )

    async def get_top_gainers(self, limit: int = 10) -> Result[list[Quote]]:
        if self._db:
            return await self._db.get_top_gainers(limit)
        sorted_q = sorted(self._mem._store.values(), key=lambda q: q.price_change_pct, reverse=True)
        return Result.ok(sorted_q[:limit])

    async def get_top_losers(self, limit: int = 10) -> Result[list[Quote]]:
        if self._db:
            return await self._db.get_top_losers(limit)
        sorted_q = sorted(self._mem._store.values(), key=lambda q: q.price_change_pct)
        return Result.ok(sorted_q[:limit])

    async def get_most_active(self, limit: int = 10) -> Result[list[Quote]]:
        if self._db:
            return await self._db.get_most_active(limit)
        sorted_q = sorted(self._mem._store.values(), key=lambda q: q.value, reverse=True)
        return Result.ok(sorted_q[:limit])

    async def list(self, page: int = 1, page_size: int = 100) -> Result[Any]:
        if self._db:
            return await self._db.list(page, page_size)
        return await self._mem.list(page, page_size)


class _QuoteDbRepo(DbRepository[Quote, QuoteModel]):
    model_class = QuoteModel

    async def get_latest(self, instrument_id: str) -> Result[Quote]:
        stmt = (
            select(QuoteModel)
            .where(QuoteModel.instrument_id == instrument_id)
            .order_by(desc(QuoteModel.date), desc(QuoteModel.time))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return Result.fail(f"No quotes for {instrument_id}")
        return Result.ok(self._to_domain(row))

    async def get_range(
        self, instrument_id: str, start_date: date, end_date: date, timeframe: str = "1d"
    ) -> Result[list[Quote]]:
        stmt = (
            select(QuoteModel)
            .where(
                QuoteModel.instrument_id == instrument_id,
                QuoteModel.date >= start_date.isoformat(),
                QuoteModel.date <= end_date.isoformat(),
            )
            .order_by(QuoteModel.date, QuoteModel.time)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok([self._to_domain(r) for r in rows])

    async def get_by_instrument(self, instrument_id: str) -> Result[list[Quote]]:
        stmt = select(QuoteModel).where(QuoteModel.instrument_id == instrument_id)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok([self._to_domain(r) for r in rows])

    async def get_by_date(self, instrument_id: str, date_str: str) -> Result[Quote | None]:
        stmt = select(QuoteModel).where(QuoteModel.instrument_id == instrument_id, QuoteModel.date == date_str).limit(1)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return Result.ok(None)
        return Result.ok(self._to_domain(row))

    async def get_market_summary(self) -> Result[dict[str, Any]]:
        from sqlalchemy import func as sa_func
        from sqlalchemy import select

        total_inst_stmt = select(sa_func.count(QuoteModel.instrument_id.distinct())).select_from(QuoteModel)
        total_inst = await self.session.execute(total_inst_stmt)
        total_q_stmt = select(sa_func.count()).select_from(QuoteModel)
        total_q = await self.session.execute(total_q_stmt)
        return Result.ok(
            {
                "total_instruments": total_inst.scalar() or 0,
                "total_quotes": total_q.scalar() or 0,
            }
        )

    async def get_top_gainers(self, limit: int = 10) -> Result[list[Quote]]:
        stmt = select(QuoteModel).order_by(QuoteModel.price_change_pct.desc().nullslast()).limit(limit)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok([self._to_domain(r) for r in rows])

    async def get_top_losers(self, limit: int = 10) -> Result[list[Quote]]:
        stmt = select(QuoteModel).order_by(QuoteModel.price_change_pct.asc().nullslast()).limit(limit)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok([self._to_domain(r) for r in rows])

    async def get_most_active(self, limit: int = 10) -> Result[list[Quote]]:
        stmt = select(QuoteModel).order_by(QuoteModel.value.desc().nullslast()).limit(limit)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok([self._to_domain(r) for r in rows])

    def _to_domain(self, orm: QuoteModel) -> Quote:
        return Quote(
            id=orm.id,
            instrument_id=orm.instrument_id,
            symbol=orm.symbol or "",
            price_close=orm.price_close or 0.0,
            price_open=orm.price_open or 0.0,
            price_high=orm.price_high or 0.0,
            price_low=orm.price_low or 0.0,
            price_last=orm.price_last or 0.0,
            price_change=orm.price_change or 0.0,
            price_change_pct=orm.price_change_pct or 0.0,
            volume=orm.volume or 0,
            value=orm.value or 0.0,
            trade_count=orm.trade_count or 0,
            price_yesterday=orm.price_yesterday or 0.0,
            price_first=orm.price_first or 0.0,
            price_max=orm.price_max or 0.0,
            price_min=orm.price_min or 0.0,
            ask_price=orm.ask_price or 0.0,
            ask_volume=orm.ask_volume or 0,
            bid_price=orm.bid_price or 0.0,
            bid_volume=orm.bid_volume or 0,
            time=orm.time or "",
            date=orm.date or "",
            timeframe=orm.timeframe or "1d",
            data_source=orm.data_source or "tsetmc",
            created_at=orm.created_at,
        )

    def _to_orm(self, domain: Quote) -> QuoteModel:
        return QuoteModel(
            id=domain.id,
            instrument_id=domain.instrument_id,
            symbol=domain.symbol or None,
            price_close=domain.price_close or None,
            price_open=domain.price_open or None,
            price_high=domain.price_high or None,
            price_low=domain.price_low or None,
            price_last=domain.price_last or None,
            price_change=domain.price_change or None,
            price_change_pct=domain.price_change_pct or None,
            volume=domain.volume or None,
            value=domain.value or None,
            trade_count=domain.trade_count or None,
            price_yesterday=domain.price_yesterday or None,
            price_first=domain.price_first or None,
            price_max=domain.price_max or None,
            price_min=domain.price_min or None,
            ask_price=domain.ask_price or None,
            ask_volume=domain.ask_volume or None,
            bid_price=domain.bid_price or None,
            bid_volume=domain.bid_volume or None,
            time=domain.time or None,
            date=domain.date or None,
            timeframe=domain.timeframe or "1d",
            data_source=domain.data_source or "tsetmc",
            created_at=domain.created_at,
        )
