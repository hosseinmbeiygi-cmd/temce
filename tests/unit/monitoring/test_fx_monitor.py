"""Unit tests for FxMonitor — FX metrics and alert state tracking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from monitoring.fx_monitor import (
    FX_STALENESS_ALERT_MINUTES,
    FX_SUSPECT_RATIO_ALERT_THRESHOLD,
    FxAlertState,
    FxMetrics,
    FxMonitor,
)


class TestFxMetrics:
    """Test FxMetrics tracking."""

    def test_initial_state(self):
        """Metrics should start at zero/None."""
        m = FxMetrics()
        assert m.last_success_timestamp is None
        assert m.staleness_seconds is None
        assert m.rows_ingested == 0
        assert m.failures == 0
        assert m.suspect_ratio == 0.0
        assert m.quality_gate_status == 0

    def test_record_sync(self):
        """record_sync should update timestamp and counter."""
        m = FxMetrics()
        m.record_sync(items_count=28, duration_ms=1500)
        assert m.last_success_timestamp is not None
        assert m.rows_ingested == 28
        assert m.staleness_seconds is not None
        assert m.staleness_seconds < 1  # just synced

    def test_record_sync_accumulates(self):
        """Multiple syncs should accumulate row count."""
        m = FxMetrics()
        m.record_sync(items_count=10)
        m.record_sync(items_count=15)
        assert m.rows_ingested == 25

    def test_record_failure(self):
        """record_failure should increment failure counter."""
        m = FxMetrics()
        m.record_failure()
        m.record_failure()
        assert m.failures == 2

    def test_update_suspect_ratio(self):
        """update_suspect_ratio should store the ratio."""
        m = FxMetrics()
        m.update_suspect_ratio(0.03)
        assert m.suspect_ratio == 0.03

    def test_update_quality_gate(self):
        """update_quality_gate should store 0 or 1."""
        m = FxMetrics()
        m.update_quality_gate(True)
        assert m.quality_gate_status == 1
        m.update_quality_gate(False)
        assert m.quality_gate_status == 0

    def test_snapshot(self):
        """snapshot should return all metrics."""
        m = FxMetrics()
        m.record_sync(items_count=28)
        snap = m.snapshot()
        assert "fx_sync_last_success_timestamp" in snap
        assert "fx_sync_rows_ingested_total" in snap
        assert "fx_sync_failures_total" in snap
        assert "fx_suspect_ratio" in snap
        assert "fx_quality_gate_status" in snap
        assert "timestamp" in snap
        assert snap["fx_sync_rows_ingested_total"] == 28


class TestFxAlertState:
    """Test FxAlertState cooldown tracking."""

    def test_can_fire_initially(self):
        """All alerts should be fireable initially."""
        state = FxAlertState()
        assert state.can_fire_staleness() is True
        assert state.can_fire_suspect() is True
        assert state.can_fire_recovery() is True

    def test_cooldown_after_firing(self):
        """Alert should not fire again within cooldown period."""
        state = FxAlertState()
        state.mark_staleness_fired()
        assert state.can_fire_staleness() is False

    def test_cooldown_expires(self):
        """Alert should fire after cooldown expires."""
        state = FxAlertState()
        state._last_staleness_alert = datetime.now(UTC) - timedelta(minutes=31)
        assert state.can_fire_staleness() is True

    def test_independent_cooldowns(self):
        """Different alert types have independent cooldowns."""
        state = FxAlertState()
        state.mark_staleness_fired()
        assert state.can_fire_staleness() is False
        assert state.can_fire_suspect() is True  # independent


class TestFxMonitor:
    """Test FxMonitor integration."""

    @pytest.mark.asyncio
    async def test_record_sync_updates_metrics(self):
        """record_sync should update metrics."""
        monitor = FxMonitor()
        await monitor.record_sync(items_count=28, duration_ms=1500, suspect_count=1)
        assert monitor.metrics.rows_ingested == 28
        assert monitor.metrics.suspect_ratio == 1 / 28

    @pytest.mark.asyncio
    async def test_record_failure(self):
        """record_failure should increment failure counter."""
        monitor = FxMonitor()
        await monitor.record_failure("test error")
        assert monitor.metrics.failures == 1

    @pytest.mark.asyncio
    async def test_check_and_alert_healthy(self):
        """check_and_alert should return healthy when recently synced."""
        monitor = FxMonitor()
        await monitor.record_sync(items_count=28)
        result = await monitor.check_and_alert()
        assert result["is_healthy"] is True
        assert result["alerts_fired"] == []

    @pytest.mark.asyncio
    async def test_check_and_alert_stale(self):
        """check_and_alert should detect staleness."""
        monitor = FxMonitor()
        # Simulate old sync
        monitor.metrics._last_success = (datetime.now(UTC) - timedelta(minutes=20)).timestamp()
        result = await monitor.check_and_alert()
        assert result["is_healthy"] is False
        assert "staleness" in result["alerts_fired"]

    @pytest.mark.asyncio
    async def test_check_and_alert_high_suspect(self):
        """check_and_alert should detect high suspect ratio."""
        monitor = FxMonitor()
        await monitor.record_sync(items_count=100, suspect_count=10)
        result = await monitor.check_and_alert()
        assert "suspect_ratio" in result["alerts_fired"]

    @pytest.mark.asyncio
    async def test_constants(self):
        """Alert thresholds should match document spec."""
        assert FX_STALENESS_ALERT_MINUTES == 15
        assert FX_SUSPECT_RATIO_ALERT_THRESHOLD == 0.05
