from __future__ import annotations

from typing import Any


class KNNModel:
    def __init__(self, n_neighbors: int = 5) -> None:
        self.n_neighbors = n_neighbors
        self._model = None

    def fit(self, X: Any, y: Any) -> None:
        from sklearn.neighbors import KNeighborsClassifier

        self._model = KNeighborsClassifier(n_neighbors=self.n_neighbors)
        self._model.fit(X, y)

    def predict(self, X: Any) -> Any:
        if self._model is None:
            raise RuntimeError("Model not fitted")
        return self._model.predict(X)
