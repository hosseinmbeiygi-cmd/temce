from __future__ import annotations

import contextlib
from datetime import date

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.result import PaginatedResult, Result
from domain.macro.entities import MacroEntity
from models.macro import MacroIndicatorModel
from repositories.base_repository import InMemoryRepository
from repositories.db_base import DbRepository


class MacroRepository:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session
        self._mem: InMemoryRepository[MacroEntity] | None = None if session else InMemoryRepository[MacroEntity]()
        self._db: _MacroDbRepo | None = None if not session else _MacroDbRepo(session)

    async def get(self, id: str) -> Result[MacroEntity]:
        if self._db:
            return await self._db.get(id)
        return await self._mem.get(id)

    async def save(self, entity: MacroEntity) -> Result[MacroEntity]:
        if self._db:
            return await self._db.save(entity)
        return await self._mem.save(entity)

    async def delete(self, id: str) -> Result[bool]:
        if self._db:
            return await self._db.delete(id)
        return await self._mem.delete(id)

    async def list(self, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[MacroEntity]]:
        if self._db:
            return await self._db.list(page, page_size)
        return await self._mem.list(page, page_size)

    async def get_by_indicator(self, indicator: str) -> Result[list[MacroEntity]]:
        if self._db:
            return await self._db.get_by_indicator(indicator)
        matches = [m for m in self._mem._store.values() if m.name == indicator]
        return Result.ok(sorted(matches, key=lambda x: x.date or date.min, reverse=True))

    async def get_by_country(self, country: str) -> Result[list[MacroEntity]]:
        if self._db:
            return await self._db.get_by_country(country)
        matches = [m for m in self._mem._store.values() if m.category == country]
        return Result.ok(matches)

    async def get_latest(self, indicator: str) -> Result[MacroEntity]:
        if self._db:
            return await self._db.get_latest(indicator)
        matches = [m for m in self._mem._store.values() if m.name == indicator]
        if not matches:
            return Result.fail(f"No data for {indicator}")
        return Result.ok(sorted(matches, key=lambda x: x.date or date.min, reverse=True)[0])

    async def count(self) -> int:
        if self._db:
            return await self._db.count()
        return len(self._mem._store)


class _MacroDbRepo(DbRepository[MacroEntity, MacroIndicatorModel]):
    model_class = MacroIndicatorModel

    async def get_by_indicator(self, indicator: str) -> Result[list[MacroEntity]]:
        stmt = select(MacroIndicatorModel).where(MacroIndicatorModel.indicator == indicator).order_by(desc(MacroIndicatorModel.date))
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok([self._to_domain(r) for r in rows])

    async def get_by_country(self, country: str) -> Result[list[MacroEntity]]:
        stmt = select(MacroIndicatorModel).where(MacroIndicatorModel.country == country).order_by(desc(MacroIndicatorModel.date))
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok([self._to_domain(r) for r in rows])

    async def get_latest(self, indicator: str) -> Result[MacroEntity]:
        stmt = (
            select(MacroIndicatorModel)
            .where(MacroIndicatorModel.indicator == indicator)
            .order_by(desc(MacroIndicatorModel.date))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return Result.fail(f"No data for {indicator}")
        return Result.ok(self._to_domain(row))

    async def count(self) -> int:
        from sqlalchemy import func as sa_func

        stmt = select(sa_func.count()).select_from(MacroIndicatorModel)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    def _to_domain(self, orm: MacroIndicatorModel) -> MacroEntity:
        d = None
        if orm.date:
            with contextlib.suppress(ValueError, TypeError):
                d = date.fromisoformat(orm.date)
        return MacroEntity(
            id=orm.id,
            name=orm.indicator,
            value=orm.value or 0.0,
            previous_value=orm.previous_value or 0.0,
            change_pct=orm.change_pct or 0.0,
            unit=orm.unit or "",
            date=d,
            frequency=orm.frequency or "monthly",
            source=orm.source or "",
            category=orm.country or "iran",
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    def _to_orm(self, domain: MacroEntity) -> MacroIndicatorModel:
        return MacroIndicatorModel(
            id=domain.id,
            indicator=domain.name,
            country=domain.category or "iran",
            value=domain.value or None,
            previous_value=domain.previous_value or None,
            change_pct=domain.change_pct or None,
            date=domain.date.isoformat() if domain.date else None,
            source=domain.source or None,
            unit=domain.unit or None,
            frequency=domain.frequency or "monthly",
            data_source="rss",
            created_at=domain.created_at,
            updated_at=domain.updated_at,
        )
