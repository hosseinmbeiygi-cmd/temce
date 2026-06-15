from __future__ import annotations

import contextlib
import json

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.result import PaginatedResult, Result
from domain.news.news_item import NewsItem
from models.news import NewsArticleModel
from repositories.base_repository import InMemoryRepository
from repositories.db_base import DbRepository


class NewsRepository:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session
        self._mem: InMemoryRepository[NewsItem] | None = None if session else InMemoryRepository[NewsItem]()
        self._db: _NewsDbRepo | None = None if not session else _NewsDbRepo(session)

    async def get(self, id: str) -> Result[NewsItem]:
        if self._db:
            return await self._db.get(id)
        return await self._mem.get(id)

    async def save(self, entity: NewsItem) -> Result[NewsItem]:
        if self._db:
            return await self._db.save(entity)
        return await self._mem.save(entity)

    async def delete(self, id: str) -> Result[bool]:
        if self._db:
            return await self._db.delete(id)
        return await self._mem.delete(id)

    async def list(self, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[NewsItem]]:
        if self._db:
            return await self._db.list(page, page_size)
        return await self._mem.list(page, page_size)

    async def search(self, query: str, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[NewsItem]]:
        if self._db:
            return await self._db.search(query, page, page_size)
        q = query.lower()
        matches = [n for n in self._mem._store.values() if q in n.title.lower() or q in n.content.lower()]
        total = len(matches)
        start = (page - 1) * page_size
        return Result.ok(
            PaginatedResult(
                items=sorted(matches, key=lambda n: n.publish_date or n.created_at, reverse=True)[
                    start : start + page_size
                ],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=max(1, (total + page_size - 1) // page_size),
            )
        )

    async def get_by_symbol(self, symbol: str, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[NewsItem]]:
        if self._db:
            return await self._db.get_by_symbol(symbol, page, page_size)
        matches = [n for n in self._mem._store.values() if symbol in n.symbols]
        total = len(matches)
        start = (page - 1) * page_size
        return Result.ok(
            PaginatedResult(
                items=sorted(matches, key=lambda n: n.publish_date or n.created_at, reverse=True)[
                    start : start + page_size
                ],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=max(1, (total + page_size - 1) // page_size),
            )
        )


class _NewsDbRepo(DbRepository[NewsItem, NewsArticleModel]):
    model_class = NewsArticleModel

    async def search(self, query: str, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[NewsItem]]:
        q = f"%{query.lower()}%"
        base = select(NewsArticleModel).where(or_(NewsArticleModel.title.ilike(q), NewsArticleModel.content.ilike(q)))
        total_result = await self.session.execute(base)
        total = len(total_result.scalars().all())

        stmt = base.order_by(desc(NewsArticleModel.published_at)).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok(
            PaginatedResult(
                items=[self._to_domain(r) for r in rows],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=max(1, (total + page_size - 1) // page_size),
            )
        )

    async def get_by_symbol(self, symbol: str, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[NewsItem]]:
        q = f"%{symbol}%"
        base = select(NewsArticleModel).where(NewsArticleModel.symbols.ilike(q))
        total_result = await self.session.execute(base)
        total = len(total_result.scalars().all())

        stmt = base.order_by(desc(NewsArticleModel.published_at)).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok(
            PaginatedResult(
                items=[self._to_domain(r) for r in rows],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=max(1, (total + page_size - 1) // page_size),
            )
        )

    def _to_domain(self, orm: NewsArticleModel) -> NewsItem:
        from datetime import datetime

        pub_date = None
        if orm.published_at:
            with contextlib.suppress(ValueError, TypeError):
                pub_date = datetime.fromisoformat(orm.published_at)
        symbols = []
        if orm.symbols:
            try:
                symbols = json.loads(orm.symbols)
            except (json.JSONDecodeError, TypeError):
                symbols = [s.strip() for s in orm.symbols.split(",") if s.strip()]
        return NewsItem(
            id=orm.id,
            title=orm.title,
            content=orm.content or "",
            summary=orm.summary or "",
            source=orm.source or "",
            url=orm.url or "",
            publish_date=pub_date,
            category=orm.category or "",
            sentiment=orm.sentiment_score or 0.0,
            sentiment_label=orm.sentiment or "neutral",
            symbols=symbols,
            data_source=orm.data_source or "rss",
            created_at=orm.created_at,
        )

    def _to_orm(self, domain: NewsItem) -> NewsArticleModel:
        return NewsArticleModel(
            id=domain.id,
            title=domain.title,
            content=domain.content or None,
            summary=domain.summary or None,
            source=domain.source or None,
            url=domain.url or None,
            category=domain.category or None,
            symbols=json.dumps(domain.symbols, ensure_ascii=False) if domain.symbols else None,
            published_at=domain.publish_date.isoformat() if domain.publish_date else None,
            sentiment=domain.sentiment_label or "neutral",
            sentiment_score=domain.sentiment,
            data_source=domain.data_source or "rss",
            created_at=domain.created_at,
        )
