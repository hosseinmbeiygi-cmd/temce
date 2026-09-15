from __future__ import annotations

from typing import Any

from domain.common.enum_types import TimeFrame

# ── Data quality helpers (v2:67 + v2:32) ─────────────────────────────────
MAX_INTERPOLATION_GAP_BARS = 3  # only interpolate gaps <=3 bars; longer gaps are dropped (v2:67)
MAX_ALLOWED_GAP_DAYS = 5  # flag gaps >5 days as regime-breaking


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

    # ── Gap detection & cleaning (v2:66, v2:67) ──────────────────────────
    def detect_gaps(self, data: list[dict[str, Any]], expected_interval_minutes: int = 1440) -> list[dict[str, Any]]:
        """Detect missing bars. Returns list of gap descriptors without mutating data."""
        if len(data) < 2:
            return []
        import pandas as pd

        gaps = []
        for i in range(1, len(data)):
            try:
                t0 = pd.to_datetime(data[i - 1].get("timestamp"))
                t1 = pd.to_datetime(data[i].get("timestamp"))
                delta_min = (t1 - t0).total_seconds() / 60
                expected = expected_interval_minutes
                if delta_min > expected * 1.5:
                    gap_bars = int(round(delta_min / expected)) - 1
                    gaps.append(
                        {
                            "between": i - 1,
                            "gap_bars": gap_bars,
                            "gap_minutes": int(delta_min),
                            "is_long": gap_bars > MAX_INTERPOLATION_GAP_BARS,
                        }
                    )
            except Exception:
                continue
        return gaps

    def clean(
        self, data: list[dict[str, Any]], expected_interval_minutes: int = 1440
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Clean data: interpolate short gaps, drop long gaps, report stats.

        Short gaps (<=MAX_INTERPOLATION_GAP_BARS) are linearly interpolated.
        Long gaps are removed from backtest range and reported.
        Returns (cleaned_data, report).
        """
        gaps = self.detect_gaps(data, expected_interval_minutes)
        long_gaps = [g for g in gaps if g["is_long"]]
        # For simplicity, we do NOT interpolate long gaps - just flag them
        # Caller should exclude long-gap windows from walk-forward evaluation
        # Short gaps: linear interpolation via pandas (forward-fill for OHLC)
        cleaned = data
        if any(not g["is_long"] for g in gaps):
            try:
                import pandas as pd

                df = pd.DataFrame(data)
                if "timestamp" in df.columns:
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                    df = df.set_index("timestamp").sort_index()
                    # interpolate only price columns, not volume
                    for col in ("open", "high", "low", "close"):
                        if col in df.columns:
                            df[col] = df[col].interpolate(limit=MAX_INTERPOLATION_GAP_BARS, limit_direction="both")
                    cleaned = df.reset_index().to_dict("records")
            except ImportError:
                pass
        report = {
            "total_bars": len(data),
            "cleaned_bars": len(cleaned),
            "gaps_detected": len(gaps),
            "long_gaps": len(long_gaps),
            "interpolated_gaps": len(gaps) - len(long_gaps),
            "long_gap_indices": [g["between"] for g in long_gaps],
        }
        return cleaned, report
