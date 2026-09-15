from __future__ import annotations

from core.logging import get_logger

logger = get_logger(__name__)


class ModelPromotionPolicy:
    def __init__(self, min_metric_threshold: float = 0.6) -> None:
        self.min_threshold = min_metric_threshold

    def should_promote(self, metrics: dict[str, float], current_best: dict[str, float] | None = None) -> bool:
        new_score = metrics.get("f1", metrics.get("r2", 0))
        if new_score < self.min_threshold:
            return False
        if current_best:
            current_score = current_best.get("f1", current_best.get("r2", 0))
            return new_score > current_score
        return True


class RollbackPolicy:
    def should_rollback(self, model_id: str, version: str, drift_score: float, error_rate: float) -> bool:
        if drift_score > 0.3:
            logger.warning("Rollback triggered for %s v%s: drift=%.3f", model_id, version, drift_score)
            return True
        if error_rate > 0.1:
            logger.warning("Rollback triggered for %s v%s: error_rate=%.3f", model_id, version, error_rate)
            return True
        return False
