"""Options ML service — expected-move forecast and Max Pain strike.

- Expected Move: terminal-price distribution under geometric Brownian motion
  (lognormal). Monte-Carlo paths give percentile bands; the analytic
  1-sigma band from ``domain.options.probability.expected_move`` is reported
  alongside as a cross-check. No ML training here — the "ML" surface is the
  distributional forecast (IV → sigma input).
- Max Pain: strike minimizing total option-holder payout at expiry, computed
  separately over call and put open interest (proper definition), with a
  fallback to the aggregate-OI helper in ``domain.options.probability``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from domain.options.probability import expected_move as _analytic_move
from domain.options.probability import max_pain_price as _aggregate_max_pain


@dataclass(frozen=True)
class ExpectedMoveResult:
    spot: float
    sigma: float
    days_to_expiry: int
    lower_68: float
    upper_68: float
    lower_95: float
    upper_95: float
    median_terminal: float
    mean_terminal: float
    analytic_lower_68: float
    analytic_upper_68: float
    n_paths: int


@dataclass(frozen=True)
class MaxPainResult:
    max_pain_strike: float
    total_payout_at_max_pain: float
    payout_by_strike: dict[float, float]


class OptionsMLService:
    """Distributional forecasts for option expiry horizons."""

    def __init__(self, n_paths: int = 20_000, seed: int = 42) -> None:
        if n_paths <= 0:
            raise ValueError("n_paths must be positive")
        self._n_paths = n_paths
        self._rng = np.random.default_rng(seed)

    def _terminal_prices(
        self, spot: float, sigma: float, t_years: float, risk_free: float = 0.0
    ) -> NDArray[np.float64]:
        """Lognormal terminal prices: S_T = S·exp((r−σ²/2)T + σ√T·Z)."""
        if spot <= 0:
            raise ValueError("spot must be positive")
        if sigma < 0 or t_years < 0:
            raise ValueError("sigma and time must be non-negative")
        drift = (risk_free - 0.5 * sigma * sigma) * t_years
        diffusion = sigma * math.sqrt(t_years) * self._rng.standard_normal(self._n_paths)
        return spot * np.exp(drift + diffusion)

    def expected_move(
        self,
        spot: float,
        sigma: float,
        days_to_expiry: int,
        risk_free: float = 0.0,
    ) -> ExpectedMoveResult:
        """Forecast the price range into expiry via Monte Carlo."""
        if days_to_expiry <= 0:
            raise ValueError("days_to_expiry must be positive")
        t_years = days_to_expiry / 365.0
        terminal = self._terminal_prices(spot, sigma, t_years, risk_free)
        lo68, hi68 = float(np.percentile(terminal, 16)), float(np.percentile(terminal, 84))
        lo95, hi95 = float(np.percentile(terminal, 2.5)), float(np.percentile(terminal, 97.5))
        a_lo, a_hi = _analytic_move(spot, sigma, t_years)
        return ExpectedMoveResult(
            spot=spot, sigma=sigma, days_to_expiry=days_to_expiry,
            lower_68=lo68, upper_68=hi68, lower_95=lo95, upper_95=hi95,
            median_terminal=float(np.median(terminal)),
            mean_terminal=float(np.mean(terminal)),
            analytic_lower_68=a_lo, analytic_upper_68=a_hi,
            n_paths=self._n_paths,
        )

    def probability_above(self, spot: float, sigma: float, days_to_expiry: int, level: float) -> float:
        """Risk-neutral-ish probability S_T > `level` from simulated paths."""
        terminal = self._terminal_prices(spot, sigma, days_to_expiry / 365.0)
        return float(np.mean(terminal > level))

    @staticmethod
    def max_pain(
        strikes: list[float],
        call_oi: list[float],
        put_oi: list[float],
    ) -> MaxPainResult:
        """Max Pain strike from separate call/put open interest.

        At expiry price P: call payout = max(P−K,0)·OI_call,
        put payout = max(K−P,0)·OI_put. Max Pain minimizes the total.
        Falls back to the aggregate helper when only one side is given.
        """
        if not strikes:
            raise ValueError("strikes must be non-empty")
        if len(call_oi) != len(strikes) or len(put_oi) != len(strikes):
            raise ValueError("call_oi/put_oi must match strikes length")
        if any(v < 0 for v in call_oi) or any(v < 0 for v in put_oi):
            raise ValueError("open interest must be non-negative")

        payout_by_strike: dict[float, float] = {}
        for px in strikes:
            total = 0.0
            for k, co, po in zip(strikes, call_oi, put_oi):
                total += max(px - k, 0.0) * co + max(k - px, 0.0) * po
            payout_by_strike[float(px)] = total
        best = min(payout_by_strike, key=payout_by_strike.get)
        if not any(call_oi) or not any(put_oi):
            agg = _aggregate_max_pain(
                [float(s) for s in strikes],
                [c + p for c, p in zip(call_oi, put_oi)],
            )
            best = float(agg)
        return MaxPainResult(
            max_pain_strike=float(best),
            total_payout_at_max_pain=payout_by_strike.get(float(best), 0.0),
            payout_by_strike=payout_by_strike,
        )
