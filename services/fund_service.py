from __future__ import annotations

from datetime import date
from typing import Any

from core.ids import new_id
from core.logging import get_logger
from core.result import PaginatedResult, Result
from domain.funds.entities import Fund, FundHolding
from domain.funds.nav import FundNAV
from repositories.base_repository import InMemoryRepository

logger = get_logger(__name__)


class FundRepository(InMemoryRepository[Fund]):
    async def get_by_symbol(self, symbol: str) -> Result[Fund]:
        for fund in self._store.values():
            if fund.symbol == symbol:
                return Result.ok(fund)
        return Result.fail(f"Fund not found with symbol: {symbol}")

    async def get_by_isin(self, isin: str) -> Result[Fund]:
        for fund in self._store.values():
            if fund.isin == isin:
                return Result.ok(fund)
        return Result.fail(f"Fund not found with ISIN: {isin}")

    async def search(self, query: str, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[Fund]]:
        q = query.lower()
        matches = [
            f for f in self._store.values() if q in f.name.lower() or q in f.symbol.lower() or q in f.isin.lower()
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


class FundNavRepository(InMemoryRepository[FundNAV]):
    async def get_by_fund(self, fund_id: str, start_date: str = "", end_date: str = "") -> Result[list[FundNAV]]:
        navs = [n for n in self._store.values() if n.fund_id == fund_id]
        if start_date:
            navs = [n for n in navs if n.nav_date and str(n.nav_date) >= start_date]
        if end_date:
            navs = [n for n in navs if n.nav_date and str(n.nav_date) <= end_date]
        navs.sort(key=lambda n: n.nav_date or date.min)
        return Result.ok(navs)


class FundHoldingRepository(InMemoryRepository[FundHolding]):
    async def get_by_fund(self, fund_id: str) -> Result[list[FundHolding]]:
        holdings = [h for h in self._store.values() if h.fund_id == fund_id]
        return Result.ok(holdings)


class FundService:
    def __init__(
        self,
        fund_repo: FundRepository | None = None,
        nav_repo: FundNavRepository | None = None,
        holding_repo: FundHoldingRepository | None = None,
    ) -> None:
        self.fund_repo = fund_repo or FundRepository()
        self.nav_repo = nav_repo or FundNavRepository()
        self.holding_repo = holding_repo or FundHoldingRepository()

    async def list_all(self, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[Fund]]:
        return await self.fund_repo.list(page, page_size)

    async def get_by_id(self, fund_id: str) -> Result[Fund]:
        return await self.fund_repo.get(fund_id)

    async def get_nav_history(
        self,
        fund_id: str,
        start_date: date | str | None = None,
        end_date: date | str | None = None,
    ) -> Result[list[FundNAV]]:
        sd = str(start_date) if start_date else ""
        ed = str(end_date) if end_date else ""
        return await self.nav_repo.get_by_fund(fund_id, sd, ed)

    async def get_holdings(self, fund_id: str) -> Result[list[FundHolding]]:
        return await self.holding_repo.get_by_fund(fund_id)

    async def create(self, name: str, **kwargs: Any) -> Result[Fund]:
        fund = Fund(id=new_id("fund"), name=name, **kwargs)
        result = await self.fund_repo.save(fund)
        if result.success:
            logger.info("Created fund %s (%s)", name, fund.id)
        return result

    async def update(self, fund_id: str, **kwargs: Any) -> Result[Fund]:
        existing = await self.fund_repo.get(fund_id)
        if not existing.success:
            return Result.fail(existing.error or f"Fund {fund_id} not found")
        fund = existing.value
        for key, value in kwargs.items():
            if hasattr(fund, key):
                setattr(fund, key, value)
        fund.mark_updated()
        result = await self.fund_repo.save(fund)
        if result.success:
            logger.info("Updated fund %s (%s)", fund.name, fund_id)
        return result

    async def save_nav(self, nav: FundNAV) -> Result[FundNAV]:
        return await self.nav_repo.save(nav)

    async def save_holding(self, holding: FundHolding) -> Result[FundHolding]:
        return await self.holding_repo.save(holding)

    async def search(self, query: str, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[Fund]]:
        return await self.fund_repo.search(query, page, page_size)
