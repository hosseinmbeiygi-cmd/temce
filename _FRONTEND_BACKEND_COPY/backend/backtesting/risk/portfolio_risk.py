from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class PortfolioRiskMetrics:
    """Comprehensive portfolio risk metrics."""

    var_95: float = 0.0
    cvar_95: float = 0.0
    stress_var: float = 0.0
    tail_risk: float = 0.0
    factor_exposure: dict[str, float] = field(default_factory=dict)
    correlation_risk: float = 0.0
    concentration_risk: float = 0.0
    liquidity_risk: float = 0.0
    intraday_var: float = 0.0
    expected_shortfall: float = 0.0
    risk_metrics: dict[str, float] = field(default_factory=dict)


class PortfolioRiskEngine:
    """Advanced portfolio-level risk management.

    Computes:
    - VaR (Value at Risk) at multiple confidence levels
    - CVaR / Expected Shortfall
    - Stress VaR (during market crises)
    - Tail risk (extreme loss probability)
    - Factor exposure (market, sector, beta)
    - Correlation breakdown risk
    - Concentration risk
    - Liquidity risk
    - Intraday VaR
    """

    def __init__(self, confidence: float = 0.95, horizon_days: int = 1) -> None:
        self.confidence = confidence
        self.horizon_days = horizon_days

    def compute_var(self, returns: list[float]) -> float:
        """Compute Value at Risk at the configured confidence level."""
        if len(returns) < 2:
            return 0.0
        arr = np.array(returns)
        var = float(np.percentile(arr, (1 - self.confidence) * 100))
        return var * np.sqrt(self.horizon_days)

    def compute_cvar(self, returns: list[float]) -> float:
        """Compute Conditional VaR (Expected Shortfall)."""
        if len(returns) < 2:
            return 0.0
        arr = np.array(returns)
        var = float(np.percentile(arr, (1 - self.confidence) * 100))
        tail = arr[arr <= var]
        if len(tail) == 0:
            return var
        return float(tail.mean()) * np.sqrt(self.horizon_days)

    def compute_stress_var(self, returns: list[float], stress_period_returns: list[float]) -> float:
        """Compute VaR using a stressed historical period."""
        combined = list(returns) + list(stress_period_returns)
        return self.compute_var(combined)

    def compute_tail_risk(self, returns: list[float], threshold: float = -0.02) -> float:
        """Probability of loss exceeding threshold (tail risk)."""
        if not returns:
            return 0.0
        arr = np.array(returns)
        return float(np.mean(arr < threshold))

    def compute_factor_exposure(
        self,
        instrument_returns: dict[str, list[float]],
        factor_returns: dict[str, list[float]],
    ) -> dict[str, float]:
        """Compute factor exposure (beta) for each instrument.

        Args:
            instrument_returns: Dict of {instrument_id: return_series}
            factor_returns: Dict of {factor_name: return_series}

        Returns:
            Dict of {factor_name: beta}
        """
        exposures: dict[str, float] = {}
        for factor_name, factor_ret in factor_returns.items():
            betas: list[float] = []
            for inst_ret in instrument_returns.values():
                min_len = min(len(inst_ret), len(factor_ret))
                if min_len < 10:
                    continue
                inst_arr = np.array(inst_ret[:min_len])
                factor_arr = np.array(factor_ret[:min_len])
                cov = np.cov(inst_arr, factor_arr)[0, 1]
                var = np.var(factor_arr)
                if var > 0:
                    betas.append(cov / var)
            exposures[factor_name] = float(np.mean(betas)) if betas else 0.0
        return exposures

    def compute_correlation_risk(self, returns_matrix: np.ndarray) -> float:
        """Measure correlation breakdown risk.

        Higher values indicate higher correlation = higher systemic risk.
        """
        if returns_matrix.ndim != 2 or returns_matrix.shape[1] < 2:
            return 0.0
        corr = np.corrcoef(returns_matrix)
        n = corr.shape[0]
        upper_tri = corr[np.triu_indices(n, k=1)]
        return float(np.mean(np.abs(upper_tri)))

    def compute_concentration_risk(self, weights: list[float]) -> float:
        """Compute Herfindahl-Hirschman Index for concentration risk.

        Higher = more concentrated = higher risk.
        """
        w = np.array(weights)
        w = w / np.sum(w) if np.sum(w) > 0 else w
        hhi = float(np.sum(w**2))
        normalized = (hhi - 1 / len(w)) / (1 - 1 / len(w)) if len(w) > 1 else 1.0
        return normalized

    def compute_liquidity_risk(
        self,
        positions: dict[str, float],
        advs: dict[str, float],
        max_participation: float = 0.1,
    ) -> float:
        """Compute liquidity risk score based on position size vs ADV."""
        scores: list[float] = []
        for inst, pos in positions.items():
            adv = advs.get(inst, 1_000_000)
            days_to_liquidate = abs(pos) / (adv * max_participation)
            # Normalize: 0 = no risk, 1 = extreme risk
            score = min(days_to_liquidate / 10, 1.0)
            scores.append(score)
        return float(np.mean(scores)) if scores else 0.0

    def compute_intraday_var(
        self,
        returns: list[float],
        intraday_multiplier: float = 3.0,
    ) -> float:
        """Compute intraday VaR (typically higher than daily VaR)."""
        daily_var = self.compute_var(returns)
        return daily_var * intraday_multiplier

    def full_assessment(
        self,
        returns: list[float],
        stress_returns: list[float] | None = None,
        positions: dict[str, float] | None = None,
        advs: dict[str, float] | None = None,
        weights: list[float] | None = None,
    ) -> PortfolioRiskMetrics:
        """Compute a full set of risk metrics in one call."""
        metrics = PortfolioRiskMetrics()
        metrics.var_95 = self.compute_var(returns)
        metrics.cvar_95 = self.compute_cvar(returns)
        metrics.tail_risk = self.compute_tail_risk(returns)

        if stress_returns:
            metrics.stress_var = self.compute_stress_var(returns, stress_returns)

        if weights:
            metrics.concentration_risk = self.compute_concentration_risk(weights)

        if positions and advs:
            metrics.liquidity_risk = self.compute_liquidity_risk(positions, advs)

        metrics.intraday_var = self.compute_intraday_var(returns)
        metrics.expected_shortfall = metrics.cvar_95

        return metrics
