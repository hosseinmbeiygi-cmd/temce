from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import new_id
from core.logging import get_logger
from core.result import PaginatedResult, Result
from domain.codal.disclosure import Disclosure
from repositories.codal_repository import CodalRepository

logger = get_logger(__name__)


class CodalService:
    def __init__(self, repo: CodalRepository | None = None, session: AsyncSession | None = None) -> None:
        self.repo = repo or CodalRepository(session=session)

    async def list_all(self, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[Disclosure]]:
        return await self.repo.list(page, page_size)

    async def get_by_instrument(
        self, instrument_id: str, page: int = 1, page_size: int = 50
    ) -> Result[PaginatedResult[Disclosure]]:
        return await self.repo.get_by_instrument(instrument_id, page, page_size)

    async def create(self, instrument_id: str, title: str, **kwargs: Any) -> Result[Disclosure]:
        disclosure = Disclosure(id=new_id("cod"), instrument_id=instrument_id, title=title, **kwargs)
        return await self.repo.save(disclosure)

    async def save(self, disclosure: Disclosure) -> Result[Disclosure]:
        return await self.repo.save(disclosure)
