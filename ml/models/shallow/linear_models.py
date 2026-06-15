from __future__ import annotations

import pickle
from typing import Any

import numpy as np

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
        with open(path, "wb") as f:
            pickle.dump(self._model, f)

    def load(self, path: str) -> None:
        with open(path, "rb") as f:
            self._model = pickle.load(f)
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
        with open(path, "wb") as f:
            pickle.dump(self._model, f)

    def load(self, path: str) -> None:
        with open(path, "rb") as f:
            self._model = pickle.load(f)
        self._is_fitted = True
