from __future__ import annotations

from typing import Any, cast

from core.database import AsyncSession
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
            return cast(dict[str, Any], obj.model_dump())
        if hasattr(obj, "dict"):
            return cast(dict[str, Any], obj.dict())
        if hasattr(obj, "__dict__"):
            return cast(dict[str, Any], vars(obj))
        if isinstance(obj, dict):
            return obj
        return dict(obj)

    async def create(self, symbol: str, name: str, **kwargs: Any) -> Result[dict[str, Any]]:
        instrument = Instrument(id=new_id("inst"), symbol=symbol, name=name, **kwargs)
        result = await self.repo.save(instrument)
        if not result.success:
            return Result.fail(result.error or "Failed to create symbol")
        return Result.ok(self._to_dict(result.value))

    async def list_all(self, page: int = 1, page_size: int = 50, market: str | None = None) -> Result[PaginatedResult[dict[str, Any]]]:
        if market:
            market_result = await self.repo.get_by_market(market)
            items = market_result.value
            if not market_result.success or items is None:
                return Result.ok(PaginatedResult(items=[], total=0, page=page, page_size=page_size, total_pages=1))
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
        page_result = await self.repo.list(page, page_size)
        page_value = page_result.value
        if not page_result.success or page_value is None:
            return Result.ok(PaginatedResult(items=[], total=0, page=page, page_size=page_size, total_pages=1))
        return Result.ok(
            PaginatedResult(
                items=[self._to_dict(item) for item in page_value.items],
                total=page_value.total,
                page=page_value.page,
                page_size=page_value.page_size,
                total_pages=page_value.total_pages,
            )
        )

    async def search(self, query: str, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[dict[str, Any]]]:
        result = await self.repo.search(query, page, page_size)
        value = result.value
        if not result.success or value is None:
            return Result.ok(PaginatedResult(items=[], total=0, page=page, page_size=page_size, total_pages=1))
        return Result.ok(
            PaginatedResult(
                items=[self._to_dict(item) for item in value.items],
                total=value.total,
                page=value.page,
                page_size=value.page_size,
                total_pages=value.total_pages,
            )
        )

    async def get_by_symbol(self, symbol: str) -> Result[dict[str, Any]]:
        result = await self.repo.get_by_symbol(symbol)
        if not result.success:
            return Result.fail(f"Symbol {symbol} not found")
        return Result.ok(vars(result.value))

    async def get_detail(self, symbol: str) -> Result[dict[str, Any]]:
        return await self.get_by_symbol(symbol)
