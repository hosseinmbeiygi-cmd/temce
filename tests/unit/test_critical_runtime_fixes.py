"""Regression tests for the 5 critical runtime fixes.

Fixes under test:
  1. news_articles.published_at VARCHAR(30) truncation — _to_orm normalizes
     microseconds so ``isoformat()`` never exceeds 25 chars.
  2. NewsIngestionService.ingest() rolls back the session after a per-article
     save failure so subsequent articles don't cascade into PendingRollbackError.
  3. SyncSnapshotsToQuotesJob / EvaluateAlertsJob / IranFearGreedIndex pass a
     datetime (not a str) for ``fetched_at >= :today`` (fetched_at is now
     TIMESTAMPTZ; asyncpg rejects strings with DataError).
  4. FundSyncService syncs funds sequentially (no asyncio.gather on a shared
     AsyncSession → no "provisioning a new connection" InvalidRequestError).
  5. Model column width allows >30 char timestamps (String(40)).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from domain.news.news_item import NewsItem
from jobs.job_context import JobContext
from models.news import NewsArticleModel
from repositories.news_repository import _NewsDbRepo


def _ctx() -> JobContext:
    return JobContext(job_id="t", job_name="t")


# ════════════════════════════════════════════════════════════════════
# Fix 1 + 5 — published_at width & microsecond normalization
# ════════════════════════════════════════════════════════════════════


class TestPublishedAtWidth:
    @pytest.mark.parametrize(
        "dt",
        [
            datetime(2026, 8, 3, 6, 0, 51, tzinfo=UTC),
            datetime.now(UTC),  # has microseconds
            datetime(2026, 8, 3, 6, 0, 51, 123456, tzinfo=UTC),
        ],
    )
    def test_to_orm_never_exceeds_25_chars(self, dt: datetime) -> None:
        """isoformat() with microseconds is 36 chars — must be normalized."""
        repo = _NewsDbRepo(MagicMock())
        item = NewsItem(
            id="news_x",
            title="T",
            content="C",
            summary="S",
            source="src",
            url="u",
            publish_date=dt,
            category="market",
            sentiment=0.0,
            sentiment_label="neutral",
            symbols=[],
            data_source="rss",
        )
        orm = repo._to_orm(item)
        assert orm.published_at is not None
        assert len(orm.published_at) <= 25, f"published_at too long: {orm.published_at!r}"

    def test_model_column_is_at_least_40(self) -> None:
        """The column must accept >30 char ISO strings (defense in depth)."""
        col = NewsArticleModel.__table__.columns["published_at"]
        assert col.type.length >= 40, f"published_at length is {col.type.length}"

    def test_to_orm_preserves_second_precision(self) -> None:
        repo = _NewsDbRepo(MagicMock())
        dt = datetime(2026, 8, 3, 6, 0, 51, 999999, tzinfo=UTC)
        item = NewsItem(
            id="news_x", title="T", content="C", summary="S", source="s",
            url="u", publish_date=dt, category="c", sentiment=0.0,
            sentiment_label="neutral", symbols=[], data_source="rss",
        )
        orm = repo._to_orm(item)
        assert orm.published_at == "2026-08-03T06:00:51+00:00"

    def test_to_orm_none_date(self) -> None:
        repo = _NewsDbRepo(MagicMock())
        item = NewsItem(
            id="news_x", title="T", content="C", summary="S", source="s",
            url="u", publish_date=None, category="c", sentiment=0.0,
            sentiment_label="neutral", symbols=[], data_source="rss",
        )
        orm = repo._to_orm(item)
        assert orm.published_at is None


# ════════════════════════════════════════════════════════════════════
# Fix 2 — news ingestion session rollback after save failure
# ════════════════════════════════════════════════════════════════════


class TestNewsIngestionRollback:
    @pytest.mark.asyncio
    async def test_failed_article_rolls_back_and_loop_continues(self) -> None:
        """A failed save must rollback so the next article can still save."""
        from services.news_ingestion import NewsIngestionService

        session = MagicMock()
        session.rollback = AsyncMock()

        news_service = MagicMock()
        # First save fails (e.g. StringDataRightTruncationError), rest succeed.
        news_service.save = AsyncMock(side_effect=[
            Exception("value too long for type character varying(30)"),
            MagicMock(), MagicMock(),
        ])
        news_service.repo.exists_by_url_or_title = AsyncMock(return_value=False)

        svc = NewsIngestionService(news_service=news_service, session=session)

        articles = [
            {"title": "a", "link": "http://x/1", "description": "d" * 40, "_source_feed": "src"},
            {"title": "b", "link": "http://x/2", "description": "d" * 40, "_source_feed": "src"},
            {"title": "c", "link": "http://x/3", "description": "d" * 40, "_source_feed": "src"},
        ]
        with (
            patch("services.news_ingestion.RSSDomesticProvider") as provider_cls,
            patch("services.news_ingestion._news_parser") as parser,
        ):
            provider = MagicMock()
            provider.feeds = {}
            provider.fetch_news = AsyncMock(return_value=MagicMock(success=True, value=articles))
            provider_cls.return_value = provider
            parser.extract_symbols = MagicMock(return_value=[])

            stats = await svc.ingest(
                save=True, verbose=False, skip_sentiment=True, min_content_length=1,
            )

        assert stats["saved"] == 2
        assert stats["errors"] == 1
        # rollback must have been called after the failed save
        session.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_session_no_crash(self) -> None:
        """When session is None, a failure still doesn't raise."""
        from services.news_ingestion import NewsIngestionService

        news_service = MagicMock()
        news_service.save = AsyncMock(side_effect=Exception("boom"))
        news_service.repo.exists_by_url_or_title = AsyncMock(return_value=False)

        svc = NewsIngestionService(news_service=news_service, session=None)

        articles = [
            {"title": "a", "link": "http://x/1", "description": "d" * 40, "_source_feed": "src"},
        ]
        with (
            patch("services.news_ingestion.RSSDomesticProvider") as provider_cls,
            patch("services.news_ingestion._news_parser") as parser,
        ):
            provider = MagicMock()
            provider.feeds = {}
            provider.fetch_news = AsyncMock(return_value=MagicMock(success=True, value=articles))
            provider_cls.return_value = provider
            parser.extract_symbols = MagicMock(return_value=[])

            stats = await svc.ingest(
                save=True, verbose=False, skip_sentiment=True, min_content_length=1,
            )

        assert stats["errors"] == 1
        assert stats["saved"] == 0


# ════════════════════════════════════════════════════════════════════
# Fix 3 — datetime (not str) cutoffs for fetched_at >= :today
# ════════════════════════════════════════════════════════════════════


class TestDatetimeCutoffs:
    @pytest.mark.asyncio
    async def test_sync_snapshots_job_passes_datetime(self) -> None:
        """SyncSnapshotsToQuotesJob must bind a datetime for :today."""
        import core.database as db
        import jobs.definitions.sync_jobs as sync_jobs
        from jobs.job_result import JobResult

        class FakeResult:
            def fetchall(self):
                return []

        session = MagicMock()
        session.execute = AsyncMock(return_value=FakeResult())

        factory = MagicMock()
        factory.__aenter__ = AsyncMock(return_value=session)
        factory.__aexit__ = AsyncMock(return_value=False)

        with patch.object(db, "async_session_factory", factory):
            job = sync_jobs.SyncSnapshotsToQuotesJob()
            result = await job.execute(_ctx())

        assert isinstance(result, JobResult)
        assert result.success
        # capture the params of the snapshot query (the first execute call)
        call = session.execute.call_args
        assert call is not None
        params = call.kwargs.get("params") or (call.args[1] if len(call.args) > 1 else {})
        today = params.get("today")
        assert today is not None, "missing :today param"
        assert isinstance(today, datetime), f":today must be datetime, got {type(today)}"
        assert not isinstance(today, str)
        # Midnight UTC today
        assert today.tzinfo is not None
        assert today.hour == 0 and today.minute == 0

    @pytest.mark.asyncio
    async def test_evaluate_alerts_job_no_enabled_alerts(self) -> None:
        """EvaluateAlertsJob runs cleanly with the patched factory."""
        import core.database as db
        import jobs.definitions.alert_jobs as alert_jobs
        from jobs.job_result import JobResult

        session = MagicMock()
        session.execute = AsyncMock(return_value=MagicMock())
        session.execute.return_value.scalars.return_value.all.return_value = []

        factory = MagicMock()
        factory.__aenter__ = AsyncMock(return_value=session)
        factory.__aexit__ = AsyncMock(return_value=False)

        with patch.object(db, "async_session_factory", factory):
            job = alert_jobs.EvaluateAlertsJob()
            result = await job.execute(_ctx())

        assert isinstance(result, JobResult)
        assert result.success
        # No alerts → success with 0 evaluated (no date query needed)
        assert result.data["evaluated"] == 0

    @pytest.mark.asyncio
    async def test_iran_fear_greed_cutoffs_are_datetime(self) -> None:
        """The 3 fetched_at cutoffs in IranFearGreedIndex must be datetime objects."""
        from services.iran_fear_greed_index import IranFearGreedIndex

        session = MagicMock()
        captured: list = []

        async def fake_execute(stmt, params=None):
            if params:
                captured.append(params.get("cutoff_today"))
            return MagicMock()

        session.execute = fake_execute
        svc = IranFearGreedIndex(session=session)

        # Trigger the three snapshot-based components
        await svc._calc_real_legal_ratio()
        await svc._calc_activity_level()
        await svc._calc_trend_extension()

        assert len(captured) == 3
        for c in captured:
            assert isinstance(c, datetime), f"cutoff_today is {type(c)}"
            assert not isinstance(c, str)
            assert c.tzinfo is not None


# ════════════════════════════════════════════════════════════════════
# Fix 4 — fund sync serialized (no gather on shared session)
# ════════════════════════════════════════════════════════════════════


class TestFundSyncSerialized:
    @pytest.mark.asyncio
    async def test_sync_all_funds_sequential(self) -> None:
        """sync_single_fund must be called once per symbol, sequentially."""
        from services.fund_sync_service import FundSyncService

        fund_service = MagicMock()
        brsapi = MagicMock()
        svc = FundSyncService(fund_service=fund_service, brsapi=brsapi)

        calls: list[str] = []

        async def fake_update(symbol, brsapi):
            calls.append(symbol)
            return {"symbol": symbol}

        fund_service.update_from_brsapi = fake_update

        with patch("services.fund_sync_service.DELAY_BETWEEN_SYMBOLS", 0.0):
            report = await svc.sync_all_funds(symbols=["A", "B", "C"], max_concurrent=5)

        assert calls == ["A", "B", "C"]
        assert report.success == 3
        assert report.failed == 0
        assert report.total == 3

    @pytest.mark.asyncio
    async def test_sync_all_aggregates_failures(self) -> None:
        from services.fund_sync_service import FundSyncService

        fund_service = MagicMock()
        brsapi = MagicMock()
        svc = FundSyncService(fund_service=fund_service, brsapi=brsapi)

        async def fake_update(symbol, brsapi):
            if symbol == "BAD":
                return {"symbol": symbol, "error": "not found"}
            return {"symbol": symbol}

        fund_service.update_from_brsapi = fake_update

        with patch("services.fund_sync_service.DELAY_BETWEEN_SYMBOLS", 0.0):
            report = await svc.sync_all_funds(symbols=["A", "BAD", "C"])

        assert report.success == 2
        assert report.failed == 1
        assert report.errors[0]["symbol"] == "BAD"
