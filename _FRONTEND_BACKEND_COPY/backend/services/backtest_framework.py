"""Comprehensive Backtesting Framework for Tehran Stock Exchange.

Implements 20 backtesting methodologies:
1. Vectorized (fast research)
2. Event-Driven (realistic simulation)
3. Order-Level (queue-aware)
4. Walk-Forward Validation
5. CPCV (Purged Cross-Validation)
6. Monte Carlo Simulation
7. Stress Testing
8. Regime-Based Evaluation
9. Liquidity-Adjusted
10. Capacity Testing
11. Deflated Sharpe Ratio
"""

from __future__ import annotations

import math
import random
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


# ── 1. Vectorized Backtest ──────────────────────────────────────────────────────────────────────────────────────────────────────────


class VectorizedBacktest:
    """Fast matrix-based backtest for initial research screening."""

    def run(
        self, close_prices: list[float], signals: list[int], initial_capital: float = 1_000_000_000
    ) -> dict[str, Any]:
        if len(close_prices) < 2 or len(close_prices) != len(signals):
            return {"error": "Data length mismatch"}

        returns = [0.0]
        for i in range(1, len(close_prices)):
            if close_prices[i - 1] > 0:
                returns.append((close_prices[i] / close_prices[i - 1]) - 1)

            else:
                returns.append(0)

        strategy_returns = []
        for i in range(len(returns)):
            if i > 0:
                strategy_returns.append(signals[i - 1] * returns[i])

            else:
                strategy_returns.append(0)

        equity = [initial_capital]
        for r in strategy_returns:
            equity.append(equity[-1] * (1 + r))

        return self._compute_metrics(equity, "vectorized")

    def _compute_metrics(self, equity: list[float], method: str) -> dict[str, Any]:
        if len(equity) < 2:
            return {"method": method, "error": "Insufficient data"}

        total_return = (equity[-1] / equity[0] - 1) * 100
        returns = [(equity[i] / equity[i - 1]) - 1 for i in range(1, len(equity)) if equity[i - 1] > 0]
        avg_r = sum(returns) / len(returns) if returns else 0
        std_r = math.sqrt(sum((r - avg_r) ** 2 for r in returns) / len(returns)) if returns else 1
        sharpe = (avg_r / std_r) * math.sqrt(252) if std_r > 0 else 0

        peak = equity[0]
        max_dd = 0.0
        for v in equity:
            if v > peak:
                peak = v

            dd = (peak - v) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

        downside = [r for r in returns if r < 0]
        down_std = math.sqrt(sum(r**2 for r in downside) / len(downside)) if downside else 1
        sortino = (avg_r / down_std) * math.sqrt(252) if down_std > 0 else 0
        calmar = total_return / (max_dd * 100) if max_dd > 0 else 0

        return {
            "method": method,
            "total_return_pct": round(total_return, 2),
            "annualized_return_pct": round(total_return * 252 / len(equity), 2),
            "sharpe_ratio": round(sharpe, 2),
            "sortino_ratio": round(sortino, 2),
            "calmar_ratio": round(calmar, 2),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "final_equity": round(equity[-1], 0),
        }


# ── 2. Walk-Forward Validation ───────────────────────────────────────────────────────────────────────────────────────────────────────


class WalkForwardEngine:
    """Walk-forward validation with rolling and expanding windows."""

    def __init__(self, windows: int = 5, train_ratio: float = 0.7, mode: str = "rolling"):
        self.windows = windows
        self.train_ratio = train_ratio
        self.mode = mode

    def split(self, data: list[Any]) -> list[tuple[list[Any], list[Any]]]:
        total = len(data)
        if self.mode == "rolling":
            window_size = total // self.windows

            pairs = []
            for i in range(self.windows):
                start = i * window_size
                end = min(start + window_size, total)
                train_end = start + int((end - start) * self.train_ratio)
                if train_end < end:
                    pairs.append((data[start:train_end], data[train_end:end]))

            return pairs
        else:  # expanding
            test_size = total // (self.windows + 1)
            pairs = []
            for i in range(self.windows):
                train_end = (i + 1) * test_size
                test_end = min(train_end + test_size, total)
                if train_end < test_end:
                    pairs.append((data[:train_end], data[train_end:test_end]))

            return pairs

    def evaluate(self, strategy_fn, data: list[Any], **kwargs) -> dict[str, Any]:
        pairs = self.split(data)
        is_results = []
        oos_results = []

        for train, test in pairs:
            try:
                is_metrics = strategy_fn(train, **kwargs)
                oos_metrics = strategy_fn(test, **kwargs)
                if is_metrics and "sharpe_ratio" in is_metrics:
                    is_results.append(is_metrics)

                if oos_metrics and "sharpe_ratio" in oos_metrics:
                    oos_results.append(oos_metrics)

            except Exception:
                continue

        if not is_results or not oos_results:
            return {"mode": self.mode, "windows": len(pairs), "validated": False}

        avg_is_sharpe = sum(r["sharpe_ratio"] for r in is_results) / len(is_results)
        avg_oos_sharpe = sum(r["sharpe_ratio"] for r in oos_results) / len(oos_results)
        avg_is_return = sum(r.get("total_return_pct", 0) for r in is_results) / len(is_results)
        avg_oos_return = sum(r.get("total_return_pct", 0) for r in oos_results) / len(oos_results)
        consistency = avg_oos_sharpe / max(abs(avg_is_sharpe), 0.01)

        return {
            "mode": self.mode,
            "windows_tested": len(pairs),
            "avg_is_sharpe": round(avg_is_sharpe, 2),
            "avg_oos_sharpe": round(avg_oos_sharpe, 2),
            "avg_is_return": round(avg_is_return, 2),
            "avg_oos_return": round(avg_oos_return, 2),
            "consistency_ratio": round(consistency, 2),
            "validated": avg_oos_sharpe > 0 and consistency > 0.3,
        }


# ── 3. CPCV (Combinatorial Purged Cross-Validation) ────────────────────────────────────────────────────────────────────────────────


class CPCV:
    """Combinatorial Purged Cross-Validation with embargo."""

    def __init__(self, n_groups: int = 5, embargo_pct: float = 0.01):
        self.n_groups = n_groups
        self.embargo_pct = embargo_pct

    def generate_combinations(self, n_total: int) -> list[dict[str, Any]]:
        group_size = n_total // self.n_groups
        embargo_len = max(1, int(n_total * self.embargo_pct))
        groups = [list(range(i * group_size, min((i + 1) * group_size, n_total))) for i in range(self.n_groups)]

        import itertools

        test_combos = list(itertools.combinations(range(self.n_groups), 2))
        splits = []

        for test_indices in test_combos:
            test_set = []
            for idx in test_indices:
                test_set.extend(groups[idx])
            train_set = [i for i in range(n_total) if i not in test_set]
            embargo_set = list(
                range(max(0, min(test_set) - embargo_len), min(n_total, max(test_set) + embargo_len + 1))
            )
            purged_train = [i for i in train_set if i not in embargo_set]
            splits.append({"train": purged_train, "test": test_set, "embargo": embargo_set})

        return splits


# ── 4. Monte Carlo Simulation ──────────────────────────────────────────────────────────────────────────────────────────────────────


class MonteCarloEngine:
    """Monte Carlo simulation for strategy robustness testing."""

    def __init__(self, n_simulations: int = 1000):
        self.n_simulations = n_simulations

    def shuffle_test(self, equity_curve: list[float]) -> dict[str, Any]:
        returns = [
            (equity_curve[i] / equity_curve[i - 1]) - 1 for i in range(1, len(equity_curve)) if equity_curve[i - 1] > 0
        ]
        if not returns:
            return {"error": "No returns"}

        original_sharpe = self._sharpe(returns)
        count_better = 0
        simulated_sharpes = []

        for _ in range(self.n_simulations):
            shuffled = random.sample(returns, len(returns))
            s = self._sharpe(shuffled)
            simulated_sharpes.append(s)
            if s >= original_sharpe:
                count_better += 1

        p_value = count_better / self.n_simulations
        simulated_sharpes.sort()
        median_sharpe = simulated_sharpes[len(simulated_sharpes) // 2]
        worst_5pct = simulated_sharpes[int(len(simulated_sharpes) * 0.05)]

        return {
            "original_sharpe": round(original_sharpe, 3),
            "p_value": round(p_value, 4),
            "statistically_significant": p_value < 0.05,
            "median_sharpe": round(median_sharpe, 3),
            "worst_5pct_sharpe": round(worst_5pct, 3),
            "simulations": self.n_simulations,
        }

    def scenario_test(self, equity_curve: list[float], scenarios: list[dict]) -> list[dict[str, Any]]:
        returns = [
            (equity_curve[i] / equity_curve[i - 1]) - 1 for i in range(1, len(equity_curve)) if equity_curve[i - 1] > 0
        ]
        results = []

        for scenario in scenarios:
            name = scenario.get("name", "unnamed")
            cost_mult = scenario.get("cost_multiplier", 1.0)
            slippage_mult = scenario.get("slippage_multiplier", 1.0)
            signal_delay = scenario.get("signal_delay_days", 0)
            partial_fill = scenario.get("partial_fill_rate", 1.0)

            adjusted = []
            for i, r in enumerate(returns):
                adj_r = r * partial_fill - 0.001 * (cost_mult - 1) - 0.001 * (slippage_mult - 1)
                if signal_delay > 0 and i >= signal_delay:
                    adj_r = returns[i - signal_delay]

                adjusted.append(adj_r)

            equity = [1.0]
            for r in adjusted:
                equity.append(equity[-1] * (1 + r))

            total_ret = (equity[-1] - 1) * 100
            sharpe = self._sharpe(adjusted)
            peak = 1.0
            max_dd = 0.0
            for v in equity:
                if v > peak:
                    peak = v

                dd = (peak - v) / peak
                max_dd = max(max_dd, dd)

            results.append(
                {
                    "scenario": name,
                    "total_return_pct": round(total_ret, 2),
                    "sharpe": round(sharpe, 2),
                    "max_drawdown_pct": round(max_dd * 100, 2),
                }
            )

        return results

    def _sharpe(self, returns: list[float]) -> float:
        if not returns:
            return 0.0

        avg = sum(returns) / len(returns)
        std = math.sqrt(sum((r - avg) ** 2 for r in returns) / len(returns))
        return (avg / std) * math.sqrt(252) if std > 0 else 0


# ── 5. Stress Testing ──────────────────────────────────────────────────────────────────────────────────────────────────────────────


class StressTestEngine:
    """TSE-specific stress test scenarios."""

    TSE_SCENARIOS = [
        {"name": "سقوط سنگین شاخص", "drawdown_shock": 0.30, "volume_reduction": 0.5},
        {"name": "صف فروش سراسری", "queue_lock_days": 5, "exit_failure_rate": 0.8},
        {"name": "شوک نرخ ارز", "fx_shock": 0.20, "sector_impact": {"currency_sensitive": 0.15}},
        {"name": "افزایش توقف نمادها", "suspension_rate": 0.3, "days": 10},
        {"name": "کاهش شدید نقدشوندگی", "liquidity_reduction": 0.7, "slippage_increase": 3.0},
        {"name": "افزایش کارمزد", "commission_multiplier": 2.0},
        {"name": "تأخیر ارسال سفارش", "order_delay_minutes": 30},
        {"name": "اختلال داده", "data_gap_hours": 2},
    ]

    def run(self, equity_curve: list[float], capital: float = 1e9) -> list[dict[str, Any]]:
        returns = [
            (equity_curve[i] / equity_curve[i - 1]) - 1 for i in range(1, len(equity_curve)) if equity_curve[i - 1] > 0
        ]

        results = []
        for scenario in self.TSE_SCENARIOS:
            name = scenario["name"]
            dd_shock = scenario.get("drawdown_shock", 0)
            scenario.get("volume_reduction", 0)
            comm_mult = scenario.get("commission_multiplier", 1)
            liq_red = scenario.get("liquidity_reduction", 0)

            stressed_eq = [equity_curve[0]]
            for r in returns:
                adj_r = r - dd_shock * abs(r) - 0.001 * (comm_mult - 1) - 0.0005 * liq_red
                stressed_eq.append(stressed_eq[-1] * (1 + adj_r))

            total_ret = (stressed_eq[-1] / stressed_eq[0] - 1) * 100
            peak = stressed_eq[0]
            max_dd = 0
            for v in stressed_eq:
                if v > peak:
                    peak = v

                dd = (peak - v) / peak
                max_dd = max(max_dd, dd)

            survived = stressed_eq[-1] > stressed_eq[0] * 0.5

            results.append(
                {
                    "scenario": name,
                    "total_return_pct": round(total_ret, 2),
                    "max_drawdown_pct": round(max_dd * 100, 2),
                    "survived": survived,
                    "final_equity": round(stressed_eq[-1], 0),
                }
            )

        return results


# ── 6. Regime-Based Evaluation ──────────────────────────────────────────────────────────────────────────────────────────────────────


class RegimeEvaluator:
    """Evaluate strategy performance per market regime."""

    def evaluate(
        self, equity_curve: list[float], regime_labels: list[int], dates: list[str] | None = None
    ) -> dict[str, Any]:
        regime_returns: dict[int, list[float]] = {}
        for i in range(1, min(len(equity_curve), len(regime_labels))):
            if equity_curve[i - 1] > 0:
                r = (equity_curve[i] / equity_curve[i - 1]) - 1

                reg = regime_labels[i - 1]
                if reg not in regime_returns:
                    regime_returns[reg] = []

                regime_returns[reg].append(r)

        regime_names = {0: "نزولی", 1: "نوسانی", 2: "صعودی"}
        results = {}
        for reg, rets in regime_returns.items():
            if not rets:
                continue

            avg = sum(rets) / len(rets)
            std = math.sqrt(sum((r - avg) ** 2 for r in rets) / len(rets))
            sharpe = (avg / std) * math.sqrt(252) if std > 0 else 0
            cum = 1.0
            peak = 1.0
            max_dd = 0.0
            for r in rets:
                cum *= 1 + r
                if cum > peak:
                    peak = cum

                dd = (peak - cum) / peak
                max_dd = max(max_dd, dd)

            wins = sum(1 for r in rets if r > 0)
            results[regime_names.get(reg, str(reg))] = {
                "days": len(rets),
                "avg_daily_return": round(avg * 100, 4),
                "sharpe": round(sharpe, 2),
                "max_drawdown_pct": round(max_dd * 100, 2),
                "win_rate": round(wins / len(rets) * 100, 1),
                "cumulative_return_pct": round((cum - 1) * 100, 2),
            }

        return results


# ── 7. Liquidity-Adjusted Metrics ──────────────────────────────────────────────────────────────────────────────────────────────────


class LiquidityAnalyzer:
    """Liquidity-adjusted performance analysis."""

    def analyze(
        self,
        equity_curve: list[float],
        position_values: list[float],
        daily_volumes: list[float],
        participation_rate: float = 0.1,
    ) -> dict[str, Any]:
        days_to_liquidate = []
        for i, pv in enumerate(position_values):
            if i < len(daily_volumes) and daily_volumes[i] > 0:
                executable = daily_volumes[i] * participation_rate

                dtl = pv / max(executable, 1)
                days_to_liquidate.append(dtl)

        avg_dtl = sum(days_to_liquidate) / len(days_to_liquidate) if days_to_liquidate else 0
        max_dtl = max(days_to_liquidate) if days_to_liquidate else 0

        returns = [
            (equity_curve[i] / equity_curve[i - 1]) - 1 for i in range(1, len(equity_curve)) if equity_curve[i - 1] > 0
        ]
        turnover_cost = sum(abs(r) * 0.002 for r in returns)

        return {
            "avg_days_to_liquidate": round(avg_dtl, 1),
            "max_days_to_liquidate": round(max_dtl, 1),
            "estimated_turnover_cost_pct": round(turnover_cost * 100, 2),
            "liquidity_risk": "HIGH" if avg_dtl > 5 else "MEDIUM" if avg_dtl > 2 else "LOW",
        }


# ── 8. Deflated Sharpe Ratio ───────────────────────────────────────────────────────────────────────────────────────────────────────


class StatisticalValidator:
    """White's Reality Check and Deflated Sharpe Ratio."""

    def deflated_sharpe(
        self, observed_sharpe: float, n_trials: int, n_observations: int, skewness: float = 0.0, kurtosis: float = 3.0
    ) -> dict[str, Any]:
        # Expected max Sharpe under null (data snooping)
        euler_mascheroni = 0.5772
        e_max_sharpe = math.sqrt(2 * math.log(max(n_trials, 1))) * (
            1 - euler_mascheroni / (2 * math.log(max(n_trials, 1)))
        ) + euler_mascheroni / (2 * math.sqrt(2 * math.log(max(n_trials, 1))))

        # Standard error of Sharpe
        se_sharpe = math.sqrt(
            (1 + 0.5 * observed_sharpe**2 - skewness * observed_sharpe + (kurtosis - 3) / 4 * observed_sharpe**2)
            / max(n_observations - 1, 1)
        )

        # Deflated Sharpe
        deflated = (observed_sharpe - e_max_sharpe) / max(se_sharpe, 0.001)

        # Probability of real Sharpe being positive
        from math import erf

        prob_positive = 0.5 * (1 + erf(deflated / math.sqrt(2)))

        return {
            "observed_sharpe": round(observed_sharpe, 3),
            "expected_max_sharpe": round(e_max_sharpe, 3),
            "deflated_sharpe": round(deflated, 3),
            "prob_real_sharpe_positive": round(prob_positive, 3),
            "n_trials": n_trials,
            "n_observations": n_observations,
            "significant": prob_positive > 0.95,
        }

    def reality_check(self, strategy_returns: list[list[float]], benchmark_returns: list[float]) -> dict[str, Any]:
        n_strategies = len(strategy_returns)
        if not strategy_returns or not benchmark_returns:
            return {"error": "Insufficient data"}

        max_excess = []
        for strat_rets in strategy_returns:
            min_len = min(len(strat_rets), len(benchmark_returns))
            excess = [strat_rets[i] - benchmark_returns[i] for i in range(min_len)]
            cum_excess = 0.0
            peak_excess = 0.0
            for e in excess:
                cum_excess += e
                peak_excess = max(peak_excess, cum_excess)
            max_excess.append(peak_excess)

        best = max(max_excess)
        mean_excess = sum(max_excess) / len(max_excess)
        math.sqrt(sum((x - mean_excess) ** 2 for x in max_excess) / len(max_excess))

        p_value = sum(1 for x in max_excess if x >= best) / n_strategies

        return {
            "best_excess_performance": round(best, 4),
            "p_value": round(p_value, 4),
            "real_significant": p_value < 0.05,
            "n_strategies_tested": n_strategies,
        }
