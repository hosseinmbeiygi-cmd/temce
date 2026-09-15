from __future__ import annotations

import numpy as np
import pandas as pd

from core.logging import get_logger
from ml.features.base import BaseFeatureBuilder
from ml.types import FeatureMatrix

logger = get_logger(__name__)


class VolumeFeatures(BaseFeatureBuilder):
    def __init__(self, window: int = 20) -> None:
        self.window = window

    def compute(self, data: pd.DataFrame) -> FeatureMatrix:
        df = data.copy()
        vol = df.get("volume", 0)
        close = df.get("close", df.get("price_close"))

        df["volume_sma"] = vol.rolling(self.window).mean()
        df["volume_std"] = vol.rolling(self.window).std()

        # ── division-by-zero guard ───────────────────────────────────
        zero_sma = (df["volume_sma"] == 0).sum()
        if zero_sma > 0:
            logger.warning(
                "VolumeFeatures: %d rows have zero volume_sma — corresponding volume_ratio will be NaN and dropped",
                zero_sma,
            )

        df["volume_ratio"] = vol.div(df["volume_sma"].replace(0, np.nan))

        nan_ratio = df["volume_ratio"].isna().sum()
        if nan_ratio > 0:
            logger.info(
                "VolumeFeatures: %d NaN values in volume_ratio (will be dropped by dropna)",
                nan_ratio,
            )

        df["dollar_volume"] = vol * close

        return FeatureMatrix(
            data=df.dropna(),
            feature_names=["volume_sma", "volume_std", "volume_ratio", "dollar_volume"],
        )

    def get_feature_names(self) -> list[str]:
        return ["volume_sma", "volume_std", "volume_ratio", "dollar_volume"]
