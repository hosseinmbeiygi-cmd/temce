from __future__ import annotations

from typing import Any


class BayesianModel:
    def __init__(self, alpha: float = 1.0) -> None:
        self.alpha = alpha
        self._model = None

    def fit(self, X: Any, y: Any) -> None:
        from sklearn.linear_model import BayesianRidge

        self._model = BayesianRidge(alpha_1=self.alpha)
        self._model.fit(X, y)

    def predict(self, X: Any) -> Any:
        if self._model is None:
            raise RuntimeError("Model not fitted")
        return self._model.predict(X)
