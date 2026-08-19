"""Unit tests for the feature-store nightly jobs.

Covers:
  - ``FeatureStoreBuildJob``: success path, context params (days/workers/symbols),
    DB-session failure, and unexpected exceptions
  - ``ScreenerDailyScoresJob``: success path with explicit date, default date,
    session failure, and exception handling

Uses a fake async session factory and mocked builder scripts — no DB writes.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jobs.definitions.feature_store_jobs import FeatureStoreBuildJob, ScreenerDailyScoresJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult

# ── Helpers ───────────────────────────────────────────────────────────────


def _make_context(**params: Any) -> JobContext:
    return JobContext(job_id="test-job", job_name="FeatureStoreBuildJob", params=params)


def _make_get_session(session: MagicMock):
    """Build a get_session() mock that yields a single session.

    ``get_session`` is an async-generator function, so the replacement must
    also be an async-generator function (not an AsyncMock — ``async for``
    needs the call to return an async iterator).
    """
    async def _gen():
        yield session

    return _gen


# ── FeatureStoreBuildJob ──────────────────────────────────────────────────


class TestFeatureStoreBuildJob:
    @pytest.mark.asyncio
    async def test_success_with_default_params(self) -> None:
        session = MagicMock()
        builder_cls = MagicMock()
        builder = builder_cls.return_value
        builder.build_all = AsyncMock(return_value={"rows": 500, "fail": 2})

        with (
            patch("core.database.get_session", _make_get_session(session)),
            patch("scripts.build_feature_store.FeatureStoreBuilder", builder_cls),
        ):
            result = await FeatureStoreBuildJob().execute(_make_context())

        assert isinstance(result, JobResult)
        assert result.success is True
        assert result.data == {"rows": 500, "fail": 2}
        builder_cls.assert_called_once_with(symbols=None, days=100, workers=4)
        builder.build_all.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_context_params_are_passed(self) -> None:
        session = MagicMock()
        builder_cls = MagicMock()
        builder = builder_cls.return_value
        builder.build_all = AsyncMock(return_value={"rows": 10, "fail": 0})

        with (
            patch("core.database.get_session", _make_get_session(session)),
            patch("scripts.build_feature_store.FeatureStoreBuilder", builder_cls),
        ):
            await FeatureStoreBuildJob().execute(
                _make_context(days="50", workers="2", symbols=["فولاد", "خودرو"])
            )

        builder_cls.assert_called_once_with(symbols=["فولاد", "خودرو"], days=50, workers=2)

    @pytest.mark.asyncio
    async def test_no_session_returns_failure(self) -> None:
        async def _empty():
            if False:
                yield None

        with patch("core.database.get_session", _empty):
            result = await FeatureStoreBuildJob().execute(_make_context())

        assert result.success is False
        assert "session" in result.error.lower()

    @pytest.mark.asyncio
    async def test_builder_exception_returns_failure(self) -> None:
        session = MagicMock()
        builder_cls = MagicMock()
        builder = builder_cls.return_value
        builder.build_all = AsyncMock(side_effect=RuntimeError("db exploded"))

        with (
            patch("core.database.get_session", _make_get_session(session)),
            patch("scripts.build_feature_store.FeatureStoreBuilder", builder_cls),
        ):
            result = await FeatureStoreBuildJob().execute(_make_context())

        assert result.success is False
        assert "db exploded" in result.error


# ── ScreenerDailyScoresJob ────────────────────────────────────────────────


class TestScreenerDailyScoresJob:
    @pytest.mark.asyncio
    async def test_success_with_explicit_date(self) -> None:
        session = MagicMock()
        build_daily_scores = AsyncMock(return_value={"rows": 120, "trade_date": "2026-01-15"})

        with (
            patch("core.database.get_session", _make_get_session(session)),
            patch("scripts.build_screener_scores.build_daily_scores", build_daily_scores),
        ):
            result = await ScreenerDailyScoresJob().execute(
                _make_context(date="2026-01-15")
            )

        assert result.success is True
        assert result.data == {"rows": 120, "trade_date": "2026-01-15"}
        build_daily_scores.assert_awaited_once_with(session, date(2026, 1, 15))

    @pytest.mark.asyncio
    async def test_defaults_to_today(self) -> None:
        session = MagicMock()
        build_daily_scores = AsyncMock(return_value={"rows": 5, "trade_date": "today"})

        with (
            patch("core.database.get_session", _make_get_session(session)),
            patch("scripts.build_screener_scores.build_daily_scores", build_daily_scores),
        ):
            await ScreenerDailyScoresJob().execute(_make_context())

        # No explicit date → today's date is passed.
        passed_date = build_daily_scores.await_args.args[1]
        assert passed_date == date.today()

    @pytest.mark.asyncio
    async def test_no_session_returns_failure(self) -> None:
        async def _empty():
            if False:
                yield None

        with patch("core.database.get_session", _empty):
            result = await ScreenerDailyScoresJob().execute(_make_context())

        assert result.success is False

    @pytest.mark.asyncio
    async def test_exception_returns_failure(self) -> None:
        session = MagicMock()

        async def _raise(session_, trade_date_):
            raise ValueError("bad date")

        with (
            patch("core.database.get_session", _make_get_session(session)),
            patch("scripts.build_screener_scores.build_daily_scores", AsyncMock(side_effect=_raise)),
        ):
            result = await ScreenerDailyScoresJob().execute(_make_context())

        assert result.success is False
        assert "bad date" in result.error
