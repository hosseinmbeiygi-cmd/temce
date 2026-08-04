"""
Unit tests for the Tehran market-hours gate (``jobs.market_hours``) and its
enforcement in the BrsApi job registry + legacy sync jobs.

Background: the free BrsApi daily quota is burned by running TSETMC/IME
sync jobs around the clock (market closed at night) — by morning the API
answers HTTP 402 and data stops updating. These jobs must be skipped
outside Tehran trading hours (Sat–Wed 08:45–12:30), while global-market
jobs (gold/currency/crypto) and manual forced runs keep working.
"""

from __future__ import annotations

from datetime import datetime, timedelta, tzinfo
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jobs.market_hours import (
    MARKET_CLOSE_HOUR,
    MARKET_CLOSE_MINUTE,
    MARKET_OPEN_HOUR,
    MARKET_OPEN_MINUTE,
    is_tehran_codal_window,
    is_tehran_market_open,
)

# ──────────────────────────────────────────────
#  is_tehran_market_open
# ──────────────────────────────────────────────


def _tehran_dt(year: int, month: int, day: int, hour: int, minute: int, weekday: int):
    """Build a fake ``datetime.now(tz)`` return for ``Asia/Tehran``."""
    dt = datetime(year, month, day, hour, minute, 0)
    # Adjust so that .weekday() matches the requested weekday
    dt = dt.replace(day=day + ((weekday - dt.weekday()) % 7))
    return dt


class FakeTehranTz(tzinfo):
    """Minimal stand-in for ``pytz.timezone('Asia/Tehran')``.

    ``datetime.now(tz)`` requires a real ``tzinfo`` subclass and calls
    ``tz.fromutc(...)``; older ``pytz`` code paths may also use
    ``localize()`` — all are faked to return the fixed wall-clock time.
    """

    def __init__(self, dt: datetime):
        self._dt = dt

    def fromutc(self, dt: datetime) -> datetime:
        return self._dt

    def localize(self, dt: datetime) -> datetime:
        return self._dt

    def utcoffset(self, dt: datetime | None) -> timedelta:
        return timedelta(hours=3, minutes=30)

    def dst(self, dt: datetime | None) -> timedelta:
        return timedelta(0)

    def tzname(self, dt: datetime | None) -> str:
        return "Asia/Tehran"


@pytest.fixture
def patch_now():
    """Patch the tz lookup so the module sees a fixed Tehran wall-clock."""

    def _patch(dt: datetime):
        fake_tz = FakeTehranTz(dt)

        def _timezone(name: str):
            assert name == "Asia/Tehran"
            return fake_tz

        patcher = patch("pytz.timezone", side_effect=_timezone)
        patcher.start()
        return patcher

    yield _patch
    patch.stopall()


class TestIsTehranMarketOpen:
    def test_market_open_morning(self, patch_now):
        dt = _tehran_dt(2026, 8, 2, MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE + 1, weekday=1)  # Tue
        patch_now(dt)
        assert is_tehran_market_open() is True

    def test_market_open_noon(self, patch_now):
        dt = _tehran_dt(2026, 8, 2, 11, 30, weekday=0)  # Mon
        patch_now(dt)
        assert is_tehran_market_open() is True

    def test_market_closed_night(self, patch_now):
        dt = _tehran_dt(2026, 8, 2, 0, 14, weekday=1)  # Tue 00:14
        patch_now(dt)
        assert is_tehran_market_open() is False

    def test_market_closed_after_close(self, patch_now):
        dt = _tehran_dt(2026, 8, 2, MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE + 1, weekday=2)  # Wed
        patch_now(dt)
        assert is_tehran_market_open() is False

    def test_market_closed_before_open(self, patch_now):
        dt = _tehran_dt(2026, 8, 2, MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE - 1, weekday=0)  # Mon
        patch_now(dt)
        assert is_tehran_market_open() is False

    def test_weekend_thursday_closed(self, patch_now):
        dt = _tehran_dt(2026, 8, 2, 10, 0, weekday=3)  # Thu (Iranian weekend)
        patch_now(dt)
        assert is_tehran_market_open() is False

    def test_weekend_friday_closed(self, patch_now):
        dt = _tehran_dt(2026, 8, 2, 10, 0, weekday=4)  # Fri
        patch_now(dt)
        assert is_tehran_market_open() is False

    def test_timezone_error_fails_open(self):
        with patch("pytz.timezone", side_effect=Exception("boom")):
            assert is_tehran_market_open() is True


class TestIsTehranCodalWindow:
    def test_codal_open_after_market(self, patch_now):
        """Afternoon (14:00) is outside trading hours but inside the Codal window."""
        dt = _tehran_dt(2026, 8, 2, 14, 0, weekday=1)  # Tue 14:00
        patch_now(dt)
        assert is_tehran_market_open() is False
        assert is_tehran_codal_window() is True

    def test_codal_open_morning(self, patch_now):
        dt = _tehran_dt(2026, 8, 2, 8, 30, weekday=0)  # Mon 08:30
        patch_now(dt)
        assert is_tehran_codal_window() is True

    def test_codal_closed_night(self, patch_now):
        dt = _tehran_dt(2026, 8, 2, 0, 14, weekday=1)  # Tue 00:14
        patch_now(dt)
        assert is_tehran_codal_window() is False

    def test_codal_closed_late_evening(self, patch_now):
        dt = _tehran_dt(2026, 8, 2, 19, 0, weekday=2)  # Wed 19:00
        patch_now(dt)
        assert is_tehran_codal_window() is False

    def test_codal_closed_weekend(self, patch_now):
        dt = _tehran_dt(2026, 8, 2, 11, 0, weekday=4)  # Fri
        patch_now(dt)
        assert is_tehran_codal_window() is False


# ──────────────────────────────────────────────
#  BrsApiJobRegistry.run_job gate
# ──────────────────────────────────────────────


class TestRunJobMarketHoursGate:
    @pytest.fixture
    def registry(self):
        from brsapi.jobs.registry import BRsAPI_SYNC_JOBS, BrsApiJobRegistry

        reg = BrsApiJobRegistry()
        reg.register_many(BRsAPI_SYNC_JOBS)
        return reg

    async def _run(self, registry, job_name: str, force: bool = False):
        """Run a job under full mocking so the gate is the only real logic."""
        session = AsyncMock()
        service = AsyncMock()
        report = MagicMock(success=True, items_count=10, duration_ms=100.0, error=None)
        service.sync = AsyncMock(return_value=report)
        registry._client = MagicMock()
        with (
            patch("brsapi.jobs.registry.get_session") as mock_gs,
            patch("brsapi.jobs.registry.BrsApiSyncService") as mock_svc_cls,
        ):
            mock_gs.return_value.__aiter__.return_value = [session]
            mock_svc_cls.return_value = service
            return await registry.run_job(job_name, force=force), service

    async def test_market_hours_job_skipped_outside_hours(self, registry):
        """``brsapi_all_symbols`` must NOT call the API outside trading hours."""
        with patch("brsapi.jobs.registry.is_tehran_market_open", return_value=False):
            result, service = await self._run(registry, "brsapi_all_symbols")
        assert result is None
        service.sync.assert_not_called()

    async def test_codal_job_skipped_outside_office_window(self, registry):
        """``brsapi_codal`` must NOT call the API when the office window is closed."""
        with patch("brsapi.jobs.registry.is_tehran_codal_window", return_value=False):
            result, service = await self._run(registry, "brsapi_codal")
        assert result is None
        service.sync.assert_not_called()

    async def test_codal_job_runs_inside_office_window(self, registry):
        """``brsapi_codal`` must call the API inside the office window."""
        with patch("brsapi.jobs.registry.is_tehran_codal_window", return_value=True):
            result, service = await self._run(registry, "brsapi_codal")
        assert result is not None
        service.sync.assert_awaited_once()

    async def test_market_hours_job_runs_inside_hours(self, registry):
        """``brsapi_all_symbols`` must call the API inside trading hours."""
        with patch("brsapi.jobs.registry.is_tehran_market_open", return_value=True):
            result, service = await self._run(registry, "brsapi_all_symbols")
        assert result is not None
        service.sync.assert_awaited_once()

    async def test_forced_run_bypasses_gate(self, registry):
        """``force=True`` (manual run) must bypass the gate."""
        with patch("brsapi.jobs.registry.is_tehran_market_open", return_value=False):
            result, service = await self._run(registry, "brsapi_all_symbols", force=True)
        assert result is not None
        service.sync.assert_awaited_once()

    async def test_global_market_job_never_gated(self, registry):
        """Gold/currency/crypto jobs must run 24/7 (no gate flag)."""
        with patch("brsapi.jobs.registry.is_tehran_market_open", return_value=False):
            result, service = await self._run(registry, "brsapi_gold_currency")
        assert result is not None
        service.sync_gold_currency.assert_awaited_once()

    async def test_run_job_now_defaults_to_force(self, registry):
        """``run_job_now`` must bypass the gate by default (admin action)."""
        registry._client = MagicMock()
        session = AsyncMock()
        service = AsyncMock()
        service.sync = AsyncMock(return_value=MagicMock(success=True, items_count=5, duration_ms=50.0))
        with (
            patch("brsapi.jobs.registry.is_tehran_market_open", return_value=False),
            patch("brsapi.jobs.registry.get_session") as mock_gs,
            patch("brsapi.jobs.registry.BrsApiSyncService") as mock_svc_cls,
        ):
            mock_gs.return_value.__aiter__.return_value = [session]
            mock_svc_cls.return_value = service
            result = await registry.run_job_now("brsapi_all_symbols")
        assert result["success"] is True
        service.sync.assert_awaited_once()

    async def test_run_job_now_respects_gate_when_force_false(self, registry):
        """``run_job_now(force=False)`` must skip and report a clear message."""
        registry._client = MagicMock()
        with (
            patch("brsapi.jobs.registry.is_tehran_market_open", return_value=False),
            patch("brsapi.jobs.registry.get_session") as mock_gs,
            patch("brsapi.jobs.registry.BrsApiSyncService") as mock_svc_cls,
        ):
            session = AsyncMock()
            mock_gs.return_value.__aiter__.return_value = [session]
            mock_svc_cls.return_value = AsyncMock()
            result = await registry.run_job_now("brsapi_all_symbols", force=False)
        assert result["success"] is False
        assert result["skipped"] is True
        assert "skipped" in result["message"]


# ──────────────────────────────────────────────
#  Legacy sync jobs gate
# ──────────────────────────────────────────────


class TestLegacySyncJobsGate:
    @pytest.fixture
    def context(self):
        return MagicMock()

    async def test_sync_quotes_skipped_outside_hours(self, context):
        from jobs.definitions.sync_jobs import SyncQuotesJob

        job = SyncQuotesJob()
        with patch("jobs.definitions.sync_jobs.is_tehran_market_open", return_value=False):
            result = await job.execute(context)
        assert result.success is True
        assert result.data.get("skipped") is True

    async def test_sync_quotes_runs_inside_hours(self, context):
        from jobs.definitions.sync_jobs import SyncQuotesJob

        job = SyncQuotesJob()
        # sync_jobs imports get_client/BrsApiSyncService/get_session locally
        # inside execute(), so patch them at their real module locations.
        with (
            patch("jobs.definitions.sync_jobs.is_tehran_market_open", return_value=True),
            patch("brsapi.client.get_client", return_value=AsyncMock(return_value=MagicMock())),
            patch("core.database.get_session") as mock_gs,
            patch("brsapi.services.sync_service.BrsApiSyncService") as mock_svc_cls,
        ):
            session = AsyncMock()
            mock_gs.return_value.__aiter__.return_value = [session]
            svc = AsyncMock()
            svc.sync = AsyncMock(return_value=MagicMock(success=True, items_count=3, error=None))
            mock_svc_cls.return_value = svc
            result = await job.execute(context)
        assert result.success is True
        assert result.data.get("skipped") is None

    async def test_sync_codal_skipped_outside_hours(self, context):
        from jobs.definitions.sync_jobs import SyncCodalJob

        job = SyncCodalJob()
        with patch("jobs.definitions.sync_jobs.is_tehran_codal_window", return_value=False):
            result = await job.execute(context)
        assert result.success is True
        assert result.data.get("skipped") is True

    async def test_sync_instruments_skipped_outside_hours(self, context):
        from jobs.definitions.sync_jobs import SyncInstrumentsJob

        job = SyncInstrumentsJob()
        with patch("jobs.definitions.sync_jobs.is_tehran_market_open", return_value=False):
            result = await job.execute(context)
        assert result.success is True
        assert result.data.get("skipped") is True
