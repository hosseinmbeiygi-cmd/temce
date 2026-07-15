from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.result import Result
from repositories.portfolio_repository import PortfolioRepository


class PortfolioService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = PortfolioRepository(session)

    async def get_portfolio(self, portfolio_id: str) -> Result[dict[str, Any]]:
        res = await self.repo.get(portfolio_id)
        if not res.success:
            return res

        portfolio = res.value
        positions_res = await self.repo.get_positions(portfolio_id)

        return Result.ok({
            "id": portfolio.id,
            "name": portfolio.name,
            "description": portfolio.description,
            "initial_capital": portfolio.initial_capital,
            "current_value": portfolio.current_capital,
            "currency": portfolio.currency,
            "positions": positions_res.value if positions_res.success else [],
        })

    async def list_portfolios(self) -> Result[list[dict[str, Any]]]:
        res = await self.repo.list()
        if not res.success:
            return res

        return Result.ok([
            {
                "id": p.id,
                "name": p.name,
                "current_value": p.current_capital,
                "total_return_pct": 0.0, # Simplified for now
            }
            for p in res.value.items
        ])

    async def create_portfolio(self, name: str, **kwargs: Any) -> Result[dict[str, Any]]:
        from core.ids import new_id
        from domain.portfolios.portfolio import Portfolio

        portfolio = Portfolio(
            id=new_id("port"),
            name=name,
            description=kwargs.get("description", ""),
            initial_capital=kwargs.get("initial_capital", 0.0),
            currency=kwargs.get("currency", "IRR"),
        )

        res = await self.repo.save(portfolio)
        if not res.success:
            return res

        return Result.ok({"id": portfolio.id, "name": portfolio.name})
