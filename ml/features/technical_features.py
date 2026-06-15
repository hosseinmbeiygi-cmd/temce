from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features.base import BaseFeatureBuilder
from ml.types import FeatureMatrix


class TechnicalFeatures(BaseFeatureBuilder):
    def compute(self, data: pd.DataFrame) -> FeatureMatrix:
        df = data.copy()
        close = df.get("close", df.get("price_close"))
        high = df.get("high", df.get("price_high"))
        low = df.get("low", df.get("price_low"))
        volume = df.get("volume", 0)

        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["rsi"] = 100 - (100 / (1 + rs))

        df["macd"] = close.ewm(span=12).mean() - close.ewm(span=26).mean()
        df["macd_signal"] = df["macd"].ewm(span=9).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        if high is not None and low is not None:
            df["atr"] = (high - low).rolling(14).mean()

        if volume is not None:
            df["volume_sma"] = volume.rolling(20).mean()
            df["volume_ratio"] = volume / df["volume_sma"].replace(0, np.nan)

        return FeatureMatrix(
            data=df.dropna(), feature_names=[c for c in df.columns if c not in ("date", "time", "symbol")]
        )

    def get_feature_names(self) -> list[str]:
        return ["rsi", "macd", "macd_signal", "macd_hist", "atr", "volume_sma", "volume_ratio"]
