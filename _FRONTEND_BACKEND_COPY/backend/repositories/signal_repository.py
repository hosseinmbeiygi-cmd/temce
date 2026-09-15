from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.result import PaginatedResult, Result
from domain.analytics.signal import Signal
from models.signal import SignalModel
from repositories.base_repository import InMemoryRepository
from repositories.db_base import DbRepository


class SignalRepository:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session
        self._mem: InMemoryRepository[Signal] | None = None if session else InMemoryRepository[Signal]()
        self._db: _SignalDbRepo | None = None if not session else _SignalDbRepo(session)

    async def get(self, id: str) -> Result[Signal]:
        if self._db:
            return await self._db.get(id)
        return await self._mem.get(id)

    async def save(self, entity: Signal) -> Result[Signal]:
        if self._db:
            return await self._db.save(entity)
        return await self._mem.save(entity)

    async def delete(self, id: str) -> Result[bool]:
        if self._db:
            return await self._db.delete(id)
        return await self._mem.delete(id)

    async def list(self, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[Signal]]:
        if self._db:
            return await self._db.list(page, page_size)
        return await self._mem.list(page, page_size)

    async def get_latest(self, instrument_id: str) -> Result[Signal]:
        if self._db:
            return await self._db.get_latest(instrument_id)
        signals = [s for s in self._mem._store.values() if s.instrument_id == instrument_id]
        if not signals:
            return Result.fail(f"No signals for {instrument_id}")
        sorted_s = sorted(signals, key=lambda s: s.created_at, reverse=True)
        return Result.ok(sorted_s[0])

    async def get_by_instrument(
        self, instrument_id: str, page: int = 1, page_size: int = 50
    ) -> Result[PaginatedResult[Signal]]:
        if self._db:
            return await self._db.get_by_instrument(instrument_id, page, page_size)
        signals = [s for s in self._mem._store.values() if s.instrument_id == instrument_id]
        total = len(signals)
        start = (page - 1) * page_size
        return Result.ok(
            PaginatedResult(
                items=sorted(signals, key=lambda s: s.created_at, reverse=True)[start : start + page_size],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=max(1, (total + page_size - 1) // page_size),
            )
        )


class _SignalDbRepo(DbRepository[Signal, SignalModel]):
    model_class = SignalModel

    async def get_latest(self, instrument_id: str) -> Result[Signal]:
        stmt = (
            select(SignalModel)
            .where(SignalModel.instrument_id == instrument_id)
            .order_by(desc(SignalModel.created_at))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return Result.fail(f"No signals for {instrument_id}")
        return Result.ok(self._to_domain(row))

    async def get_by_instrument(
        self, instrument_id: str, page: int = 1, page_size: int = 50
    ) -> Result[PaginatedResult[Signal]]:
        from sqlalchemy import func as sa_func

        count_stmt = select(sa_func.count()).select_from(SignalModel).where(SignalModel.instrument_id == instrument_id)
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = (
            select(SignalModel)
            .where(SignalModel.instrument_id == instrument_id)
            .order_by(desc(SignalModel.created_at))
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

    def _to_domain(self, orm: SignalModel) -> Signal:
        from domain.common.enum_types import SignalType

        return Signal(
            id=orm.id,
            instrument_id=orm.instrument_id or "",
            signal_type=SignalType(orm.signal_type) if orm.signal_type else SignalType.NEUTRAL,
            symbol=orm.symbol or "",
            source=orm.source or "",
            strategy=orm.message or "",
            timeframe=orm.timeframe or "1d",
            description=orm.message or "",
            score=orm.strength or 0.0,
            confidence=0.0,
            created_at=orm.created_at,
        )

    def _to_orm(self, domain: Signal) -> SignalModel:
        return SignalModel(
            id=domain.id,
            instrument_id=domain.instrument_id or None,
            symbol=domain.symbol or "",
            signal_type=domain.signal_type.value if domain.signal_type else "neutral",
            strength=domain.score,
            source=domain.source or None,
            message=domain.description or None,
            timeframe=domain.timeframe or "1d",
            data_source="system",
            created_at=domain.created_at,
        )
