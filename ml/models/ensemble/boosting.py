from __future__ import annotations

from typing import Any


class BoostingEnsemble:
    def __init__(self, n_estimators: int = 100, learning_rate: float = 0.1) -> None:
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self._model = None

    def fit(self, X: Any, y: Any) -> None:
        from sklearn.ensemble import GradientBoostingClassifier

        self._model = GradientBoostingClassifier(
            n_estimators=self.n_estimators,
            learning_rate=self.learning_rate,
        )
        self._model.fit(X, y)

    def predict(self, X: Any) -> Any:
        if self._model is None:
            raise RuntimeError("Model not fitted")
        return self._model.predict(X)
