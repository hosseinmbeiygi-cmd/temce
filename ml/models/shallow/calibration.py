from __future__ import annotations

from typing import Any


class ModelCalibrator:
    def __init__(self, method: str = "sigmoid") -> None:
        self.method = method
        self._calibrator = None

    def fit(self, y_true: Any, y_score: Any) -> None:
        from sklearn.linear_model import LogisticRegression

        base = LogisticRegression()
        base.fit(y_score.reshape(-1, 1), y_true)
        self._calibrator = base

    def calibrate(self, y_score: Any) -> Any:
        if self._calibrator is None:
            raise RuntimeError("Calibrator not fitted")
        return self._calibrator.predict_proba(y_score.reshape(-1, 1))
