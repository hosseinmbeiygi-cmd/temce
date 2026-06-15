from __future__ import annotations

from typing import Any

from domain.common.enum_types import TimeFrame


class Resampler:
    _TIMEFRAME_MAP = {
        TimeFrame.M1: "1min",
        TimeFrame.M5: "5min",
        TimeFrame.M15: "15min",
        TimeFrame.M30: "30min",
        TimeFrame.H1: "1h",
        TimeFrame.D1: "1D",
        TimeFrame.W1: "1W",
        TimeFrame.MONTHLY: "1M",
    }

    def resample(self, data: list[dict[str, Any]], from_tf: TimeFrame, to_tf: TimeFrame) -> list[dict[str, Any]]:
        if from_tf == to_tf:
            return data
        try:
            import pandas as pd

            df = pd.DataFrame(data)
            if "timestamp" not in df.columns:
                return data
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp")
            rule = self._TIMEFRAME_MAP.get(to_tf, "1D")
            agg_dict: dict[str, str] = {}
            for col in df.columns:
                if col in ("close", "price", "nav"):
                    agg_dict[col] = "last"
                elif col in ("volume", "quantity"):
                    agg_dict[col] = "sum"
                elif col in ("open",):
                    agg_dict[col] = "first"
                elif col in ("high",):
                    agg_dict[col] = "max"
                elif col in ("low",):
                    agg_dict[col] = "min"
                else:
                    agg_dict[col] = "mean"
            resampled = df.resample(rule).agg(agg_dict).dropna().reset_index()
            return resampled.to_dict("records")
        except ImportError:
            return data

    def to_daily(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self.resample(data, TimeFrame.M1, TimeFrame.D1)

    def to_weekly(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self.resample(data, TimeFrame.D1, TimeFrame.W1)

    def to_monthly(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self.resample(data, TimeFrame.D1, TimeFrame.MONTHLY)
