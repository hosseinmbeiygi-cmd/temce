from __future__ import annotations

from typing import Any


class HyperparameterTuner:
    def __init__(self, n_trials: int = 50) -> None:
        self.n_trials = n_trials

    def optimize(self, model_cls: type, param_space: dict[str, Any], X: Any, y: Any) -> dict[str, Any]:
        import random

        best_score = -float("inf")
        best_params = {}
        for _ in range(self.n_trials):
            params = {k: random.choice(v) if isinstance(v, list) else v for k, v in param_space.items()}
            model = model_cls(**params)
            try:
                from sklearn.model_selection import cross_val_score

                scores = cross_val_score(model, X, y, cv=3)
                score = scores.mean()
            except Exception:
                score = -float("inf")
            if score > best_score:
                best_score = score
                best_params = params
        return {"best_params": best_params, "best_score": best_score}
