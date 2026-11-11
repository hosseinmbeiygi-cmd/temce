from __future__ import annotations

from typing import Any


class HyperparameterTuner:
    def __init__(self, n_trials: int = 50, n_folds: int = 3, horizon: int = 1, gap_extra: int = 0, seed: int = 42) -> None:
        self.n_trials = n_trials
        self.n_folds = n_folds
        self.horizon = horizon
        self.gap_extra = gap_extra
        self.seed = seed

    def optimize(self, model_cls: type, param_space: dict[str, Any], X: Any, y: Any) -> dict[str, Any]:
        import random

        from core.seed import set_global_seed
        from ml.evaluation.cross_validation import CrossValidator

        set_global_seed(self.seed)

        rng = random.Random(self.seed)
        best_score = -float("inf")
        best_params: dict[str, Any] = {}
        for _ in range(self.n_trials):
            params = {k: rng.choice(v) if isinstance(v, list) else v for k, v in param_space.items()}
            model = model_cls(**params)
            try:
                from sklearn.base import clone

                cv = CrossValidator(n_folds=self.n_folds, horizon=self.horizon, gap_extra=self.gap_extra)
                res = cv.validate(clone(model), X, y)
                score = float(res.value["mean_test"]) if res.success else -float("inf")
            except Exception:
                score = -float("inf")
            if score > best_score:
                best_score = score
                best_params = params
        return {"best_params": best_params, "best_score": best_score}
