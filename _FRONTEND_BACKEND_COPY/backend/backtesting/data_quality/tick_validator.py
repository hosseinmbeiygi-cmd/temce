from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np


@dataclass
class DataQualityReport:
    """Report of data quality issues found."""

    n_ticks_checked: int = 0
    n_bad_ticks: int = 0
    n_timestamp_drifts: int = 0
    n_missing_events: int = 0
    n_price_anomalies: int = 0
    n_volume_anomalies: int = 0
    n_spread_anomalies: int = 0
    bad_tick_indices: list[int] = field(default_factory=list)
    drift_events: list[dict[str, Any]] = field(default_factory=list)
    quality_score: float = 1.0
    warnings: list[str] = field(default_factory=list)


class TickValidator:
    """Data quality engine for detecting and fixing market data issues.

    Detects:
    - Bad ticks (zero/negative price, extreme values)
    - Timestamp drift (out-of-order, gaps, duplicates)
    - Price anomalies (outliers, limit breaks)
    - Volume anomalies (zero volume on trade events)
    - Spread anomalies (negative spread, extreme spread)
    """

    def __init__(self, price_std_threshold: float = 5.0, max_gap_seconds: float = 300.0) -> None:
        self.price_std_threshold = price_std_threshold
        self.max_gap_seconds = max_gap_seconds
        self._price_history: deque[float] = deque(maxlen=100)
        self._last_timestamp: datetime | None = None

    def validate_trades(self, trades: list[dict[str, Any]]) -> DataQualityReport:
        """Validate a list of trade events."""
        self.reset()
        report = DataQualityReport()
        report.n_ticks_checked = len(trades)

        for i, trade in enumerate(trades):
            price = trade.get("price", 0)
            volume = trade.get("volume", 0) or trade.get("quantity", 0)
            timestamp = trade.get("timestamp")

            # Bad price check
            if price <= 0:
                report.n_bad_ticks += 1
                report.bad_tick_indices.append(i)
                report.warnings.append(f"Tick {i}: zero/negative price {price}")
                continue

            # Price anomaly
            if len(self._price_history) >= 20:
                mean_p = float(np.mean(self._price_history))
                std_p = float(np.std(self._price_history))
                if std_p > 0 and abs(price - mean_p) > self.price_std_threshold * std_p:
                    report.n_price_anomalies += 1
                    report.warnings.append(f"Tick {i}: price anomaly {price} (mean={mean_p:.2f}, std={std_p:.2f})")

            # Volume anomaly
            if volume <= 0:
                report.n_volume_anomalies += 1

            # Timestamp drift
            if timestamp and self._last_timestamp:
                if hasattr(timestamp, "timestamp") and hasattr(self._last_timestamp, "timestamp"):
                    diff = (timestamp - self._last_timestamp).total_seconds()
                    if diff < 0:
                        report.n_timestamp_drifts += 1
                        report.drift_events.append({"index": i, "type": "out_of_order", "diff_seconds": diff})
                    elif diff > self.max_gap_seconds:
                        report.n_missing_events += 1
                        expected = int(diff / 1.0)  # assuming 1-second intervals
                        report.drift_events.append(
                            {"index": i, "type": "gap", "diff_seconds": diff, "expected_missing": expected - 1}
                        )

            self._price_history.append(price)
            self._last_timestamp = timestamp

        # Quality score
        total_issues = (
            report.n_bad_ticks + report.n_timestamp_drifts + report.n_missing_events + report.n_price_anomalies
        )
        if report.n_ticks_checked > 0:
            report.quality_score = max(0.0, 1.0 - (total_issues / report.n_ticks_checked))

        return report

    def validate_quotes(self, quotes: list[dict[str, Any]]) -> DataQualityReport:
        """Validate a list of quote events (focus on spread anomalies)."""
        self.reset()
        report = DataQualityReport()
        report.n_ticks_checked = len(quotes)

        for i, q in enumerate(quotes):
            bid = q.get("bid", 0) or q.get("bid_price", 0)
            ask = q.get("ask", 0) or q.get("ask_price", 0)

            if bid <= 0 or ask <= 0:
                report.n_bad_ticks += 1
                continue

            # Negative spread
            if ask < bid:
                report.n_spread_anomalies += 1
                report.warnings.append(f"Quote {i}: negative spread bid={bid} ask={ask}")

            # Extreme spread
            if bid > 0:
                spread_pct = (ask - bid) / bid
                if spread_pct > 0.1:  # 10% spread is extreme
                    report.n_spread_anomalies += 1
                    report.warnings.append(f"Quote {i}: extreme spread {spread_pct * 100:.1f}%")

        total_issues = report.n_bad_ticks + report.n_spread_anomalies
        if report.n_ticks_checked > 0:
            report.quality_score = max(0.0, 1.0 - (total_issues / report.n_ticks_checked))

        return report

    def repair_tick(
        self, tick: dict[str, Any], prev_tick: dict[str, Any] | None, next_tick: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Attempt to repair a bad tick by interpolation."""
        repaired = dict(tick)
        price = tick.get("price", 0)

        if price <= 0 and prev_tick and next_tick:
            prev_p = prev_tick.get("price", 0)
            next_p = next_tick.get("price", 0)
            if prev_p > 0 and next_p > 0:
                repaired["price"] = (prev_p + next_p) / 2
                repaired["_repaired"] = True

        elif price <= 0 and prev_tick:
            repaired["price"] = prev_tick.get("price", 0)
            repaired["_repaired"] = True

        return repaired

    def estimate_missing_events(
        self, timestamps: list[datetime], expected_interval_seconds: float = 1.0
    ) -> list[dict[str, Any]]:
        """Estimate missing events from timestamp gaps."""
        missing: list[dict[str, Any]] = []
        for i in range(1, len(timestamps)):
            if hasattr(timestamps[i], "timestamp") and hasattr(timestamps[i - 1], "timestamp"):
                gap = (timestamps[i] - timestamps[i - 1]).total_seconds()
                if gap > expected_interval_seconds * 2:
                    n_missing = int(gap / expected_interval_seconds) - 1
                    for j in range(n_missing):
                        est_ts = timestamps[i - 1] + timedelta(seconds=expected_interval_seconds * (j + 1))
                        missing.append({"estimated_timestamp": est_ts, "gap_before_index": i})
        return missing

    def reset(self) -> None:
        self._price_history.clear()
        self._last_timestamp = None
