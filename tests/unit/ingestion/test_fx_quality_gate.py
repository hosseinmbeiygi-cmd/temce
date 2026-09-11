"""Unit tests for FxQualityGate — FX data readiness checks.

Tests the three quality conditions: volume, freshness, and suspect ratio.
Uses mocked database sessions for async testing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from ingestion.fx.quality_gate import (
    FX_MAX_STALENESS_MINUTES,
    FX_MAX_SUSPECT_RATIO,
    FX_MIN_ROWS,
    FxQualityGate,
)

# ── Helpers ───────────────────────────────────────────────────────────


_FRESH = object()  # sentinel: use a dynamically fresh timestamp


def _fresh_iso() -> str:
    """Timestamp ~1 minute ago, computed at call time.

    Avoids hardcoded dates that go stale and break the staleness check
    (15-minute threshold) as calendar time advances.
    """
    return (datetime.now(UTC) - timedelta(minutes=1)).isoformat()


def _make_result(scalar_value=None):
    """Create a mock result object with scalar_one()/scalar_one_or_none()."""
    result = MagicMock()
    result.scalar_one.return_value = scalar_value
    result.scalar_one_or_none.return_value = scalar_value
    return result


def _mock_session(
    row_count: int = 300,
    latest_fetched_at: str | None | object = _FRESH,
) -> AsyncMock:
    """Create a mock async session with configurable query results.

    ``latest_fetched_at`` defaults to a fresh timestamp so the staleness
    check passes regardless of when the test runs; pass ``None``
    explicitly to test the missing-timestamp path.
    """
    if latest_fetched_at is _FRESH:
        latest_fetched_at = _fresh_iso()
    session = AsyncMock()

    # Track call order
    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Row count query
            return _make_result(row_count)
        elif call_count == 2:
            # Latest fetched_at query
            return _make_result(latest_fetched_at)
        else:
            # Suspect count query (always returns 0 — column may not exist)
            return _make_result(0)

    session.execute = mock_execute
    return session


# ── FxQualityGate.report() Tests ──────────────────────────────────────


class TestFxQualityGateReport:
    """Test FxQualityGate.report() quality checks."""

    @pytest.mark.asyncio
    async def test_ready_when_all_conditions_met(self):
        """Market should be ready when all conditions pass."""
        gate = FxQualityGate()
        session = _mock_session(row_count=300)

        report = await gate.report(session)

        assert report["is_ready"] is True
        assert report["row_count"] == 300
        assert report["reason"] is None

    @pytest.mark.asyncio
    async def test_not_ready_when_insufficient_rows(self):
        """Market should not be ready when row count is below threshold."""
        gate = FxQualityGate(min_rows=200)
        session = _mock_session(row_count=50)

        report = await gate.report(session)

        assert report["is_ready"] is False
        assert report["row_count"] == 50
        assert "Insufficient data" in report["reason"]

    @pytest.mark.asyncio
    async def test_not_ready_when_data_stale(self):
        """Market should not be ready when data is stale."""
        gate = FxQualityGate(max_staleness_minutes=15)
        # Data from 30 minutes ago
        stale_time = (datetime.now(UTC) - timedelta(minutes=30)).isoformat()
        session = _mock_session(row_count=300, latest_fetched_at=stale_time)

        report = await gate.report(session)

        assert report["is_ready"] is False
        assert "stale" in report["reason"].lower() or "Stale" in report["reason"]

    @pytest.mark.asyncio
    async def test_not_ready_when_no_fetched_at(self):
        """Market should not be ready when fetched_at is None."""
        gate = FxQualityGate()
        session = _mock_session(row_count=300, latest_fetched_at=None)

        report = await gate.report(session)

        assert report["is_ready"] is False
        assert "fetched_at" in report["reason"].lower()

    @pytest.mark.asyncio
    async def test_ready_with_exact_min_rows(self):
        """Market should be ready when row count equals minimum."""
        gate = FxQualityGate(min_rows=200)
        session = _mock_session(row_count=200)

        report = await gate.report(session)

        assert report["is_ready"] is True

    @pytest.mark.asyncio
    async def test_ready_with_just_fresh_data(self):
        """Market should be ready when data is just within staleness threshold."""
        gate = FxQualityGate(max_staleness_minutes=15)
        # Data from 14 minutes ago (just within threshold)
        fresh_time = (datetime.now(UTC) - timedelta(minutes=14)).isoformat()
        session = _mock_session(row_count=300, latest_fetched_at=fresh_time)

        report = await gate.report(session)

        assert report["is_ready"] is True

    @pytest.mark.asyncio
    async def test_report_includes_suspect_ratio(self):
        """Report should include suspect_ratio field."""
        gate = FxQualityGate()
        session = _mock_session(row_count=300)

        report = await gate.report(session)

        assert "suspect_ratio" in report
        assert isinstance(report["suspect_ratio"], float)


# ── FxQualityGate.check() Tests ───────────────────────────────────────


class TestFxQualityGateCheck:
    """Test FxQualityGate.check() boolean result."""

    @pytest.mark.asyncio
    async def test_check_returns_true_when_ready(self):
        """check() should return True when all conditions pass."""
        gate = FxQualityGate()
        session = _mock_session(row_count=300)

        result = await gate.check(session)

        assert result is True

    @pytest.mark.asyncio
    async def test_check_returns_false_when_not_ready(self):
        """check() should return False when conditions fail."""
        gate = FxQualityGate(min_rows=200)
        session = _mock_session(row_count=50)

        result = await gate.check(session)

        assert result is False


# ── FxQualityGate Threshold Tests ─────────────────────────────────────


class TestFxQualityGateThresholds:
    """Test FxQualityGate with different threshold configurations."""

    @pytest.mark.asyncio
    async def test_custom_min_rows(self):
        """Custom min_rows should be respected."""
        gate = FxQualityGate(min_rows=500)
        session = _mock_session(row_count=300)

        report = await gate.report(session)

        assert report["is_ready"] is False
        assert "300 rows < 500 required" in report["reason"]

    @pytest.mark.asyncio
    async def test_custom_max_staleness(self):
        """Custom max_staleness_minutes should be respected."""
        gate = FxQualityGate(max_staleness_minutes=5)
        # Data from 6 minutes ago
        stale_time = (datetime.now(UTC) - timedelta(minutes=6)).isoformat()
        session = _mock_session(row_count=300, latest_fetched_at=stale_time)

        report = await gate.report(session)

        assert report["is_ready"] is False

    @pytest.mark.asyncio
    async def test_zero_min_rows_always_passes_volume(self):
        """Zero min_rows should always pass the volume check."""
        gate = FxQualityGate(min_rows=0)
        session = _mock_session(row_count=0)

        report = await gate.report(session)

        # Should pass volume check (0 >= 0)
        assert "Insufficient data" not in (report["reason"] or "")


# ── Module Constants Tests ────────────────────────────────────────────


class TestFxQualityGateConstants:
    """Test quality gate default constants."""

    def test_default_min_rows(self):
        """Default min_rows should match FX_MIN_ROWS."""
        gate = FxQualityGate()
        assert gate.min_rows == FX_MIN_ROWS

    def test_default_max_staleness(self):
        """Default max_staleness should match FX_MAX_STALENESS_MINUTES."""
        gate = FxQualityGate()
        assert gate.max_staleness_minutes == FX_MAX_STALENESS_MINUTES

    def test_default_max_suspect_ratio(self):
        """Default max_suspect_ratio should match FX_MAX_SUSPECT_RATIO."""
        gate = FxQualityGate()
        assert gate.max_suspect_ratio == FX_MAX_SUSPECT_RATIO
