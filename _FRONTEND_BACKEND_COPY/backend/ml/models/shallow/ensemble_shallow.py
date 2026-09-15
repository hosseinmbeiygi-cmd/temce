from __future__ import annotations

from typing import Any


class ShallowEnsemble:
    def __init__(self) -> None:
        self._models: list[Any] = []

    def add_model(self, model: Any) -> None:
        self._models.append(model)

    def fit(self, X: Any, y: Any) -> None:
        for model in self._models:
            model.fit(X, y)

    def predict(self, X: Any) -> Any:
        import numpy as np

        predictions = np.array([m.predict(X) for m in self._models])
        return np.mean(predictions, axis=0)
