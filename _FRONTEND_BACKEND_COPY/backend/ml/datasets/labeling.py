from __future__ import annotations

import pandas as pd

from ml.types import TargetVector


class LabelGenerator:
    def future_return(self, prices: pd.Series, horizon: int = 5) -> TargetVector:
        future = prices.shift(-horizon) / prices - 1
        return TargetVector(data=future.dropna(), name=f"future_return_{horizon}", task_type="regression")

    def binary_direction(self, prices: pd.Series, horizon: int = 5) -> TargetVector:
        future = prices.shift(-horizon)
        direction = (future > prices).astype(int)
        return TargetVector(data=direction.dropna(), name=f"direction_{horizon}", task_type="binary_classification")

    def volatility_regime(self, returns: pd.Series, window: int = 20) -> TargetVector:
        vol = returns.rolling(window).std()
        median = vol.median()
        regime = (vol > median).astype(int)
        return TargetVector(data=regime.dropna(), name="vol_regime", task_type="binary_classification")
