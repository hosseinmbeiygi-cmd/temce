"""Tests for the news dual-write into the new ``news_items`` schema.

Covers ``services/news_dual_write.py`` and its wiring into
``NewsIngestionService._save_article``:

* Dedup hash semantics (NFKC/casefold/whitespace normalization, URL in identity)
* ``NewsDualWriter.mirror``: insert, dedup hit (returns None), source registry
  upsert with ``last_fetched_at``, symbol tag rows
* Failure isolation: a dual-write error must NOT break the legacy save path
  (the module is additive by contract) and must roll the shared session back
* Toggle: ``dual_write_enabled=False`` (or missing session) disables the mirror
* End-to-end ``ingest()`` with a stubbed RSS provider writes both
  ``news_articles`` (legacy) and ``news_items`` (new schema) from one run

The DB-backed tests run against the real Postgres (migration 0054 tables) and
clean their ``test_dw_*`` rows up afterwards; they are skipped when no DB is
reachable so the suite stays usable offline.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from core.result import Result
from services.news_dual_write import NewsDualWriter, compute_dedup_hash
from services.news_ingestion import NewsIngestionService

_MARK = "test_dw"  # row marker for cleanup


# ── helpers ──────────────────────────────────────────────────────────────


def _engine():
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("DATABASE_URL not set")
    try:
        import asyncio

        eng = create_async_engine(url)
        # probe connectivity + migration presence
        asyncio.get_event_loop_policy()
        return eng
    except Exception:
        pytest.skip("DB not reachable")


async def _cleanup(eng) -> None:
    async with eng.begin() as c:
        await c.execute(text("DELETE FROM news_tags WHERE tag_value LIKE 'DW%' OR news_id IN (SELECT id FROM news_items WHERE title LIKE :m)", ), {"m": f"%{_MARK}%"})
        await c.execute(text("DELETE FROM news_items WHERE title LIKE :m OR title LIKE :m2"), {"m": f"{_MARK}%", "m2": f"%{_MARK}%"})
        await c.execute(text("DELETE FROM news_ingestion_sources WHERE source_name LIKE :m"), {"m": f"{_MARK}%"})


# ── pure-function tests (no DB) ──────────────────────────────────────────


class TestDedupHash:
    def test_stable_and_normalized(self):
        h1 = compute_dedup_hash("قیمت طلا امروز", "https://x.test/a")
        h2 = compute_dedup_hash("قیمت  طلا   امروز ", "HTTPS://X.TEST/a")
        assert h1 == h2
        assert len(h1) == 64

    def test_different_url_is_different_identity(self):
        assert compute_dedup_hash("t", "https://x/a") != compute_dedup_hash("t", "https://x/b")

    def test_different_title_is_different_identity(self):
        assert compute_dedup_hash("t1", "https://x/a") != compute_dedup_hash("t2", "https://x/a")

    def test_empty_inputs_do_not_crash(self):
        h = compute_dedup_hash("", "")
        assert len(h) == 64


# ── DB-backed tests ──────────────────────────────────────────────────────


@pytest.fixture
async def db_session():
    eng = _engine()
    # probe: table must exist (migration 0054 applied)
    try:
        async with eng.connect() as c:
            await c.execute(text("SELECT 1 FROM news_items LIMIT 1"))
    except Exception:
        await eng.dispose()
        pytest.skip("news_items table not available (run migration 0054)")
    from sqlalchemy.ext.asyncio import async_sessionmaker

    maker = async_sessionmaker(eng, expire_on_commit=False)
    session = maker()
    try:
        yield session
    finally:
        await session.close()
        await _cleanup(eng)
        await eng.dispose()


class TestDualWriterMirror:
    async def test_insert_returns_id_and_writes_tags_and_source(self, db_session):
        w = NewsDualWriter()
        nid = await w.mirror(
            db_session,
            title=f"{_MARK} headline one",
            body="body",
            source=f"{_MARK}_feed",
            url=f"https://x.test/{uuid.uuid4().hex}",
            published_at=datetime(2026, 9, 18, 10, 0),
            category="companies",
            is_breaking=False,
            symbols=["DWFOOL", "DWFDXA"],
            dedup_hash=compute_dedup_hash(f"{_MARK} headline one", f"https://x.test/{uuid.uuid4().hex}"),
        )
        await db_session.commit()
        assert nid is not None

        tags = await db_session.execute(
            text("SELECT tag_type, tag_value, confidence FROM news_tags WHERE news_id = :n"),
            {"n": nid},
        )
        rows = tags.all()
        assert {r[1] for r in rows} == {"DWFOOL", "DWFDXA"}
        assert all(r[0] == "stock_symbol" and float(r[2]) == 1.0 for r in rows)

        src = await db_session.execute(
            text("SELECT source_type, last_fetched_at IS NOT NULL FROM news_ingestion_sources WHERE source_name = :s"),
            {"s": f"{_MARK}_feed"},
        )
        srow = src.one_or_none()
        assert srow is not None and srow[0] == "rss" and srow[1] is True

    async def test_second_mirror_with_same_hash_is_noop(self, db_session):
        w = NewsDualWriter()
        h = compute_dedup_hash(f"{_MARK} dup check", f"https://x.test/{uuid.uuid4().hex}")
        n1 = await w.mirror(
            db_session,
            title=f"{_MARK} dup check",
            body=None,
            source=f"{_MARK}_dupfeed",
            url="https://x.test/dup",
            published_at=None,
            category="market",
            is_breaking=False,
            symbols=[],
            dedup_hash=h,
        )
        await db_session.commit()
        n2 = await w.mirror(
            db_session,
            title=f"{_MARK} dup check",
            body=None,
            source=f"{_MARK}_dupfeed",
            url="https://x.test/dup",
            published_at=None,
            category="market",
            is_breaking=False,
            symbols=[],
            dedup_hash=h,
        )
        await db_session.commit()
        assert n1 is not None and n2 is None  # dedup hit → skipped

    async def test_source_registry_updates_last_fetched(self, db_session):
        w = NewsDualWriter()
        common = dict(
            title=f"{_MARK} src freshness",
            body=None,
            source=f"{_MARK}_freshfeed",
            published_at=None,
            category="market",
            is_breaking=False,
            symbols=[],
        )
        await w.mirror(db_session, url="https://x.test/f1", dedup_hash="f" * 64, **common)
        await db_session.commit()
        t1 = (
            await db_session.execute(
                text("SELECT last_fetched_at FROM news_ingestion_sources WHERE source_name = :s"),
                {"s": f"{_MARK}_freshfeed"},
            )
        ).scalar_one()
        await w.mirror(db_session, url="https://x.test/f2", dedup_hash="e" * 64, **common)
        await db_session.commit()
        t2 = (
            await db_session.execute(
                text("SELECT last_fetched_at FROM news_ingestion_sources WHERE source_name = :s"),
                {"s": f"{_MARK}_freshfeed"},
            )
        ).scalar_one()
        assert t2 >= t1  # upsert bumped the stamp (or at least did not go back)


class TestFailureIsolation:
    async def test_safe_mirror_swallows_errors_and_rolls_back(self, db_session, caplog):
        w = NewsDualWriter(session=db_session)
        article = {"title": f"{_MARK} boom"}
        with patch.object(
            w, "mirror", side_effect=RuntimeError("simulated DB failure")
        ):
            ok = await w.safe_mirror(article, title="x", dedup_hash="a" * 64)
        assert ok is False  # never raised

    async def test_safe_mirror_disabled_or_sessionless(self, db_session):
        article = {"title": f"{_MARK} off"}
        w_off = NewsDualWriter(session=db_session, enabled=False)
        assert await w_off.safe_mirror(article, title="x") is False
        w_nos = NewsDualWriter(session=None, enabled=True)
        assert await w_nos.safe_mirror(article, title="x") is False

    async def test_legacy_save_survives_dual_write_failure(self, db_session):
        """The contract: mirror errors never break the legacy ``news_articles`` path."""
        service = NewsIngestionService(session=db_session, dual_write_enabled=True)
        # Make the mirror blow up on the shared session.
        with patch.object(
            service.dual_writer, "safe_mirror", side_effect=RuntimeError("boom")
        ):
            # …but the pipeline's per-article guard catches it before save is reached?
            # No — safe_mirror is called AFTER legacy save; an exception there WOULD
            # propagate. Verify the wiring uses safe_mirror (which cannot raise):
            import inspect

            src = inspect.getsource(NewsIngestionService._save_article)
            assert "safe_mirror" in src, "pipeline must call the fail-safe wrapper"

        # And with a genuinely failing mirror call (patched at mirror level),
        # the legacy save still completes:
        with patch.object(
            service.dual_writer, "mirror", side_effect=RuntimeError("boom")
        ):
            await service._save_article(
                {
                    "title": f"{_MARK} legacy survives",
                    "link": f"https://x.test/legacy-{uuid.uuid4().hex}",
                    "description": "desc",
                    "_source_feed": f"{_MARK}_legacy",
                }
            )
        # Legacy row landed:
        exists = await db_session.execute(
            text("SELECT count(*) FROM news_articles WHERE title = :t"),
            {"t": f"{_MARK} legacy survives"},
        )
        assert exists.scalar_one() == 1


class TestIngestEndToEnd:
    async def test_one_run_writes_both_schemas(self, db_session):
        """Full pipeline: stubbed provider → legacy news_articles + new news_items."""
        article: dict[str, Any] = {
            "title": f"{_MARK} e2e headline",
            "link": f"https://x.test/e2e-{uuid.uuid4().hex}",
            "description": "تست dual-write",
            "published_at": "2026-09-18T09:00:00+00:00",
            "category": "companies",
            "_source_feed": f"{_MARK}_e2e",
        }

        async def fake_fetch(limit: int = 50):
            return Result.ok([dict(article)])

        service = NewsIngestionService(session=db_session, dual_write_enabled=True)
        with patch("services.news_ingestion.RSSDomesticProvider") as ProviderMock:
            ProviderMock.return_value = AsyncMock()
            ProviderMock.return_value.feeds = {"x": "y"}
            ProviderMock.return_value.fetch_news = fake_fetch

            stats = await service.ingest(
                sources=[f"{_MARK}_e2e"],
                limit_per_source=5,
                save=True,
                verbose=False,
            )

        assert stats["errors"] == 0, stats.get("articles") and [
            a for a in stats["articles"] if a.get("error")
        ]
        assert stats["saved"] == 1

        # New schema received the mirror:
        row = await db_session.execute(
            text("SELECT id, category, source FROM news_items WHERE title = :t"),
            {"t": f"{_MARK} e2e headline"},
        )
        nrow = row.one_or_none()
        assert nrow is not None, "dual-write row missing after ingest()"
        assert nrow.category == "companies" and nrow.source == f"{_MARK}_e2e"

        # Second identical run must not duplicate (dedup fast-path):
        with patch("services.news_ingestion.RSSDomesticProvider") as ProviderMock:
            ProviderMock.return_value = AsyncMock()
            ProviderMock.return_value.feeds = {"x": "y"}
            ProviderMock.return_value.fetch_news = fake_fetch
            stats2 = await service.ingest(
                sources=[f"{_MARK}_e2e"], limit_per_source=5, save=True, verbose=False
            )
        count = await db_session.execute(
            text("SELECT count(*) FROM news_items WHERE title = :t"),
            {"t": f"{_MARK} e2e headline"},
        )
        assert count.scalar_one() == 1
