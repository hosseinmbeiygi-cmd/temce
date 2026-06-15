from __future__ import annotations

from typing import Any


class CVTrainer:
    def __init__(self, n_folds: int = 5) -> None:
        self.n_folds = n_folds

    def cross_validate(self, model: Any, X: Any, y: Any) -> dict[str, list[float]]:
        from sklearn.model_selection import cross_val_score

        scores = cross_val_score(model, X, y, cv=self.n_folds)
        return {"scores": scores.tolist(), "mean": float(scores.mean()), "std": float(scores.std())}
