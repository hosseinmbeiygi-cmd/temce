from __future__ import annotations

from typing import Any


class CVTrainer:
    def __init__(self, n_folds: int = 5, horizon: int = 1, gap_extra: int = 0) -> None:
        self.n_folds = n_folds
        self.horizon = horizon
        self.gap_extra = gap_extra

    def cross_validate(self, model: Any, X: Any, y: Any) -> dict[str, list[float]]:
        from ml.evaluation.cross_validation import CrossValidator

        result = CrossValidator(
            n_folds=self.n_folds, horizon=self.horizon, gap_extra=self.gap_extra
        ).validate(model, X, y)
        if not result.success:
            raise ValueError(result.error)
        v = result.value
        return {"scores": v["test_scores"], "mean": v["mean_test"], "std": float(__import__("numpy").std(v["test_scores"])) if v["test_scores"] else 0.0}
