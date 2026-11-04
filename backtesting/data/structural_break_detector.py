from __future__ import annotations

"""Structural break detection for market regime changes.

Tags historical data with regulatory regime periods so that strategies
are not trained across incompatible market structures.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class StructuralBreak:
    date: datetime
    name: str
    description: str
    market: str = "all"
    severity: str = "major"  # major / minor / info


@dataclass
class StructuralBreakReport:
    breaks: list[StructuralBreak] = field(default_factory=list)
    n_breaks: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_breaks": self.n_breaks,
            "breaks": [
                {
                    "date": b.date.isoformat() if b.date else "",
                    "name": b.name,
                    "market": b.market,
                    "severity": b.severity,
                }
                for b in self.breaks
            ],
        }


# Pre-defined structural breaks for Iranian market (expand as needed)
IRAN_MARKET_BREAKS = [
    StructuralBreak(
        date=datetime(2020, 3, 20),
        name="Covid Crash",
        description="Global pandemic crash; all markets affected",
        market="all",
        severity="major",
    ),
    StructuralBreak(
        date=datetime(2021, 5, 1),
        name="بورس ۱۴۰۰ اصلاح",
        description="Major correction in Tehran Stock Exchange",
        market="stock",
        severity="major",
    ),
    StructuralBreak(
        date=datetime(2023, 1, 1),
        name="FX Unification",
        description="Currency unification policy shift",
        market="currency",
        severity="major",
    ),
    StructuralBreak(
        date=datetime(2024, 3, 21),
        name="2024 Market Reform",
        description="Trading hour and settlement rule changes",
        market="stock",
        severity="minor",
    ),
]


class StructuralBreakDetector:
    """Detects and tags structural breaks in market data.

    Combines pre-defined breaks (regulatory/economic) with statistical
    detection (Chow test / CUSUM) for unknown break points.
    """

    def __init__(self, known_breaks: list[StructuralBreak] | None = None):
        self.known_breaks = known_breaks or IRAN_MARKET_BREAKS

    def detect(
        self,
        prices: list[float],
        dates: list[datetime],
        market: str = "all",
    ) -> StructuralBreakReport:
        """Detect structural breaks in a price series.

        Args:
            prices: Time-ordered price series.
            dates: Corresponding dates.
            market: Market filter for known breaks.

        Returns:
            StructuralBreakReport with detected breaks.
        """
        report = StructuralBreakReport()

        # 1. Add known breaks within date range
        if dates:
            start, end = dates[0], dates[-1]
            for b in self.known_breaks:
                if b.market in (market, "all") and start <= b.date <= end:
                    report.breaks.append(b)

        # 2. Statistical detection: simplified CUSUM
        if len(prices) >= 50:
            try:
                import numpy as np

                returns = np.diff(prices) / np.array(prices[:-1])
                mean = np.mean(returns)
                std = np.std(returns)
                if std > 0:
                    cumulative = np.cumsum((returns - mean) / std)
                    threshold = 3.0 * np.sqrt(len(returns))
                    # Find points where cumulative exceeds threshold
                    for i in range(1, len(cumulative)):
                        if abs(cumulative[i]) > threshold and abs(cumulative[i]) > abs(
                            cumulative[i - 1]
                        ):
                            if dates and i < len(dates):
                                report.breaks.append(
                                    StructuralBreak(
                                        date=dates[i],
                                        name="Statistical Break (CUSUM)",
                                        description=f"Detected structural shift at index {i}",
                                        market=market,
                                        severity="minor",
                                    )
                                )
            except ImportError:
                report.warnings.append("NumPy not available for CUSUM detection")

        report.n_breaks = len(report.breaks)
        return report

    def get_market_regime_periods(
        self,
        market: str = "all",
    ) -> list[dict[str, Any]]:
        """Get time periods between structural breaks for a market.

        Returns a list of regime periods, each with start/end and a
        description of the regime. Use this to segment backtesting
        data into structurally homogeneous periods.
        """
        relevant = [
            b for b in self.known_breaks if b.market in (market, "all")
        ]
        relevant.sort(key=lambda x: x.date)
        periods = []
        prev_date = datetime(2015, 1, 1)
        for b in relevant:
            periods.append({
                "start": prev_date.isoformat(),
                "end": b.date.isoformat(),
                "regime": f"Pre-{b.name}" if periods else "Initial",
                "ended_by": b.name,
            })
            prev_date = b.date
        periods.append({
            "start": prev_date.isoformat(),
            "end": "present",
            "regime": f"Post-{relevant[-1].name}" if relevant else "Unknown",
        })
        return periods
