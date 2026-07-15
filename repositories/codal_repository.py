"""DB-backed Codal repository.

Stores & retrieves ``Disclosure`` domain objects via the ``CodalReportModel``
ORM model.  Falls back to in-memory storage when no SQLAlchemy session is given.
"""

from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.result import PaginatedResult, Result
from domain.codal.disclosure import Disclosure
from models.codal import CodalReportModel
from repositories.base_repository import InMemoryRepository
from repositories.db_base import DbRepository


class CodalRepository:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session
        self._mem: InMemoryRepository[Disclosure] | None = None if session else InMemoryRepository[Disclosure]()
        self._db: _CodalDbRepo | None = None if not session else _CodalDbRepo(session)

    async def get(self, id: str) -> Result[Disclosure]:
        if self._db:
            return await self._db.get(id)
        return await self._mem.get(id)

    async def save(self, entity: Disclosure) -> Result[Disclosure]:
        if self._db:
            return await self._db.save(entity)
        return await self._mem.save(entity)

    async def delete(self, id: str) -> Result[bool]:
        if self._db:
            return await self._db.delete(id)
        return await self._mem.delete(id)

    async def list(self, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[Disclosure]]:
        if self._db:
            return await self._db.list(page, page_size)
        return await self._mem.list(page, page_size)

    async def get_by_instrument(
        self, instrument_id: str, page: int = 1, page_size: int = 50
    ) -> Result[PaginatedResult[Disclosure]]:
        if self._db:
            return await self._db.get_by_instrument(instrument_id, page, page_size)
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

    async def get_by_symbol(
        self, symbol: str, page: int = 1, page_size: int = 50
    ) -> Result[PaginatedResult[Disclosure]]:
        if self._db:
            return await self._db.get_by_symbol(symbol, page, page_size)
        items = [d for d in self._mem._store.values() if d.symbol == symbol]
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

    async def get_by_key(
        self, symbol: str, report_type: str, fiscal_year: str, period: str
    ) -> Result[Disclosure | None]:
        """Find an existing disclosure by unique key (symbol + type + year + period)."""
        if self._db:
            return await self._db.get_by_key(symbol, report_type, fiscal_year, period)
        for d in self._mem._store.values():
            if (
                d.symbol == symbol
                and d.disclosure_type == report_type
                and d.fiscal_year == fiscal_year
                and d.period == period
            ):
                return Result.ok(d)
        return Result.ok(None)


class _CodalDbRepo(DbRepository[Disclosure, CodalReportModel]):
    model_class = CodalReportModel

    async def get_by_instrument(
        self, instrument_id: str, page: int = 1, page_size: int = 50
    ) -> Result[PaginatedResult[Disclosure]]:
        from sqlalchemy import func as sa_func

        count_stmt = select(sa_func.count()).select_from(CodalReportModel).where(
            CodalReportModel.instrument_id == instrument_id
        )
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = (
            select(CodalReportModel)
            .where(CodalReportModel.instrument_id == instrument_id)
            .order_by(desc(CodalReportModel.publish_date))
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

    async def get_by_symbol(
        self, symbol: str, page: int = 1, page_size: int = 50
    ) -> Result[PaginatedResult[Disclosure]]:
        from sqlalchemy import func as sa_func

        count_stmt = select(sa_func.count()).select_from(CodalReportModel).where(
            CodalReportModel.symbol == symbol
        )
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = (
            select(CodalReportModel)
            .where(CodalReportModel.symbol == symbol)
            .order_by(desc(CodalReportModel.publish_date))
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

    def _to_domain(self, orm: CodalReportModel) -> Disclosure:
        from datetime import date

        pub_date = None
        if orm.publish_date:
            # Try ISO format first
            try:
                pub_date = date.fromisoformat(orm.publish_date)
            except (ValueError, TypeError):
                # Persian/Shamsi date like "۱۴۰۵/۰۴/۰۲" — store as string
                pass

        return Disclosure(
            id=orm.id,
            instrument_id=orm.instrument_id or orm.symbol or "",
            title=f"{orm.report_type or ''} {orm.fiscal_year or ''}".strip(),
            symbol=orm.symbol or "",
            company_name=orm.company_name or "",
            publish_date=pub_date,
            fiscal_year=orm.fiscal_year or "",
            period=orm.period or "",
            disclosure_type=orm.report_type or "",
            category="",
            summary=orm.summary or "",
            url=orm.attachment_url or "",
            data_source=orm.data_source or "codal",
            extra={"raw_publish_date": orm.publish_date or ""},
        )

    async def get_by_key(
        self, symbol: str, report_type: str, fiscal_year: str, period: str
    ) -> Result[Disclosure | None]:
        stmt = (
            select(CodalReportModel)
            .where(
                CodalReportModel.symbol == symbol,
                CodalReportModel.report_type == report_type,
                CodalReportModel.fiscal_year == fiscal_year,
                CodalReportModel.period == period,
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return Result.ok(None)
        return Result.ok(self._to_domain(row))

    def _to_orm(self, domain: Disclosure) -> CodalReportModel:
        return CodalReportModel(
            id=domain.id,
            instrument_id=domain.instrument_id or "",
            symbol=domain.symbol,
            company_name=domain.company_name or "",
            isin="",
            report_type=domain.disclosure_type,
            fiscal_year=domain.fiscal_year,
            period=domain.period,
            publish_date=str(domain.publish_date) if domain.publish_date else None,
            attachment_url=domain.url,
            summary=domain.summary,
            data_source=domain.data_source or "codal",
        )
