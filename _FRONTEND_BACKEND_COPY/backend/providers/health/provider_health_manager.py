from __future__ import annotations

from typing import Any

from core.constants import ProviderHealth
from core.logging import get_logger
from providers.health.provider_health_score import ProviderHealthScore
from providers.health.provider_incidents import ProviderIncidents
from providers.health.provider_status_history import ProviderStatusHistory

logger = get_logger(__name__)


class ProviderHealthManager:
    def __init__(self) -> None:
        self.scores: dict[str, ProviderHealthScore] = {}
        self.incidents = ProviderIncidents()
        self.history = ProviderStatusHistory()

    def register(self, name: str) -> None:
        self.scores[name] = ProviderHealthScore(name=name)

    def record_success(self, name: str, latency_ms: float = 0.0) -> None:
        score = self.scores.get(name)
        if score:
            score.record_success(latency_ms)
            self.history.record(name, ProviderHealth.HEALTHY)

    def record_failure(self, name: str, error: str = "") -> None:
        score = self.scores.get(name)
        if score:
            score.record_failure()
            self.history.record(name, ProviderHealth.DOWN)
            self.incidents.report(name, error)

    def get_health(self, name: str) -> ProviderHealth:
        score = self.scores.get(name)
        if not score:
            return ProviderHealth.UNKNOWN
        return score.status()

    def summary(self) -> dict[str, Any]:
        return {
            name: {"status": s.status().value, "uptime_pct": s.uptime_percentage()} for name, s in self.scores.items()
        }
