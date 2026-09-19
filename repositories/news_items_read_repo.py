"""Read repository for the new ``news_items`` schema (migration 0054).

Serves the /news read endpoints from the new tables when
``settings.news_read_from_items`` is True. The legacy repo
(``NewsRepository``/``_NewsDbRepo`` on ``news_articles``) stays the default
read path and the only write path; this class is purely additive read-side
logic so the flag can be flipped back at any time without data risk.

Domain mapping (``news_items`` -> ``domain.news.NewsItem``):

* ``body`` -> ``content`` and ``summary`` (the new schema has no separate
  summary column; the old row shape is preserved as closely as possible)
* ``published_at`` -> ``publish_date`` (a real TIMESTAMP in this schema —
  no string parsing, unlike the legacy repo)
* ``source_url`` -> ``url``
* symbol tags (``news_tags`` rows with ``tag_type='stock_symbol'``) ->
  ``symbols`` (one batched query per page)
* ids are prefixed ``ni_`` (news-item) to stay disjoint from legacy
  ``news_*`` string ids in API consumers
* ordering: newest first by COALESCE(published_at, created_at), matching
  the legacy repo's semantics; date windows are inclusive like
  ``_NewsDbRepo._published_range`` and normalized to naive UTC
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Select, desc, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.dbcompat import naive_utc
from core.logging import get_logger
from core.result import PaginatedResult, Result
from domain.news.news_item import NewsItem
from models.news_items import NewsItemModel, NewsTagModel

logger = get_logger(__name__)


class NewsItemsReadRepo:
    """DB-backed read access to ``news_items`` with legacy-shaped results."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def is_enabled() -> bool:
        return bool(getattr(settings, "news_read_from_items", False))

    @staticmethod
    def _naive_utc(dt: datetime) -> datetime:
        """Thin wrapper over :func:`core.dbcompat.naive_utc` (trap #2)."""
        return naive_utc(dt)

    def _order_expr(self):
        return desc(func.coalesce(NewsItemModel.published_at, NewsItemModel.created_at))

    @staticmethod
    def _to_domain(item: NewsItemModel, symbols: list[str]) -> NewsItem:
        return NewsItem(
            id=f"ni_{item.id}",
            title=item.title,
            content=item.body or "",
            summary=item.body or "",
            source=item.source or "",
            url=item.source_url or "",
            publish_date=item.published_at or item.created_at,
            category=item.category or "",
            sentiment=0.0,
            sentiment_label="neutral",
            symbols=symbols,
            data_source="news_items",
            created_at=item.created_at,
        )

    async def _symbols_for(self, ids: list[int]) -> dict[int, list[str]]:
        """Batched stock_symbol tags for one page of items."""
        if not ids:
            return {}
        rows = await self.session.execute(
            select(NewsTagModel.news_id, NewsTagModel.tag_value).where(
                NewsTagModel.news_id.in_(ids),
                NewsTagModel.tag_type == "stock_symbol",
            )
        )
        mapping: dict[int, list[str]] = {}
        for news_id, tag_value in rows.all():
            mapping.setdefault(int(news_id), []).append(tag_value or "")
        return {k: sorted({v for v in vals if v}) for k, vals in mapping.items()}

    def _window_clauses(
        self, date_from: datetime | None, date_to: datetime | None
    ) -> list:
        col = func.coalesce(NewsItemModel.published_at, NewsItemModel.created_at)
        clauses = []
        if date_from is not None:
            clauses.append(col >= self._naive_utc(date_from))
        if date_to is not None:
            clauses.append(col <= self._naive_utc(date_to))
        return clauses

    async def _run_query(
        self,
        stmt: Select,
        page: int,
        page_size: int,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> Result[PaginatedResult[NewsItem]]:
        for clause in self._window_clauses(date_from, date_to):
            stmt = stmt.where(clause)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        result = await self.session.execute(
            stmt.order_by(self._order_expr())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = result.scalars().all()

        symbols_map = await self._symbols_for([r.id for r in rows])
        items = [
            self._to_domain(r, symbols_map.get(r.id, [])) for r in rows
        ]
        return Result.ok(
            PaginatedResult(
                items=items,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=max(1, (total + page_size - 1) // page_size),
            )
        )

    async def list(
        self,
        page: int = 1,
        page_size: int = 100,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> Result[PaginatedResult[NewsItem]]:
        return await self._run_query(
            select(NewsItemModel), page, page_size, date_from, date_to
        )

    async def search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 50,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> Result[PaginatedResult[NewsItem]]:
        q = f"%{query.lower()}%"
        stmt = select(NewsItemModel).where(
            or_(
                func.lower(NewsItemModel.title).like(q),
                func.lower(NewsItemModel.body).like(q),
            )
        )
        return await self._run_query(stmt, page, page_size, date_from, date_to)

    async def get_by_symbol(
        self,
        symbol: str,
        page: int = 1,
        page_size: int = 50,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> Result[PaginatedResult[NewsItem]]:
        """Items tagged with ``symbol`` — matching against *every* spelling
        variant of it (exact ``tag_value`` IN-match, not LIKE).

        Variants = the canonical symbol + its Persian/Arabic spellings +
        any persisted alias from ``news_tag_symbol_map`` (manual mappings
        included), so ``/news/symbol/وبانك`` also returns items the tagger
        wrote as ``وبانک``. Degrades to pure spelling variants when the
        mapping table is absent (pre-0059 environments).
        """
        variants: set[str] = set()
        try:
            from services.news_tag_symbol_mapper import (
                NewsTagSymbolMapper,
                _spelling_variants,
            )

            variants |= _spelling_variants(symbol)
            variants |= await NewsTagSymbolMapper(self.session).tag_values_for_symbol(symbol)
        except Exception:  # noqa: BLE001 — read path must never hard-fail on mapping
            logger.debug("tag_variant lookup failed; using spelling variants only", exc_info=True)
            variants = {symbol}
        stmt = select(NewsItemModel).where(
            exists(
                select(NewsTagModel.id).where(
                    NewsTagModel.news_id == NewsItemModel.id,
                    NewsTagModel.tag_type == "stock_symbol",
                    NewsTagModel.tag_value.in_(variants),
                )
            )
        )
        return await self._run_query(stmt, page, page_size, date_from, date_to)
