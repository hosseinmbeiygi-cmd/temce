from __future__ import annotations

from typing import Any

import pandas as pd

from core.logging import get_logger
from core.result import Result
from ml.artifacts import ArtifactManager
from ml.models.registry import model_registry
from ml.types import FeatureMatrix, PredictionResult

logger = get_logger(__name__)


class Predictor:
    def __init__(self, artifact_manager: ArtifactManager) -> None:
        self.artifact_manager = artifact_manager
        self._model_cache: dict[str, Any] = {}

    async def predict(
        self, model_id: str, features: dict[str, float | int | str] | pd.DataFrame | FeatureMatrix
    ) -> Result[PredictionResult]:
        try:
            if model_id not in self._model_cache:
                model, _ = self.artifact_manager.load_model(model_id)
                self._model_cache[model_id] = model
            
            model = self._model_cache[model_id]
            if isinstance(features, dict):
                df = pd.DataFrame([features])
                fm = FeatureMatrix(data=df)
            elif isinstance(features, pd.DataFrame):
                fm = FeatureMatrix(data=features)
            else:
                fm = features

            result = model.predict(fm)
            return Result.ok(result)
        except Exception as e:
            logger.error("Prediction failed for %s: %s", model_id, e)
            return Result.fail(str(e))

    async def batch_predict(self, model_id: str, features_list: list[dict[str, Any]]) -> Result[list[PredictionResult]]:
        df = pd.DataFrame(features_list)
        fm = FeatureMatrix(data=df)
        try:
            if model_id not in self._model_cache:
                model, _ = self.artifact_manager.load_model(model_id)
                self._model_cache[model_id] = model
            
            model = self._model_cache[model_id]
            result = model.predict(fm)
            return Result.ok([result])
        except Exception as e:
            return Result.fail(str(e))
