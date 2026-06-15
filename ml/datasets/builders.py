from __future__ import annotations

from typing import Any

import pandas as pd

from ml.datasets.base import BaseDatasetBuilder
from ml.datasets.labeling import LabelGenerator
from ml.datasets.loaders import DataLoader
from ml.datasets.splitting import DataSplitter
from ml.types import FeatureMatrix, SplitMeta, TargetVector


class DatasetBuilder(BaseDatasetBuilder):
    def __init__(self) -> None:
        self.loader = DataLoader()
        self.labeler = LabelGenerator()
        self.splitter = DataSplitter()

    async def load(self, config: dict[str, Any]) -> tuple[FeatureMatrix, TargetVector]:
        prices = await self.loader.load_market_data(
            config.get("instrument_ids", []),
            config.get("start_date", ""),
            config.get("end_date", ""),
        )
        if not prices.success or prices.value is None or prices.value.empty:
            raise ValueError("No data loaded")
        df = prices.value
        feat = FeatureMatrix(data=df)
        target = self.labeler.future_return(
            df.get("close", df.get("price_close", pd.Series())),
            horizon=config.get("horizon", 5),
        )
        return feat, target

    def split(self, features: FeatureMatrix, targets: TargetVector, config: dict[str, Any]) -> SplitMeta:
        method = config.get("split_method", "time")
        if method == "time":
            return self.splitter.time_based(features, targets)
        return self.splitter.time_based(features, targets)

    def get_split(self, features: FeatureMatrix, targets: TargetVector, config: dict[str, Any]) -> SplitMeta:
        return self.split(features, targets, config)
