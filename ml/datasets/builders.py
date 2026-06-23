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
        if not config.get("instrument_ids"):
            raise ValueError("Instrument IDs must be specified")
            
        start_date = config.get("start_date", "")
        end_date = config.get("end_date", "")
        if not start_date or not end_date:
            raise ValueError("Both start_date and end_date must be specified")
            
        print(f"Trying to load data for {config['instrument_ids']} from {start_date} to {end_date}")
        prices = await self.loader.load_market_data(
            config["instrument_ids"],
            start_date,
            end_date,
            source=config.get("data_source", "yahoo")
        )
        print(f"Received data: {prices.value.head() if prices.value is not None else 'None'}")
        if not prices.success:
            raise ValueError(f"Data loading failed: {getattr(prices, 'error', 'Unknown error')}")
        if prices.value is None or prices.value.empty:
            raise ValueError("No data loaded - empty DataFrame returned")
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
