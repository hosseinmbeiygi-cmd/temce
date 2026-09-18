"""Tests for the ``NEWS_READ_FROM_ITEMS`` flag-gated read path.

The flag switches /news READS to the new ``news_items`` schema (migration
0054) without touching the write path (legacy + dual-write always run).
These tests run against real Postgres and are skipped when no DB is
reachable, mirroring ``test_news_dual_write.py``:

* flag default is False (legacy path stays the default)
* ``NewsRepository`` routes reads to ``news_items`` only when the flag is
  on AND a session exists; writes are never affected
* ``ni_`` id prefix keeps item ids disjoint from legacy ``news_*`` ids
* date windows (?from/?to) work identically on the new path
* get_by_symbol uses the exact structured tag match
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from core.result import Result

_MARK = "test_rd"  # row marker for cleanup


def _engine():
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("DATABASE_URL not set")
    try:
        from sqlalchemy.ext.asyncio import create_async_engine

        return create_async_engine(url)
    except Exception:
        pytest.skip("DB not reachable")


# ── flag defaults ────────────────────────────────────────────────────────


class TestFlagDefaults:
    def test_flag_defaults_off(self):
        from core.config import settings

        assert settings.news_read_from_items is False

    def test_repo_without_session_never_routes_to_items(self):
        from repositories.news_repository import NewsRepository

        repo = NewsRepository(session=None)
        assert repo.reading_from_items is False

    def test_repo_with_session_flag_off_stays_legacy(self, monkeypatch):
        from unittest.mock import MagicMock

        from core.config import settings as real_settings
        from repositories.news_repository import NewsRepository
        from repositories.news_items_read_repo import NewsItemsReadRepo

        # flag explicitly False
        monkeypatch.setattr(real_settings, "news_read_from_items", False, raising=False)
        repo = NewsRepository(session=MagicMock())
        assert repo.reading_from_items is False
        assert NewsItemsReadRepo.is_enabled() is False


# ── DB-backed routing + behavior ─────────────────────────────────────────


class TestItemsReadPath:
    @pytest.fixture()
    def db_env(self):
        eng = _engine()
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            yield eng, loop
        finally:
            loop.close()
            import asyncio as _a

            _a.set_event_loop(None)
            # engine disposal happens inside the test loop
        eng.sync_engine.dispose()

    @pytest.mark.asyncio
    async def test_flag_on_routes_reads_to_items(self, monkeypatch):
        url = os.environ.get("DATABASE_URL") or ""
        if not url:
            pytest.skip("DATABASE_URL not set")
        from unittest.mock import MagicMock

        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from core.config import settings as real_settings
        from domain.news.news_item import NewsItem
        from repositories.news_repository import NewsRepository

        eng = create_async_engine(url)
        marker = f"{_MARK}_{uuid.uuid4().hex[:8]}"
        maker = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with maker() as session:
                # seed one legacy + one news_items row
                await session.execute(
                    text(
                        "INSERT INTO news_articles (id, title, source, url, category, published_at, published_at_ts, created_at) "
                        "VALUES (:i, :t, :s, :u, 'market', :p, :pts, now())"
                    ),
                    dict(i=f"{marker}_leg", t=f"{marker} legacy row", s=f"{marker}src",
                         u=f"https://x.test/{marker}_leg", p="2026-09-10T08:00:00+00:00",
                         pts=datetime(2026, 9, 10, 8, 0)),
                )
                res = await session.execute(
                    text(
                        "INSERT INTO news_items (title, body, source, source_url, published_at, category, is_breaking, dedup_hash) "
                        "VALUES (:t, :b, :s, :u, :p, 'market', FALSE, :h) RETURNING id"
                    ),
                    dict(t=f"{marker} items row", b=f"{marker} body", s=f"{marker}src",
                         u=f"https://x.test/{marker}_it", p=datetime(2026, 9, 10, 9, 0),
                         h=f"hash_{marker}"),
                )
                item_id = res.scalar_one()
                await session.execute(
                    text("INSERT INTO news_tags (news_id, tag_type, tag_value, confidence) "
                         "VALUES (:n, 'stock_symbol', :v, 1.0)"),
                    dict(n=item_id, v="فولاد"),
                )
                await session.commit()

                # ── flag OFF: legacy read wins, items row invisible ──
                monkeypatch.setattr(real_settings, "news_read_from_items", False, raising=False)
                repo_off = NewsRepository(session=session)
                assert repo_off.reading_from_items is False
                off = await repo_off.search(marker)
                assert off.success
                assert all(not i.id.startswith("ni_") for i in off.value.items)

                # ── flag ON: reads served from news_items ──
                monkeypatch.setattr(real_settings, "news_read_from_items", True, raising=False)
                repo_on = NewsRepository(session=session)
                assert repo_on.reading_from_items is True

                found = await repo_on.search(marker)
                assert found.success
                ids = [i.id for i in found.value.items]
                assert ids == [f"ni_{item_id}"]

                # domain mapping
                only = found.value.items[0]
                assert isinstance(only, NewsItem)
                assert only.title == f"{marker} items row"
                assert only.content == f"{marker} body"
                assert only.summary == f"{marker} body"
                assert only.url == f"https://x.test/{marker}_it"
                assert only.publish_date == datetime(2026, 9, 10, 9, 0)
                assert only.category == "market"
                assert only.symbols == ["فولاد"]
                assert only.data_source == "news_items"

                # list() + pagination shape
                listed = await repo_on.list(page=1, page_size=5)
                assert listed.success and listed.value.page_size == 5

                # date window (?from/?to) works on the new path — scoped via
                # search() because page 1 of list() over the 15k corpus holds
                # only the newest rows, not the seeded marker.
                window = await repo_on.search(
                    marker, page=1, page_size=5,
                    date_from=datetime(2026, 9, 1, tzinfo=UTC),
                    date_to=datetime(2026, 9, 30, tzinfo=UTC),
                )
                assert window.success
                assert [i.id for i in window.value.items] == [f"ni_{item_id}"]

                # empty future window -> nothing
                future = await repo_on.list(
                    page=1, page_size=5,
                    date_from=datetime(2099, 1, 1, tzinfo=UTC),
                    date_to=datetime(2099, 12, 31, tzinfo=UTC),
                )
                assert future.value.total == 0

                # get_by_symbol via structured tags (exact match)
                by_sym = await repo_on.get_by_symbol("فولاد", page=1, page_size=20)
                assert by_sym.success
                assert f"ni_{item_id}" in [i.id for i in by_sym.value.items]
        finally:
            async with maker() as session:
                await session.execute(
                    text("DELETE FROM news_articles WHERE id LIKE :p"), {"p": f"{marker}%"}
                )
                await session.execute(
                    text("DELETE FROM news_items WHERE title LIKE :p"), {"p": f"{marker}%"}
                )
                await session.commit()
            await eng.dispose()
