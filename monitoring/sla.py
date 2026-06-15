from __future__ import annotations

from datetime import datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class SLAMonitor:
    def __init__(self, uptime_threshold_pct: float = 99.9, latency_threshold_ms: float = 500) -> None:
        self.uptime_threshold = uptime_threshold_pct
        self.latency_threshold = latency_threshold_ms
        self._checks: list[dict[str, Any]] = []

    def record_check(self, service: str, success: bool, latency_ms: float) -> None:
        self._checks.append(
            {
                "service": service,
                "success": success,
                "latency_ms": latency_ms,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    def uptime(self, service: str) -> float:
        relevant = [c for c in self._checks if c["service"] == service]
        if not relevant:
            return 100.0
        successes = sum(1 for c in relevant if c["success"])
        return successes / len(relevant) * 100

    def report(self) -> dict[str, Any]:
        services = {c["service"] for c in self._checks}
        return {
            service: {
                "uptime_pct": self.uptime(service),
                "check_count": sum(1 for c in self._checks if c["service"] == service),
            }
            for service in services
        }
