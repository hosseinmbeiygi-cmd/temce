"""Unit tests for GoldQualityGate — gold data readiness checks."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from ingestion.gold.quality_gate import (
    GOLD_MAX_STALENESS_MINUTES,
    GOLD_MAX_SUSPECT_RATIO,
    GOLD_MIN_ROWS,
    GoldQualityGate,
)

_FRESH = object()  # sentinel: use a dynamically fresh timestamp


def _fresh_iso() -> str:
    """Timestamp ~1 minute ago, computed at call time.

    Avoids hardcoded dates that go stale and break the staleness check
    as calendar time advances.
    """
    return (datetime.now(UTC) - timedelta(minutes=1)).isoformat()


def _make_result(scalar_value=None):
    """Create a mock result object."""
    result = MagicMock()
    result.scalar_one.return_value = scalar_value
    result.scalar_one_or_none.return_value = scalar_value
    return result


def _mock_session(
    row_count: int = 300,
    latest_fetched_at: str | None | object = _FRESH,
) -> AsyncMock:
    """Create a mock async session.

    ``latest_fetched_at`` defaults to a fresh timestamp so the staleness
    check passes regardless of when the test runs; pass ``None``
    explicitly to test the missing-timestamp path.
    """
    if latest_fetched_at is _FRESH:
        latest_fetched_at = _fresh_iso()
    session = AsyncMock()
    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _make_result(row_count)
        elif call_count == 2:
            return _make_result(latest_fetched_at)
        else:
            return _make_result(0)

    session.execute = mock_execute
    return session


class TestGoldQualityGateReport:
    """Test GoldQualityGate.report() quality checks."""

    @pytest.mark.asyncio
    async def test_ready_when_all_conditions_met(self):
        gate = GoldQualityGate()
        session = _mock_session(row_count=300)
        report = await gate.report(session)
        assert report["is_ready"] is True

    @pytest.mark.asyncio
    async def test_not_ready_when_insufficient_rows(self):
        gate = GoldQualityGate(min_rows=200)
        session = _mock_session(row_count=50)
        report = await gate.report(session)
        assert report["is_ready"] is False
        assert "Insufficient data" in report["reason"]

    @pytest.mark.asyncio
    async def test_not_ready_when_data_stale(self):
        gate = GoldQualityGate(max_staleness_minutes=15)
        stale_time = (datetime.now(UTC) - timedelta(minutes=30)).isoformat()
        session = _mock_session(row_count=300, latest_fetched_at=stale_time)
        report = await gate.report(session)
        assert report["is_ready"] is False

    @pytest.mark.asyncio
    async def test_not_ready_when_no_fetched_at(self):
        gate = GoldQualityGate()
        session = _mock_session(row_count=300, latest_fetched_at=None)
        report = await gate.report(session)
        assert report["is_ready"] is False

    @pytest.mark.asyncio
    async def test_ready_with_exact_min_rows(self):
        gate = GoldQualityGate(min_rows=200)
        session = _mock_session(row_count=200)
        report = await gate.report(session)
        assert report["is_ready"] is True


class TestGoldQualityGateCheck:
    """Test GoldQualityGate.check() boolean result."""

    @pytest.mark.asyncio
    async def test_check_returns_true_when_ready(self):
        gate = GoldQualityGate()
        session = _mock_session(row_count=300)
        result = await gate.check(session)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_returns_false_when_not_ready(self):
        gate = GoldQualityGate(min_rows=200)
        session = _mock_session(row_count=50)
        result = await gate.check(session)
        assert result is False


class TestGoldQualityGateConstants:
    """Test quality gate default constants."""

    def test_default_min_rows(self):
        gate = GoldQualityGate()
        assert gate.min_rows == GOLD_MIN_ROWS

    def test_default_max_staleness(self):
        gate = GoldQualityGate()
        assert gate.max_staleness_minutes == GOLD_MAX_STALENESS_MINUTES

    def test_default_max_suspect_ratio(self):
        gate = GoldQualityGate()
        assert gate.max_suspect_ratio == GOLD_MAX_SUSPECT_RATIO
