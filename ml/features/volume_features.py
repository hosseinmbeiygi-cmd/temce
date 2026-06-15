from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features.base import BaseFeatureBuilder
from ml.types import FeatureMatrix


class VolumeFeatures(BaseFeatureBuilder):
    def __init__(self, window: int = 20) -> None:
        self.window = window

    def compute(self, data: pd.DataFrame) -> FeatureMatrix:
        df = data.copy()
        vol = df.get("volume", 0)
        close = df.get("close", df.get("price_close"))
        df["volume_sma"] = vol.rolling(self.window).mean()
        df["volume_std"] = vol.rolling(self.window).std()
        df["volume_ratio"] = vol / df["volume_sma"].replace(0, np.nan)
        df["dollar_volume"] = vol * close
        return FeatureMatrix(
            data=df.dropna(), feature_names=["volume_sma", "volume_std", "volume_ratio", "dollar_volume"]
        )

    def get_feature_names(self) -> list[str]:
        return ["volume_sma", "volume_std", "volume_ratio", "dollar_volume"]
