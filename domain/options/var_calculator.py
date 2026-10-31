"""Value at Risk (VaR) and Conditional VaR (CVaR/Expected Shortfall) for option portfolios.

Supports:
- Historical simulation (distribution-free, handles fat tails)
- Variance-covariance (parametric, fast)
- Monte Carlo simulation

Designed for Iranian options market with fat-tailed return distributions.

Unit contract (audit FIN-11)
----------------------------
Every ``returns``/``mu``/``sigma`` input is a **decimal fraction** (``0.02`` =
2%). The old code documented "percentage" while doing decimal arithmetic, so a
caller following the docstring got a VaR 100x too large. Percent-scaled input
is rejected loudly instead of being silently mixed. ``var_*``/``cvar_*`` are
currency amounts; ``var_*_pct`` are true percentages of ``portfolio_value``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray as _NDArray
from scipy import stats


@dataclass
class VaRResult:
    """Value at Risk calculation result.

    ``var_95``/``cvar_95`` are losses in the portfolio's currency (positive =
    loss). ``var_95_pct`` is the same figure as a percentage of the portfolio
    (``2.5`` means 2.5%).
    """
    var_95: float
    var_99: float
    cvar_95: float    # Conditional VaR (Expected Shortfall) at 95%
    cvar_99: float    # Conditional VaR at 99%
    method: str
    portfolio_value: float
    var_95_pct: float  # Percentage of portfolio (2.5 = 2.5%)
    var_99_pct: float
    confidence_intervals: dict[str, float] | None = None


#: Above this median |return| the input is almost certainly percent-scaled:
#: a 50% typical daily move does not exist in decimal form.
_PERCENT_DETECTION_MEDIAN = 0.5


def _validate_decimal_returns(returns: _NDArray[np.float64]) -> _NDArray[np.float64]:
    """Return finite decimal returns, or raise when the scale is ambiguous."""
    arr = np.asarray(returns, dtype=float)
    if arr.size == 0:
        raise ValueError("returns array is empty")
    if not np.all(np.isfinite(arr)):
        raise ValueError("returns contain NaN/inf")
    if float(np.median(np.abs(arr))) > _PERCENT_DETECTION_MEDIAN:
        raise ValueError(
            "returns look like percentages (median |r| > 0.5); pass decimal "
            "fractions instead (0.02 for 2%)"
        )
    return arr



class VaRCalculator:
    """Calculate VaR and CVaR for options portfolios."""

    @staticmethod
    def historical_simulation(
        returns: _NDArray[np.float64],
        portfolio_value: float,
        holding_period: int = 1,
    ) -> VaRResult:
        """Historical simulation VaR.

        Most appropriate for Iranian market due to fat tails and skewness.
        No distribution assumptions required.

        Args:
            returns: Array of historical daily returns as decimal fractions
                (``0.02`` = 2%, audit FIN-11)
            portfolio_value: Current portfolio value in IRR
            holding_period: Number of days for VaR horizon
        """
        returns = _validate_decimal_returns(returns)
        if len(returns) < 30:
            raise ValueError("Need at least 30 historical returns")

        # Scale returns for holding period (square root of time)
        scaled_returns = returns * np.sqrt(holding_period)

        # VaR at 95% and 99% confidence (ratios, then reported as percent)
        var_95_ratio = -np.percentile(scaled_returns, 5)
        var_99_ratio = -np.percentile(scaled_returns, 1)

        # CVaR (Expected Shortfall) = average of losses beyond VaR (guard empty tail)
        tail_95 = scaled_returns[scaled_returns <= -var_95_ratio]
        tail_99 = scaled_returns[scaled_returns <= -var_99_ratio]
        cvar_95_ratio = -np.mean(tail_95) if tail_95.size > 0 else var_95_ratio
        if not np.isfinite(cvar_95_ratio):
            cvar_95_ratio = var_95_ratio
        cvar_99_ratio = -np.mean(tail_99) if tail_99.size > 0 else var_99_ratio
        if not np.isfinite(cvar_99_ratio):
            cvar_99_ratio = var_99_ratio

        return VaRResult(
            var_95=float(var_95_ratio * portfolio_value),
            var_99=float(var_99_ratio * portfolio_value),
            cvar_95=float(cvar_95_ratio * portfolio_value),
            cvar_99=float(cvar_99_ratio * portfolio_value),
            method="historical",
            portfolio_value=portfolio_value,
            var_95_pct=float(var_95_ratio * 100.0),
            var_99_pct=float(var_99_ratio * 100.0),
        )

    @staticmethod
    def parametric_var(
        returns: _NDArray[np.float64],
        portfolio_value: float,
        holding_period: int = 1,
    ) -> VaRResult:
        """Variance-covariance (parametric) VaR.

        Assumes normal distribution. Fast but may underestimate tail risk
        in Iranian market. ``returns`` are decimal fractions (audit FIN-11).
        """
        returns = _validate_decimal_returns(returns)
        mu = np.mean(returns)
        sigma = np.std(returns, ddof=1)

        # Adjust for holding period
        mu_h = mu * holding_period
        sigma_h = sigma * np.sqrt(holding_period)

        z_95 = stats.norm.ppf(0.05)
        z_99 = stats.norm.ppf(0.01)

        var_95_ratio = float(-(mu_h + z_95 * sigma_h))
        var_99_ratio = float(-(mu_h + z_99 * sigma_h))

        # CVaR for normal distribution
        cvar_95_ratio = float(-mu_h + sigma_h * stats.norm.pdf(z_95) / 0.05)
        cvar_99_ratio = float(-mu_h + sigma_h * stats.norm.pdf(z_99) / 0.01)

        return VaRResult(
            var_95=var_95_ratio * portfolio_value,
            var_99=var_99_ratio * portfolio_value,
            cvar_95=cvar_95_ratio * portfolio_value,
            cvar_99=cvar_99_ratio * portfolio_value,
            method="parametric",
            portfolio_value=portfolio_value,
            var_95_pct=var_95_ratio * 100.0,
            var_99_pct=var_99_ratio * 100.0,
        )

    @staticmethod
    def monte_carlo_var(
        portfolio_value: float,
        mu: float,
        sigma: float,
        n_sims: int = 10000,
        holding_period: int = 1,
        seed: int = 42,
    ) -> VaRResult:
        """Monte Carlo simulation VaR.

        Simulates portfolio returns using geometric Brownian motion.
        ``mu``/``sigma`` are annualized decimal fractions (0.15 = 15%).
        """
        if mu > 1.0 or mu < -1.0 or sigma > 3.0:
            raise ValueError(
                "mu/sigma look like percentages; pass decimal fractions "
                "(0.15 for 15%, audit FIN-11)"
            )
        rng = np.random.default_rng(seed)

        # Simulate returns
        daily_returns = rng.normal(mu / 252, sigma / math.sqrt(252), (n_sims, holding_period))
        cumulative_returns = np.prod(1 + daily_returns, axis=1) - 1

        var_95_ratio = float(-np.percentile(cumulative_returns, 5))
        var_99_ratio = float(-np.percentile(cumulative_returns, 1))

        _t95 = cumulative_returns[cumulative_returns <= -var_95_ratio]
        _t99 = cumulative_returns[cumulative_returns <= -var_99_ratio]
        cvar_95_ratio = float(-np.mean(_t95)) if _t95.size > 0 else var_95_ratio
        cvar_99_ratio = float(-np.mean(_t99)) if _t99.size > 0 else var_99_ratio
        if not np.isfinite(cvar_95_ratio):
            cvar_95_ratio = var_95_ratio
        if not np.isfinite(cvar_99_ratio):
            cvar_99_ratio = var_99_ratio

        return VaRResult(
            var_95=var_95_ratio * portfolio_value,
            var_99=var_99_ratio * portfolio_value,
            cvar_95=cvar_95_ratio * portfolio_value,
            cvar_99=cvar_99_ratio * portfolio_value,
            method="monte_carlo",
            portfolio_value=portfolio_value,
            var_95_pct=var_95_ratio * 100.0,
            var_99_pct=var_99_ratio * 100.0,
        )

    @staticmethod
    def greeks_based_var(
        portfolio_delta: float,
        portfolio_gamma: float,
        portfolio_vega: float,
        spot_price: float,
        spot_move_pct: float,
        vol_move_pct: float,
        portfolio_value: float,
    ) -> VaRResult:
        """VaR using Taylor expansion (Greeks-based).

        Estimates P&L change from delta-gamma-vega approximation:
        dP ≈ Δ*dS + 0.5*Γ*dS² + V*dσ

        ``spot_move_pct``/``vol_move_pct`` are decimal fractions (0.02 = 2%,
        audit FIN-11). Useful for real-time risk monitoring without historical
        data.
        """
        if abs(spot_move_pct) > 1.0 or abs(vol_move_pct) > 3.0:
            raise ValueError(
                "spot_move_pct/vol_move_pct look like percentages; pass "
                "decimal fractions (0.02 for 2%, audit FIN-11)"
            )
        dS = spot_price * spot_move_pct

        pnl_95 = (portfolio_delta * dS * 1.645
                  + 0.5 * portfolio_gamma * (dS * 1.645)**2
                  + portfolio_vega * vol_move_pct * 1.645)

        pnl_99 = (portfolio_delta * dS * 2.326
                  + 0.5 * portfolio_gamma * (dS * 2.326)**2
                  + portfolio_vega * vol_move_pct * 2.326)

        return VaRResult(
            var_95=abs(pnl_95),
            var_99=abs(pnl_99),
            cvar_95=abs(pnl_95) * 1.3,  # Approximation
            cvar_99=abs(pnl_99) * 1.3,
            method="greeks_based",
            portfolio_value=portfolio_value,
            var_95_pct=abs(pnl_95) / portfolio_value * 100.0 if portfolio_value > 0 else 0,
            var_99_pct=abs(pnl_99) / portfolio_value * 100.0 if portfolio_value > 0 else 0,
        )
