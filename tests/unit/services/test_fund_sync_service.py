"""Unit tests for the fund sync service.

Covers:
  - ``SyncReport`` / ``SyncResult`` data classes (summary string, defaults)
  - ``sync_single_fund`` success / error-in-result / exception paths
  - session rollback on unexpected exceptions
  - ``sync_all_funds`` reporting and serialized execution (lock + delay)

Uses fakes for ``FundService`` and the BrsApi query service — no network.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.fund_sync_service import (
    FundSyncService,
    SyncReport,
    SyncResult,
    _is_market_open,
    _next_market_open_delay,
)

# ── Helpers ───────────────────────────────────────────────────────────────


def _make_fund_service(result: dict | None = None, error: Exception | None = None) -> MagicMock:
    svc = MagicMock()
    if error is not None:
        svc.update_from_brsapi = AsyncMock(side_effect=error)
    else:
        svc.update_from_brsapi = AsyncMock(return_value=result or {})
    return svc


def _make_brsapi() -> MagicMock:
    brsapi = MagicMock()
    brsapi.session = MagicMock()
    brsapi.session.rollback = AsyncMock()
    return brsapi


def _make_service(
    fund_service: MagicMock | None = None,
    brsapi: MagicMock | None = None,
) -> FundSyncService:
    return FundSyncService(
        fund_service=fund_service or _make_fund_service(),
        brsapi=brsapi or _make_brsapi(),
    )


# ── Data classes ──────────────────────────────────────────────────────────


class TestSyncResult:
    def test_defaults(self) -> None:
        r = SyncResult(symbol="آگاس", success=True)
        assert r.symbol == "آگاس"
        assert r.success is True
        assert r.error is None
        assert r.duration_ms == 0.0


class TestSyncReport:
    def test_defaults(self) -> None:
        r = SyncReport()
        assert r.total == 0
        assert r.success == 0
        assert r.failed == 0
        assert r.skipped == 0
        assert r.errors == []
        assert r.duration_ms == 0.0
        assert isinstance(r.timestamp, str)
        datetime.fromisoformat(r.timestamp)  # ISO-8601

    def test_summary_string(self) -> None:
        r = SyncReport(total=10, success=8, failed=2, duration_ms=5000.0)
        text = r.summary
        assert "10 symbols" in text
        assert "8 ok" in text
        assert "2 failed" in text
        assert "0 skipped" in text
        assert "5.0s" in text


# ── sync_single_fund ──────────────────────────────────────────────────────


class TestSyncSingleFund:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        fund_service = _make_fund_service(result={"nav": 1000.0})
        brsapi = _make_brsapi()
        svc = _make_service(fund_service=fund_service, brsapi=brsapi)

        result = await svc.sync_single_fund("آگاس")

        assert result.symbol == "آگاس"
        assert result.success is True
        assert result.error is None
        fund_service.update_from_brsapi.assert_awaited_once_with(
            symbol="آگاس",
            brsapi=brsapi,
        )
        brsapi.session.rollback.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_error_in_result_dict(self) -> None:
        fund_service = _make_fund_service(result={"error": "symbol not found"})
        svc = _make_service(fund_service=fund_service)

        result = await svc.sync_single_fund("ناموجود")

        assert result.success is False
        assert result.error == "symbol not found"

    @pytest.mark.asyncio
    async def test_exception_rolls_back_session(self) -> None:
        fund_service = _make_fund_service(error=RuntimeError("db is down"))
        brsapi = _make_brsapi()
        svc = _make_service(fund_service=fund_service, brsapi=brsapi)

        result = await svc.sync_single_fund("آگاس")

        assert result.success is False
        assert "db is down" in result.error
        brsapi.session.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_exception_without_session_does_not_crash(self) -> None:
        fund_service = _make_fund_service(error=ValueError("boom"))
        brsapi = MagicMock()  # no .session attribute
        svc = _make_service(fund_service=fund_service, brsapi=brsapi)

        result = await svc.sync_single_fund("آگاس")

        assert result.success is False
        assert "boom" in result.error


# ── sync_all_funds ────────────────────────────────────────────────────────


class TestSyncAllFunds:
    @pytest.mark.asyncio
    async def test_all_success(self) -> None:
        fund_service = _make_fund_service(result={"nav": 1.0})
        svc = _make_service(fund_service=fund_service)

        with patch("services.fund_sync_service.DELAY_BETWEEN_SYMBOLS", 0.0):
            report = await svc.sync_all_funds(symbols=["آگاس", "آسامید"])

        assert report.total == 2
        assert report.success == 2
        assert report.failed == 0
        assert report.errors == []
        assert fund_service.update_from_brsapi.await_count == 2

    @pytest.mark.asyncio
    async def test_mixed_success_and_failure(self) -> None:
        fund_service = _make_fund_service()
        fund_service.update_from_brsapi = AsyncMock(
            side_effect=[
                {"nav": 1.0},
                {"error": "invalid symbol"},
                RuntimeError("timeout"),
            ]
        )
        svc = _make_service(fund_service=fund_service)

        with patch("services.fund_sync_service.DELAY_BETWEEN_SYMBOLS", 0.0):
            report = await svc.sync_all_funds(symbols=["آگاس", "آسامید", "آکاریز"])

        assert report.total == 3
        assert report.success == 1
        assert report.failed == 2
        assert len(report.errors) == 2
        assert report.errors[0]["symbol"] == "آسامید"
        assert "invalid symbol" in report.errors[0]["error"]
        assert "timeout" in report.errors[1]["error"]

    @pytest.mark.asyncio
    async def test_default_symbols_used(self) -> None:
        fund_service = _make_fund_service()
        svc = _make_service(fund_service=fund_service)

        with patch("services.fund_sync_service.DELAY_BETWEEN_SYMBOLS", 0.0):
            report = await svc.sync_all_funds()

        # Defaults to KNOWN_FUND_SYMBOLS — one update call per symbol.
        assert report.total == len(_known_symbols())
        assert fund_service.update_from_brsapi.await_count == report.total

    @pytest.mark.asyncio
    async def test_concurrent_calls_serialized_by_lock(self) -> None:
        """Two concurrent sync_all_funds calls must not interleave (lock).

        The fake fund service raises when a second call starts while one is
        already in-flight — exactly the failure mode the real shared
        AsyncSession has. Without the lock this test fails; with the lock
        the two sync cycles run one after another.
        """
        import asyncio

        fund_service = _make_fund_service()
        in_flight = 0
        max_in_flight = 0

        async def _concurrency_guard(symbol: str, **kwargs):
            nonlocal in_flight, max_in_flight
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0)  # give the scheduler a chance to interleave
            in_flight -= 1
            return {"nav": 1.0}

        fund_service.update_from_brsapi = AsyncMock(side_effect=_concurrency_guard)
        svc = _make_service(fund_service=fund_service)

        with patch("services.fund_sync_service.DELAY_BETWEEN_SYMBOLS", 0.0):
            r1, r2 = await asyncio.gather(
                svc.sync_all_funds(symbols=["آگاس", "آسامید"]),
                svc.sync_all_funds(symbols=["آگاس", "آسامید"]),
            )

        assert r1.success == 2
        assert r2.success == 2
        # The lock serialized the two cycles — never two calls in flight.
        assert max_in_flight == 1
        assert fund_service.update_from_brsapi.await_count == 4


def _known_symbols():
    from services.fund_sync_service import KNOWN_FUND_SYMBOLS

    return KNOWN_FUND_SYMBOLS


# ── Market-hours helpers ──────────────────────────────────────────────────


class _FakeTime(datetime):
    """datetime subclass returning a fixed Tehran-local wall-clock time."""

    _fixed_time = "10:00:00"  # 10:00 → inside the 08:45-12:30 window

    @classmethod
    def now(cls, tz=None):

        hh, mm, ss = (int(p) for p in cls._fixed_time.split(":"))
        return cls(2026, 1, 15, hh, mm, ss, tzinfo=tz)


class TestMarketHoursHelpers:
    @pytest.mark.asyncio
    async def test_is_market_open_mid_session(self) -> None:
        """10:00 Tehran is inside the 08:45-12:30 window."""
        with patch("services.fund_sync_service.datetime", _FakeTime):
            assert _is_market_open() is True

    @pytest.mark.asyncio
    async def test_is_market_open_before_open(self) -> None:
        """07:00 Tehran is before the market open."""
        _FakeTime._fixed_time = "07:00:00"
        try:
            with patch("services.fund_sync_service.datetime", _FakeTime):
                assert _is_market_open() is False
        finally:
            _FakeTime._fixed_time = "10:00:00"

    @pytest.mark.asyncio
    async def test_is_market_open_after_close(self) -> None:
        """15:00 Tehran is after the market close."""
        _FakeTime._fixed_time = "15:00:00"
        try:
            with patch("services.fund_sync_service.datetime", _FakeTime):
                assert _is_market_open() is False
        finally:
            _FakeTime._fixed_time = "10:00:00"

    @pytest.mark.asyncio
    async def test_next_market_open_delay_before_open(self) -> None:
        """At 07:00 the delay is the time until 08:45 (1h45m)."""
        _FakeTime._fixed_time = "07:00:00"
        try:
            with patch("services.fund_sync_service.datetime", _FakeTime):
                delay = _next_market_open_delay()
            assert delay == pytest.approx(105 * 60, rel=0.05)
        finally:
            _FakeTime._fixed_time = "10:00:00"
