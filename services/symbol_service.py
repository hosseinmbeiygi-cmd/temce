from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.result import Result
from repositories.instrument_repository import InstrumentRepository

logger = get_logger(__name__)


class SymbolService:
    def __init__(self, repo: InstrumentRepository | None = None, session: AsyncSession | None = None) -> None:
        if repo is None:
            repo = InstrumentRepository(session=session)
        self.repo = repo

    async def search(self, query: str) -> Result[dict[str, Any]]:
        result = await self.repo.search(query)
        if not result.success:
            return Result.ok({"items": [], "total": 0})
        return Result.ok(
            {
                "items": [vars(item) for item in result.value.items],
                "total": result.value.total,
            }
        )

    async def get_by_symbol(self, symbol: str) -> Result[dict[str, Any]]:
        result = await self.repo.get_by_symbol(symbol)
        if not result.success:
            return Result.fail(f"Symbol {symbol} not found")
        return Result.ok(vars(result.value))
