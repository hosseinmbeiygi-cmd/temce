from __future__ import annotations

import contextlib
import json
from datetime import UTC, datetime

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from core.dbcompat import naive_utc
from core.logging import get_logger
from core.result import PaginatedResult, Result
from services.news_read_canary import ReadPathDecision, compare_page

logger = get_logger(__name__)
from domain.news.news_item import NewsItem
from models.news import NewsArticleModel
from repositories.base_repository import InMemoryRepository
from repositories.db_base import DbRepository
from repositories.news_items_read_repo import NewsItemsReadRepo


class NewsRepository:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session
        self._mem: InMemoryRepository[NewsItem] | None = None if session else InMemoryRepository[NewsItem]()
        self._db: _NewsDbRepo | None = None if not session else _NewsDbRepo(session)
        # Canary READ path (NEWS_READ_MODE off/shadow/canary/full + legacy
        # boolean NEWS_READ_FROM_ITEMS forcing full): serves list/search/
        # get_by_symbol from the new ``news_items`` schema (migration 0054)
        # per services.news_read_canary, with shadow comparison in non-full
        # modes. Writes ALWAYS stay on the legacy repo + dual-write, so any
        # mode flip is data-safe both ways.
        self._items_read: "NewsItemsReadRepo | None" = (
            NewsItemsReadRepo(session) if session and NewsItemsReadRepo.is_enabled() else None
        )

    async def _route(self, discriminator: str) -> "tuple[ReadPathDecision, Any, Any]":
        """Resolve the canary decision and return (decision, legacy_repo,
        items_repo) for one read request. Legacy/mem repo may be None only
        when neither exists (degenerate test setups)."""
        from services.news_read_canary import decide, resolve_mode

        mode = await resolve_mode()
        decision = decide(mode, discriminator)
        legacy = self._db or self._mem
        items = self._items_read if (decision.serve_items or decision.shadow) else None
        return decision, legacy, items

    @property
    def reading_from_items(self) -> bool:
        """True when reads are currently served from ``news_items``."""
        return self._items_read is not None

    async def get(self, id: str) -> Result[NewsItem]:
        if self._db:
            return await self._db.get(id)
        return await self._mem.get(id)

    async def save(self, entity: NewsItem) -> Result[NewsItem]:
        if self._db:
            return await self._db.save(entity)
        return await self._mem.save(entity)

    async def exists_by_url_or_title(self, url: str, title: str) -> bool:
        if self._db:
            return await self._db.exists_by_url_or_title(url, title)
        return any(
            (url and n.url == url) or n.title == title
            for n in self._mem._store.values()
        )

    async def delete(self, id: str) -> Result[bool]:
        if self._db:
            return await self._db.delete(id)
        return await self._mem.delete(id)

    async def list(
        self,
        page: int = 1,
        page_size: int = 100,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> Result[PaginatedResult[NewsItem]]:
        decision, legacy, items = await self._route(f"list:{page}:{page_size}")
        served = None
        probed = None
        if decision.serve_items and items is not None:
            served = await items.list(page, page_size, date_from=date_from, date_to=date_to)
        elif legacy is not None:
            served = await (self._db or self._mem).list(page, page_size, date_from=date_from, date_to=date_to)
        if decision.shadow and items is not None and self._db is not None:
            try:
                probed = await self._items_read_probe(page, page_size, date_from, date_to)
            except Exception:  # noqa: BLE001 — probe failure must not break serving
                pass
        await self._record_parity(decision, served, probed)
        if served is not None:
            return served
        return await self._mem.list(page, page_size)

    async def search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 50,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> Result[PaginatedResult[NewsItem]]:
        decision, legacy, items = await self._route(f"search:{query}:{page}:{page_size}")
        served = None
        probed = None
        if decision.serve_items and items is not None:
            served = await self._items_read.search(query, page, page_size, date_from=date_from, date_to=date_to)
        elif self._db is not None:
            served = await self._db.search(query, page, page_size, date_from=date_from, date_to=date_to)
        elif self._mem is not None:
            q = query.lower()
            matches = [n for n in self._mem._store.values() if q in n.title.lower() or q in n.content.lower()]
            total = len(matches)
            start = (page - 1) * page_size
            served = Result.ok(
                PaginatedResult(
                    items=matches[start : start + page_size],
                    total=total,
                    page=page,
                    page_size=page_size,
                    total_pages=max(1, (total + page_size - 1) // page_size),
                )
            )
        if decision.shadow and items is not None and self._db is not None:
            try:
                probed = await self._items_read.search(query, page, page_size, date_from=date_from, date_to=date_to)
            except Exception:  # noqa: BLE001
                pass
        await self._record_parity(decision, served, probed)
        if served is not None:
            return served
        return Result.ok(PaginatedResult(items=[], total=0, page=page, page_size=page_size, total_pages=1))
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

    async def get_by_symbol(
        self,
        symbol: str,
        page: int = 1,
        page_size: int = 50,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> Result[PaginatedResult[NewsItem]]:
        decision, legacy, items = await self._route(f"symbol:{symbol}:{page}:{page_size}")
        served = None
        probed = None
        if decision.serve_items and items is not None:
            served = await self._items_read.get_by_symbol(symbol, page, page_size, date_from=date_from, date_to=date_to)
        elif self._db is not None:
            served = await self._db.get_by_symbol(symbol, page, page_size, date_from=date_from, date_to=date_to)
        elif self._mem is not None:
            matches = [n for n in self._mem._store.values() if symbol in n.symbols]
            total = len(matches)
            start = (page - 1) * page_size
            served = Result.ok(
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
        if decision.shadow and items is not None and self._db is not None:
            try:
                probed = await self._items_read.get_by_symbol(
                    symbol, page, page_size, date_from=date_from, date_to=date_to
                )
            except Exception:  # noqa: BLE001
                pass
        await self._record_parity(decision, served, probed)
        if served is not None:
            return served
        return Result.ok(PaginatedResult(items=[], total=0, page=page, page_size=page_size, total_pages=1))

    async def _items_read_probe(self, page, page_size, date_from, date_to):
        """Shadow probe of list() on the items repo (kept separate so the
        legacy-served list() path stays symmetric with search/symbol)."""
        return await self._items_read.list(page, page_size, date_from=date_from, date_to=date_to)

    async def _record_parity(
        self,
        decision: "ReadPathDecision",
        served: Result[PaginatedResult[NewsItem]] | None,
        probed: Result[PaginatedResult[NewsItem]] | None,
    ) -> None:
        """Fire-and-forget parity accounting — never raises, never blocks
        the response on anything but the tiny counter write."""
        from services.news_read_canary import record

        try:
            if not decision.shadow:
                await record(decision, compared=False, parity=False)
                return
            legacy_page = served.value if served is not None and served.success else None
            items_page = probed.value if probed is not None and probed.success else None
            parity = await compare_page(legacy_page, items_page)
            if not parity:
                # Directional attribution: parity_divergent covers BOTH
                # true regressions (items missing rows legacy serves) and
                # *deliberate* improvements (the new path resolves
                # spelling variants + tag aliases the legacy LIKE-match
                # cannot, e.g. /symbol/وبانك finds the وبانک-tagged
                # items). Auto-halt must only trip on regressions, so
                # improvements are counted separately.
                _l = legacy_page.total if legacy_page is not None else 0
                _i = items_page.total if items_page is not None else 0
                kind = "items_superset" if _i > _l else "true_divergence"
                await record(decision, compared=True, parity=False, divergence_kind=kind)
            else:
                await record(decision, compared=True, parity=parity)
        except Exception:  # noqa: BLE001 — accounting must never break reads
            logger.debug("news read-path parity accounting failed", exc_info=True)


class _NewsDbRepo(DbRepository[NewsItem, NewsArticleModel]):
    model_class = NewsArticleModel

    @staticmethod
    def _naive_utc(dt: datetime) -> datetime:
        """Thin wrapper over :func:`core.dbcompat.naive_utc` (trap #2:
        asyncpg rejects aware datetimes against naive-timestamp columns)."""
        return naive_utc(dt)

    @staticmethod
    def _published_range(
        date_from: datetime | None,
        date_to: datetime | None,
    ):
        """SQLAlchemy where-clause for the ``?from``/``?to`` window.

        Filters on the migration-0054 ``published_at_ts`` TIMESTAMP column
        (falls back to ``created_at`` when the backfill has not run in this
        environment yet). ``date_to`` is inclusive because clients naturally
        expect ``?to=2026-09-17`` to contain that whole day; bounds are
        normalized to naive UTC (see :meth:`_naive_utc`).
        """
        clauses = []
        if date_from is not None:
            clauses.append(
                func.coalesce(
                    NewsArticleModel.published_at_ts, NewsArticleModel.created_at
                ) >= _NewsDbRepo._naive_utc(date_from)
            )
        if date_to is not None:
            clauses.append(
                func.coalesce(
                    NewsArticleModel.published_at_ts, NewsArticleModel.created_at
                ) <= _NewsDbRepo._naive_utc(date_to)
            )
        return clauses

    async def exists_by_url_or_title(self, url: str, title: str) -> bool:
        """Check if an article with the same URL or title already exists in DB."""
        conditions = [NewsArticleModel.title == title]
        if url:
            conditions.append(NewsArticleModel.url == url)
        stmt = select(NewsArticleModel.id).where(or_(*conditions)).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def list(
        self,
        page: int = 1,
        page_size: int = 100,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> Result[PaginatedResult[NewsItem]]:
        # Filter: only articles with a source (exclude legacy NULL-source ISNA articles)
        source_filter = NewsArticleModel.source.isnot(None) & (NewsArticleModel.source != "")

        # Inner: DISTINCT ON (title) — one row per title, newest first.
        # Ordering key = TIMESTAMP (published_at_ts), NOT the VARCHAR
        # published_at string — lexical sort of ISO strings with mixed
        # offsets mis-orders rows and diverges from the news_items read
        # path (canary parity requirement).
        _pub_ts = func.coalesce(NewsArticleModel.published_at_ts, NewsArticleModel.created_at)
        inner = (
            select(NewsArticleModel)
            .where(
                source_filter,
                *self._published_range(date_from, date_to),
            )
            .distinct(NewsArticleModel.title)
            .order_by(NewsArticleModel.title, desc(_pub_ts).nullslast())
        ).subquery()

        # Count unique titles
        count_stmt = select(func.count()).select_from(inner)
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Outer: re-order by published TIMESTAMP DESC for pagination.
        # title tie-break mirrors the news_items ordering exactly (titles
        # are identical across schemas) so ties are deterministic in both
        # plans and parity holds for same-timestamp bursts.
        alias = aliased(NewsArticleModel, inner)
        _alias_pub_ts = func.coalesce(alias.published_at_ts, alias.created_at)
        stmt = (
            select(alias)
            .order_by(desc(_alias_pub_ts).nullslast(), desc(alias.title))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
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

    async def search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 50,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> Result[PaginatedResult[NewsItem]]:
        q = f"%{query.lower()}%"
        source_filter = NewsArticleModel.source.isnot(None) & (NewsArticleModel.source != "")
        where_clause = or_(NewsArticleModel.title.ilike(q), NewsArticleModel.content.ilike(q)) & source_filter
        for clause in self._published_range(date_from, date_to):
            where_clause = where_clause & clause

        count_stmt = (
            select(func.count())
            .select_from(NewsArticleModel)
            .where(where_clause)
        )
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = (
            select(NewsArticleModel)
            .where(where_clause)
            .order_by(
                desc(func.coalesce(NewsArticleModel.published_at_ts, NewsArticleModel.created_at)).nullslast(),
                desc(NewsArticleModel.title),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
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

    async def get_by_symbol(
        self,
        symbol: str,
        page: int = 1,
        page_size: int = 50,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> Result[PaginatedResult[NewsItem]]:
        q = f"%{symbol}%"
        source_filter = NewsArticleModel.source.isnot(None) & (NewsArticleModel.source != "")
        where_clause = NewsArticleModel.symbols.ilike(q) & source_filter
        for clause in self._published_range(date_from, date_to):
            where_clause = where_clause & clause

        count_stmt = (
            select(func.count())
            .select_from(NewsArticleModel)
            .where(where_clause)
        )
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = (
            select(NewsArticleModel)
            .where(where_clause)
            .order_by(
                desc(func.coalesce(NewsArticleModel.published_at_ts, NewsArticleModel.created_at)).nullslast(),
                desc(NewsArticleModel.title),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
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
        # Normalize to second precision — `isoformat()` on a datetime with
        # microseconds (e.g. `datetime.now(UTC)`) yields a 36-char string that
        # exceeds the published_at VARCHAR(30) column and raises
        # StringDataRightTruncationError. Stripping microseconds keeps every
        # value <= 25 chars regardless of column width.
        pub_str: str | None = None
        if domain.publish_date:
            pd = domain.publish_date
            if hasattr(pd, "replace"):
                pd = pd.replace(microsecond=0)
            pub_str = pd.isoformat()
        return NewsArticleModel(
            id=domain.id,
            title=domain.title,
            content=domain.content or None,
            summary=domain.summary or None,
            source=domain.source or None,
            url=domain.url or None,
            category=domain.category or None,
            symbols=json.dumps(domain.symbols, ensure_ascii=False) if domain.symbols else None,
            published_at=pub_str,
            sentiment=domain.sentiment_label or "neutral",
            sentiment_score=domain.sentiment,
            data_source=domain.data_source or "rss",
            created_at=domain.created_at,
        )
