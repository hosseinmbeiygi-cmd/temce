from __future__ import annotations

import pandas as pd

from ml.features.base import BaseFeatureBuilder
from ml.types import FeatureMatrix


class PriceFeatures(BaseFeatureBuilder):
    def __init__(self, window_sizes: list[int] | None = None) -> None:
        self.window_sizes = window_sizes or [5, 10, 20, 50]

    def compute(self, data: pd.DataFrame) -> FeatureMatrix:
        df = data.copy()
        close = df.get("close", df.get("price_close"))
        for w in self.window_sizes:
            df[f"return_{w}"] = close.pct_change(w)
            df[f"ma_{w}"] = close.rolling(w).mean()
            df[f"volatility_{w}"] = close.pct_change().rolling(w).std()
        if "high" in df and "low" in df:
            df["range"] = (df["high"] - df["low"]) / df.get("close", df["low"])
        return FeatureMatrix(
            data=df.dropna(), feature_names=[c for c in df.columns if c not in ("date", "time", "symbol")]
        )

    def get_feature_names(self) -> list[str]:
        names = []
        for w in self.window_sizes:
            names.extend([f"return_{w}", f"ma_{w}", f"volatility_{w}"])
        names.append("range")
        return names
