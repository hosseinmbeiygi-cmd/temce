from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import new_id
from core.logging import get_logger
from core.result import PaginatedResult, Result
from domain.instruments.instrument import Instrument
from repositories.instrument_repository import InstrumentRepository

logger = get_logger(__name__)


class SymbolService:
    def __init__(self, repo: InstrumentRepository | None = None, session: AsyncSession | None = None) -> None:
        if repo is None:
            repo = InstrumentRepository(session=session)
        self.repo = repo

    @staticmethod
    def _to_dict(obj: Any) -> dict[str, Any]:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
        if hasattr(obj, "__dict__"):
            return vars(obj)
        if isinstance(obj, dict):
            return obj
        return dict(obj)

    async def create(self, symbol: str, name: str, **kwargs: Any) -> Result[dict[str, Any]]:
        instrument = Instrument(id=new_id("inst"), symbol=symbol, name=name, **kwargs)
        result = await self.repo.save(instrument)
        if not result.success:
            return Result.fail(result.error or "Failed to create symbol")
        return Result.ok(self._to_dict(result.value))

    async def list_all(
        self, page: int = 1, page_size: int = 50, market: str | None = None
    ) -> Result[PaginatedResult[dict[str, Any]]]:
        if market:
            result = await self.repo.get_by_market(market)
            if not result.success:
                return Result.ok(PaginatedResult(items=[], total=0, page=page, page_size=page_size, total_pages=1))
            items = result.value
            total = len(items)
            start = (page - 1) * page_size
            end = start + page_size
            page_items = [self._to_dict(item) for item in items[start:end]]
            return Result.ok(
                PaginatedResult(
                    items=page_items,
                    total=total,
                    page=page,
                    page_size=page_size,
                    total_pages=max(1, (total + page_size - 1) // page_size),
                )
            )
        result = await self.repo.list(page, page_size)
        if not result.success:
            return Result.ok(PaginatedResult(items=[], total=0, page=page, page_size=page_size, total_pages=1))
        return Result.ok(
            PaginatedResult(
                items=[self._to_dict(item) for item in result.value.items],
                total=result.value.total,
                page=result.value.page,
                page_size=result.value.page_size,
                total_pages=result.value.total_pages,
            )
        )

    async def search(self, query: str, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[dict[str, Any]]]:
        result = await self.repo.search(query, page, page_size)
        if not result.success:
            return Result.ok(PaginatedResult(items=[], total=0, page=page, page_size=page_size, total_pages=1))
        return Result.ok(
            PaginatedResult(
                items=[self._to_dict(item) for item in result.value.items],
                total=result.value.total,
                page=result.value.page,
                page_size=result.value.page_size,
                total_pages=result.value.total_pages,
            )
        )

    async def get_by_symbol(self, symbol: str) -> Result[dict[str, Any]]:
        result = await self.repo.get_by_symbol(symbol)
        if not result.success:
            return Result.fail(f"Symbol {symbol} not found")
        return Result.ok(vars(result.value))

    async def get_detail(self, symbol: str) -> Result[dict[str, Any]]:
        return await self.get_by_symbol(symbol)
