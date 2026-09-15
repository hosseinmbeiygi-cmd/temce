from __future__ import annotations

import pickle
from typing import Any

import numpy as np

from core.paths import validate_safe_path
from ml.models.base import BaseModel
from ml.models.registry import model_registry
from ml.types import FeatureMatrix, PredictionResult, TargetVector


class RandomForestModel(BaseModel):
    def __init__(self, name: str = "random_forest", params: dict[str, Any] | None = None) -> None:
        super().__init__(name, params)
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

        task = self.params.pop("task", "regression")
        if task == "classification":
            self._model = RandomForestClassifier(**self.params)
        else:
            self._model = RandomForestRegressor(**self.params)

    def fit(self, X: FeatureMatrix, y: TargetVector, **kwargs: Any) -> None:
        self._model.fit(X.values, y.values)
        self._is_fitted = True

    def predict(self, X: FeatureMatrix) -> PredictionResult:
        preds = self._model.predict(X.values)
        probs = None
        if hasattr(self._model, "predict_proba"):
            probs = self._model.predict_proba(X.values)
        return PredictionResult(predictions=preds, probabilities=probs, model_id=self.name)

    def save(self, path: str) -> None:
        safe = validate_safe_path(path)
        safe.write_bytes(pickle.dumps(self._model))

    def load(self, path: str) -> None:
        safe = validate_safe_path(path)
        self._model = pickle.loads(safe.read_bytes())
        self._is_fitted = True

    @property
    def feature_importances(self) -> np.ndarray:
        return self._model.feature_importances_


class XGBoostModel(BaseModel):
    def __init__(self, name: str = "xgboost", params: dict[str, Any] | None = None) -> None:
        super().__init__(name, params)
        try:
            import xgboost as xgb

            task = self.params.pop("task", "regression")
            objective = "reg:squarederror" if task == "regression" else "binary:logistic"
            self._model = (
                xgb.XGBRegressor(objective=objective, **self.params)
                if task == "regression"
                else xgb.XGBClassifier(**self.params)
            )
        except ImportError:
            raise ImportError("xgboost not installed. Install with: pip install xgboost")

    def fit(self, X: FeatureMatrix, y: TargetVector, **kwargs: Any) -> None:
        self._model.fit(X.values, y.values, **kwargs)
        self._is_fitted = True

    def predict(self, X: FeatureMatrix) -> PredictionResult:
        preds = self._model.predict(X.values)
        probs = None
        if hasattr(self._model, "predict_proba"):
            probs = self._model.predict_proba(X.values)
        return PredictionResult(predictions=preds, probabilities=probs, model_id=self.name)

    def save(self, path: str) -> None:
        safe = validate_safe_path(path)
        self._model.save_model(str(safe))

    def load(self, path: str) -> None:
        safe = validate_safe_path(path)
        self._model.load_model(str(safe))
        self._is_fitted = True


model_registry.register("random_forest", RandomForestModel)
model_registry.register("xgboost", XGBoostModel)
