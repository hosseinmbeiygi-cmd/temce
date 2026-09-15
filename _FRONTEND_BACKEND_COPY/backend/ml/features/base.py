from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from ml.types import FeatureMatrix


class BaseFeatureBuilder(ABC):
    @abstractmethod
    def compute(self, data: pd.DataFrame) -> FeatureMatrix: ...

    @abstractmethod
    def get_feature_names(self) -> list[str]: ...

    def compute_from_dict(self, data: dict) -> FeatureMatrix:
        df = pd.DataFrame([data]) if isinstance(data, dict) else pd.DataFrame(data)
        return self.compute(df)
