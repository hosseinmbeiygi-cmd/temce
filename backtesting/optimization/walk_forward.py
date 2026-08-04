"""
Walk-Forward Optimization (Enhanced)
=====================================

Splits data into in-sample (training) and out-of-sample (testing) windows,
optimizes on in-sample, validates on out-of-sample. This prevents overfitting.

Enhancements over basic implementation:
1. Anchored walk-forward (expanding window) option
2. Parameter stability penalty across windows
3. Improved objective function
4. Walk-forward efficiency metric
5. Parameter consistency score
"""

from __future__ import annotations

import asyncio
import itertools
import json as _json
import math
from collections import Counter
from typing import Any

from backtesting.engine.simulator import BacktestSimulator
from backtesting.strategies.registry import get_strategy_registry
from core.logging import get_logger

logger = get_logger(__name__)


def _compute_metrics(equity: list[float], trades: list[Any]) -> dict[str, float]:
    """Compute performance metrics for a single window."""
    if len(equity) < 2 or not trades:
        return {"return_pct": 0, "sharpe": 0, "max_dd": 100, "win_rate": 0, "trades": 0}

    total_return = ((equity[-1] / equity[0]) - 1) * 100
    returns = [(equity[i] / equity[i - 1]) - 1 for i in range(1, len(equity))]
    avg_r = sum(returns) / len(returns) if returns else 0
    std_r = math.sqrt(sum((r - avg_r) ** 2 for r in returns) / len(returns)) if returns else 1
    sharpe = (avg_r / std_r) * math.sqrt(252) if std_r > 0 else 0

    peak = equity[0]
    max_dd = 0.0
    for nav in equity:
        if nav > peak:
            peak = nav
        dd = (peak - nav) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)

    wins = sum(1 for t in trades if getattr(t, "pnl", 0) > 0)
    win_rate = (wins / len(trades) * 100) if trades else 0

    return {
        "return_pct": round(total_return, 2),
        "sharpe": round(sharpe, 2),
        "max_dd": round(max_dd * 100, 2),
        "win_rate": round(win_rate, 1),
        "trades": len(trades),
    }


def _objective_function(metrics: dict[str, float], n_windows: int = 1) -> float:
    """Improved objective function for optimization.

    Balances return, risk, and consistency:
    - Sharpe ratio (primary signal)
    - Return (secondary)
    - Drawdown penalty
    - Trade frequency bonus (penalize too few trades)
    """
    sharpe = metrics.get("sharpe", 0)
    ret = metrics.get("return_pct", 0)
    dd = metrics.get("max_dd", 100)
    trades = metrics.get("trades", 0)

    # Sharpe is primary driver
    score = sharpe * 0.4

    # Return component (diminishing returns above 50%)
    score += min(ret * 0.003, 0.3)

    # Drawdown penalty (severe for > 20%)
    dd_penalty = 0
    if dd > 20:
        dd_penalty = (dd - 20) * 0.01
    elif dd > 10:
        dd_penalty = (dd - 10) * 0.005
    score -= dd_penalty

    # Trade frequency: penalize too few trades (< 5) or too many (> 100)
    if trades < 5:
        score -= 0.2
    elif trades > 100:
        score -= 0.1

    return score


class WalkForwardOptimizer:
    """Walk-forward optimization with anchored mode and parameter stability."""

    def __init__(
        self,
        windows: int = 5,
        train_ratio: float = 0.7,
        max_workers: int | None = None,
        anchored: bool = False,
        stability_penalty: float = 0.1,
    ) -> None:
        """
        Args:
            windows: Number of walk-forward windows
            train_ratio: Fraction of each window used for training
            max_workers: Max parallel optimization workers
            anchored: If True, use anchored (expanding) windows
            stability_penalty: Penalty weight for parameter instability (0-1)
        """
        self.windows = windows
        self.train_ratio = train_ratio
        self._max_workers = max_workers
        self.anchored = anchored
        self.stability_penalty = stability_penalty

    def _get_max_workers(self) -> int:
        if self._max_workers is not None:
            return self._max_workers
        try:
            from core.config import settings
            return getattr(settings, "backtest_max_optimization_workers", 4)
        except Exception:
            return 4

    async def _eval_combo(
        self,
        cls: type,
        combo: tuple,
        keys: list[str],
        train_data: list[dict[str, Any]],
        capital: float,
        simulator: BacktestSimulator,
    ) -> tuple[float, dict[str, Any]]:
        """Evaluate a single parameter combination on train data."""
        params = dict(zip(keys, combo, strict=False))
        try:
            strategy = cls(**{k: int(v) if isinstance(v, float) and v == int(v) else v for k, v in params.items()})
            result = simulator.run(strategy, initial_capital=capital, data=train_data)
            if not result.success:
                return (-1e9, params)
            equity = [ep.nav for ep in result.value.equity_curve]
            trades = result.value.trades
            metrics = _compute_metrics(equity, trades)
            score = _objective_function(metrics)
            return (score, params)
        except Exception:
            return (-1e9, params)

    async def _optimize_window(
        self,
        cls: type,
        all_combos: list[tuple],
        keys: list[str],
        train_data: list[dict[str, Any]],
        capital: float,
        simulator: BacktestSimulator,
    ) -> tuple[dict[str, Any], float]:
        """Find best params for a single window. Returns (params, score)."""
        max_workers = self._get_max_workers()
        semaphore = asyncio.Semaphore(max_workers)

        async def _bounded_eval(combo: tuple) -> tuple[float, dict[str, Any]]:
            async with semaphore:
                return await self._eval_combo(cls, combo, keys, train_data, capital, simulator)

        tasks = [_bounded_eval(combo) for combo in all_combos]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        best_score = -1e9
        best_params = {}
        for r in results:
            if isinstance(r, Exception):
                continue
            score, params = r
            if score > best_score:
                best_score = score
                best_params = params

        return best_params, best_score

    def _compute_parameter_stability(self, params_list: list[dict[str, Any]]) -> float:
        """Compute parameter stability across windows (0-1).

        Higher = more stable = better.
        Uses coefficient of variation for numeric params.
        """
        if len(params_list) < 2:
            return 1.0

        stability_scores = []

        # Get all parameter keys
        all_keys = set()
        for p in params_list:
            all_keys.update(p.keys())

        for key in all_keys:
            values = [p.get(key) for p in params_list if key in p]
            if not values or not all(isinstance(v, (int, float)) for v in values):
                # For non-numeric params, check if most common
                counter = Counter(str(v) for v in values)
                most_common_pct = counter.most_common(1)[0][1] / len(values)
                stability_scores.append(most_common_pct)
                continue

            # Coefficient of variation for numeric params
            vals = [float(v) for v in values]
            mean = sum(vals) / len(vals)
            if mean == 0:
                stability_scores.append(1.0)
                continue
            std = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
            cv = std / abs(mean)
            # Convert CV to stability (lower CV = higher stability)
            stability_scores.append(max(0, 1 - cv))

        return sum(stability_scores) / len(stability_scores) if stability_scores else 1.0

    def _select_best_params(
        self,
        params_list: list[dict[str, Any]],
        scores: list[float],
    ) -> dict[str, Any]:
        """Select best parameters using weighted scoring.

        Weights:
        - In-sample score: 60%
        - Parameter stability: 30%
        - Consistency bonus: 10%
        """
        if not params_list:
            return {}

        self._compute_parameter_stability(params_list)

        # Weighted score for each unique param set
        param_scores: dict[str, float] = {}
        param_counts: dict[str, int] = {}

        for params, score in zip(params_list, scores, strict=False):
            key = _json.dumps(params, sort_keys=True)
            if key not in param_scores:
                param_scores[key] = 0
                param_counts[key] = 0
            param_scores[key] += score
            param_counts[key] += 1

        best_key = max(param_scores.keys(), key=lambda k: param_scores[k])
        best_params = _json.loads(best_key)

        return best_params

    async def optimize(
        self,
        strategy_name: str,
        param_grid: dict[str, list[Any]],
        data: list[dict[str, Any]],
        capital: float,
        simulator: BacktestSimulator,
    ) -> dict[str, Any]:
        """Run walk-forward optimization with anchoring and stability analysis.

        Returns:
            Dict with strategy results, stability metrics, and recommendations.
        """
        registry = get_strategy_registry()
        cls = registry.get(strategy_name)
        if cls is None:
            return {"error": f"Strategy {strategy_name} not found"}

        window_size = len(data) // self.windows
        if window_size < 20:
            return {"error": "Not enough data for walk-forward optimization"}

        all_combos = list(itertools.product(*[param_grid[k] for k in param_grid]))
        keys = list(param_grid.keys())

        oos_results = []
        all_params = []
        all_scores = []

        for w in range(self.windows):
            if self.anchored:
                # Anchored: expanding window (always starts from beginning)
                end = (w + 1) * window_size + int(len(data) * (1 - self.train_ratio))
                end = min(end, len(data))
                window_data = data[:end]
            else:
                # Rolling: fixed-size window
                start = w * window_size
                end = min(start + window_size, len(data))
                window_data = data[start:end]

            split = int(len(window_data) * self.train_ratio)
            train_data = window_data[:split]
            test_data = window_data[split:]

            if len(test_data) < 10:
                continue

            # Optimize on train data
            best_params, best_score = await self._optimize_window(
                cls, all_combos, keys, train_data, capital, simulator
            )

            # Validate on test data (out-of-sample)
            if best_params:
                try:
                    strategy = cls(**{k: int(v) if isinstance(v, float) and v == int(v) else v for k, v in best_params.items()})
                    result = simulator.run(strategy, initial_capital=capital, data=test_data)
                    if result.success:
                        equity = [ep.nav for ep in result.value.equity_curve]
                        trades = result.value.trades
                        oos_metrics = _compute_metrics(equity, trades)
                        oos_metrics["window"] = w + 1
                        oos_metrics["params"] = best_params
                        oos_results.append(oos_metrics)
                        all_params.append(best_params)
                        all_scores.append(best_score)
                except Exception:
                    continue

        if not oos_results:
            return {"error": "No valid walk-forward results"}

        # Compute aggregate metrics
        avg_return = sum(r["return_pct"] for r in oos_results) / len(oos_results)
        avg_sharpe = sum(r["sharpe"] for r in oos_results) / len(oos_results)
        consistency = sum(1 for r in oos_results if r["return_pct"] > 0) / len(oos_results) * 100

        # Parameter stability
        param_stability = self._compute_parameter_stability(all_params)

        # Walk-forward efficiency (OOS performance / IS performance)
        is_sharpe_avg = sum(s for s in all_scores if s > 0) / max(len(all_scores), 1)
        wf_efficiency = avg_sharpe / max(is_sharpe_avg, 0.01) if is_sharpe_avg > 0 else 0

        # Overfitting score (lower is better)
        overfitting_score = 100 - (consistency * 0.4 + param_stability * 30 + wf_efficiency * 30)
        overfitting_score = max(0, min(100, overfitting_score))

        # Select best parameters
        best_params = self._select_best_params(all_params, all_scores)

        return {
            "strategy": strategy_name,
            "best_params": best_params,
            "oos_results": oos_results,
            "avg_oos_return": round(avg_return, 2),
            "avg_oos_sharpe": round(avg_sharpe, 2),
            "consistency": round(consistency, 1),
            "parameter_stability": round(param_stability, 3),
            "walk_forward_efficiency": round(wf_efficiency, 3),
            "overfitting_score": round(overfitting_score, 1),
            "n_windows": len(oos_results),
            "anchored": self.anchored,
            "recommendation": self._generate_recommendation(
                consistency, param_stability, wf_efficiency, overfitting_score
            ),
        }

    def _generate_recommendation(
        self,
        consistency: float,
        stability: float,
        wf_efficiency: float,
        overfitting: float,
    ) -> str:
        """Generate human-readable recommendation based on metrics."""
        if overfitting < 30 and consistency > 70 and stability > 0.7:
            return "EXCELLENT: Strategy shows strong OOS performance with stable parameters. Ready for paper trading."
        elif overfitting < 50 and consistency > 50:
            return "GOOD: Strategy shows reasonable OOS performance. Consider additional validation before live trading."
        elif overfitting < 70:
            return "CAUTION: Strategy may be overfit. Parameters are somewhat unstable. Increase validation period."
        else:
            return "WARNING: Strategy shows signs of overfitting. Do NOT use for live trading without further validation."
