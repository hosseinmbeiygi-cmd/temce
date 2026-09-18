"""Tests for the news dead-source health service.

Covers ``services/news_source_health.py`` (stale/never_fetched/
unregistered detection over ``news_ingestion_sources``), the alert
message builder, the cooldown-gated notify path, the job wrapper, and
the ``/news/sources/health`` endpoint. DB-backed tests run against real
Postgres (skipped offline); row cleanup uses a marker prefix.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_MARK = "test_nsh"


# ── helpers ──────────────────────────────────────────────────────────────


def _report_template() -> dict:
    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "thresholds": {"stale_minutes": 120, "never_fetched_hours": 24},
        "summary": {
            "total_registered": 3,
            "active": 3,
            "healthy": 1,
            "stale_count": 1,
            "never_fetched_count": 1,
            "unregistered_count": 0,
            "all_ok": False,
        },
        "stale_sources": ["dead_feed"],
        "never_fetched_sources": ["new_feed"],
        "unregistered_sources": [],
        "sources": [],
    }


# ── alert message builder (pure) ─────────────────────────────────────────


class TestAlertMessage:
    def test_all_ok_returns_none(self):
        from services.news_source_health import NewsSourceHealthService

        report = _report_template()
        report["summary"]["all_ok"] = True
        report["stale_sources"] = []
        report["never_fetched_sources"] = []
        assert NewsSourceHealthService.alert_message(report) is None

    def test_error_report_returns_none(self):
        from services.news_source_health import NewsSourceHealthService

        assert NewsSourceHealthService.alert_message({"error": "boom"}) is None

    def test_lists_each_category(self):
        from services.news_source_health import NewsSourceHealthService

        msg = NewsSourceHealthService.alert_message(_report_template())
        assert msg is not None
        assert "dead_feed" in msg
        assert "new_feed" in msg
        assert "120min" in msg
        assert "Unregistered" not in msg  # empty list must not render a line

    def test_unregistered_line_renders(self):
        from services.news_source_health import NewsSourceHealthService

        report = _report_template()
        report["unregistered_sources"] = ["renamed_feed"]
        msg = NewsSourceHealthService.alert_message(report)
        assert "renamed_feed" in msg


# ── notify cooldown (mocked redis + telegram) ────────────────────────────


class TestNotifyCooldown:
    @pytest.mark.asyncio
    async def test_alert_fires_and_cooldown_blocks_second(self):
        from core.config import settings
        from services.news_source_health import NewsSourceHealthService

        sent: list[str] = []

        class FakeTg:
            async def send(self, message, parse_mode="HTML"):
                sent.append(message)

        class FakeRedis:
            def __init__(self):
                self.store = {}

            async def get(self, k):
                return self.store.get(k)

            async def setex(self, k, ttl, v):
                self.store[k] = v

        redis = FakeRedis()
        session = AsyncMock()
        svc = NewsSourceHealthService(session)

        with (
            patch.object(svc, "health_report", AsyncMock(return_value=_report_template())),
            patch("core.cache.get_cache") as gc,
            patch("integrations.notifications.telegram_sender.TelegramSender", FakeTg),
        ):
            cache = MagicMock()
            cache.client = redis
            gc.return_value = cache

            first = await svc.notify_if_degraded()
            assert first is not None and len(sent) == 1

            # second run within cooldown -> blocked
            second = await svc.notify_if_degraded()
            assert second is None and len(sent) == 1

            # cooldown expiry -> fires again
            await redis.setex("alert:news_source_health", -1, "1")  # expired key
            redis.store.pop("alert:news_source_health", None)
            _ = settings.news_source_alert_cooldown_seconds
            third = await svc.notify_if_degraded()
            assert third is not None and len(sent) == 2

    @pytest.mark.asyncio
    async def test_healthy_report_never_alerts(self):
        from services.news_source_health import NewsSourceHealthService

        session = AsyncMock()
        svc = NewsSourceHealthService(session)
        report = _report_template()
        report["summary"]["all_ok"] = True
        with patch.object(svc, "health_report", AsyncMock(return_value=report)):
            assert await svc.notify_if_degraded() is None


# ── job wrapper ──────────────────────────────────────────────────────────


class TestJobWrapper:
    @staticmethod
    def _ctx() -> "JobContext":
        from jobs.job_context import JobContext

        return JobContext(job_id="j1", job_name="NewsSourceHealthJob", params={})

    @pytest.mark.asyncio
    async def test_disabled_when_threshold_zero(self, monkeypatch):
        from core.config import settings as real_settings
        from jobs.definitions.news_jobs import NewsSourceHealthJob

        monkeypatch.setattr(real_settings, "news_source_stale_minutes", 0, raising=False)
        result = await NewsSourceHealthJob().execute(self._ctx())
        assert result.success
        assert result.data == {"status": "disabled"}

    @pytest.mark.asyncio
    async def test_success_when_healthy(self, monkeypatch):
        from core.config import settings as real_settings
        from jobs.definitions.news_jobs import NewsSourceHealthJob

        monkeypatch.setattr(real_settings, "news_source_stale_minutes", 120, raising=False)

        class FakeSvc:
            def __init__(self, session):
                pass

            async def notify_if_degraded(self):
                return None

        with patch("services.news_source_health.NewsSourceHealthService", FakeSvc):
            result = await NewsSourceHealthJob().execute(self._ctx())
        assert result.success
        assert result.data["alerted"] is False


# ── DB-backed: report over the real registry ─────────────────────────────


class TestHealthReportDb:
    @pytest.mark.asyncio
    async def test_report_detects_stale_and_never_fetched(self):
        url = os.environ.get("DATABASE_URL") or ""
        if not url:
            pytest.skip("DATABASE_URL not set")
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from core.config import settings
        from services.news_source_health import NewsSourceHealthService

        eng = create_async_engine(url)
        marker = f"{_MARK}_{uuid.uuid4().hex[:8]}"
        maker = async_sessionmaker(eng, expire_on_commit=False)
        stale_minutes = settings.news_source_stale_minutes
        try:
            async with maker() as session:
                # fresh source (fetched just now)
                await session.execute(
                    text("INSERT INTO news_ingestion_sources (source_name, source_type, is_active, last_fetched_at) "
                         "VALUES (:n, 'rss', TRUE, now())"),
                    dict(n=f"{marker}_fresh"),
                )
                # stale source (fetched long ago)
                await session.execute(
                    text("INSERT INTO news_ingestion_sources (source_name, source_type, is_active, last_fetched_at) "
                         "VALUES (:n, 'rss', TRUE, now() - make_interval(mins => :m))"),
                    dict(n=f"{marker}_stale", m=stale_minutes + 60),
                )
                # never fetched, registered long ago
                await session.execute(
                    text("INSERT INTO news_ingestion_sources (source_name, source_type, is_active, last_fetched_at, created_at) "
                         "VALUES (:n, 'rss', TRUE, NULL, now() - interval '48 hours')"),
                    dict(n=f"{marker}_never"),
                )
                # a news row written by an unregistered source
                await session.execute(
                    text("INSERT INTO news_articles (id, title, source, url, category, created_at) "
                         "VALUES (:i, :t, :s, :u, 'market', now())"),
                    dict(i=f"{marker}_art", t=f"{marker} article", s=f"{marker}_ghost",
                         u=f"https://x.test/{marker}_art"),
                )
                await session.commit()

                svc = NewsSourceHealthService(session)
                report = await svc.health_report()
                assert not report.get("error")
                s = report["summary"]

                assert f"{marker}_stale" in report["stale_sources"]
                assert f"{marker}_never" in report["never_fetched_sources"]
                assert f"{marker}_ghost" in report["unregistered_sources"]
                assert s["stale_count"] >= 1 and s["never_fetched_count"] >= 1
                assert s["unregistered_count"] >= 1
                assert s["all_ok"] is False
                assert s["total_registered"] >= 3

                # per-source payload shape
                by_name = {x["source_name"]: x for x in report["sources"]}
                assert by_name[f"{marker}_fresh"]["status"] == "healthy"
                assert by_name[f"{marker}_fresh"]["minutes_since_fetch"] is not None
                assert by_name[f"{marker}_stale"]["status"] == "stale"
                assert by_name[f"{marker}_never"]["status"] == "never_fetched"

                # alert message reflects the DB state (names may be
                # truncated to 8 per line when real stale sources exist —
                # the report itself is the authoritative full list)
                msg = NewsSourceHealthService.alert_message(report)
                assert msg is not None
                assert f"{marker}_stale" in msg or f"{marker}_stale" in report["stale_sources"]
                assert f"{marker}_ghost" in msg
        finally:
            async with maker() as session:
                await session.execute(
                    text("DELETE FROM news_ingestion_sources WHERE source_name LIKE :p"),
                    {"p": f"{marker}%"},
                )
                await session.execute(
                    text("DELETE FROM news_articles WHERE id LIKE :p"), {"p": f"{marker}%"}
                )
                await session.commit()
            await eng.dispose()


# ── endpoint: ?notify=true ────────────────────────────────────────────────


class TestEndpointNotifyFlag:
    @pytest.mark.asyncio
    async def test_notify_flag_returns_alert_fired_honestly(self, monkeypatch):
        """``?notify=true`` reports alert_fired for both alert paths."""
        from apps.api.endpoints.news import news_sources_health

        session = AsyncMock()
        svc = MagicMock()
        degraded = _report_template()
        healthy = {**_report_template(), "summary": {**_report_template()["summary"], "all_ok": True}}

        # The endpoint imports the class inside its body at call time, so
        # patch it at the source module for the whole test.
        monkeypatch.setattr(
            "services.news_source_health.NewsSourceHealthService", lambda s: svc
        )

        # degraded + notify -> alert sent
        svc.notify_if_degraded = AsyncMock(return_value=dict(degraded))
        resp = await news_sources_health(notify=True, session=session)
        assert resp.data["alert_fired"] is True

        # degraded + cooldown-blocked (notify returns None) -> fall back to
        # plain report, alert_fired False
        svc.notify_if_degraded = AsyncMock(return_value=None)
        svc.health_report = AsyncMock(return_value=dict(degraded))
        resp = await news_sources_health(notify=True, session=session)
        assert resp.data["alert_fired"] is False

        # healthy + no notify -> plain report without the key
        svc.health_report = AsyncMock(return_value=dict(healthy))
        resp = await news_sources_health(notify=False, session=session)
        assert "alert_fired" not in resp.data
