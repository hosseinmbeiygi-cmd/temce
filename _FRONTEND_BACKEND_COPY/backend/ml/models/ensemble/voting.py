from __future__ import annotations

from typing import Any

import numpy as np

from core.logging import get_logger
from ml.models.ensemble.base_ensemble import BaseEnsembleModel
from ml.types import FeatureMatrix, PredictionResult, TargetVector

logger = get_logger(__name__)


class VotingEnsemble(BaseEnsembleModel):
    def __init__(self, name: str = "voting", params: dict[str, Any] | None = None) -> None:
        default_params = {
            "strategy": "average",
            "weights": None,
        }
        merged = {**default_params, **(params or {})}
        super().__init__(name, merged)
        self._weights: np.ndarray | None = None

    @property
    def strategy(self) -> str:
        return self.params.get("strategy", "average")

    def _normalize_weights(self, n_models: int) -> np.ndarray:
        weights = self.params.get("weights")
        if weights is not None and len(weights) == n_models:
            w = np.array(weights, dtype=np.float64)
            total = w.sum()
            if total > 0:
                return w / total
        return np.ones(n_models, dtype=np.float64) / n_models

    def aggregate_predictions(self, base_predictions: list[np.ndarray], **kwargs: Any) -> np.ndarray:
        strategy = self.strategy
        predictions_array = np.array(base_predictions)
        n_models = predictions_array.shape[0]

        if strategy == "average":
            return np.mean(predictions_array, axis=0)

        if strategy == "weighted":
            weights = self._normalize_weights(n_models)
            weighted_sum = np.zeros_like(predictions_array[0], dtype=np.float64)
            for i in range(n_models):
                weighted_sum += weights[i] * predictions_array[i].astype(np.float64)
            return weighted_sum

        if strategy == "median":
            return np.median(predictions_array, axis=0)

        if strategy == "max":
            return np.max(predictions_array, axis=0)

        if strategy == "min":
            return np.min(predictions_array, axis=0)

        logger.warning("Unknown voting strategy '%s', falling back to average", strategy)
        return np.mean(predictions_array, axis=0)

    def fit(self, X: FeatureMatrix, y: TargetVector, **kwargs: Any) -> None:
        if not self._base_models:
            raise ValueError("No base models added to voting ensemble")
        super().fit(X, y, **kwargs)
        n_models = len(self._base_models)
        self._weights = self._normalize_weights(n_models)
        logger.info(
            "Voting ensemble %s fitted with strategy=%s, weights=%s",
            self.name,
            self.strategy,
            self._weights.tolist(),
        )

    def predict(self, X: FeatureMatrix) -> PredictionResult:
        return super().predict(X)
