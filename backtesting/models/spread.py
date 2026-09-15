"""Spread estimation models (roadmap v2:31).

When L1/L2 orderbook is unavailable (most Iran data), estimate spread from OHLC
using Corwin-Schultz (2012) or fallback to historical fixed spread.

Corwin-Schultz estimator:
  beta = E[sum(log(H/L)^2)] over 2 days
  gamma = log(H_t/L_t)^2 aggregated
  alpha = (sqrt(2*beta) - sqrt(beta)) / (3 - 2*sqrt(2)) - sqrt(gamma/(3-2*sqrt2))
  spread = 2*(exp(alpha)-1)/(1+exp(alpha))

All outputs are in bps and tagged as ESTIMATE (not exact). Callers must store
the provenance flag (estimated vs observed) for audit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal


@dataclass
class SpreadEstimate:
    spread_bps: float
    method: Literal["corwin_schultz", "fixed", "historical", "observed"]
    is_estimate: bool = True
    confidence: float = 0.5  # 0-1, lower when few bars


class SpreadEstimator:
    """Estimate effective spread when orderbook unavailable."""

    def __init__(
        self,
        fixed_spread_bps: float = 5.0,
        min_spread_bps: float = 1.0,
        max_spread_bps: float = 300.0,
    ) -> None:
        self.fixed_spread_bps = fixed_spread_bps
        self.min_spread_bps = min_spread_bps
        self.max_spread_bps = max_spread_bps

    def estimate_corwin_schultz(self, bars: list[dict]) -> SpreadEstimate:
        """Estimate spread from OHLC bars using Corwin-Schultz (2-day window).

        bars: list of dict with high, low, close. Needs >=2 bars.
        Returns bps. If insufficient data, returns fixed fallback.
        """
        if len(bars) < 2:
            return SpreadEstimate(spread_bps=self.fixed_spread_bps, method="fixed", is_estimate=True, confidence=0.2)
        try:
            # Two-day high/low
            highs = [float(b.get("high", b.get("close", 0))) for b in bars[-2:]]
            lows = [float(b.get("low", b.get("close", 0))) for b in bars[-2:]]
            if any(v <= 0 for v in highs + lows):
                raise ValueError("non-positive high/low")
            # beta: sum of squared log(H/L) over 2 days
            beta = sum(math.log(h / l) ** 2 for h, l in zip(highs, lows, strict=False))
            # gamma: log( max(highs)/min(lows) )^2
            high_max = max(highs)
            low_min = min(lows)
            if low_min <= 0 or high_max <= 0:
                raise ValueError("invalid range")
            gamma = math.log(high_max / low_min) ** 2
            k1 = 3 - 2 * math.sqrt(2)
            k2 = math.sqrt(2) * math.sqrt(max(beta, 0)) - math.sqrt(max(beta, 0))
            # Standard CS alpha
            denom = k1
            if denom == 0:
                raise ValueError("denom 0")
            alpha_arg = k2 / denom - math.sqrt(max(gamma, 0) / denom) if gamma >= 0 else 0
            # Clamp alpha to avoid exp overflow
            alpha = max(-5, min(5, alpha_arg))
            spread = 2 * (math.exp(alpha) - 1) / (1 + math.exp(alpha))
            spread_bps = max(0, spread * 10_000)
            spread_bps = max(self.min_spread_bps, min(spread_bps, self.max_spread_bps))
            # Confidence based on sample size and beta stability
            confidence = 0.6 if len(bars) >= 20 else 0.4
            return SpreadEstimate(
                spread_bps=round(spread_bps, 2), method="corwin_schultz", is_estimate=True, confidence=confidence
            )
        except Exception:
            return SpreadEstimate(spread_bps=self.fixed_spread_bps, method="fixed", is_estimate=True, confidence=0.2)

    def estimate_historical(self, spread_history_bps: list[float]) -> SpreadEstimate:
        """Use historical average spread (bucketed by hour if available)."""
        if not spread_history_bps:
            return SpreadEstimate(spread_bps=self.fixed_spread_bps, method="fixed", is_estimate=True, confidence=0.2)
        avg = sum(spread_history_bps) / len(spread_history_bps)
        avg = max(self.min_spread_bps, min(avg, self.max_spread_bps))
        conf = min(0.8, 0.3 + len(spread_history_bps) * 0.02)
        return SpreadEstimate(spread_bps=round(avg, 2), method="historical", is_estimate=True, confidence=conf)

    def range_bps(self, bars: list[dict], confidence_level: float = 0.95) -> tuple[float, float]:
        """Return (low_bps, high_bps) spread range for sensitivity (v2:33)."""
        est = self.estimate_corwin_schultz(bars)
        # +- 50% range as documented approximation band
        low = est.spread_bps * 0.5
        high = est.spread_bps * 1.5
        low = max(self.min_spread_bps, low)
        high = min(self.max_spread_bps, high)
        return (round(low, 2), round(high, 2))
