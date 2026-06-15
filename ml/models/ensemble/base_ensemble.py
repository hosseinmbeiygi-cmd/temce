from __future__ import annotations

import pickle
from abc import abstractmethod
from typing import Any

import numpy as np

from core.logging import get_logger
from ml.models.base import BaseModel
from ml.types import FeatureMatrix, PredictionResult, TargetVector

logger = get_logger(__name__)


class BaseEnsembleModel(BaseModel):
    def __init__(self, name: str = "", params: dict[str, Any] | None = None) -> None:
        super().__init__(name, params)
        self._base_models: list[BaseModel] = []

    @property
    def base_models(self) -> list[BaseModel]:
        return self._base_models

    @base_models.setter
    def base_models(self, models: list[BaseModel]) -> None:
        self._base_models = models

    def add_model(self, model: BaseModel) -> None:
        self._base_models.append(model)

    def _collect_base_predictions(self, X: FeatureMatrix) -> list[np.ndarray]:
        all_predictions: list[np.ndarray] = []
        for model in self._base_models:
            if not model.is_fitted:
                logger.warning("Base model %s is not fitted, skipping", model.name)
                continue
            result = model.predict(X)
            all_predictions.append(result.predictions)
        return all_predictions

    @abstractmethod
    def aggregate_predictions(self, base_predictions: list[np.ndarray], **kwargs: Any) -> np.ndarray: ...

    def fit(self, X: FeatureMatrix, y: TargetVector, **kwargs: Any) -> None:
        for model in self._base_models:
            logger.info("Fitting base model: %s", model.name)
            model.fit(X, y, **kwargs)
        self._is_fitted = True
        logger.info("Ensemble %s fitted with %d base models", self.name, len(self._base_models))

    def predict(self, X: FeatureMatrix) -> PredictionResult:
        base_predictions = self._collect_base_predictions(X)
        if not base_predictions:
            raise RuntimeError("No base model predictions available")
        aggregated = self.aggregate_predictions(base_predictions)
        return PredictionResult(predictions=aggregated, model_id=self.name)

    def save(self, path: str) -> None:
        import os

        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        payload = {
            "name": self.name,
            "params": self.params,
            "is_fitted": self._is_fitted,
            "base_models": [],
        }
        for model in self._base_models:
            model_data = {
                "class": model.__class__.__name__,
                "name": model.name,
                "params": model.params,
                "is_fitted": model.is_fitted,
            }
            payload["base_models"].append(model_data)
        with open(path, "wb") as f:
            pickle.dump(payload, f)
        logger.info("Ensemble model saved to %s", path)

    def load(self, path: str) -> None:
        with open(path, "rb") as f:
            payload = pickle.load(f)
        self.name = payload.get("name", self.name)
        self.params = payload.get("params", self.params)
        self._is_fitted = payload.get("is_fitted", False)
        self._base_models = []
        logger.info("Ensemble model loaded from %s", path)
