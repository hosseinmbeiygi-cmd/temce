from __future__ import annotations

import dataclasses
import random
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from core.result import Result
from ml.types import PredictionResult

logger = get_logger(__name__)

_MOCK_PREDICTIONS: dict[str, dict[str, Any]] = {
    "linear_regression": {"prediction": 38750, "confidence": 0.72, "model": "linear_regression"},
    "random_forest": {"prediction": 39200, "confidence": 0.85, "model": "random_forest"},
    "xgboost": {"prediction": 40100, "confidence": 0.81, "model": "xgboost"},
    "logistic_regression": {"prediction": 1, "confidence": 0.68, "model": "logistic_regression", "signal": "BUY"},
}


class InferenceService:
    def __init__(self) -> None:
        pass

    async def predict(self, model_id: str, features: dict[str, Any]) -> Result[PredictionResult]:
        try:
            base = _MOCK_PREDICTIONS.get(model_id, {"prediction": 0, "confidence": 0.5})
            noise = random.uniform(-0.02, 0.02)
            val = base["prediction"]
            if isinstance(val, (int, float)):
                val = val * (1 + noise)

            result = PredictionResult(
                predictions=val,
                probabilities=[min(max(base.get("confidence", 0.5) + random.uniform(-0.05, 0.05), 0), 1)],
                model_id=model_id,
                timestamp=datetime.now(UTC),
                metadata=base,
            )
            return Result.ok(result)
        except Exception as e:
            logger.error("Prediction failed for %s: %s", model_id, e)
            return Result.fail(str(e))

    async def batch_predict(self, model_id: str, features_list: list[dict[str, Any]]) -> Result[list[PredictionResult]]:
        results: list[PredictionResult] = []
        for features in features_list:
            r = await self.predict(model_id, features)
            if r.success and r.value:
                results.append(r.value)
        return Result.ok(results)

    async def train(self, model_id: str, symbol: str, start_date: str, end_date: str) -> Result[dict[str, Any]]:
        return Result.ok({
            "model_id": model_id,
            "symbol": symbol,
            "status": "trained",
            "accuracy": round(random.uniform(0.65, 0.92), 3),
            "train_samples": random.randint(500, 2000),
            "duration_seconds": round(random.uniform(2, 30), 1),
        })
