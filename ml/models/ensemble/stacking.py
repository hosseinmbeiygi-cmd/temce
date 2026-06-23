from __future__ import annotations

import pickle
from typing import Any

import numpy as np

from core.logging import get_logger
from core.paths import validate_safe_path
from ml.models.base import BaseModel
from ml.models.ensemble.base_ensemble import BaseEnsembleModel
from ml.types import FeatureMatrix, PredictionResult, TargetVector

logger = get_logger(__name__)


class StackingEnsemble(BaseEnsembleModel):
    def __init__(self, name: str = "stacking", params: dict[str, Any] | None = None) -> None:
        default_params = {
            "use_original_features": True,
            "cv_folds": 5,
        }
        merged = {**default_params, **(params or {})}
        super().__init__(name, merged)
        self._meta_model: BaseModel | None = None

    @property
    def meta_model(self) -> BaseModel | None:
        return self._meta_model

    @meta_model.setter
    def meta_model(self, model: BaseModel) -> None:
        self._meta_model = model

    def _build_meta_features(self, X: FeatureMatrix, base_predictions: list[np.ndarray]) -> np.ndarray:
        meta_features = np.column_stack(base_predictions)
        if self.params.get("use_original_features", True):
            meta_features = np.hstack([X.values, meta_features])
        return meta_features

    def fit(self, X: FeatureMatrix, y: TargetVector, **kwargs: Any) -> None:
        if not self._base_models:
            raise ValueError("No base models added to stacking ensemble")
        if self._meta_model is None:
            raise ValueError("Meta model not set. Assign meta_model before fitting.")

        for model in self._base_models:
            logger.info("Fitting stacking base model: %s", model.name)
            model.fit(X, y, **kwargs)

        base_predictions = self._collect_base_predictions(X)
        meta_features = self._build_meta_features(X, base_predictions)
        meta_target = y.values

        logger.info("Fitting meta model: %s", self._meta_model.name)
        meta_X = FeatureMatrix(data=__import__("pandas").DataFrame(meta_features))
        meta_y = TargetVector(data=__import__("pandas").Series(meta_target))
        self._meta_model.fit(meta_X, meta_y, **kwargs)

        self._is_fitted = True
        logger.info(
            "Stacking ensemble %s fitted with %d base models and meta model %s",
            self.name,
            len(self._base_models),
            self._meta_model.name,
        )

    def predict(self, X: FeatureMatrix) -> PredictionResult:
        if self._meta_model is None or not self._meta_model.is_fitted:
            raise RuntimeError("Meta model not fitted")
        base_predictions = self._collect_base_predictions(X)
        if not base_predictions:
            raise RuntimeError("No base model predictions available")
        meta_features = self._build_meta_features(X, base_predictions)
        meta_X = FeatureMatrix(data=__import__("pandas").DataFrame(meta_features))
        result = self._meta_model.predict(meta_X)
        return PredictionResult(predictions=result.predictions, model_id=self.name)

    def aggregate_predictions(self, base_predictions: list[np.ndarray], **kwargs: Any) -> np.ndarray:
        return np.mean(base_predictions, axis=0)

    def save(self, path: str) -> None:
        safe = validate_safe_path(path)
        safe.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "name": self.name,
            "params": self.params,
            "is_fitted": self._is_fitted,
            "base_models": [],
            "meta_model_name": self._meta_model.name if self._meta_model else "",
        }
        for model in self._base_models:
            payload["base_models"].append(
                {
                    "class": model.__class__.__name__,
                    "name": model.name,
                    "params": model.params,
                    "is_fitted": model.is_fitted,
                }
            )
        safe.write_bytes(pickle.dumps(payload))
        logger.info("Stacking ensemble saved to %s", safe)

    def load(self, path: str) -> None:
        safe = validate_safe_path(path)
        payload = pickle.loads(safe.read_bytes())
        self.name = payload.get("name", self.name)
        self.params = payload.get("params", self.params)
        self._is_fitted = payload.get("is_fitted", False)
        self._base_models = []
        logger.info("Stacking ensemble loaded from %s", safe)
