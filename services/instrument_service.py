from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.result import Result
from repositories.instrument_repository import InstrumentRepository

logger = get_logger(__name__)


class InstrumentService:
    def __init__(self, repo: InstrumentRepository | None = None, session: AsyncSession | None = None) -> None:
        if repo is None:
            repo = InstrumentRepository(session=session)
        self.repo = repo

    async def search(self, query: str) -> Result[list[dict[str, Any]]]:
        result = await self.repo.search(query)
        if not result.success:
            return Result.ok([])
        return Result.ok([vars(item) for item in result.value.items])  # type: ignore

    async def get_by_symbol(self, symbol: str) -> Result[dict[str, Any]]:
        result = await self.repo.get_by_symbol(symbol)
        if not result.success:
            return Result.fail(f"Instrument {symbol} not found")
        return Result.ok(vars(result.value))

    async def get_by_isin(self, isin: str) -> Result[dict[str, Any]]:
        result = await self.repo.get_by_isin(isin)
        if not result.success:
            return Result.fail(f"Instrument with ISIN {isin} not found")
        return Result.ok(vars(result.value))

    async def list_all(self) -> Result[list[dict[str, Any]]]:
        result = await self.repo.list(page_size=10000)
        if not result.success:
            return Result.ok([])
        return Result.ok([vars(item) for item in result.value.items])  # type: ignore

    async def create(self, **data: Any) -> Result[dict[str, Any]]:
        return Result.ok(data)
