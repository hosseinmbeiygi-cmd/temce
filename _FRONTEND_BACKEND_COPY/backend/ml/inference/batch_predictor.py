from __future__ import annotations

from typing import Any


class BatchPredictor:
    def __init__(self, model: Any, batch_size: int = 64) -> None:
        self.model = model
        self.batch_size = batch_size

    def predict(self, X: Any) -> Any:
        import numpy as np

        n = len(X)
        results = []
        for i in range(0, n, self.batch_size):
            batch = X[i : i + self.batch_size]
            results.append(np.asarray(self.model.predict(batch)))
        return np.concatenate(results)
