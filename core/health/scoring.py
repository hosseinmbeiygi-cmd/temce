from __future__ import annotations

from core.constants import ProviderHealth
from core.health import HealthStatus


class HealthScore:
    def __init__(self) -> None:
        self._weights: dict[str, float] = {}

    def set_weight(self, component: str, weight: float) -> None:
        self._weights[component] = weight

    def calculate(self, results: dict[str, HealthStatus]) -> float:
        total_weight = 0.0
        weighted_sum = 0.0
        for component, status in results.items():
            weight = self._weights.get(component, 1.0)
            total_weight += weight
            score = self._status_to_score(status.status)
            weighted_sum += score * weight
        if total_weight == 0:
            return 0.0
        return weighted_sum / total_weight

    def _status_to_score(self, status: ProviderHealth) -> float:
        mapping = {
            ProviderHealth.HEALTHY: 1.0,
            ProviderHealth.DEGRADED: 0.5,
            ProviderHealth.DOWN: 0.0,
            ProviderHealth.UNKNOWN: 0.0,
        }
        return mapping.get(status, 0.0)

    def label(self, score: float) -> str:
        if score >= 0.9:
            return "healthy"
        elif score >= 0.5:
            return "degraded"
        return "unhealthy"
