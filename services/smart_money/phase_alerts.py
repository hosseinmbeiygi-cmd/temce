"""Phase Alert Service — monitors phase changes and generates notifications.

Tracks phase transitions for symbols and creates alerts when significant
phase changes occur (upgrades to bullish phases or downgrades).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from core.logging import get_logger

logger = get_logger(__name__)

# Phase priority (lower = more bullish)
PHASE_PRIORITY: dict[str, int] = {
    "confirmed_smart_money": 1,
    "breakout_ready": 2,
    "float_lock": 3,
    "active_absorption": 4,
    "early_accumulation": 5,
    "neutral": 6,
}

# Phase labels in Persian
PHASE_LABELS: dict[str, str] = {
    "confirmed_smart_money": "پول هوشمند تأیید شد",
    "breakout_ready": "آماده شکست",
    "float_lock": "قفل شناور",
    "active_absorption": "جذب فعال",
    "early_accumulation": "تجمع اولیه",
    "neutral": "خنثی",
}

# Alert severity based on phase change significance
BULLISH_PHASES = {"confirmed_smart_money", "breakout_ready", "float_lock", "active_absorption"}


@dataclass
class PhaseChangeEvent:
    """Represents a phase change event for a symbol."""
    symbol: str
    old_phase: str
    new_phase: str
    old_priority: int
    new_priority: int
    smc_score: float
    timestamp: float
    is_upgrade: bool
    severity: str  # "info", "warning", "success"
    message: str


@dataclass
class PhaseAlertConfig:
    """Configuration for phase alert service."""
    # Minimum SMC score to trigger alerts
    min_smc_for_alert: float = 0.5
    # Cooldown between alerts for same symbol (seconds)
    cooldown_seconds: int = 3600  # 1 hour
    # Phases that trigger "success" alerts
    success_phases: set[str] = field(default_factory=lambda: {"confirmed_smart_money", "breakout_ready"})
    # Phases that trigger "warning" alerts
    warning_phases: set[str] = field(default_factory=lambda: {"neutral"})


class PhaseAlertService:
    """Monitors phase changes and generates alerts.

    Memory-optimized with LRU eviction for phase history.
    """

    def __init__(self, config: PhaseAlertConfig | None = None, max_history: int = 1000) -> None:
        self._config = config or PhaseAlertConfig()
        self._phase_history: dict[str, str] = {}
        self._last_alert_time: dict[str, float] = {}
        self._events: list[PhaseChangeEvent] = []
        self._max_history = max_history
        self._max_events = 200

    @property
    def config(self) -> PhaseAlertConfig:
        return self._config

    def check_phase_change(
        self,
        symbol: str,
        new_phase: str,
        smc_score: float,
    ) -> PhaseChangeEvent | None:
        """Check if phase changed and generate alert if needed.

        Returns PhaseChangeEvent if phase changed and alert should be fired,
        None otherwise.
        """
        old_phase = self._phase_history.get(symbol)

        # First time seeing this symbol
        if old_phase is None:
            self._phase_history[symbol] = new_phase
            # LRU eviction for phase history
            if len(self._phase_history) > self._max_history:
                oldest = next(iter(self._phase_history))
                del self._phase_history[oldest]
            return None

        # No change
        if old_phase == new_phase:
            return None

        # Phase changed!
        self._phase_history[symbol] = new_phase

        old_prio = PHASE_PRIORITY.get(old_phase, 6)
        new_prio = PHASE_PRIORITY.get(new_phase, 6)
        is_upgrade = new_prio < old_prio

        # Determine severity
        severity = self._determine_severity(new_phase, smc_score, is_upgrade)

        # Check cooldown
        if not self._should_alert(symbol, severity):
            return None

        # Check minimum SMC for alert
        if smc_score < self._config.min_smc_for_alert and severity != "success":
            return None

        # Build message
        message = self._build_message(symbol, old_phase, new_phase, smc_score, is_upgrade)

        event = PhaseChangeEvent(
            symbol=symbol,
            old_phase=old_phase,
            new_phase=new_phase,
            old_priority=old_prio,
            new_priority=new_prio,
            smc_score=smc_score,
            timestamp=time.time(),
            is_upgrade=is_upgrade,
            severity=severity,
            message=message,
        )

        self._events.append(event)
        # LRU eviction for events
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]
        self._last_alert_time[symbol] = time.time()

        logger.info(
            "Phase change alert: %s %s → %s (SMC=%.2f, severity=%s)",
            symbol, old_phase, new_phase, smc_score, severity,
        )

        return event

    def _determine_severity(self, phase: str, smc_score: float, is_upgrade: bool) -> str:
        """Determine alert severity based on phase and SMC score."""
        if phase in self._config.success_phases and smc_score >= 0.7:
            return "success"
        elif phase in self._config.warning_phases:
            return "warning"
        elif is_upgrade and smc_score >= 0.6:
            return "info"
        return "info"

    def _should_alert(self, symbol: str, severity: str) -> bool:
        """Check if we should alert based on cooldown."""
        last_time = self._last_alert_time.get(symbol, 0)
        cooldown = self._config.cooldown_seconds

        # Success alerts have shorter cooldown
        if severity == "success":
            cooldown = cooldown // 2

        return time.time() - last_time >= cooldown

    def _build_message(
        self,
        symbol: str,
        old_phase: str,
        new_phase: str,
        smc_score: float,
        is_upgrade: bool,
    ) -> str:
        """Build alert message in Persian."""
        old_label = PHASE_LABELS.get(old_phase, old_phase)
        new_label = PHASE_LABELS.get(new_phase, new_phase)
        direction = "ارتقا" if is_upgrade else "تنزل"
        smc_pct = round(smc_score * 100)

        if is_upgrade:
            return (
                f"🟢 {symbol}: {direction} فاز\n"
                f"از «{old_label}» به «{new_label}»\n"
                f"امتیاز SMC: {smc_pct}%"
            )
        else:
            return (
                f"🔴 {symbol}: {direction} فاز\n"
                f"از «{old_label}» به «{new_label}»\n"
                f"امتیاز SMC: {smc_pct}%"
            )

    def get_recent_events(self, limit: int = 50) -> list[PhaseChangeEvent]:
        """Get recent phase change events."""
        return self._events[-limit:]

    def get_symbol_phase(self, symbol: str) -> str | None:
        """Get current phase for a symbol."""
        return self._phase_history.get(symbol)

    def get_all_phases(self) -> dict[str, str]:
        """Get all tracked symbol phases."""
        return dict(self._phase_history)

    def clear_history(self) -> None:
        """Clear all phase history and events."""
        self._phase_history.clear()
        self._last_alert_time.clear()
        self._events.clear()


# Global singleton
_phase_alert_service: PhaseAlertService | None = None


def get_phase_alert_service() -> PhaseAlertService:
    """Get or create the global phase alert service."""
    global _phase_alert_service
    if _phase_alert_service is None:
        _phase_alert_service = PhaseAlertService()
    return _phase_alert_service
