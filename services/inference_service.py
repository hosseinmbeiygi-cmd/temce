from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from ml.inference.predictor import Predictor
from ml.types import PredictionResult

logger = get_logger(__name__)


class InferenceService:
    def __init__(self, predictor: Predictor | None = None) -> None:
        self.predictor = predictor or Predictor()

    async def predict(self, model_id: str, features: dict[str, Any]) -> Result[PredictionResult]:
        return await self.predictor.predict(model_id, features)

    async def batch_predict(self, model_id: str, features_list: list[dict[str, Any]]) -> Result[list[PredictionResult]]:
        return await self.predictor.batch_predict(model_id, features_list)
