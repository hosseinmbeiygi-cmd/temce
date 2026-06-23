from __future__ import annotations

import pickle
from typing import Any

import numpy as np

from core.paths import validate_safe_path
from ml.models.base import BaseModel
from ml.types import FeatureMatrix, PredictionResult, TargetVector


class LinearRegressionModel(BaseModel):
    def __init__(self, name: str = "linear_regression", params: dict[str, Any] | None = None) -> None:
        super().__init__(name, params)
        from sklearn.linear_model import LinearRegression as SkLinearRegression

        self._model = SkLinearRegression(**self.params)

    def fit(self, X: FeatureMatrix, y: TargetVector, **kwargs: Any) -> None:
        self._model.fit(X.values, y.values)
        self._is_fitted = True

    def predict(self, X: FeatureMatrix) -> PredictionResult:
        preds = self._model.predict(X.values)
        return PredictionResult(predictions=preds, model_id=self.name)

    def save(self, path: str) -> None:
        safe = validate_safe_path(path)
        safe.write_bytes(pickle.dumps(self._model))

    def load(self, path: str) -> None:
        safe = validate_safe_path(path)
        self._model = pickle.loads(safe.read_bytes())
        self._is_fitted = True

    @property
    def coefficients(self) -> np.ndarray:
        return self._model.coef_


class LogisticRegressionModel(BaseModel):
    def __init__(self, name: str = "logistic_regression", params: dict[str, Any] | None = None) -> None:
        super().__init__(name, params)
        from sklearn.linear_model import LogisticRegression as SkLogisticRegression

        self._model = SkLogisticRegression(**self.params)

    def fit(self, X: FeatureMatrix, y: TargetVector, **kwargs: Any) -> None:
        self._model.fit(X.values, y.values)
        self._is_fitted = True

    def predict(self, X: FeatureMatrix) -> PredictionResult:
        preds = self._model.predict(X.values)
        probs = self._model.predict_proba(X.values) if hasattr(self._model, "predict_proba") else None
        return PredictionResult(predictions=preds, probabilities=probs, model_id=self.name)

    def save(self, path: str) -> None:
        safe = validate_safe_path(path)
        safe.write_bytes(pickle.dumps(self._model))

    def load(self, path: str) -> None:
        safe = validate_safe_path(path)
        self._model = pickle.loads(safe.read_bytes())
        self._is_fitted = True
