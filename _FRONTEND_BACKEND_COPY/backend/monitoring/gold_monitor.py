"""Gold Market Monitor — metrics, alerts, and health checks for gold data.

Architecture follows the gold implementation document (section 9):
- Prometheus-style metrics via MetricsCollector
- Telegram alerts for sync failure (>15min stale)
- Quality gate status tracking

Usage::

    from monitoring.gold_monitor import gold_monitor
    await gold_monitor.record_sync(items_count=9, duration_ms=1500)
    await gold_monitor.check_and_alert(session)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


# ── Gold Metrics (Prometheus-compatible) ──────────────────────────────


class GoldMetrics:
    """In-memory metrics for gold sync operations.

    These map to Prometheus-style metrics:
    - gold_sync_last_success_timestamp: gauge (epoch seconds)
    - gold_sync_rows_ingested_total: counter
    - gold_sync_failures_total: counter
    - gold_quality_gate_status: gauge (0=not ready, 1=ready)
    """

    def __init__(self) -> None:
        self._last_success: float | None = None
        self._rows_ingested: int = 0
        self._failures: int = 0
        self._quality_gate_status: int = 0  # 0=not ready, 1=ready

    @property
    def last_success_timestamp(self) -> float | None:
        """Timestamp of last successful sync (epoch seconds)."""
        return self._last_success

    @property
    def staleness_seconds(self) -> float | None:
        """Seconds since last successful sync. None if never synced."""
        if self._last_success is None:
            return None
        return datetime.now(UTC).timestamp() - self._last_success

    @property
    def rows_ingested(self) -> int:
        return self._rows_ingested

    @property
    def failures(self) -> int:
        return self._failures

    @property
    def quality_gate_status(self) -> int:
        return self._quality_gate_status

    def record_sync(self, items_count: int, duration_ms: float = 0.0) -> None:
        """Record a successful gold sync."""
        self._last_success = datetime.now(UTC).timestamp()
        self._rows_ingested += items_count

    def record_failure(self) -> None:
        """Record a failed gold sync."""
        self._failures += 1

    def update_quality_gate(self, is_ready: bool) -> None:
        """Update quality gate status."""
        self._quality_gate_status = 1 if is_ready else 0

    def snapshot(self) -> dict[str, Any]:
        """Return a snapshot of all gold metrics."""
        return {
            "gold_sync_last_success_timestamp": self._last_success,
            "gold_sync_staleness_seconds": self.staleness_seconds,
            "gold_sync_rows_ingested_total": self._rows_ingested,
            "gold_sync_failures_total": self._failures,
            "gold_quality_gate_status": self._quality_gate_status,
            "timestamp": datetime.now(UTC).isoformat(),
        }


# ── Gold Alert Rules ──────────────────────────────────────────────────

# Alert when sync hasn't succeeded for this many minutes
GOLD_STALENESS_ALERT_MINUTES = 15

# Cooldown between repeated alerts (minutes)
GOLD_ALERT_COOLDOWN_MINUTES = 30


class GoldAlertState:
    """Tracks alert cooldowns to avoid spam."""

    def __init__(self) -> None:
        self._last_staleness_alert: datetime | None = None
        self._last_recovery_alert: datetime | None = None

    def can_fire_staleness(self) -> bool:
        """Check if staleness alert can fire (cooldown expired)."""
        if self._last_staleness_alert is None:
            return True
        elapsed = (datetime.now(UTC) - self._last_staleness_alert).total_seconds() / 60
        return elapsed >= GOLD_ALERT_COOLDOWN_MINUTES

    def can_fire_recovery(self) -> bool:
        """Check if recovery alert can fire."""
        if self._last_recovery_alert is None:
            return True
        elapsed = (datetime.now(UTC) - self._last_recovery_alert).total_seconds() / 60
        return elapsed >= GOLD_ALERT_COOLDOWN_MINUTES

    def mark_staleness_fired(self) -> None:
        self._last_staleness_alert = datetime.now(UTC)

    def mark_recovery_fired(self) -> None:
        self._last_recovery_alert = datetime.now(UTC)


# ── Gold Monitor ──────────────────────────────────────────────────────


class GoldMonitor:
    """Main gold monitoring class — combines metrics, alerts, and health checks.

    Usage::

        monitor = GoldMonitor()
        monitor.metrics.record_sync(items_count=9)
        await monitor.check_and_alert(session)
    """

    def __init__(self) -> None:
        self.metrics = GoldMetrics()
        self._alert_state = GoldAlertState()
        self._was_unhealthy: bool = False  # track recovery

    async def record_sync(
        self,
        items_count: int,
        duration_ms: float = 0.0,
    ) -> None:
        """Record a successful gold sync and update metrics."""
        self.metrics.record_sync(items_count, duration_ms)

    async def record_failure(self, error: str = "") -> None:
        """Record a failed gold sync."""
        self.metrics.record_failure()
        logger.warning("Gold sync failure recorded: %s", error)

    async def check_and_alert(self, session: Any = None) -> dict[str, Any]:
        """Check gold health and fire alerts if needed.

        Returns a status dict with:
        - is_healthy: bool
        - alerts_fired: list[str]
        - metrics: dict (snapshot)
        """
        alerts_fired: list[str] = []

        # Check staleness
        staleness = self.metrics.staleness_seconds
        if staleness is not None:
            staleness_minutes = staleness / 60

            # Staleness alert
            if staleness_minutes > GOLD_STALENESS_ALERT_MINUTES:
                if self._alert_state.can_fire_staleness():
                    await self._send_telegram_alert(
                        title="⚠️ Gold Sync Stale",
                        message=(
                            f"Gold data hasn't synced for {staleness_minutes:.0f} minutes "
                            f"(threshold: {GOLD_STALENESS_ALERT_MINUTES}min). "
                            f"Last success: {datetime.fromtimestamp(self.metrics.last_success_timestamp, tz=UTC).strftime('%H:%M:%S UTC')}"
                        ),
                        severity="warning",
                    )
                    self._alert_state.mark_staleness_fired()
                    alerts_fired.append("staleness")
                self._was_unhealthy = True

        # Recovery alert
        if self._was_unhealthy and staleness is not None and staleness < 300:
            if self._alert_state.can_fire_recovery():
                await self._send_telegram_alert(
                    title="✅ Gold Sync Recovered",
                    message=f"Gold sync is healthy again. Staleness: {staleness:.0f}s",
                    severity="info",
                )
                self._alert_state.mark_recovery_fired()
                alerts_fired.append("recovery")
            self._was_unhealthy = False

        return {
            "is_healthy": not self._was_unhealthy,
            "alerts_fired": alerts_fired,
            "metrics": self.metrics.snapshot(),
        }

    async def _send_telegram_alert(
        self,
        title: str,
        message: str,
        severity: str = "info",
    ) -> None:
        """Send alert via Telegram."""
        try:
            from integrations.notifications.telegram_sender import TelegramSender

            sender = TelegramSender()
            icon = {"critical": "🔴", "warning": "⚠️", "info": "✅"}.get(severity, "ℹ️")
            text = f"<b>{icon} {title}</b>\n\n{message}"
            result = await sender.send(text)
            if not result.success:
                logger.debug("Telegram alert failed: %s", result.error)
        except Exception as e:
            logger.debug("Could not send Telegram alert: %s", e)


# ── Singleton ─────────────────────────────────────────────────────────

gold_monitor = GoldMonitor()
