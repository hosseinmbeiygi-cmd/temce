from __future__ import annotations

from typing import Any


class MixtureOfExperts:
    def __init__(self) -> None:
        self._experts: list[Any] = []
        self._gating: Any = None

    def add_expert(self, expert: Any) -> None:
        self._experts.append(expert)

    def fit(self, X: Any, y: Any) -> None:
        from sklearn.linear_model import LogisticRegression

        self._gating = LogisticRegression()
        self._gating.fit(X, y)
        for expert in self._experts:
            expert.fit(X, y)

    def predict(self, X: Any) -> Any:
        if self._gating is None:
            raise RuntimeError("Not fitted")
        import numpy as np

        gate_preds = self._gating.predict_proba(X)
        expert_preds = np.array([e.predict(X) for e in self._experts])
        weights = gate_preds.T
        return np.average(expert_preds, axis=0, weights=weights)
