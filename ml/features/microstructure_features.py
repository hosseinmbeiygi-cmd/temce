"""Microstructure features from raw trades (ریز معاملات).

Builds features from tick-level trade data: VWAP, trade size distribution,
large trade detection, and price impact signals.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features.base import BaseFeatureBuilder
from ml.types import FeatureMatrix


class MicrostructureFeatures(BaseFeatureBuilder):
    """Features derived from individual trades (tick-level data)."""

    def compute(self, data: pd.DataFrame) -> FeatureMatrix:
        """Compute microstructure features from aggregated trade data.

        Expects a DataFrame with columns from daily trades aggregation:
        date, symbol, trade_count, volume, value, price_open, price_high,
        price_low, price_close, price_last.
        """
        df = data.copy()

        # ── VWAP ──────────────────────────────────────────────────
        df["vwap"] = df["value"] / df["volume"].replace(0, np.nan)
        df["vwap_deviation"] = (df["price_close"] - df["vwap"]) / df["vwap"].replace(0, np.nan)

        # ── Trade intensity (trades per million volume) ───────────
        df["trade_intensity"] = df["trade_count"] / df["volume"].replace(0, np.nan) * 1e6
        df["avg_trade_size"] = df["value"] / df["trade_count"].replace(0, np.nan)

        # ── Price impact proxy ────────────────────────────────────
        daily_range = (df["price_high"] - df["price_low"]).replace(0, np.nan)
        df["value_range_ratio"] = df["value"] / daily_range

        # ── Volume-weighted price deviation from VWAP ─────────────
        # How far the high/low deviates from the volume-weighted average
        df["vw_high_ratio"] = (df["price_high"] - df["vwap"]) / df["vwap"].replace(0, np.nan)
        df["vw_low_ratio"] = (df["price_low"] - df["vwap"]) / df["vwap"].replace(0, np.nan)

        # ── Trade frequency features ──────────────────────────────
        for w in [3, 5]:
            df[f"trade_count_ma{w}"] = df["trade_count"].rolling(w).mean()
            df[f"trade_count_ratio{w}"] = df["trade_count"] / df[f"trade_count_ma{w}"].replace(0, np.nan)

        # ── Value distribution features ───────────────────────────
        for w in [3, 5]:
            df[f"value_ma{w}"] = df["value"].rolling(w).mean()
            df[f"value_ratio{w}"] = df["value"] / df[f"value_ma{w}"].replace(0, np.nan)

        # ── Price efficiency (how much of the range was captured) ──
        df["price_efficiency"] = (df["price_close"] - df["price_open"]) / daily_range
        df["price_efficiency"] = df["price_efficiency"].clip(-1, 1)

        feature_names = [c for c in df.columns if c not in ("date", "trade_date", "symbol", "symbol_id")]
        # Drop rows where more than 50% of feature columns are NaN
        thresh = max(1, int(0.5 * len(feature_names)))
        df = df.dropna(subset=feature_names, thresh=thresh)
        # Forward-fill remaining NaN for time-series continuity
        df[feature_names] = df[feature_names].ffill(limit=3).bfill(limit=1)
        return FeatureMatrix(data=df.reset_index(drop=True), feature_names=feature_names)

    def get_feature_names(self) -> list[str]:
        return [
            "vwap", "vwap_deviation",
            "trade_intensity", "avg_trade_size",
            "value_range_ratio",
            "vw_high_ratio", "vw_low_ratio",
            "trade_count_ma3", "trade_count_ratio3",
            "trade_count_ma5", "trade_count_ratio5",
            "value_ma3", "value_ratio3",
            "value_ma5", "value_ratio5",
            "price_efficiency",
        ]
