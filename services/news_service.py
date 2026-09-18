from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import new_id
from core.logging import get_logger
from core.result import PaginatedResult, Result
from domain.news.news_item import NewsItem
from repositories.news_repository import NewsRepository

logger = get_logger(__name__)


class NewsService:
    def __init__(self, repo: NewsRepository | None = None, session: AsyncSession | None = None) -> None:
        if repo is None:
            repo = NewsRepository(session=session)
        self.repo = repo

    @staticmethod
    def _window_kwargs(date_from: datetime | None, date_to: datetime | None) -> dict[str, Any]:
        """Forward only the bounds actually provided, so calls without a
        window keep the exact pre-existing repo call signature."""
        kwargs: dict[str, Any] = {}
        if date_from is not None:
            kwargs["date_from"] = date_from
        if date_to is not None:
            kwargs["date_to"] = date_to
        return kwargs

    async def list_all(
        self,
        page: int = 1,
        page_size: int = 50,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> Result[PaginatedResult[NewsItem]]:
        result = await self.repo.list(page, page_size, **self._window_kwargs(date_from, date_to))
        if result.success and result.value and result.value.items:
            result.value.items.sort(
                key=lambda x: x.publish_date or x.created_at or "",
                reverse=True,
            )
        return result

    async def search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 50,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> Result[PaginatedResult[NewsItem]]:
        return await self.repo.search(query, page, page_size, **self._window_kwargs(date_from, date_to))

    async def get_by_symbol(
        self,
        symbol: str,
        page: int = 1,
        page_size: int = 50,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> Result[PaginatedResult[NewsItem]]:
        return await self.repo.get_by_symbol(symbol, page, page_size, **self._window_kwargs(date_from, date_to))

    async def create(self, title: str, **kwargs: Any) -> Result[NewsItem]:
        item = NewsItem(id=new_id("news"), title=title, **kwargs)
        return await self.repo.save(item)

    async def save(self, item: NewsItem) -> Result[NewsItem]:
        return await self.repo.save(item)
