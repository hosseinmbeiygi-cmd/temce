"""Regression tests for the ``?from``/``?to`` date-range filter on the
``/news`` endpoints.

Covers the filter wired through the whole stack on the migration-0054
``published_at_ts`` TIMESTAMP column:

* ``parse_news_date_range``: ISO-8601 forms, bare-date ``?to`` whole-day
  expansion, naive-as-UTC, one-sided windows, error messages.
* ``list_news`` / ``search_news`` / ``news_by_symbol``: date filtering and
  composition with the existing ``category`` filter, invalid input -> error
  payload, params forwarded to the service layer.
* ``_NewsDbRepo._published_range``: clause generation against the real
  Postgres ``news_articles`` table (skipped without ``DATABASE_URL``), plus
  an end-to-end ``repo.list(date_from=..., date_to=...)`` run.

The endpoint tests use the real router functions with a stubbed
``NewsService`` — no HTTP server, mirroring ``test_news_category.py``.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from apps.api.endpoints import news as news_endpoint
from apps.api.endpoints.news import (
    list_news,
    news_by_category,
    news_by_symbol,
    parse_news_date_range,
    search_news,
    trending_news,
)
from core.result import PaginatedResult, Result
from domain.news.news_item import NewsItem

_MARK = "test_dtr"  # row marker for DB-test cleanup


# ── helpers ──────────────────────────────────────────────────────────────


def _news_item(news_id: str, category: str = "market", pub: datetime | None = None) -> NewsItem:
    return NewsItem(
        id=news_id,
        title=f"title {news_id}",
        summary="sum",
        source="rss",
        url=f"https://example.test/{news_id}",
        publish_date=pub or datetime(2026, 9, 16, 10, 0, tzinfo=UTC),
        category=category,
    )


def _stub_service(items: list[NewsItem], capture: dict[str, Any] | None = None) -> AsyncMock:
    """Stub NewsService mirroring the repo contract: the date window is
    applied at the DB layer, so the stub filters by ``publish_date`` when
    ``date_from``/``date_to`` are passed — letting the tests verify the full
    endpoint contract against realistic service semantics."""

    def _filter(items_: list[NewsItem], **kwargs: Any) -> list[NewsItem]:
        f, t = kwargs.get("date_from"), kwargs.get("date_to")
        if f is None and t is None:
            return list(items_)
        return [
            i for i in items_
            if i.publish_date is not None
            and (f is None or i.publish_date >= f)
            and (t is None or i.publish_date <= t)
        ]

    async def _list_all(*args: Any, **kwargs: Any):
        if capture is not None:
            capture["list_all"] = kwargs
        kept = _filter(items, **kwargs)
        return Result.ok(
            PaginatedResult(items=kept, total=len(kept), page=1, page_size=50, total_pages=1)
        )

    async def _search(*args: Any, **kwargs: Any):
        if capture is not None:
            capture["search"] = kwargs
        kept = _filter(items, **kwargs)
        return Result.ok(
            PaginatedResult(items=kept, total=len(kept), page=1, page_size=50, total_pages=1)
        )

    async def _get_by_symbol(*args: Any, **kwargs: Any):
        if capture is not None:
            capture["get_by_symbol"] = kwargs
        kept = _filter(items, **kwargs)
        return Result.ok(
            PaginatedResult(items=kept, total=len(kept), page=1, page_size=50, total_pages=1)
        )

    service = AsyncMock()
    service.list_all.side_effect = _list_all
    service.search.side_effect = _search
    service.get_by_symbol.side_effect = _get_by_symbol
    return service


# ── parse_news_date_range ───────────────────────────────────────────────


class TestParseDateRange:
    def test_absent_params_return_none(self):
        assert parse_news_date_range(None, None) is None
        assert parse_news_date_range("", "") is None

    def test_bare_dates(self):
        f, t = parse_news_date_range("2026-09-01", "2026-09-16")
        assert f == datetime(2026, 9, 1, tzinfo=UTC)
        # bare ?to includes the whole day
        assert t == datetime(2026, 9, 16, 23, 59, 59, tzinfo=UTC)

    def test_full_iso_datetimes(self):
        f, t = parse_news_date_range("2026-09-01T08:30:00Z", "2026-09-16T10:00:00Z")
        assert f == datetime(2026, 9, 1, 8, 30, tzinfo=UTC)
        assert t == datetime(2026, 9, 16, 10, 0, tzinfo=UTC)

    def test_offset_and_naive_forms(self):
        f, t = parse_news_date_range("2026-09-01T12:00:00+03:30", "2026-09-16T10:00")
        assert f.utcoffset().total_seconds() == 3.5 * 3600
        # naive values are read as UTC
        assert t == datetime(2026, 9, 16, 10, 0, tzinfo=UTC)

    def test_one_sided_windows(self):
        f, t = parse_news_date_range("2026-09-01", None)
        assert f is not None and t is None
        f, t = parse_news_date_range(None, "2026-09-16")
        assert f is None and t is not None

    def test_garbage_input_raises_with_hint(self):
        with pytest.raises(ValueError) as exc:
            parse_news_date_range("yesterday", None)
        assert "Invalid from" in str(exc.value)
        assert "ISO-8601" in str(exc.value)
        with pytest.raises(ValueError) as exc:
            parse_news_date_range(None, "2026-13-99")
        assert "Invalid to" in str(exc.value)


# ── endpoint wiring ──────────────────────────────────────────────────────


class TestListNewsDateFilter:
    @pytest.mark.asyncio
    async def test_filters_outside_window(self):
        items = [
            _news_item("old", pub=datetime(2026, 1, 1, tzinfo=UTC)),
            _news_item("in", pub=datetime(2026, 9, 10, tzinfo=UTC)),
        ]
        result = await list_news(
            page=1, page_size=50, category=None, from_="2026-09-01", to="2026-09-30",
            service=_stub_service(items), session=AsyncMock(),
        )
        assert [i.id for i in result.data.items] == ["in"]

    @pytest.mark.asyncio
    async def test_composes_with_category(self):
        items = [
            _news_item("mkt", category="market", pub=datetime(2026, 9, 10, tzinfo=UTC)),
            _news_item("cmp", category="companies", pub=datetime(2026, 9, 10, tzinfo=UTC)),
            _news_item("old", category="market", pub=datetime(2026, 1, 1, tzinfo=UTC)),
        ]
        result = await list_news(
            page=1, page_size=50, category="market", from_="2026-09-01", to=None,
            service=_stub_service(items), session=AsyncMock(),
        )
        assert [i.id for i in result.data.items] == ["mkt"]

    @pytest.mark.asyncio
    async def test_no_params_keeps_unfiltered_behavior(self):
        items = [_news_item("a"), _news_item("b")]
        result = await list_news(
            page=1, page_size=50, category=None, from_=None, to=None,
            service=_stub_service(items), session=AsyncMock(),
        )
        assert len(result.data.items) == 2

    @pytest.mark.asyncio
    async def test_invalid_from_returns_error_payload(self):
        result = await list_news(
            page=1, page_size=50, category=None, from_="not-a-date", to=None,
            service=AsyncMock(), session=AsyncMock(),
        )
        assert result.success is False
        assert result.error is not None and "Invalid from" in result.error["message"]

    @pytest.mark.asyncio
    async def test_params_forwarded_to_service(self):
        capture: dict[str, Any] = {}
        service = _stub_service([], capture=capture)
        await list_news(
            page=1, page_size=50, category=None,
            from_="2026-09-01T00:00:00Z", to="2026-09-16",
            service=service, session=AsyncMock(),
        )
        kw = capture["list_all"]
        assert kw["date_from"] == datetime(2026, 9, 1, tzinfo=UTC)
        assert kw["date_to"] == datetime(2026, 9, 16, 23, 59, 59, tzinfo=UTC)


class TestSearchAndSymbolDateFilter:
    @pytest.mark.asyncio
    async def test_search_filters_by_window(self):
        items = [
            _news_item("in", pub=datetime(2026, 9, 10, tzinfo=UTC)),
            _news_item("old", pub=datetime(2026, 1, 1, tzinfo=UTC)),
        ]
        result = await search_news(
            q="title", page=1, page_size=50, from_="2026-09-01", to=None,
            service=_stub_service(items),
        )
        assert [i.id for i in result.data.items] == ["in"]

    @pytest.mark.asyncio
    async def test_search_invalid_to_is_error(self):
        result = await search_news(
            q="x", page=1, page_size=50, from_=None, to="32nd of Mordad",
            service=AsyncMock(),
        )
        assert result.success is False and "Invalid to" in result.error["message"]

    @pytest.mark.asyncio
    async def test_symbol_route_forwards_window(self):
        capture: dict[str, Any] = {}
        service = _stub_service([], capture=capture)
        await news_by_symbol(
            symbol="فولاد", page=1, page_size=50,
            from_=None, to="2026-09-16", service=service,
        )
        kw = capture["get_by_symbol"]
        assert kw["date_to"] == datetime(2026, 9, 16, 23, 59, 59, tzinfo=UTC)
        assert kw["date_from"] is None


# ── repo clause generation + real-DB behavior ────────────────────────────


class TestCategoryAndTrendingDateFilter:
    """``?from``/``?to`` on the category and trending routes."""

    @pytest.mark.asyncio
    async def test_category_filters_by_window(self):
        items = [
            _news_item("mkt_old", category="market", pub=datetime(2026, 1, 1, tzinfo=UTC)),
            _news_item("mkt_in", category="market", pub=datetime(2026, 9, 10, tzinfo=UTC)),
        ]
        result = await news_by_category(
            category="market", page=1,
            from_="2026-09-01", to=None,
            service=_stub_service(items), session=AsyncMock(),
        )
        assert [i.id for i in result.data] == ["mkt_in"]

    @pytest.mark.asyncio
    async def test_category_invalid_from_is_error(self):
        result = await news_by_category(
            category="market", page=1,
            from_="nonsense", to=None,
            service=AsyncMock(), session=AsyncMock(),
        )
        assert result.success is False
        assert "Invalid from" in result.error["message"]

    @pytest.mark.asyncio
    async def test_trending_filters_by_window(self):
        items = [
            _news_item("t_old", pub=datetime(2026, 1, 1, tzinfo=UTC)),
            _news_item("t_in", pub=datetime(2026, 9, 10, tzinfo=UTC)),
        ]
        result = await trending_news(
            limit=10, from_="2026-09-01", to="2026-09-30",
            service=_stub_service(items), session=AsyncMock(),
        )
        assert [i.id for i in result.data] == ["t_in"]

    @pytest.mark.asyncio
    async def test_trending_no_params_returns_unfiltered(self):
        items = [_news_item("a"), _news_item("b")]
        result = await trending_news(
            limit=10, from_=None, to=None,
            service=_stub_service(items), session=AsyncMock(),
        )
        assert len(result.data) == 2


class TestPublishedRangeClauses:
    def test_both_none_yields_no_clauses(self):
        from repositories.news_repository import _NewsDbRepo

        assert _NewsDbRepo._published_range(None, None) == []

    def test_clauses_reference_coalesce(self):
        from sqlalchemy import func
        from models.news import NewsArticleModel
        from repositories.news_repository import _NewsDbRepo

        clauses = _NewsDbRepo._published_range(datetime(2026, 1, 1), datetime(2026, 9, 1))
        assert len(clauses) == 2
        # each clause compares COALESCE(published_at_ts, created_at) to a bound
        for clause, bound in zip(clauses, (datetime(2026, 1, 1), datetime(2026, 9, 1))):
            compiled = str(
                clause.compile(compile_kwargs={"literal_binds": True})
            )
            assert "coalesce" in compiled.lower()
            assert "published_at_ts" in compiled
            assert "created_at" in compiled
        _ = func  # imported for readability symmetry


class TestDbRepoDateFilter:
    """End-to-end against real Postgres (skipped offline), marked rows only."""

    @pytest.mark.asyncio
    async def test_list_respects_window(self):
        url = os.environ.get("DATABASE_URL") or ""
        if not url:
            pytest.skip("DATABASE_URL not set")
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        eng = create_async_engine(url)
        marker = f"{_MARK}_{uuid.uuid4().hex[:8]}"
        maker = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with maker() as session:
                try:
                    await session.execute(
                        text(
                            "INSERT INTO news_articles "
                            "(id, title, source, url, category, published_at, published_at_ts, created_at) "
                            "VALUES (:i, :t, :s, :u, 'market', :p, :pts, now())"
                        ),
                        [
                            # naive UTC values — the column is
                            # ``timestamp without time zone`` (UTC by
                            # convention), mirroring the production rows.
                            dict(i=f"{marker}_old", t=f"{marker} old", s=f"{marker}src",
                                 u=f"https://x.test/{marker}_old", p="2026-01-01T00:00:00+00:00",
                                 pts=datetime(2026, 1, 1)),
                            dict(i=f"{marker}_in", t=f"{marker} in", s=f"{marker}src",
                                 u=f"https://x.test/{marker}_in", p="2026-09-10T00:00:00+00:00",
                                 pts=datetime(2026, 9, 10)),
                        ],
                    )
                    await session.commit()
                except Exception as exc:
                    import logging

                    logging.getLogger(__name__).warning("DB-test setup failed: %s", exc)
                    pytest.skip(f"news_articles setup failed: {type(exc).__name__}")

                from repositories.news_repository import NewsRepository

                repo = NewsRepository(session=session)
                # Corpus-independent checks (15k+ real rows share the table,
                # so page-1 membership assertions would be fragile):
                # 1. search scoped to the marker title + Sep window -> only _in
                search = await repo.search(
                    marker, page=1, page_size=50,
                    date_from=datetime(2026, 9, 1, tzinfo=UTC),
                    date_to=datetime(2026, 9, 30, tzinfo=UTC),
                )
                assert [i.id for i in search.value.items] == [f"{marker}_in"]

                # 2. same marker, 2099 window -> nothing matches the predicate
                empty = await repo.search(
                    marker, page=1, page_size=50,
                    date_from=datetime(2099, 1, 1, tzinfo=UTC),
                    date_to=datetime(2099, 12, 31, tzinfo=UTC),
                )
                assert empty.value.total == 0

                # 3. list() over a 2099 window excludes the whole corpus
                future = await repo.list(page=1, page_size=10,
                                         date_from=datetime(2099, 1, 1, tzinfo=UTC),
                                         date_to=datetime(2099, 12, 31, tzinfo=UTC))
                assert future.value.total == 0
        finally:
            # cleanup marked rows
            async with maker() as session:
                await session.execute(
                    text("DELETE FROM news_articles WHERE id LIKE :p"), {"p": f"{marker}%"}
                )
                await session.commit()
            await eng.dispose()
