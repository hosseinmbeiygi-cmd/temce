"""Unit tests for GoldMonitor — gold metrics and alert state tracking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from monitoring.gold_monitor import (
    GOLD_STALENESS_ALERT_MINUTES,
    GoldAlertState,
    GoldMetrics,
    GoldMonitor,
)


class TestGoldMetrics:
    """Test GoldMetrics tracking."""

    def test_initial_state(self):
        m = GoldMetrics()
        assert m.last_success_timestamp is None
        assert m.staleness_seconds is None
        assert m.rows_ingested == 0
        assert m.failures == 0
        assert m.quality_gate_status == 0

    def test_record_sync(self):
        m = GoldMetrics()
        m.record_sync(items_count=9, duration_ms=1500)
        assert m.last_success_timestamp is not None
        assert m.rows_ingested == 9
        assert m.staleness_seconds is not None
        assert m.staleness_seconds < 1

    def test_record_sync_accumulates(self):
        m = GoldMetrics()
        m.record_sync(items_count=5)
        m.record_sync(items_count=4)
        assert m.rows_ingested == 9

    def test_record_failure(self):
        m = GoldMetrics()
        m.record_failure()
        m.record_failure()
        assert m.failures == 2

    def test_update_quality_gate(self):
        m = GoldMetrics()
        m.update_quality_gate(True)
        assert m.quality_gate_status == 1
        m.update_quality_gate(False)
        assert m.quality_gate_status == 0

    def test_snapshot(self):
        m = GoldMetrics()
        m.record_sync(items_count=9)
        snap = m.snapshot()
        assert "gold_sync_last_success_timestamp" in snap
        assert "gold_sync_rows_ingested_total" in snap
        assert "gold_sync_failures_total" in snap
        assert "gold_quality_gate_status" in snap
        assert "timestamp" in snap
        assert snap["gold_sync_rows_ingested_total"] == 9


class TestGoldAlertState:
    """Test GoldAlertState cooldown tracking."""

    def test_can_fire_initially(self):
        state = GoldAlertState()
        assert state.can_fire_staleness() is True
        assert state.can_fire_recovery() is True

    def test_cooldown_after_firing(self):
        state = GoldAlertState()
        state.mark_staleness_fired()
        assert state.can_fire_staleness() is False

    def test_cooldown_expires(self):
        state = GoldAlertState()
        state._last_staleness_alert = datetime.now(UTC) - timedelta(minutes=31)
        assert state.can_fire_staleness() is True


class TestGoldMonitor:
    """Test GoldMonitor integration."""

    @pytest.mark.asyncio
    async def test_record_sync_updates_metrics(self):
        monitor = GoldMonitor()
        await monitor.record_sync(items_count=9, duration_ms=1500)
        assert monitor.metrics.rows_ingested == 9

    @pytest.mark.asyncio
    async def test_record_failure(self):
        monitor = GoldMonitor()
        await monitor.record_failure("test error")
        assert monitor.metrics.failures == 1

    @pytest.mark.asyncio
    async def test_check_and_alert_healthy(self):
        monitor = GoldMonitor()
        await monitor.record_sync(items_count=9)
        result = await monitor.check_and_alert()
        assert result["is_healthy"] is True
        assert result["alerts_fired"] == []

    @pytest.mark.asyncio
    async def test_check_and_alert_stale(self):
        monitor = GoldMonitor()
        monitor.metrics._last_success = (datetime.now(UTC) - timedelta(minutes=20)).timestamp()
        result = await monitor.check_and_alert()
        assert result["is_healthy"] is False
        assert "staleness" in result["alerts_fired"]

    @pytest.mark.asyncio
    async def test_constants(self):
        assert GOLD_STALENESS_ALERT_MINUTES == 15
