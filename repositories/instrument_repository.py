from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.result import PaginatedResult, Result
from domain.instruments.instrument import Instrument
from models.instrument import InstrumentModel
from repositories.base_repository import InMemoryRepository
from repositories.db_base import DbRepository


class InstrumentRepository:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session
        self._mem: InMemoryRepository[Instrument] | None = None if session else InMemoryRepository[Instrument]()
        self._db: _InstrumentDbRepo | None = None if not session else _InstrumentDbRepo(session)

    async def get(self, id: str) -> Result[Instrument]:
        if self._db:
            return await self._db.get(id)
        return await self._mem.get(id)  # type: ignore

    async def save(self, entity: Instrument) -> Result[Instrument]:
        if self._db:
            return await self._db.save(entity)
        return await self._mem.save(entity)  # type: ignore

    async def delete(self, id: str) -> Result[bool]:
        if self._db:
            return await self._db.delete(id)
        return await self._mem.delete(id)  # type: ignore

    async def list(self, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[Instrument]]:
        if self._db:
            return await self._db.list(page, page_size)
        return await self._mem.list(page, page_size)  # type: ignore

    async def get_by_symbol(self, symbol: str) -> Result[Instrument]:
        if self._db:
            return await self._db.get_by_symbol(symbol)
        for inst in self._mem._store.values():  # type: ignore
            if inst.symbol == symbol:
                return Result.ok(inst)
        return Result.fail(f"Instrument {symbol} not found")

    async def get_by_isin(self, isin: str) -> Result[Instrument]:
        if self._db:
            return await self._db.get_by_isin(isin)
        for inst in self._mem._store.values():  # type: ignore
            if inst.isin == isin:
                return Result.ok(inst)
        return Result.fail(f"Instrument with ISIN {isin} not found")

    async def search(self, query: str, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[Instrument]]:
        if self._db:
            return await self._db.search(query, page, page_size)
        # In-memory fallback (no session): plain substring + Finglish match.
        from services.symbol_catalog import finglish_symbol_candidates

        q = query.lower()
        matches = [inst for inst in self._mem._store.values() if q in inst.symbol.lower() or q in inst.name.lower()]  # type: ignore
        extra = finglish_symbol_candidates(query)
        if extra:
            known = {m.symbol for m in matches}
            for inst in self._mem._store.values():  # type: ignore
                if inst.symbol in extra and inst.symbol not in known:
                    matches.append(inst)
        total = len(matches)
        start = (page - 1) * page_size
        return Result.ok(
            PaginatedResult(
                items=matches[start : start + page_size],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=max(1, (total + page_size - 1) // page_size),
            )
        )

    async def get_by_market(self, market_type: str) -> Result[list[Instrument]]:
        if self._db:
            return await self._db.get_by_market(market_type)
        matches = [inst for inst in self._mem._store.values() if inst.market_type.value == market_type]  # type: ignore
        return Result.ok(matches)

    async def count(self) -> int:
        if self._db:
            return await self._db.count()
        return len(self._mem._store)  # type: ignore


class _InstrumentDbRepo(DbRepository[Instrument, InstrumentModel]):
    model_class = InstrumentModel

    async def get_by_symbol(self, symbol: str) -> Result[Instrument]:
        stmt = select(InstrumentModel).where(InstrumentModel.symbol == symbol)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return Result.fail(f"Instrument {symbol} not found")
        return Result.ok(self._to_domain(row))

    async def get_by_isin(self, isin: str) -> Result[Instrument]:
        stmt = select(InstrumentModel).where(InstrumentModel.isin == isin)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return Result.fail(f"Instrument with ISIN {isin} not found")
        return Result.ok(self._to_domain(row))

    async def search(self, query: str, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[Instrument]]:
        from services.symbol_catalog import finglish_symbol_candidates

        q = f"%{query.lower()}%"
        # Plain substring match on symbol/name + Finglish: a Latin query like
        # ``folad`` must also find the Persian symbol ``فولاد`` in PostgreSQL.
        predicate = or_(InstrumentModel.symbol.ilike(q), InstrumentModel.name.ilike(q))
        extra = finglish_symbol_candidates(query)
        if extra:
            predicate = or_(predicate, InstrumentModel.symbol.in_(extra))
        from sqlalchemy import func as sa_func

        count_stmt = select(sa_func.count()).select_from(InstrumentModel).where(predicate)
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = select(InstrumentModel).where(predicate).offset((page - 1) * page_size).limit(page_size)
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

    async def get_by_market(self, market_type: str) -> Result[list[Instrument]]:
        stmt = select(InstrumentModel).where(InstrumentModel.market_type == market_type)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok([self._to_domain(r) for r in rows])

    async def count(self) -> int:
        from sqlalchemy import func as sa_func

        stmt = select(sa_func.count()).select_from(InstrumentModel)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    def _to_domain(self, orm: InstrumentModel) -> Instrument:
        from domain.common.enum_types import AssetClass, InstrumentStatus, MarketType

        # ``tags`` and ``metadata_`` are real ``UnicodeJSON`` columns
        # (see ``models/instrument.py``). SQLAlchemy delivers them as native
        # ``list`` / ``dict`` on Postgres and parses a JSON string on SQLite.
        # NULL columns come back as ``None``; ``or []`` / ``or {}`` collapses
        # both ``None`` and an empty parsed value to a usable default.
        tags = list(orm.tags) if orm.tags else []
        metadata = dict(orm.metadata_) if orm.metadata_ else {}

        return Instrument(
            id=orm.id,
            symbol=orm.symbol,
            name=orm.name or "",
            isin=orm.isin or "",
            market_type=MarketType(orm.market_type) if orm.market_type else MarketType.BOURS,
            asset_class=AssetClass(orm.asset_class) if orm.asset_class else AssetClass.EQUITY,
            status=InstrumentStatus(orm.status) if orm.status else InstrumentStatus.ACTIVE,
            sector_code=orm.sector_code or "",
            group_code=orm.group_code or "",
            sub_group_code=orm.sub_group_code or "",
            tick_size=orm.tick_size or 1.0,
            lot_size=orm.lot_size or 1,
            par_value=orm.par_value or 1000,
            eps=orm.eps or 0.0,
            shares_count=orm.shares_count or 0,
            base_volume=orm.base_volume or 0,
            market_id=orm.market_id or "",
            exchange_code=orm.exchange_code or "",
            board_code=orm.board_code or "",
            data_source=orm.data_source or "tsetmc",
            tags=tags,
            metadata=metadata,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    def _to_orm(self, domain: Instrument) -> InstrumentModel:
        # Empty collections must become SQL NULL (not '[]'/'{}'); the
        # ``UnicodeJSON`` type handles JSON serialization and ``ensure_ascii``.
        tags = list(domain.tags) if domain.tags else None
        meta = dict(domain.metadata) if domain.metadata else None

        return InstrumentModel(
            id=domain.id,
            symbol=domain.symbol,
            name=domain.name,
            isin=domain.isin or None,
            market_type=domain.market_type.value if domain.market_type else None,
            asset_class=domain.asset_class.value if domain.asset_class else None,
            status=domain.status.value if domain.status else "active",
            sector_code=domain.sector_code or None,
            group_code=domain.group_code or None,
            sub_group_code=domain.sub_group_code or None,
            tick_size=domain.tick_size or None,
            lot_size=domain.lot_size or None,
            par_value=domain.par_value or None,
            eps=domain.eps or None,
            shares_count=domain.shares_count or None,
            base_volume=domain.base_volume or None,
            market_id=domain.market_id or None,
            tags=tags,
            metadata_=meta,
            exchange_code=domain.exchange_code or None,
            board_code=domain.board_code or None,
            data_source=domain.data_source or "tsetmc",
            created_at=domain.created_at,
            updated_at=domain.updated_at,
        )

