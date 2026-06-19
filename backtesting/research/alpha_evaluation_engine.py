from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class AlphaEvaluation:
    """Complete evaluation results for a single alpha."""
    alpha_id: str = ""
    sharpe_ratio: float = 0.0
    information_coefficient: float = 0.0
    ic_mean: float = 0.0
    ic_std: float = 0.0
    ic_ratio: float = 0.0
    ic_decay: list[float] = field(default_factory=list)  # IC at each lag
    t_statistic: float = 0.0
    p_value: float = 1.0
    hit_rate: float = 0.0
    turnover: float = 0.0
    capacity: float = 0.0
    rank_ic: float = 0.0
    quantile_returns: list[float] = field(default_factory=list)
    stability_score: float = 0.0
    half_life_days: float = 0.0
    status: str = "pending"
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class AlphaEvaluationEngine:
    """Evaluates alpha signals for quality, predictive power, and robustness.

    Computes:
    - Information Coefficient (IC) and IC decay
    - Sharpe ratio of the signal
    - t-statistic for statistical significance
    - Hit rate and turnover
    - Capacity estimate
    - Rank IC (Spearman correlation)
    - Quantile returns analysis
    - Stability across time periods
    - Half-life of predictive power

    Usage:
        engine = AlphaEvaluationEngine()
        result = engine.evaluate(signals, forward_returns)
        print(f"IC: {result.information_coefficient:.3f}")
        print(f"IC decay: {result.ic_decay}")
    """

    def evaluate(
        self,
        signals: np.ndarray,
        forward_returns: np.ndarray,
        alpha_id: str = "",
        trading_days: int = 252,
    ) -> AlphaEvaluation:
        """Evaluate an alpha signal.

        Args:
            signals: array of alpha signal values
            forward_returns: array of forward returns (same length)
            alpha_id: optional identifier
            trading_days: number of trading days per year

        Returns:
            AlphaEvaluation with all metrics
        """
        result = AlphaEvaluation(alpha_id=alpha_id)

        signals = np.asarray(signals, dtype=float).flatten()
        forward_returns = np.asarray(forward_returns, dtype=float).flatten()

        if len(signals) < 5 or len(forward_returns) < 5:
            result.status = "insufficient_data"
            return result

        n = min(len(signals), len(forward_returns))
        signals = signals[:n]
        forward_returns = forward_returns[:n]

        # Remove NaN/inf
        mask = np.isfinite(signals) & np.isfinite(forward_returns)
        signals = signals[mask]
        forward_returns = forward_returns[mask]

        if len(signals) < 5:
            result.status = "insufficient_clean_data"
            return result

        n = len(signals)

        # 1. Information Coefficient (Pearson correlation)
        if np.std(signals) > 0 and np.std(forward_returns) > 0:
            corr_matrix = np.corrcoef(signals, forward_returns)
            result.information_coefficient = float(corr_matrix[0, 1])
        else:
            result.information_coefficient = 0.0

        # 2. Rank IC (Spearman correlation)
        rank_sig = np.argsort(np.argsort(signals))
        rank_ret = np.argsort(np.argsort(forward_returns))
        if np.std(rank_sig) > 0 and np.std(rank_ret) > 0:
            rank_corr = np.corrcoef(rank_sig, rank_ret)
            result.rank_ic = float(rank_corr[0, 1])
        else:
            result.rank_ic = 0.0

        # 3. IC mean/std/ratio
        # Compute rolling IC if possible (chunked cross-sectional)
        ic_values = self._compute_ic_chunks(signals, forward_returns, chunk_size=max(n // 20, 10))
        if len(ic_values) > 0:
            result.ic_mean = float(np.mean(ic_values))
            result.ic_std = float(np.std(ic_values))
            result.ic_ratio = float(result.ic_mean / max(result.ic_std, 1e-8))
        else:
            result.ic_mean = result.information_coefficient
            result.ic_std = 0.0
            result.ic_ratio = 0.0

        # 4. IC decay (predictive power over time)
        result.ic_decay = self._compute_ic_decay(signals, forward_returns, max_lags=min(20, n // 2))

        # 5. t-statistic
        if result.ic_std > 0:
            result.t_statistic = result.ic_mean / (result.ic_std / np.sqrt(len(ic_values) if len(ic_values) > 0 else n))
        else:
            result.t_statistic = 0.0

        # Approximate p-value from normal distribution
        from scipy.stats import norm
        result.p_value = float(2 * (1 - norm.cdf(abs(result.t_statistic))))

        # 6. Sharpe ratio of signal
        sig_returns = signals * forward_returns  # long-short portfolio
        if np.std(sig_returns) > 0:
            result.sharpe_ratio = float(np.mean(sig_returns) / np.std(sig_returns) * np.sqrt(trading_days))

        # 7. Hit rate (percentage of correct directional predictions)
        correct = np.sum((signals > 0) & (forward_returns > 0)) + np.sum((signals < 0) & (forward_returns < 0))
        result.hit_rate = float(correct / n)

        # 8. Turnover (average absolute change in signal)
        if n > 1:
            result.turnover = float(np.mean(np.abs(np.diff(np.sign(signals)))))
        else:
            result.turnover = 0.0

        # 9. Quantile returns
        result.quantile_returns = self._compute_quantile_returns(signals, forward_returns, n_quantiles=5)

        # 10. Half-life (decay of IC over lags)
        if len(result.ic_decay) > 2:
            decay = np.array(result.ic_decay)
            # Find lag where IC drops below half of first value
            half = abs(decay[0]) * 0.5 if abs(decay[0]) > 0 else 0.01
            for i, d in enumerate(decay):
                if abs(d) < half:
                    result.half_life_days = float(i)
                    break
            else:
                result.half_life_days = float(len(decay))

        # 11. Stability (IC consistency across periods)
        if len(ic_values) > 1:
            result.stability_score = 1.0 - min(float(np.std(ic_values) / max(abs(np.mean(ic_values)), 0.01)), 1.0)

        # 12. Capacity (rough estimate)
        if result.turnover > 0:
            result.capacity = 1.0 / max(result.turnover, 0.01) * result.ic_ratio * 0.01

        result.status = "evaluated"
        return result

    def compare(self, evaluations: list[AlphaEvaluation]) -> list[dict[str, Any]]:
        """Compare multiple alphas and rank them."""
        ranked = []
        for i, ev in enumerate(evaluations):
            score = (
                ev.ic_ratio * 0.3
                + min(ev.sharpe_ratio, 5) / 5 * 0.2
                + ev.stability_score * 0.2
                + ev.hit_rate * 0.15
                + min(ev.half_life_days / 10, 1) * 0.15
            )
            ranked.append({
                "rank": 0,
                "alpha_id": ev.alpha_id,
                "composite_score": score,
                "ic": ev.information_coefficient,
                "sharpe": ev.sharpe_ratio,
                "stability": ev.stability_score,
                "hit_rate": ev.hit_rate,
                "half_life": ev.half_life_days,
            })

        ranked.sort(key=lambda x: x["composite_score"], reverse=True)
        for i, r in enumerate(ranked):
            r["rank"] = i + 1
        return ranked

    def _compute_ic_chunks(
        self,
        signals: np.ndarray,
        returns: np.ndarray,
        chunk_size: int = 20,
    ) -> list[float]:
        """Compute IC over time chunks (forward-looking correlation stability)."""
        ic_values: list[float] = []
        for i in range(0, len(signals) - chunk_size, chunk_size // 2):
            chunk_sig = signals[i:i + chunk_size]
            chunk_ret = returns[i:i + chunk_size]
            if np.std(chunk_sig) > 0 and np.std(chunk_ret) > 0:
                c = np.corrcoef(chunk_sig, chunk_ret)
                ic_values.append(float(c[0, 1]))
        return ic_values

    def _compute_ic_decay(
        self,
        signals: np.ndarray,
        returns: np.ndarray,
        max_lags: int = 20,
    ) -> list[float]:
        """Compute IC at different forward lags to see signal decay."""
        decay: list[float] = []
        for lag in range(max_lags):
            if lag >= len(signals) - 1:
                break
            sig = signals[:len(signals) - lag]
            ret = returns[lag:]
            if np.std(sig) > 0 and np.std(ret) > 0:
                c = np.corrcoef(sig, ret)
                decay.append(float(c[0, 1]))
            else:
                decay.append(0.0)
        return decay

    def _compute_quantile_returns(
        self,
        signals: np.ndarray,
        returns: np.ndarray,
        n_quantiles: int = 5,
    ) -> list[float]:
        """Compute average forward return for each signal quantile."""
        if len(signals) < n_quantiles:
            return [0.0] * n_quantiles
        quantiles = np.percentile(signals, np.linspace(0, 100, n_quantiles + 1)[1:-1])
        labels = np.digitize(signals, quantiles)
        quant_returns = []
        for q in range(n_quantiles):
            mask = labels == q
            if np.sum(mask) > 0:
                quant_returns.append(float(np.mean(returns[mask])))
            else:
                quant_returns.append(0.0)
        return quant_returns
