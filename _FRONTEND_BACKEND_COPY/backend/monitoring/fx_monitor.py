"""FX Market Monitor — metrics, alerts, and health checks for FX data.

Architecture follows the gold monitoring pattern (document §10):
- Prometheus-style metrics via MetricsCollector
- Telegram alerts for sync failure (>15min stale)
- Telegram alert for high suspect ratio (>5%)
- Quality gate status tracking

Usage::

    from monitoring.fx_monitor import fx_monitor
    await fx_monitor.record_sync(items_count=28, duration_ms=1500)
    await fx_monitor.check_and_alert(session)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


# ── FX Metrics (Prometheus-compatible) ────────────────────────────────


class FxMetrics:
    """In-memory metrics for FX sync operations.

    These map to Prometheus-style metrics:
    - fx_sync_last_success_timestamp: gauge (epoch seconds)
    - fx_sync_rows_ingested_total: counter
    - fx_sync_failures_total: counter
    - fx_suspect_ratio: gauge (0.0-1.0)
    - fx_quality_gate_status: gauge (0=not ready, 1=ready)
    """

    def __init__(self) -> None:
        self._last_success: float | None = None
        self._rows_ingested: int = 0
        self._failures: int = 0
        self._suspect_ratio: float = 0.0
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
    def suspect_ratio(self) -> float:
        return self._suspect_ratio

    @property
    def quality_gate_status(self) -> int:
        return self._quality_gate_status

    def record_sync(self, items_count: int, duration_ms: float = 0.0) -> None:
        """Record a successful FX sync."""
        self._last_success = datetime.now(UTC).timestamp()
        self._rows_ingested += items_count

    def record_failure(self) -> None:
        """Record a failed FX sync."""
        self._failures += 1

    def update_suspect_ratio(self, ratio: float) -> None:
        """Update the suspect ratio from quality gate."""
        self._suspect_ratio = ratio

    def update_quality_gate(self, is_ready: bool) -> None:
        """Update quality gate status."""
        self._quality_gate_status = 1 if is_ready else 0

    def snapshot(self) -> dict[str, Any]:
        """Return a snapshot of all FX metrics."""
        return {
            "fx_sync_last_success_timestamp": self._last_success,
            "fx_sync_staleness_seconds": self.staleness_seconds,
            "fx_sync_rows_ingested_total": self._rows_ingested,
            "fx_sync_failures_total": self._failures,
            "fx_suspect_ratio": self._suspect_ratio,
            "fx_quality_gate_status": self._quality_gate_status,
            "timestamp": datetime.now(UTC).isoformat(),
        }


# ── FX Alert Rules ────────────────────────────────────────────────────

# Alert when sync hasn't succeeded for this many minutes
FX_STALENESS_ALERT_MINUTES = 15

# Alert when suspect ratio exceeds this threshold
FX_SUSPECT_RATIO_ALERT_THRESHOLD = 0.05

# Cooldown between repeated alerts (minutes)
FX_ALERT_COOLDOWN_MINUTES = 30


class FxAlertState:
    """Tracks alert cooldowns to avoid spam."""

    def __init__(self) -> None:
        self._last_staleness_alert: datetime | None = None
        self._last_suspect_alert: datetime | None = None
        self._last_recovery_alert: datetime | None = None

    def can_fire_staleness(self) -> bool:
        """Check if staleness alert can fire (cooldown expired)."""
        if self._last_staleness_alert is None:
            return True
        elapsed = (datetime.now(UTC) - self._last_staleness_alert).total_seconds() / 60
        return elapsed >= FX_ALERT_COOLDOWN_MINUTES

    def can_fire_suspect(self) -> bool:
        """Check if suspect ratio alert can fire (cooldown expired)."""
        if self._last_suspect_alert is None:
            return True
        elapsed = (datetime.now(UTC) - self._last_suspect_alert).total_seconds() / 60
        return elapsed >= FX_ALERT_COOLDOWN_MINUTES

    def can_fire_recovery(self) -> bool:
        """Check if recovery alert can fire."""
        if self._last_recovery_alert is None:
            return True
        elapsed = (datetime.now(UTC) - self._last_recovery_alert).total_seconds() / 60
        return elapsed >= FX_ALERT_COOLDOWN_MINUTES

    def mark_staleness_fired(self) -> None:
        self._last_staleness_alert = datetime.now(UTC)

    def mark_suspect_fired(self) -> None:
        self._last_suspect_alert = datetime.now(UTC)

    def mark_recovery_fired(self) -> None:
        self._last_recovery_alert = datetime.now(UTC)


# ── FX Monitor ────────────────────────────────────────────────────────


class FxMonitor:
    """Main FX monitoring class — combines metrics, alerts, and health checks.

    Usage::

        monitor = FxMonitor()
        monitor.metrics.record_sync(items_count=28)
        await monitor.check_and_alert(session)
    """

    def __init__(self) -> None:
        self.metrics = FxMetrics()
        self._alert_state = FxAlertState()
        self._was_unhealthy: bool = False  # track recovery

    async def record_sync(
        self,
        items_count: int,
        duration_ms: float = 0.0,
        suspect_count: int = 0,
    ) -> None:
        """Record a successful FX sync and update metrics."""
        self.metrics.record_sync(items_count, duration_ms)

        # Update suspect ratio
        if items_count > 0:
            ratio = suspect_count / items_count
            self.metrics.update_suspect_ratio(ratio)

    async def record_failure(self, error: str = "") -> None:
        """Record a failed FX sync."""
        self.metrics.record_failure()
        logger.warning("FX sync failure recorded: %s", error)

    async def check_and_alert(self, session: Any = None) -> dict[str, Any]:
        """Check FX health and fire alerts if needed.

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
            if staleness_minutes > FX_STALENESS_ALERT_MINUTES:
                if self._alert_state.can_fire_staleness():
                    await self._send_telegram_alert(
                        title="⚠️ FX Sync Stale",
                        message=(
                            f"FX data hasn't synced for {staleness_minutes:.0f} minutes "
                            f"(threshold: {FX_STALENESS_ALERT_MINUTES}min). "
                            f"Last success: {datetime.fromtimestamp(self.metrics.last_success_timestamp, tz=UTC).strftime('%H:%M:%S UTC')}"
                        ),
                        severity="warning",
                    )
                    self._alert_state.mark_staleness_fired()
                    alerts_fired.append("staleness")
                self._was_unhealthy = True

        # Check suspect ratio
        if self.metrics.suspect_ratio > FX_SUSPECT_RATIO_ALERT_THRESHOLD:
            if self._alert_state.can_fire_suspect():
                await self._send_telegram_alert(
                    title="⚠️ FX High Suspect Ratio",
                    message=(
                        f"Suspect data ratio: {self.metrics.suspect_ratio:.1%} "
                        f"(threshold: {FX_SUSPECT_RATIO_ALERT_THRESHOLD:.0%}). "
                        f"Possible source errors or extreme volatility."
                    ),
                    severity="warning",
                )
                self._alert_state.mark_suspect_fired()
                alerts_fired.append("suspect_ratio")

        # Recovery alert
        if self._was_unhealthy and staleness is not None and staleness < 300:
            if self._alert_state.can_fire_recovery():
                await self._send_telegram_alert(
                    title="✅ FX Sync Recovered",
                    message=f"FX sync is healthy again. Staleness: {staleness:.0f}s",
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

fx_monitor = FxMonitor()
