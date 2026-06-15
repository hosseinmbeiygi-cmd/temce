from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ml.types import FeatureMatrix, SplitMeta, TargetVector


class BaseDatasetBuilder(ABC):
    @abstractmethod
    async def load(self, config: dict[str, Any]) -> tuple[FeatureMatrix, TargetVector]: ...

    @abstractmethod
    def split(self, features: FeatureMatrix, targets: TargetVector, config: dict[str, Any]) -> SplitMeta: ...

    @abstractmethod
    def get_split(self, features: FeatureMatrix, targets: TargetVector, config: dict[str, Any]) -> SplitMeta: ...
