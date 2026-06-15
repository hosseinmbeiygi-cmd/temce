from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ml.types import FeatureMatrix, PredictionResult, TargetVector


class BaseModel(ABC):
    def __init__(self, name: str = "", params: dict[str, Any] | None = None) -> None:
        self.name = name or self.__class__.__name__
        self.params = params or {}
        self._is_fitted = False

    @abstractmethod
    def fit(self, X: FeatureMatrix, y: TargetVector, **kwargs: Any) -> None: ...

    @abstractmethod
    def predict(self, X: FeatureMatrix) -> PredictionResult: ...

    @abstractmethod
    def save(self, path: str) -> None: ...

    @abstractmethod
    def load(self, path: str) -> None: ...

    @property
    def is_fitted(self) -> bool:
        return self._is_fitted

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, fitted={self._is_fitted})"
