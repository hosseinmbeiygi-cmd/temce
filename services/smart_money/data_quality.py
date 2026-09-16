"""Data Quality Gate — validates incoming data before scoring.

Rejects or flags data that is incomplete, stale, or contains outliers.
Ensures the scoring engine never processes corrupt data silently.

Level 17: Price validation for negative/zero values.
Level 18: Configurable history window (short/medium/long).
Level 61: Corporate actions awareness (split/dividend detection).
"""

from __future__ import annotations

import contextlib
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core.logging import get_logger
from core.time import utc_now_naive

logger = get_logger(__name__)


@dataclass
class DataQualityReport:
    """Result of data quality validation for one symbol."""
    symbol: str = ""
    is_valid: bool = True
    quality_score: float = 1.0  # 0.0 = terrible, 1.0 = perfect
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    analysis_mode: str = "full"  # full | partial
    history_days: int = 0
    missing_fields: list[str] = field(default_factory=list)


class DataQualityGate:
    """Validates quote + history data before scoring.

    Returns a DataQualityReport with validity, quality_score, and issues.
    If data is partially valid, analysis_mode is set to "partial".
    """

    REQUIRED_QUOTE_FIELDS = {"price_close", "volume", "value"}
    IMPORTANT_QUOTE_FIELDS = {"price_open", "price_high", "price_low", "price_last"}

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        self.min_history_days = config.get("min_history_days", 5)
        self.max_price_change_pct = config.get("max_price_change_pct", 20.0)
        self.min_volume = config.get("min_volume", 0)
        self.min_value = config.get("min_value", 0)
        self.max_stale_days = config.get("max_stale_days", 5)
        self.outlier_zscore = config.get("outlier_zscore_threshold", 3.5)

    def validate(
        self,
        symbol: str,
        quote: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> DataQualityReport:
        """Validate quote and history data for a symbol."""
        report = DataQualityReport(symbol=symbol, is_valid=True, quality_score=1.0)

        # 1. Check required fields
        self._check_required_fields(quote, report)

        # 2. Check history length
        self._check_history_length(history, report)

        # 3. Check for stale data
        self._check_staleness(quote, report)

        # 4. Check for zero/negative values
        self._check_zero_values(quote, report)

        # 5. Check for extreme price changes
        self._check_price_outliers(quote, history, report)

        # 6. Check for volume anomalies
        self._check_volume_anomalies(quote, history, report)

        # Level 13/61: Check for corporate actions
        self._check_corporate_actions(quote, history, report)

        # 7. Determine analysis mode
        if report.issues:
            report.is_valid = False
            report.quality_score = max(0.0, 1.0 - len(report.issues) * 0.15 - len(report.warnings) * 0.05)

            # If quality is low but not zero, allow partial analysis
            if report.quality_score > 0.3:
                report.analysis_mode = "partial"
                report.is_valid = True  # Allow partial scoring
                logger.info("Data quality partial for %s: score=%.2f issues=%s", symbol, report.quality_score, report.issues)
            else:
                logger.warning("Data quality too low for %s: score=%.2f issues=%s", symbol, report.quality_score, report.issues)

        return report

    def _check_required_fields(self, quote: dict[str, Any], report: DataQualityReport) -> None:
        for field_name in self.REQUIRED_QUOTE_FIELDS:
            val = quote.get(field_name)
            if val is None or val == 0:
                report.issues.append(f"Missing or zero required field: {field_name}")
                report.missing_fields.append(field_name)

        for field_name in self.IMPORTANT_QUOTE_FIELDS:
            val = quote.get(field_name)
            if val is None or val == 0:
                report.warnings.append(f"Missing important field: {field_name}")

    def _check_history_length(self, history: list[dict[str, Any]], report: DataQualityReport) -> None:
        report.history_days = len(history)
        if len(history) < self.min_history_days:
            report.issues.append(f"Insufficient history: {len(history)} days (minimum {self.min_history_days})")

    def _check_staleness(self, quote: dict[str, Any], report: DataQualityReport) -> None:
        date_str = quote.get("date", "")
        if date_str:
            with contextlib.suppress(Exception):
                # Try multiple date formats
                for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        data_date = datetime.strptime(date_str, fmt)
                        age_days = (utc_now_naive() - data_date).days
                        if age_days > self.max_stale_days:
                            report.warnings.append(f"Stale data: {age_days} days old")
                        break
                    except ValueError:
                        continue

    def _check_zero_values(self, quote: dict[str, Any], report: DataQualityReport) -> None:
        volume = quote.get("volume", 0)
        value = quote.get("value", 0)

        if volume is not None and volume <= self.min_volume:
            report.warnings.append(f"Zero or very low volume: {volume}")

        if value is not None and value <= self.min_value:
            report.warnings.append(f"Zero or very low value: {value}")

        # Level 17: Price validation for negative/zero values
        for price_field in ("price_close", "price_open", "price_high", "price_low", "price_last"):
            price_val = quote.get(price_field, 0)
            if price_val is not None and price_val < 0:
                report.issues.append(f"Negative price in {price_field}: {price_val}")
            elif price_val is not None and price_val == 0:
                report.warnings.append(f"Zero price in {price_field}")

        # Check price consistency
        c = quote.get("price_close", 0)
        h = quote.get("price_high", 0)
        low = quote.get("price_low", 0)
        quote.get("price_open", 0)

        if h > 0 and low > 0 and h < low:
            report.issues.append("Invalid OHLC: high < low")

        if c > 0 and h > 0 and c > h:
            report.warnings.append("Close > High (possible data error)")

        if c > 0 and low > 0 and c < low:
            report.warnings.append("Close < Low (possible data error)")

    def _check_price_outliers(
        self, quote: dict[str, Any], history: list[dict[str, Any]], report: DataQualityReport
    ) -> None:
        c = quote.get("price_close", 0)
        o = quote.get("price_open", 0)

        if c > 0 and o > 0:
            change_pct = abs((c - o) / o) * 100
            if change_pct > self.max_price_change_pct:
                report.warnings.append(f"Extreme price change: {change_pct:.1f}% (max {self.max_price_change_pct}%)")

    def _check_volume_anomalies(
        self, quote: dict[str, Any], history: list[dict[str, Any]], report: DataQualityReport
    ) -> None:
        if len(history) < 5:
            return

        vols = [q.get("volume", 0) for q in history[-20:] if q.get("volume", 0) > 0]
        if len(vols) < 3:
            return

        mean_vol = sum(vols) / len(vols)
        std_vol = math.sqrt(sum((v - mean_vol) ** 2 for v in vols) / len(vols)) if len(vols) > 1 else 1.0

        current_vol = quote.get("volume", 0)
        if std_vol > 0 and mean_vol > 0:
            z_score = (current_vol - mean_vol) / std_vol
            if abs(z_score) > self.outlier_zscore:
                report.warnings.append(f"Volume outlier: z-score={z_score:.2f}")

    def _check_corporate_actions(
        self, quote: dict[str, Any], history: list[dict[str, Any]], report: DataQualityReport
    ) -> None:
        """Level 13/61: Detect potential corporate actions (splits, dividends).

        A sudden large price drop with proportionally large volume increase
        may indicate a stock split or dividend distribution.
        """
        if len(history) < 2:
            return

        prev = history[-2]
        prev_close = prev.get("price_close", 0)
        curr_close = quote.get("price_close", 0)

        if prev_close > 0 and curr_close > 0:
            price_change_pct = abs((curr_close - prev_close) / prev_close) * 100

            # Detect potential split: price drops >40% with volume spike
            if price_change_pct > 40:
                prev_vol = prev.get("volume", 0) or 1
                curr_vol = quote.get("volume", 0) or 1
                vol_ratio = curr_vol / prev_vol if prev_vol > 0 else 1.0

                if vol_ratio > 2.0:
                    report.warnings.append(
                        f"Potential corporate action detected: price {price_change_pct:.1f}% change "
                        f"with volume {vol_ratio:.1f}x increase"
                    )

    def _check_history_length(self, history: list[dict[str, Any]], report: DataQualityReport) -> None:
        report.history_days = len(history)
        if len(history) < self.min_history_days:
            report.issues.append(f"Insufficient history: {len(history)} days (minimum {self.min_history_days})")
