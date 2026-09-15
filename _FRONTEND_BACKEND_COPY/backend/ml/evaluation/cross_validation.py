from __future__ import annotations

from typing import Any

from core.result import Result


class CrossValidator:
    def __init__(self, n_folds: int = 5) -> None:
        self.n_folds = n_folds

    def validate(self, model: Any, X: Any, y: Any) -> Result[dict[str, Any]]:
        try:
            from sklearn.model_selection import cross_validate as sk_cv

            scores = sk_cv(model, X, y, cv=self.n_folds, return_train_score=True)
            return Result.ok(
                {
                    "test_scores": scores["test_score"].tolist(),
                    "train_scores": scores["train_score"].tolist(),
                    "mean_test": float(scores["test_score"].mean()),
                    "mean_train": float(scores["train_score"].mean()),
                }
            )
        except Exception as e:
            return Result.fail(str(e))
