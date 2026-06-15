from __future__ import annotations

from typing import Any


class BaggingEnsemble:
    def __init__(self, n_estimators: int = 10) -> None:
        self.n_estimators = n_estimators
        self._models: list[Any] = []

    def fit(self, X: Any, y: Any) -> None:
        from sklearn.ensemble import BaggingClassifier
        from sklearn.tree import DecisionTreeClassifier

        self._model = BaggingClassifier(
            estimator=DecisionTreeClassifier(),
            n_estimators=self.n_estimators,
        )
        self._model.fit(X, y)

    def predict(self, X: Any) -> Any:
        if not hasattr(self, "_model") or self._model is None:
            raise RuntimeError("Model not fitted")
        return self._model.predict(X)
