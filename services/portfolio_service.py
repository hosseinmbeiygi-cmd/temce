from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.result import Result
from repositories.portfolio_repository import PortfolioRepository


class PortfolioService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = PortfolioRepository(session)

    async def get_portfolio(self, portfolio_id: str, owner_id: str | None = None) -> Result[dict[str, Any]]:
        # ``owner_id=None`` keeps the historical unscoped read for admins.
        if owner_id is None:
            res = await self.repo.get(portfolio_id)
        else:
            res = await self.repo.get_owned(portfolio_id, owner_id=owner_id)
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

    async def list_portfolios(self, owner_id: str | None = None) -> Result[list[dict[str, Any]]]:
        if owner_id is None:
            res = await self.repo.list()
        else:
            res = await self.repo.list_owned(owner_id=owner_id)
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

    async def create_portfolio(self, name: str, owner_id: str = "", **kwargs: Any) -> Result[dict[str, Any]]:
        from core.ids import new_id
        from domain.portfolios.portfolio import Portfolio

        portfolio = Portfolio(
            id=new_id("port"),
            name=name,
            owner_id=owner_id,
            description=kwargs.get("description", ""),
            initial_capital=kwargs.get("initial_capital", 0.0),
            currency=kwargs.get("currency", "IRR"),
        )

        res = await self.repo.save(portfolio)
        if not res.success:
            return res

        return Result.ok({"id": portfolio.id, "name": portfolio.name})
