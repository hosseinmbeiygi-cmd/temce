from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
import pandas as pd

from ml.types import FeatureMatrix, ModelArtifactMeta, PredictionResult, SplitMeta, TargetVector


class DatasetBuilder(ABC):
    @abstractmethod
    async def build(self, config: dict[str, Any]) -> tuple[FeatureMatrix, TargetVector]: ...

    @abstractmethod
    def get_split(self, features: FeatureMatrix, targets: TargetVector, config: dict[str, Any]) -> SplitMeta: ...


class FeatureBuilder(ABC):
    @abstractmethod
    def compute(self, data: pd.DataFrame) -> FeatureMatrix: ...

    @abstractmethod
    def get_feature_names(self) -> list[str]: ...


class ModelTrainer(ABC):
    @abstractmethod
    async def train(self, X_train: FeatureMatrix, y_train: TargetVector, **kwargs: Any) -> ModelArtifactMeta: ...

    @abstractmethod
    async def validate(
        self, model_meta: ModelArtifactMeta, X_val: FeatureMatrix, y_val: TargetVector
    ) -> dict[str, float]: ...


class ModelPredictor(ABC):
    @abstractmethod
    async def predict(self, model_meta: ModelArtifactMeta, features: FeatureMatrix) -> PredictionResult: ...

    @abstractmethod
    async def predict_proba(self, model_meta: ModelArtifactMeta, features: FeatureMatrix) -> np.ndarray: ...


class ModelEvaluator(ABC):
    @abstractmethod
    def evaluate(self, y_true: TargetVector, y_pred: PredictionResult) -> dict[str, float]: ...

    @abstractmethod
    def get_metric_names(self) -> list[str]: ...
