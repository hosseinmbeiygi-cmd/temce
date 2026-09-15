from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from ml.evaluation.metrics import MetricsCalculator
from ml.models.base import BaseModel
from ml.models.registry import model_registry
from ml.types import FeatureMatrix, ModelArtifactMeta, TargetVector

logger = get_logger(__name__)


class Trainer:
    def __init__(self) -> None:
        self.metrics_calc = MetricsCalculator()

    async def train(
        self,
        model: BaseModel,
        X_train: FeatureMatrix,
        y_train: TargetVector,
        X_val: FeatureMatrix | None = None,
        y_val: TargetVector | None = None,
        **kwargs: Any,
    ) -> Result[ModelArtifactMeta]:
        try:
            logger.info("Training %s on %d samples", model.name, X_train.shape[0])
            model.fit(X_train, y_train, **kwargs)

            metrics: dict[str, float] = {}
            if X_val is not None and y_val is not None:
                preds = model.predict(X_val)
                metrics = self.metrics_calc.compute(y_val.values, preds.predictions)

            meta = ModelArtifactMeta(
                model_id=model.name,
                version="1.0",
                metrics=metrics,
                params=model.params,
                feature_names=X_train.feature_names,
            )
            return Result.ok(meta)
        except Exception as e:
            logger.error("Training failed for %s: %s", model.name, e)
            return Result.fail(str(e))

    async def train_from_registry(
        self, model_name: str, X_train: FeatureMatrix, y_train: TargetVector, **kwargs: Any
    ) -> Result[ModelArtifactMeta]:
        model = model_registry.create(model_name)
        return await self.train(model, X_train, y_train, **kwargs)
