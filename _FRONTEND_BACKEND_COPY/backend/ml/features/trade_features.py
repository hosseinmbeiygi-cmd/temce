"""Trade-level features from daily_real_legal and trades tables.

Builds features capturing real/legal (حقیقی/حقوقی) flow dynamics and
trade-level microstructure signals.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features.base import BaseFeatureBuilder
from ml.types import FeatureMatrix


class TradeFeatures(BaseFeatureBuilder):
    """Features derived from daily_real_legal (حقیقی/حقوقی) data."""

    def compute(self, data: pd.DataFrame) -> FeatureMatrix:
        df = data.copy()

        # ── Real/Legal flow ratios ────────────────────────────────
        total_vol = df["real_buy_volume"] + df["real_sell_volume"] + df["legal_buy_volume"] + df["legal_sell_volume"]
        total_vol = total_vol.replace(0, np.nan)

        df["real_buy_volume_ratio"] = df["real_buy_volume"] / total_vol
        df["legal_buy_volume_ratio"] = df["legal_buy_volume"] / total_vol

        # ── Net flows ─────────────────────────────────────────────
        df["real_net_flow"] = df["real_buy_value"] - df["real_sell_value"]
        df["legal_net_flow"] = df["legal_buy_value"] - df["legal_sell_value"]

        # Normalize net flows by total value
        total_value = (
            df["real_buy_value"] + df["real_sell_value"] + df["legal_buy_value"] + df["legal_sell_value"]
        ).replace(0, np.nan)
        df["real_net_flow_pct"] = df["real_net_flow"] / total_value
        df["legal_net_flow_pct"] = df["legal_net_flow"] / total_value

        # ── Buy/sell pressure ─────────────────────────────────────
        total_buy_count = df["real_buy_count"] + df["legal_buy_count"]
        total_sell_count = df["real_sell_count"] + df["legal_sell_count"]
        total_sell_count = total_sell_count.replace(0, np.nan)
        df["buy_sell_pressure"] = total_buy_count / total_sell_count

        # ── Smart money signal ────────────────────────────────────
        # Positive = net legal buying (institutional accumulation)
        # Negative = net legal selling (institutional distribution)
        df["smart_money_signal"] = np.sign(df["legal_net_flow"])

        # ── Flow momentum (rolling deltas) ────────────────────────
        for w in [3, 5]:
            df[f"real_net_flow_ma{w}"] = df["real_net_flow"].rolling(w).mean()
            df[f"legal_net_flow_ma{w}"] = df["legal_net_flow"].rolling(w).mean()
            df[f"real_net_flow_delta{w}"] = df["real_net_flow"] - df["real_net_flow_ma{w}"]
            df[f"legal_net_flow_delta{w}"] = df["legal_net_flow"] - df["legal_net_flow_ma{w}"]

        # ── Volume concentration ──────────────────────────────────
        df["real_buy_vol_concentration"] = df["real_buy_volume"] / df["real_buy_count"].replace(0, np.nan)
        df["legal_buy_vol_concentration"] = df["legal_buy_volume"] / df["legal_buy_count"].replace(0, np.nan)

        feature_names = [c for c in df.columns if c not in ("date", "trade_date", "symbol", "symbol_id")]
        # Drop rows where more than 50% of feature columns are NaN
        thresh = max(1, int(0.5 * len(feature_names)))
        df = df.dropna(subset=feature_names, thresh=thresh)
        # Forward-fill remaining NaN (up to 3 rows) for time-series continuity
        df[feature_names] = df[feature_names].ffill(limit=3).bfill(limit=1)
        return FeatureMatrix(data=df.reset_index(drop=True), feature_names=feature_names)

    def get_feature_names(self) -> list[str]:
        return [
            "real_buy_volume_ratio",
            "legal_buy_volume_ratio",
            "real_net_flow",
            "legal_net_flow",
            "real_net_flow_pct",
            "legal_net_flow_pct",
            "buy_sell_pressure",
            "smart_money_signal",
            "real_net_flow_ma3",
            "legal_net_flow_ma3",
            "real_net_flow_delta3",
            "legal_net_flow_delta3",
            "real_net_flow_ma5",
            "legal_net_flow_ma5",
            "real_net_flow_delta5",
            "legal_net_flow_delta5",
            "real_buy_vol_concentration",
            "legal_buy_vol_concentration",
        ]
