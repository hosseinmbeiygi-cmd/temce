from __future__ import annotations

import pickle
from typing import Any

import numpy as np

from core.logging import get_logger
from ml.models.base import BaseModel
from ml.models.ensemble.base_ensemble import BaseEnsembleModel
from ml.types import FeatureMatrix, PredictionResult, TargetVector

logger = get_logger(__name__)


class BlendingEnsemble(BaseEnsembleModel):
    def __init__(self, name: str = "blending", params: dict[str, Any] | None = None) -> None:
        default_params = {
            "holdout_fraction": 0.2,
            "use_original_features": True,
            "random_state": 42,
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

    def _split_data(
        self, X: FeatureMatrix, y: TargetVector
    ) -> tuple[FeatureMatrix, FeatureMatrix, TargetVector, TargetVector]:
        holdout_frac = self.params.get("holdout_fraction", 0.2)
        random_state = self.params.get("random_state", 42)
        n_samples = X.shape[0]
        n_holdout = max(1, int(n_samples * holdout_frac))
        rng = np.random.RandomState(random_state)
        indices = rng.permutation(n_samples)
        holdout_idx = indices[:n_holdout]
        train_idx = indices[n_holdout:]

        X_train = FeatureMatrix(data=X.data.iloc[train_idx].reset_index(drop=True))
        X_holdout = FeatureMatrix(data=X.data.iloc[holdout_idx].reset_index(drop=True))
        y_train = TargetVector(data=y.data.iloc[train_idx].reset_index(drop=True))
        y_holdout = TargetVector(data=y.data.iloc[holdout_idx].reset_index(drop=True))
        return X_train, X_holdout, y_train, y_holdout

    def _build_meta_features(self, X: FeatureMatrix, base_predictions: list[np.ndarray]) -> np.ndarray:
        meta_features = np.column_stack(base_predictions)
        if self.params.get("use_original_features", True):
            meta_features = np.hstack([X.values, meta_features])
        return meta_features

    def fit(self, X: FeatureMatrix, y: TargetVector, **kwargs: Any) -> None:
        if not self._base_models:
            raise ValueError("No base models added to blending ensemble")
        if self._meta_model is None:
            raise ValueError("Meta model not set. Assign meta_model before fitting.")

        X_train, X_holdout, y_train, y_holdout = self._split_data(X, y)
        logger.info(
            "Blending split: train=%d, holdout=%d",
            X_train.shape[0],
            X_holdout.shape[0],
        )

        for model in self._base_models:
            logger.info("Fitting blending base model on train split: %s", model.name)
            model.fit(X_train, y_train, **kwargs)

        base_predictions_holdout = []
        for model in self._base_models:
            result = model.predict(X_holdout)
            base_predictions_holdout.append(result.predictions)

        meta_features = self._build_meta_features(X_holdout, base_predictions_holdout)
        meta_X = FeatureMatrix(data=__import__("pandas").DataFrame(meta_features))
        meta_y = y_holdout

        logger.info("Fitting meta model on holdout: %s", self._meta_model.name)
        self._meta_model.fit(meta_X, meta_y, **kwargs)

        self._is_fitted = True
        logger.info(
            "Blending ensemble %s fitted with %d base models and meta model %s",
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
        import os

        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
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
        with open(path, "wb") as f:
            pickle.dump(payload, f)
        logger.info("Blending ensemble saved to %s", path)

    def load(self, path: str) -> None:
        with open(path, "rb") as f:
            payload = pickle.load(f)
        self.name = payload.get("name", self.name)
        self.params = payload.get("params", self.params)
        self._is_fitted = payload.get("is_fitted", False)
        self._base_models = []
        logger.info("Blending ensemble loaded from %s", path)
