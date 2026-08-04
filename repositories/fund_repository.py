"""📦 Fund Repository — ذخیره و بازیابی داده‌های صندوق‌ها

Supports two backends:
  - InMemory (default, no session) — for dev/test/demo
  - PostgreSQL via SQLAlchemy AsyncSession — for production

Follows the same pattern as InstrumentRepository.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import new_id
from core.logging import get_logger
from core.result import PaginatedResult, Result
from domain.funds.entities import Fund
from models.fund import FundModel
from repositories.base_repository import InMemoryRepository
from repositories.db_base import DbRepository

logger = get_logger(__name__)


class FundRepository:
    """Repository with auto-fallback: InMemory → PostgreSQL when session is provided."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session
        self._mem: InMemoryRepository[Fund] | None = None if session else InMemoryRepository[Fund]()
        self._db: _FundDbRepo | None = None if not session else _FundDbRepo(session)

    # ── CRUD ──────────────────────────────────────────────────────

    async def get(self, id: str) -> Result[Fund]:
        if self._db:
            return await self._db.get(id)
        return await self._mem.get(id)  # type: ignore

    async def save(self, entity: Fund) -> Result[Fund]:
        if self._db:
            return await self._db.save(entity)
        return await self._mem.save(entity)  # type: ignore

    async def delete(self, id: str) -> Result[bool]:
        if self._db:
            return await self._db.delete(id)
        return await self._mem.delete(id)  # type: ignore

    async def list(self, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[Fund]]:
        if self._db:
            return await self._db.list(page, page_size)
        return await self._mem.list(page, page_size)  # type: ignore

    # ── Domain-specific ───────────────────────────────────────────

    async def get_by_symbol(self, symbol: str) -> Result[Fund]:
        """Find a fund by its trading symbol."""
        if self._db:
            return await self._db.get_by_symbol(symbol)
        for fund in self._mem._store.values():  # type: ignore
            if fund.symbol == symbol:
                return Result.ok(fund)
        return Result.fail(f"Fund not found with symbol: {symbol}")

    async def get_by_isin(self, isin: str) -> Result[Fund]:
        """Find a fund by its ISIN code."""
        if self._db:
            return await self._db.get_by_isin(isin)
        for fund in self._mem._store.values():  # type: ignore
            if fund.isin == isin:
                return Result.ok(fund)
        return Result.fail(f"Fund not found with ISIN: {isin}")

    async def get_by_fund_type(self, fund_type: str, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[Fund]]:
        """List funds filtered by type."""
        if self._db:
            return await self._db.get_by_fund_type(fund_type, page, page_size)
        matches = [f for f in self._mem._store.values() if f.fund_type == fund_type]  # type: ignore
        total = len(matches)
        start = (page - 1) * page_size
        return Result.ok(
            PaginatedResult(
                items=matches[start: start + page_size],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=max(1, (total + page_size - 1) // page_size),
            )
        )

    async def search(self, query: str, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[Fund]]:
        """Search funds by name, symbol, or ISIN."""
        if self._db:
            return await self._db.search(query, page, page_size)
        q = query.strip().lower()
        matches = [
            f for f in self._mem._store.values()  # type: ignore
            if q in f.name.lower() or q in f.symbol.lower() or q in f.isin.lower()
        ]
        total = len(matches)
        start = (page - 1) * page_size
        end = start + page_size
        return Result.ok(
            PaginatedResult(
                items=matches[start:end],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=max(1, (total + page_size - 1) // page_size),
            )
        )

    async def count_by_type(self) -> dict[str, int]:
        """Count funds grouped by type."""
        if self._db:
            return await self._db.count_by_type()
        counts: dict[str, int] = {}
        for f in self._mem._store.values():  # type: ignore
            ft = f.fund_type or "ساير"
            counts[ft] = counts.get(ft, 0) + 1
        return counts

    async def count(self) -> int:
        """Total number of funds."""
        if self._db:
            return await self._db.count()
        return len(self._mem._store)  # type: ignore


class _FundDbRepo(DbRepository[Fund, FundModel]):
    """PostgreSQL-backed repository for Fund domain entity."""

    model_class = FundModel

    # ── Domain lookups ────────────────────────────────────────────

    async def get_by_symbol(self, symbol: str) -> Result[Fund]:
        stmt = select(FundModel).where(FundModel.symbol == symbol)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return Result.fail(f"Fund not found with symbol: {symbol}")
        return Result.ok(self._to_domain(row))

    async def get_by_isin(self, isin: str) -> Result[Fund]:
        stmt = select(FundModel).where(FundModel.isin == isin)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return Result.fail(f"Fund not found with ISIN: {isin}")
        return Result.ok(self._to_domain(row))

    async def get_by_fund_type(self, fund_type: str, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[Fund]]:
        from sqlalchemy import func as sa_func

        count_stmt = select(sa_func.count()).select_from(FundModel).where(FundModel.fund_type == fund_type)
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = (
            select(FundModel)
            .where(FundModel.fund_type == fund_type)
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

    async def search(self, query: str, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[Fund]]:
        from sqlalchemy import func as sa_func

        q = f"%{query.strip().lower()}%"
        predicate = FundModel.symbol.ilike(q) | FundModel.name.ilike(q) | FundModel.isin.ilike(q)
        count_stmt = select(sa_func.count()).select_from(FundModel).where(predicate)
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = select(FundModel).where(predicate).offset((page - 1) * page_size).limit(page_size)
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

    async def count_by_type(self) -> dict[str, int]:
        from sqlalchemy import func as sa_func

        stmt = select(FundModel.fund_type, sa_func.count()).group_by(FundModel.fund_type)
        result = await self.session.execute(stmt)
        return {row[0] or "ساير": row[1] for row in result.all()}

    async def count(self) -> int:
        from sqlalchemy import func as sa_func

        stmt = select(sa_func.count()).select_from(FundModel)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    # ── Mapping ───────────────────────────────────────────────────

    def _to_domain(self, orm: FundModel) -> Fund:
        return Fund(
            id=orm.id,
            name=orm.name,
            symbol=orm.symbol,
            isin=orm.isin or "",
            fund_type=orm.fund_type or "",
            nav=orm.nav or 0.0,
            total_units=orm.shares_count or 0,
            status="active",
            extra={
                "nav_change": orm.nav_change,
                "nav_change_pct": orm.nav_change_pct,
                "price_last": orm.price_last,
                "price_close": orm.price_close,
                "price_yesterday": orm.price_yesterday,
                "price_max": orm.price_max,
                "price_min": orm.price_min,
                "trade_volume": orm.trade_volume,
                "trade_value": orm.trade_value,
                "trade_count": orm.trade_count,
                "base_volume": orm.base_volume,
                "market_value": orm.market_value,
                "buy_real_volume": orm.buy_real_volume,
                "buy_legal_volume": orm.buy_legal_volume,
                "sell_real_volume": orm.sell_real_volume,
                "sell_legal_volume": orm.sell_legal_volume,
                "time": orm.time or "",
                "data_source": orm.data_source or "tsetmc",
            },
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    def _to_orm(self, domain: Fund) -> FundModel:
        extra = domain.extra or {}
        return FundModel(
            id=domain.id,
            symbol=domain.symbol,
            name=domain.name,
            isin=domain.isin or None,
            fund_type=domain.fund_type or None,
            nav=domain.nav,
            nav_change=extra.get("nav_change"),
            nav_change_pct=extra.get("nav_change_pct"),
            price_last=extra.get("price_last"),
            price_close=extra.get("price_close"),
            price_yesterday=extra.get("price_yesterday"),
            price_max=extra.get("price_max"),
            price_min=extra.get("price_min"),
            trade_volume=extra.get("trade_volume"),
            trade_value=extra.get("trade_value"),
            trade_count=extra.get("trade_count"),
            shares_count=domain.total_units,
            base_volume=extra.get("base_volume"),
            market_value=extra.get("market_value"),
            buy_real_volume=extra.get("buy_real_volume"),
            buy_legal_volume=extra.get("buy_legal_volume"),
            sell_real_volume=extra.get("sell_real_volume"),
            sell_legal_volume=extra.get("sell_legal_volume"),
            time=extra.get("time") or "",
            data_source=extra.get("data_source") or "tsetmc",
            snapshot_date=extra.get("snapshot_date"),
        )


def new_fund_id() -> str:
    """Generate a new unique fund ID."""
    return new_id("fund")
