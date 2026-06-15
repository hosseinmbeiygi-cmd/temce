from __future__ import annotations

from typing import Any


class ModelEnsembler:
    def __init__(self, strategy: str = "average") -> None:
        self.strategy = strategy
        self._models: list[Any] = []

    def add(self, model: Any) -> None:
        self._models.append(model)

    def predict(self, X: Any) -> Any:
        import numpy as np

        if not self._models:
            raise RuntimeError("No models in ensemble")
        preds = np.array([m.predict(X) for m in self._models])
        if self.strategy == "average":
            return np.mean(preds, axis=0)
        if self.strategy == "median":
            return np.median(preds, axis=0)
        if self.strategy == "max":
            return np.max(preds, axis=0)
        raise ValueError(f"Unknown strategy: {self.strategy}")
