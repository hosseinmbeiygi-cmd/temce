from __future__ import annotations

from typing import Any

from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.result import PaginatedResult, Result
from domain.portfolios.portfolio import Portfolio
from models.portfolio import PortfolioModel, PortfolioPositionModel
from repositories.db_base import DbRepository


class PortfolioRepository(DbRepository[Portfolio, PortfolioModel]):
    model_class = PortfolioModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_owned(self, portfolio_id: str, owner_id: str | None = None) -> Result[Portfolio]:
        """Fetch a portfolio, optionally restricted to its owner.

        ``owner_id=None`` means "no owner filter" and is only passed for admins.
        Three distinct outcomes are kept apart: not found, not yours (also
        reported as not found so the endpoint cannot be used as an existence
        oracle), and found.
        """
        stmt = select(PortfolioModel).where(PortfolioModel.id == portfolio_id)
        if owner_id is not None:
            stmt = stmt.where(PortfolioModel.owner == owner_id)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return Result.fail(f"PortfolioModel {portfolio_id} not found")
        return Result.ok(self._to_domain(row))

    async def list_owned(
        self,
        owner_id: str | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Result[PaginatedResult[Portfolio]]:
        stmt_count = select(sa_func.count()).select_from(PortfolioModel)
        stmt_rows = select(PortfolioModel)
        if owner_id is not None:
            stmt_count = stmt_count.where(PortfolioModel.owner == owner_id)
            stmt_rows = stmt_rows.where(PortfolioModel.owner == owner_id)

        total = (await self.session.execute(stmt_count)).scalar() or 0
        stmt_rows = stmt_rows.offset((page - 1) * page_size).limit(page_size)
        rows = (await self.session.execute(stmt_rows)).scalars().all()
        return Result.ok(
            PaginatedResult(
                items=[self._to_domain(r) for r in rows],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=max(1, (total + page_size - 1) // page_size),
            )
        )

    async def get_positions(self, portfolio_id: str) -> Result[list[dict[str, Any]]]:
        stmt = select(PortfolioPositionModel).where(PortfolioPositionModel.portfolio_id == portfolio_id)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok([
            {
                "id": row.id,
                "symbol": row.symbol,
                "quantity": row.quantity,
                "avg_cost": row.avg_cost,
                "current_price": row.current_price,
                "market_value": row.market_value,
                "unrealized_pnl": row.unrealized_pnl,
                "weight_pct": row.weight_pct,
            }
            for row in rows
        ])

    def _to_domain(self, orm: PortfolioModel) -> Portfolio:
        return Portfolio(
            id=orm.id,
            name=orm.name,
            description=orm.description or "",
            initial_capital=orm.initial_capital or 0.0,
            current_capital=orm.current_value or 0.0,
            currency=orm.currency or "IRR",
            owner_id=orm.owner or "system",
        )

    def _to_orm(self, domain: Portfolio) -> PortfolioModel:
        return PortfolioModel(
            id=domain.id,
            name=domain.name,
            description=domain.description,
            initial_capital=domain.initial_capital,
            current_value=domain.current_capital,
            currency=domain.currency,
            owner=domain.owner_id,
        )
