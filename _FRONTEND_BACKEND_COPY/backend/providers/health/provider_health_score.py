from __future__ import annotations

from typing import Any

from core.constants import ProviderHealth
from core.logging import get_logger

logger = get_logger(__name__)


class ProviderHealthScore:
    def __init__(self, name: str, window_size: int = 100) -> None:
        self.name = name
        self.window_size = window_size
        self.successes: int = 0
        self.failures: int = 0
        self.total_calls: int = 0
        self.total_latency_ms: float = 0.0
        self.consecutive_failures: int = 0
        self.consecutive_successes: int = 0

    def record_success(self, latency_ms: float = 0.0) -> None:
        self.successes += 1
        self.total_calls += 1
        self.total_latency_ms += latency_ms
        self.consecutive_failures = 0
        self.consecutive_successes += 1

    def record_failure(self) -> None:
        self.failures += 1
        self.total_calls += 1
        self.consecutive_successes = 0
        self.consecutive_failures += 1

    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 1.0
        return self.successes / self.total_calls

    def failure_rate(self) -> float:
        return 1.0 - self.success_rate()

    def uptime_percentage(self) -> float:
        return self.success_rate() * 100.0

    def avg_latency(self) -> float:
        if self.successes == 0:
            return 0.0
        return self.total_latency_ms / self.successes

    def status(self) -> ProviderHealth:
        if self.consecutive_failures >= 5:
            return ProviderHealth.DOWN
        if self.failure_rate() > 0.3:
            return ProviderHealth.DEGRADED
        if self.total_calls == 0 or self.success_rate() >= 0.95:
            return ProviderHealth.HEALTHY
        return ProviderHealth.DEGRADED

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status().value,
            "success_rate": self.success_rate(),
            "uptime_pct": self.uptime_percentage(),
            "avg_latency_ms": self.avg_latency(),
            "consecutive_failures": self.consecutive_failures,
            "total_calls": self.total_calls,
        }
