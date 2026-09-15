"""Value at Risk (VaR) and Conditional VaR (CVaR/Expected Shortfall) for option portfolios.

Supports:
- Historical simulation (distribution-free, handles fat tails)
- Variance-covariance (parametric, fast)
- Monte Carlo simulation

Designed for Iranian options market with fat-tailed return distributions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray as _NDArray
from scipy import stats


@dataclass
class VaRResult:
    """Value at Risk calculation result."""

    var_95: float
    var_99: float
    cvar_95: float  # Conditional VaR (Expected Shortfall) at 95%
    cvar_99: float  # Conditional VaR at 99%
    method: str
    portfolio_value: float
    var_95_pct: float  # As percentage of portfolio
    var_99_pct: float
    confidence_intervals: dict[str, float] | None = None


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
            returns: Array of historical daily returns (percentage)
            portfolio_value: Current portfolio value in IRR
            holding_period: Number of days for VaR horizon
        """
        if len(returns) < 30:
            raise ValueError("Need at least 30 historical returns")

        # Scale returns for holding period (square root of time)
        scaled_returns = returns * np.sqrt(holding_period)

        # VaR at 95% and 99% confidence
        var_95_pct = -np.percentile(scaled_returns, 5)
        var_99_pct = -np.percentile(scaled_returns, 1)

        # CVaR (Expected Shortfall) = average of losses beyond VaR (guard empty tail)
        tail_95 = scaled_returns[scaled_returns <= -var_95_pct]
        tail_99 = scaled_returns[scaled_returns <= -var_99_pct]
        cvar_95_pct = -np.mean(tail_95) if tail_95.size > 0 else var_95_pct
        if not np.isfinite(cvar_95_pct):
            cvar_95_pct = var_95_pct
        cvar_99_pct = -np.mean(tail_99) if tail_99.size > 0 else var_99_pct
        if not np.isfinite(cvar_99_pct):
            cvar_99_pct = var_99_pct

        return VaRResult(
            var_95=var_95_pct * portfolio_value,
            var_99=var_99_pct * portfolio_value,
            cvar_95=cvar_95_pct * portfolio_value,
            cvar_99=cvar_99_pct * portfolio_value,
            method="historical",
            portfolio_value=portfolio_value,
            var_95_pct=var_95_pct,
            var_99_pct=var_99_pct,
        )

    @staticmethod
    def parametric_var(
        returns: _NDArray[np.float64],
        portfolio_value: float,
        holding_period: int = 1,
    ) -> VaRResult:
        """Variance-covariance (parametric) VaR.

        Assumes normal distribution. Fast but may underestimate tail risk
        in Iranian market.
        """
        mu = np.mean(returns)
        sigma = np.std(returns, ddof=1)

        # Adjust for holding period
        mu_h = mu * holding_period
        sigma_h = sigma * np.sqrt(holding_period)

        z_95 = stats.norm.ppf(0.05)
        z_99 = stats.norm.ppf(0.01)

        var_95_pct = -(mu_h + z_95 * sigma_h)
        var_99_pct = -(mu_h + z_99 * sigma_h)

        # CVaR for normal distribution
        cvar_95_pct = -mu_h + sigma_h * stats.norm.pdf(z_95) / 0.05
        cvar_99_pct = -mu_h + sigma_h * stats.norm.pdf(z_99) / 0.01

        return VaRResult(
            var_95=var_95_pct * portfolio_value,
            var_99=var_99_pct * portfolio_value,
            cvar_95=cvar_95_pct * portfolio_value,
            cvar_99=cvar_99_pct * portfolio_value,
            method="parametric",
            portfolio_value=portfolio_value,
            var_95_pct=var_95_pct,
            var_99_pct=var_99_pct,
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
        """
        rng = np.random.default_rng(seed)

        # Simulate returns
        daily_returns = rng.normal(mu / 252, sigma / math.sqrt(252), (n_sims, holding_period))
        cumulative_returns = np.prod(1 + daily_returns, axis=1) - 1

        var_95_pct = -np.percentile(cumulative_returns, 5)
        var_99_pct = -np.percentile(cumulative_returns, 1)

        cvar_95_pct = -np.mean(cumulative_returns[cumulative_returns <= -var_95_pct])
        cvar_99_pct = -np.mean(cumulative_returns[cumulative_returns <= -var_99_pct])

        return VaRResult(
            var_95=var_95_pct * portfolio_value,
            var_99=var_99_pct * portfolio_value,
            cvar_95=cvar_95_pct * portfolio_value,
            cvar_99=cvar_99_pct * portfolio_value,
            method="monte_carlo",
            portfolio_value=portfolio_value,
            var_95_pct=var_95_pct,
            var_99_pct=var_99_pct,
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

        Useful for real-time risk monitoring without historical data.
        """
        dS = spot_price * spot_move_pct

        pnl_95 = (
            portfolio_delta * dS * 1.645
            + 0.5 * portfolio_gamma * (dS * 1.645) ** 2
            + portfolio_vega * vol_move_pct * 1.645
        )

        pnl_99 = (
            portfolio_delta * dS * 2.326
            + 0.5 * portfolio_gamma * (dS * 2.326) ** 2
            + portfolio_vega * vol_move_pct * 2.326
        )

        return VaRResult(
            var_95=abs(pnl_95),
            var_99=abs(pnl_99),
            cvar_95=abs(pnl_95) * 1.3,  # Approximation
            cvar_99=abs(pnl_99) * 1.3,
            method="greeks_based",
            portfolio_value=portfolio_value,
            var_95_pct=abs(pnl_95) / portfolio_value if portfolio_value > 0 else 0,
            var_99_pct=abs(pnl_99) / portfolio_value if portfolio_value > 0 else 0,
        )
