from __future__ import annotations

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

    async def list_all(self, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[NewsItem]]:
        return await self.repo.list(page, page_size)

    async def search(self, query: str, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[NewsItem]]:
        return await self.repo.search(query, page, page_size)

    async def get_by_symbol(self, symbol: str, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[NewsItem]]:
        return await self.repo.get_by_symbol(symbol, page, page_size)

    async def create(self, title: str, **kwargs: Any) -> Result[NewsItem]:
        item = NewsItem(id=new_id("news"), title=title, **kwargs)
        return await self.repo.save(item)

    async def save(self, item: NewsItem) -> Result[NewsItem]:
        return await self.repo.save(item)
