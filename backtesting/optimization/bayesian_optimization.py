from __future__ import annotations

from collections.abc import Callable

import numpy as np


class BayesianOptimization:
    def __init__(self, n_iter: int = 20, n_initial: int = 5) -> None:
        self.n_iter = n_iter
        self.n_initial = n_initial
        self._X: list[dict[str, float]] = []
        self._y: list[float] = []

    def optimize(
        self,
        param_bounds: dict[str, tuple[float, float]],
        objective_fn: Callable[[dict[str, float]], float],
    ) -> tuple[dict[str, float], float]:
        list(param_bounds.keys())
        for _ in range(self.n_initial):
            sample = {n: np.random.uniform(lo, hi) for n, (lo, hi) in param_bounds.items()}
            value = objective_fn(sample)
            self._X.append(sample)
            self._y.append(value)

        for _i in range(self.n_iter):
            next_point = self._propose(param_bounds)
            value = objective_fn(next_point)
            self._X.append(next_point)
            self._y.append(value)

        best_idx = int(np.argmax(self._y))
        return self._X[best_idx], self._y[best_idx]

    def _propose(self, bounds: dict[str, tuple[float, float]]) -> dict[str, float]:
        n_params = len(bounds)
        X = np.array([[v[n] for n in bounds] for v in self._X])
        y = np.array(self._y)
        y.max()
        n_candidates = 1000
        candidates = np.random.rand(n_candidates, n_params)
        for i, (_n, (lo, hi)) in enumerate(bounds.items()):
            candidates[:, i] = lo + candidates[:, i] * (hi - lo)

        if len(X) < 2:
            best_idx = np.argmax(y)
            return dict(self._X[best_idx])

        from scipy.spatial.distance import cdist

        distances = cdist(candidates, X).min(axis=1)
        ei = y.max() - y.mean() + 0.01 * distances
        ei = np.maximum(ei, 0)
        best_candidate = candidates[np.argmax(ei)]
        return {n: float(best_candidate[i]) for i, n in enumerate(bounds)}

    def get_history(self) -> tuple[list[dict[str, float]], list[float]]:
        return list(self._X), list(self._y)

    def reset(self) -> None:
        self._X.clear()
        self._y.clear()
