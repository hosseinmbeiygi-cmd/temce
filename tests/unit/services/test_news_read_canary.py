"""Tests for the news read-path canary rollout (``NEWS_READ_MODE``).

Layers:

* pure decisions (``decide``/``_canary_bucket``/``normalize_mode``) —
  deterministic slicing, no flicker between schemas for a stable key
* parity comparison — id prefixes stripped (``news_`` vs ``ni_``),
  total/ordering mismatches count as divergence
* routing through ``NewsRepository`` in shadow mode against real
  Postgres — served page keeps the legacy contract, both counters tick
* auto-halt evaluation — below floor with enough samples flips the
  shared mode to ``off``; disabled via ``NEWS_READ_HALT_ENABLED=false``
* halter job wiring and the admin dial endpoint (HTTP, mocked auth)

Redis is not required: counters degrade to the in-memory dict.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

_MARK = "test_canary"


def _engine():
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("DATABASE_URL not set")
    try:
        from sqlalchemy.ext.asyncio import create_async_engine

        return create_async_engine(url)
    except Exception:
        pytest.skip("DB not reachable")


# ── pure decision logic ──────────────────────────────────────────────────


class TestDecisions:
    def test_normalize_mode(self):
        from services.news_read_canary import normalize_mode

        assert normalize_mode("SHADOW") == "shadow"
        assert normalize_mode("junk") == "off"
        assert normalize_mode(None) == "off"

    def test_off_and_full(self):
        from services.news_read_canary import decide

        off = decide("off", "k")
        assert off.serve_legacy and not off.serve_items and not off.shadow
        full = decide("full", "k")
        assert full.serve_items and not full.serve_legacy and not full.shadow

    def test_shadow_probes(self):
        from services.news_read_canary import decide

        d = decide("shadow", "k")
        assert d.serve_legacy and d.shadow and not d.serve_items

    def test_canary_slice_deterministic(self):
        from services.news_read_canary import _canary_bucket, decide

        assert all(_canary_bucket(f"r{i}", 100) for i in range(50))
        assert not any(_canary_bucket(f"r{i}", 0) for i in range(50))
        # same key always same side
        assert _canary_bucket("stable", 10) == _canary_bucket("stable", 10)
        # the decision honors it without flicker
        a, b = decide("canary", "stable"), decide("canary", "stable")
        assert a.serve_items == b.serve_items

    def test_canary_fraction_roughly_honored(self):
        from services.news_read_canary import _canary_bucket

        inside = sum(_canary_bucket(f"r{i}", 25) for i in range(1000))
        assert 150 < inside < 350  # ~25% ± noise


# ── parity comparison ────────────────────────────────────────────────────


class _Page:
    def __init__(self, ids, total):
        self._ids = ids
        self.total = total
        from types import SimpleNamespace

        # Parity keys off the natural key (url, title fallback) — ids are
        # NOT comparable across schemas. url derives from the id tail here
        # so order/total mismatches still produce distinct keys.
        self.items = [
            SimpleNamespace(id=i, url=f"https://x.test/{i.split('_', 1)[-1]}")
            for i in ids
        ]


class TestParity:
    @pytest.mark.asyncio
    async def test_prefix_insensitive_match(self):
        from services.news_read_canary import compare_page

        legacy = _Page(["news_a", "news_b"], 2)
        items = _Page(["ni_a", "ni_b"], 2)
        assert await compare_page(legacy, items)

    @pytest.mark.asyncio
    async def test_total_mismatch_diverges(self):
        from services.news_read_canary import compare_page

        assert not await compare_page(_Page(["news_a"], 1), _Page(["ni_a"], 2))

    @pytest.mark.asyncio
    async def test_order_mismatch_diverges(self):
        from services.news_read_canary import compare_page

        assert not await compare_page(_Page(["news_a", "news_b"], 2), _Page(["ni_b", "ni_a"], 2))

    @pytest.mark.asyncio
    async def test_none_probed_diverges(self):
        from services.news_read_canary import compare_page

        assert not await compare_page(_Page(["news_a"], 1), None)


# ── DB-backed shadow routing ─────────────────────────────────────────────


class TestShadowRouting:
    @pytest.mark.asyncio
    async def test_shadow_serves_legacy_and_counts(self, monkeypatch):
        eng = _engine()
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from core.config import settings as real_settings
        from repositories.news_repository import NewsRepository
        from services import news_read_canary as canary

        marker = f"{_MARK}_{uuid.uuid4().hex[:8]}"
        maker = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with maker() as session:
                # one row visible in BOTH schemas (legacy id mirrors the
                # production ``new_id("news")`` shape — parity keys off URL,
                # but the served-id assertion below checks the prefix)
                await session.execute(
                    text(
                        "INSERT INTO news_articles (id, title, source, url, category, published_at, published_at_ts, created_at) "
                        "VALUES (:i, :t, :s, :u, 'market', :p, :pts, now())"
                    ),
                    dict(i=f"news_{marker}", t=f"{marker} legacy", s=f"{marker}src",
                         u=f"https://x.test/{marker}", p="2026-09-10T08:00:00+00:00",
                         pts=datetime(2026, 9, 10, 8, 0)),
                )
                res = await session.execute(
                    text(
                        "INSERT INTO news_items (title, body, source, source_url, published_at, category, dedup_hash) "
                        "VALUES (:t, :b, :s, :u, :p, 'market', :h) RETURNING id"
                    ),
                    dict(t=f"{marker} legacy", b="b", s=f"{marker}src",
                         u=f"https://x.test/{marker}", p=datetime(2026, 9, 10, 8, 0),
                         h=f"hash_{marker}"),
                )
                item_id = res.scalar_one()
                await session.commit()

                monkeypatch.setattr(real_settings, "news_read_mode", "shadow", raising=False)
                monkeypatch.setattr(real_settings, "news_read_from_items", False, raising=False)
                canary._mem_counters.clear()

                repo = NewsRepository(session=session)
                found = await repo.search(marker)
                assert found.success
                # served from LEGACY even in shadow mode
                assert all(i.id.startswith("news_") for i in found.value.items)

                # counters ticked in the module memory (Redis absent in tests)
                assert canary._mem_counters["served"] >= 1
                assert canary._mem_counters["compared"] >= 1
                assert canary._mem_counters["parity_ok"] >= 1
                stats = await canary.window_stats()
                assert stats["parity_percent"] == 100.0
        finally:
            async with maker() as session:
                # Cleanup keyed on the unique per-run marker. The items
                # delete must run FIRST: legacy deletion is by id prefix,
                # and a items row deleted by title keeps working even if
                # the legacy delete above misses (marker prefix ≠ full id
                # when legacy ids use the news_ prefix).
                await session.execute(text("DELETE FROM news_items WHERE title LIKE :p"), {"p": f"{marker}%"})
                await session.execute(text("DELETE FROM news_articles WHERE id LIKE :p"), {"p": f"%{marker}%"})
                await session.commit()
                # Safety net for older runs that leaked rows (marker is
                # unique per run, but the 2026-09-20 shadow runs leaked
                # three rows because cleanup matched id, not the full id).
                await session.execute(
                    text("DELETE FROM news_articles WHERE title LIKE 'test_canary_%' AND url LIKE 'https://x.test/test_canary_%'")
                )
                await session.commit()
            await eng.dispose()

    @pytest.mark.asyncio
    async def test_full_mode_routes_to_items(self, monkeypatch):
        eng = _engine()
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from core.config import settings as real_settings
        from repositories.news_repository import NewsRepository

        marker = f"{_MARK}_{uuid.uuid4().hex[:8]}"
        maker = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with maker() as session:
                res = await session.execute(
                    text(
                        "INSERT INTO news_items (title, body, source, source_url, published_at, category, dedup_hash) "
                        "VALUES (:t, :b, :s, :u, :p, 'market', :h) RETURNING id"
                    ),
                    dict(t=f"{marker} t", b="b", s=f"{marker}src",
                         u=f"https://x.test/{marker}", p=datetime(2026, 9, 10, 8, 0),
                         h=f"hash_{marker}"),
                )
                item_id = res.scalar_one()
                await session.commit()

                monkeypatch.setattr(real_settings, "news_read_mode", "full", raising=False)
                monkeypatch.setattr(real_settings, "news_read_from_items", False, raising=False)

                repo = NewsRepository(session=session)
                found = await repo.search(marker)
                assert found.success
                assert [i.id for i in found.value.items] == [f"ni_{item_id}"]
        finally:
            async with maker() as session:
                await session.execute(text("DELETE FROM news_items WHERE title LIKE :p"), {"p": f"{marker}%"})
                await session.commit()
            await eng.dispose()


# ── auto-halt ────────────────────────────────────────────────────────────


class TestAutoHalt:
    @pytest.mark.asyncio
    async def test_below_floor_halts(self, monkeypatch):
        from services import news_read_canary as canary

        monkeypatch.setattr(canary, "_mem_counters", dict(canary._mem_counters))
        # 20 true divergences (regressions) — regression parity = 80% < 99% floor.
        canary._mem_counters.update(
            {"compared": 100, "parity_ok": 80, "parity_divergent": 20,
             "divergence_true_divergence": 20}
        )
        monkeypatch.setattr(canary, "window_stats", canary.window_stats)

        # no Redis → resolve_mode falls back to settings (non-off) and the
        # halt writes to settings.news_read_mode
        from core.config import settings as real_settings
        monkeypatch.setattr(real_settings, "news_read_mode", "shadow", raising=False)
        monkeypatch.setattr(real_settings, "news_read_halt_enabled", True, raising=False)
        monkeypatch.setattr(real_settings, "news_read_parity_floor_percent", 99, raising=False)
        monkeypatch.setattr(real_settings, "news_read_parity_min_samples", 50, raising=False)

        result = await canary.evaluate_auto_halt()
        assert result["halted"] is True
        assert real_settings.news_read_mode == "off"

    @pytest.mark.asyncio
    async def test_disabled_halter_never_halts(self, monkeypatch):
        from services import news_read_canary as canary

        canary._mem_counters.update({"compared": 100, "parity_ok": 10, "parity_divergent": 90})
        from core.config import settings as real_settings
        monkeypatch.setattr(real_settings, "news_read_mode", "shadow", raising=False)
        monkeypatch.setattr(real_settings, "news_read_halt_enabled", False, raising=False)

        result = await canary.evaluate_auto_halt()
        assert result["halted"] is False
        assert real_settings.news_read_mode == "shadow"

    @pytest.mark.asyncio
    async def test_not_enough_samples_no_judgement(self, monkeypatch):
        from services import news_read_canary as canary

        canary._mem_counters.update({"compared": 10, "parity_ok": 0, "parity_divergent": 10})
        from core.config import settings as real_settings
        monkeypatch.setattr(real_settings, "news_read_mode", "shadow", raising=False)
        monkeypatch.setattr(real_settings, "news_read_halt_enabled", True, raising=False)
        monkeypatch.setattr(real_settings, "news_read_parity_min_samples", 50, raising=False)

        result = await canary.evaluate_auto_halt()
        assert result["halted"] is False
        assert "not enough samples" in result["reason"]


# ── halter job + admin dial endpoint ─────────────────────────────────────


class TestJobAndEndpoint:
    @pytest.mark.asyncio
    async def test_halter_job_runs(self):
        from jobs.job_context import JobContext
        from jobs.definitions.news_jobs import NewsReadPathHalterJob
        from services import news_read_canary as canary

        canary._mem_counters.clear()
        job = NewsReadPathHalterJob()
        result = await job.run(JobContext(**_ctx_kwargs()))
        assert result.success
        assert result.data["checked"] is True

    def test_mode_endpoint_auth_chain(self, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from apps.api.endpoints.news import router as news_router
        from core.security.tokens import create_access_token

        app = FastAPI()
        app.include_router(news_router, prefix="/news")

        # Real JWT (dependency_overrides can't match the closure require_roles
        # builds internally — same lesson as test_news_tag_map_admin.py).
        token = create_access_token({"sub": "op-admin", "roles": ["admin"]})
        c = TestClient(app, raise_server_exceptions=False)
        c.headers.update({"Authorization": f"Bearer {token}"})

        # invalid mode → error payload
        resp = c.post("/news/read-path/mode", params={"mode": "banana"})
        assert resp.status_code == 200
        assert resp.json()["success"] is False

        # valid mode → applied (settings fallback without Redis) + echoed
        from core.config import settings as real_settings
        monkeypatch.setattr(real_settings, "news_read_mode", "off", raising=False)
        resp = c.post("/news/read-path/mode", params={"mode": "shadow"})
        assert resp.json()["success"] is True
        assert resp.json()["data"]["mode"] == "shadow"
        assert real_settings.news_read_mode == "shadow"

        # status endpoint exposes mode + window
        resp = c.get("/news/read-path/status")
        body = resp.json()
        assert body["success"] and "mode" in body["data"] and "parity_percent" in body["data"]


def _ctx_kwargs() -> dict:
    """JobContext kwargs — built dynamically so signature changes surface
    as a clear TypeError instead of a stale fixture."""
    import inspect
    from jobs.job_context import JobContext

    sig = inspect.signature(JobContext)
    kwargs: dict = {}
    for name, param in sig.parameters.items():
        if param.default is inspect._empty:
            kwargs[name] = None
    return kwargs
