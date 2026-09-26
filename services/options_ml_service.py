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
class VolatilityForecast:
    realized_vol_annual: float
    garch_omega: float
    garch_alpha: float
    garch_beta: float
    unconditional_vol_annual: float
    n_observations: int


@dataclass(frozen=True)
class TouchProbability:
    probability_of_profit: float
    probability_of_touch_upper: float
    probability_of_touch_lower: float
    breakeven_upper: float
    breakeven_lower: float


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

    # ── Phase 4: realized-vol forecasting (GARCH) + touch probabilities ──

    @staticmethod
    def garch_forecast(
        log_returns: list[float] | NDArray[np.float64],
        horizon_days: int = 30,
    ) -> VolatilityForecast:
        """GARCH(1,1) realized-volatility forecast (variance targeting).

        Fits alpha/beta on a coarse grid by Gaussian log-likelihood with
        omega fixed at ``long_run_var * (1 - alpha - beta)``; forecasts the
        average daily variance over `horizon_days` and annualizes it.
        Falls back to sample std when fewer than 30 observations exist.
        """
        rets = np.asarray(log_returns, dtype=float)
        rets = rets[np.isfinite(rets)]
        n = len(rets)
        if n == 0:
            raise ValueError("log_returns must be non-empty")
        if horizon_days <= 0:
            raise ValueError("horizon_days must be positive")
        long_var = float(np.var(rets))
        if n < 30 or long_var <= 0:
            vol = math.sqrt(max(long_var, 0.0)) * math.sqrt(252.0)
            return VolatilityForecast(vol, 0.0, 0.0, 0.0, vol, n)

        demeaned = rets - float(np.mean(rets))
        best_ll, best = -math.inf, (0.05, 0.90)
        for alpha in (0.02, 0.05, 0.08, 0.12):
            for beta in (0.80, 0.85, 0.90, 0.93):
                if alpha + beta >= 0.999:
                    continue
                omega = long_var * (1.0 - alpha - beta)
                var = long_var
                ll = 0.0
                for r in demeaned:
                    var = omega + alpha * r * r + beta * var
                    if var <= 0:
                        ll = -math.inf
                        break
                    ll += -0.5 * (math.log(2 * math.pi * var) + r * r / var)
                if math.isfinite(ll) and ll > best_ll:
                    best_ll, best = ll, (alpha, beta)
        alpha, beta = best
        omega = long_var * (1.0 - alpha - beta)
        var = omega + alpha * demeaned[-1] ** 2 + beta * long_var
        horizon_var = 0.0
        for _ in range(horizon_days):
            horizon_var += var
            var = omega + (alpha + beta) * var
        avg_daily = horizon_var / horizon_days
        realized = math.sqrt(max(avg_daily, 0.0)) * math.sqrt(252.0)
        uncond = math.sqrt(max(long_var, 0.0)) * math.sqrt(252.0)
        return VolatilityForecast(realized, omega, alpha, beta, uncond, n)

    def touch_probabilities(
        self,
        spot: float,
        sigma: float,
        days_to_expiry: int,
        breakeven_upper: float,
        breakeven_lower: float,
        risk_free: float = 0.0,
    ) -> TouchProbability:
        """PoP (expire beyond breakeven) + touch probabilities from full paths."""
        if days_to_expiry <= 0:
            raise ValueError("days_to_expiry must be positive")
        steps = min(max(days_to_expiry, 1), 252)
        dt = (days_to_expiry / 365.0) / steps
        shocks = self._rng.standard_normal((self._n_paths, steps))
        drift = (risk_free - 0.5 * sigma * sigma) * dt
        diffusion = sigma * math.sqrt(dt) * shocks
        log_paths = np.cumsum(drift + diffusion, axis=1)
        terminal = spot * np.exp(log_paths[:, -1])
        running_max = spot * np.exp(np.maximum.accumulate(log_paths, axis=1).max(axis=1))
        running_min = spot * np.exp(np.minimum.accumulate(log_paths, axis=1).min(axis=1))
        pop = float(np.mean((terminal >= breakeven_upper) | (terminal <= breakeven_lower)))
        return TouchProbability(
            probability_of_profit=pop,
            probability_of_touch_upper=float(np.mean(running_max >= breakeven_upper)),
            probability_of_touch_lower=float(np.mean(running_min <= breakeven_lower)),
            breakeven_upper=breakeven_upper,
            breakeven_lower=breakeven_lower,
        )

    @staticmethod
    def put_call_ratio(call_volume: float, put_volume: float) -> float:
        """Put/Call volume ratio (contrarian sentiment gauge)."""
        if call_volume <= 0:
            return 0.0
        return max(put_volume, 0.0) / call_volume

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
