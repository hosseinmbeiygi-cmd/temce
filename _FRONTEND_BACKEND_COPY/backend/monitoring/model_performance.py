from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class ModelPerformanceMonitor:
    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def record_prediction(self, model_id: str, version: str, prediction: Any, actual: Any) -> None:
        self._records.append(
            {
                "model_id": model_id,
                "version": version,
                "prediction": prediction,
                "actual": actual,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    def hit_rate(self, model_id: str, window: int = 100) -> float:
        relevant = [r for r in self._records if r["model_id"] == model_id][-window:]
        if not relevant:
            return 0.0
        hits = sum(1 for r in relevant if r.get("correct", False))
        return hits / len(relevant)

    def report(self, model_id: str) -> dict[str, Any]:
        return {
            "model_id": model_id,
            "total_predictions": sum(1 for r in self._records if r["model_id"] == model_id),
            "hit_rate": self.hit_rate(model_id),
        }
