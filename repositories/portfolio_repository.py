from __future__ import annotations

from typing import Any
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from core.result import PaginatedResult, Result
from models.portfolio import PortfolioModel, PortfolioPositionModel
from repositories.base_repository import DbRepository
from domain.portfolios.portfolio import Portfolio

class PortfolioRepository(DbRepository[Portfolio, PortfolioModel]):
    model_class = PortfolioModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

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
