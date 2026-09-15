from __future__ import annotations

"""Spread estimator from OHLC data (Corwin-Schultz, 2012)."""
import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SpreadEstimate:
    spread_pct: float
    spread_bps: float
    high_low_ratio: float
    two_day_hl_ratio: float
    alpha: float
    beta: float
    valid: bool = True
    warnings: list[str] = field(default_factory=list)


@dataclass
class SpreadEstimatorResult:
    estimates: list[SpreadEstimate] = field(default_factory=list)
    median_spread_bps: float = 0.0
    mean_spread_bps: float = 0.0
    std_spread_bps: float = 0.0
    min_spread_bps: float = 0.0
    max_spread_bps: float = 0.0
    n_valid_estimates: int = 0
    n_total_periods: int = 0
    quality_warnings: list[str] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, Any]:
        return {
            "median_spread_bps": round(self.median_spread_bps, 2),
            "mean_spread_bps": round(self.mean_spread_bps, 2),
            "std_spread_bps": round(self.std_spread_bps, 2),
            "spread_range_bps": (round(self.min_spread_bps, 2), round(self.max_spread_bps, 2)),
            "n_valid_estimates": self.n_valid_estimates,
            "n_total_periods": self.n_total_periods,
        }


class CorwinSchultzSpread:
    def __init__(
        self, min_periods: int = 10, max_spread_bps: float = 500.0, negative_spread_handling: str = "zero"
    ) -> None:
        self.min_periods = min_periods
        self.max_spread_bps = max_spread_bps
        self.negative_spread_handling = negative_spread_handling

    def estimate(
        self, highs: list[float], lows: list[float], closes: list[float] | None = None
    ) -> SpreadEstimatorResult:
        n = len(highs)
        if n < self.min_periods:
            return SpreadEstimatorResult(n_total_periods=n, quality_warnings=[f"Fewer than {self.min_periods} periods"])
        if len(lows) != n:
            raise ValueError("highs and lows must have the same length")
        estimates = []
        for i in range(n - 1):
            h1, l1 = highs[i], lows[i]
            h2, l2 = highs[i + 1], lows[i + 1]
            if any(v <= 0 for v in (h1, l1, h2, l2)):
                estimates.append(SpreadEstimate(0, 0, 0, 0, 0, 0, valid=False, warnings=["Zero/neg price"]))
                continue
            hl = math.log(h1 / l1) if l1 > 0 else 0.0
            twod = math.log(max(h1, h2) / min(l1, l2)) if min(l1, l2) > 0 else 0.0
            alpha = (hl**2) / (4 * math.log(2)) if hl != 0 else 0.0
            beta2 = max(twod - alpha, 0.0)
            spr = max((2 * (math.exp(beta2) - 1)) / (1 + math.exp(beta2)), 0.0)
            se = SpreadEstimate(spr, spr * 10000, hl, twod, alpha, beta2, valid=True)
            if spr * 10000 > self.max_spread_bps:
                se.valid = False
                se.warnings.append(f"Spread {spr * 10000:.1f} bps exceeds max")
            estimates.append(se)
        v = [e for e in estimates if e.valid]
        vb = [e.spread_bps for e in v]
        if not vb:
            return SpreadEstimatorResult(
                estimates=estimates, n_total_periods=n, quality_warnings=["No valid estimates"]
            )
        sb = sorted(vb)
        m = len(sb) // 2
        med = sb[m] if len(sb) % 2 else (sb[m - 1] + sb[m]) / 2
        mn = sum(vb) / len(vb)
        sd = (sum((b - mn) ** 2 for b in vb) / len(vb)) ** 0.5
        return SpreadEstimatorResult(
            estimates=estimates,
            median_spread_bps=med,
            mean_spread_bps=mn,
            std_spread_bps=sd,
            min_spread_bps=min(vb),
            max_spread_bps=max(vb),
            n_valid_estimates=len(v),
            n_total_periods=len(estimates),
        )


def estimate_spread_from_ohlc(highs, lows, closes=None):
    return CorwinSchultzSpread().estimate(highs, lows, closes).median_spread_bps
