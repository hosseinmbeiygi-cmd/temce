from __future__ import annotations

from typing import Any


class WeightedAverageEnsemble:
    def __init__(self, weights: list[float] | None = None) -> None:
        self.weights = weights
        self._models: list[Any] = []

    def add_model(self, model: Any) -> None:
        self._models.append(model)

    def predict(self, X: Any) -> Any:
        import numpy as np

        if not self._models:
            raise RuntimeError("No models in ensemble")
        predictions = np.array([m.predict(X) for m in self._models])
        if self.weights is None:
            self.weights = [1.0 / len(self._models)] * len(self._models)
        return np.average(predictions, axis=0, weights=self.weights)
