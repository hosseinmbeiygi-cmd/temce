from __future__ import annotations

"""Missing data detection and handling policy.

Policy: gaps are detected and marked, NOT filled with synthetic data.
If a gap exceeds the threshold, the affected period is excluded from
backtesting rather than being silently interpolated.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DataGap:
    start_idx: int
    end_idx: int
    start_date: datetime | None = None
    end_date: datetime | None = None
    gap_days: float = 0.0
    excluded: bool = False


@dataclass
class MissingDataReport:
    total_periods: int = 0
    gaps_found: list[DataGap] = field(default_factory=list)
    total_gap_days: float = 0.0
    max_gap_days: float = 0.0
    periods_excluded: int = 0
    ratio_missing: float = 0.0
    policy_action: str = "none"
    warnings: list[str] = field(default_factory=list)


class MissingDataPolicy:
    """Detects and handles missing data. NEVER fills with synthetic data."""

    def __init__(self, max_gap_days: float = 5.0, max_missing_ratio: float = 0.1):
        self.max_gap_days = max_gap_days
        self.max_missing_ratio = max_missing_ratio

    def analyze(self, dates: list[datetime], prices: list[float] | None = None) -> MissingDataReport:
        report = MissingDataReport(total_periods=len(dates))
        if len(dates) < 2:
            report.warnings.append("Insufficient data for gap analysis")
            return report

        gaps = []
        for i in range(1, len(dates)):
            if hasattr(dates[i], "timestamp") and hasattr(dates[i - 1], "timestamp"):
                gap_days = (dates[i] - dates[i - 1]).total_seconds() / 86400
            else:
                continue
            if gap_days > 1.5:
                gap = DataGap(
                    start_idx=i - 1,
                    end_idx=i,
                    start_date=dates[i - 1],
                    end_date=dates[i],
                    gap_days=gap_days,
                    excluded=gap_days > self.max_gap_days,
                )
                gaps.append(gap)

        report.gaps_found = gaps
        report.total_gap_days = sum(g.gap_days for g in gaps)
        report.max_gap_days = max((g.gap_days for g in gaps), default=0.0)
        report.periods_excluded = sum(1 for g in gaps if g.excluded)

        total_possible = len(dates)
        missing = report.total_gap_days
        report.ratio_missing = missing / total_possible if total_possible > 0 else 0.0

        if report.ratio_missing > self.max_missing_ratio:
            report.policy_action = "warn"
            report.warnings.append(
                f"Missing ratio {report.ratio_missing:.1%} exceeds threshold {self.max_missing_ratio:.0%}"
            )
        elif gaps:
            report.policy_action = "exclude_gaps"
        else:
            report.policy_action = "ok"

        return report

    def excluded_indices(self, report: MissingDataReport) -> set[int]:
        indices = set()
        for g in report.gaps_found:
            if g.excluded:
                for i in range(g.start_idx, g.end_idx + 1):
                    indices.add(i)
        return indices
