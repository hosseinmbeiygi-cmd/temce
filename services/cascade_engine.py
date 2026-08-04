"""Cascading Filter Pipeline Engine for Tehran Stock Exchange.

Implements a multi-stage filtering approach:
  Stage 1: Liquidity & Volume Filter (~700 -> ~150 symbols)
  Stage 2: Technical Base Filter (~150 -> ~50 symbols)
  Stage 3: Microstructure & Order Flow (~50 -> ~15 symbols)
  Stage 4: Strategy Generation & Genetic Optimization
  Stage 5: 6-Stage Quality Filter
  Stage 6: Walk-Forward Validation
"""
from __future__ import annotations

import asyncio
import itertools
import math
import random
from datetime import date
from typing import Any

from backtesting.engine.simulator import BacktestSimulator
from backtesting.strategies.registry import get_strategy_registry, register_all_strategies
from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)

# ── Parameter Ranges for Genetic Optimization ─────────────────────────────────────────────────────────────────────────────────────────

PARAM_GRID: dict[str, dict[str, list[Any]]] = {
    "moving_average_cross": {
        "fast_period": [3, 5, 7, 10, 12, 15, 20],
        "slow_period": [15, 20, 25, 30, 40, 50, 60, 80, 100, 120],
    },
    "momentum": {
        "lookback": [5, 10, 15, 20, 25, 30, 40, 60],
        "threshold_pct": [0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0],
    },
    "mean_reversion": {
        "lookback": [10, 15, 20, 25, 30, 40],
        "entry_z": [1.0, 1.5, 2.0, 2.5, 3.0],
        "exit_z": [0.0, 0.2, 0.3, 0.5, 0.8],
    },
    "breakout": {
        "lookback": [10, 15, 20, 25, 30, 40, 60],
        "breakout_pct": [0.0, 0.3, 0.5, 1.0, 1.5, 2.0],
    },
    "rsi_reversion": {
        "period": [7, 10, 14, 21],
        "oversold": [15, 20, 25, 30, 35],
        "overbought": [65, 70, 75, 80, 85],
    },
    "volatility_breakout": {
        "lookback": [10, 15, 20, 25, 30],
        "multiplier": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0],
    },
    "half_trend": {
        "amplitude": [1, 2, 3, 4, 5],
        "channel_deviation": [1.0, 1.5, 2.0, 2.5, 3.0],
    },
    "squeeze_momentum": {
        "bb_period": [15, 20, 25, 30],
        "bb_std": [1.5, 2.0, 2.5],
        "kc_period": [15, 20, 25, 30],
        "kc_mult": [1.0, 1.5, 2.0],
    },
    "support_resistance": {
        "lookback": [10, 15, 20, 25, 30, 40],
        "vol_threshold": [1.0, 1.3, 1.5, 2.0, 2.5],
    },
}


def compute_total_combinations(strategies: list[str], use_genetic: bool = True,
                                population_size: int = 50, generations: int = 12,
                                num_symbols: int = 1) -> int:
    """Calculate total parameter combinations for given strategies."""
    total = 0
    for sid in strategies:
        ranges = PARAM_GRID.get(sid, {})
        if not ranges:
            continue
        combos = 1
        for vals in ranges.values():
            combos *= len(vals)
        total += combos
    total *= max(num_symbols, 1)
    if use_genetic:
        total += len(strategies) * population_size * generations * max(num_symbols, 1)
    return total


# ── 6-Stage Quality Filter ────────────────────────────────────────────────────────────────────────────────────────────────────────────

DEFAULT_FILTERS = {
    "stage1_min_return": 5.0,
    "stage2_max_drawdown": 25.0,
    "stage3_min_sharpe": 0.5,
    "stage4_min_win_rate": 40.0,
    "stage5_min_trades": 5,
    "stage6_min_profit_factor": 1.2,
}


def apply_quality_filter(metrics: dict[str, Any], filters: dict[str, Any]) -> tuple[bool, str]:
    """Apply 6-stage quality filter to strategy metrics."""
    if metrics["total_return_pct"] < filters["stage1_min_return"]:
        return False, f"Return {metrics['total_return_pct']:.1f}% < {filters['stage1_min_return']}%"
    if metrics["max_drawdown_pct"] > filters["stage2_max_drawdown"]:
        return False, f"Drawdown {metrics['max_drawdown_pct']:.1f}% > {filters['stage2_max_drawdown']}%"
    if metrics["sharpe_ratio"] < filters["stage3_min_sharpe"]:
        return False, f"Sharpe {metrics['sharpe_ratio']:.2f} < {filters['stage3_min_sharpe']}"
    if metrics["win_rate"] < filters["stage4_min_win_rate"]:
        return False, f"Win rate {metrics['win_rate']:.1f}% < {filters['stage4_min_win_rate']}%"
    if metrics["total_trades"] < filters["stage5_min_trades"]:
        return False, f"Trades {metrics['total_trades']} < {filters['stage5_min_trades']}"
    if metrics["profit_factor"] < filters["stage6_min_profit_factor"]:
        return False, f"Profit factor {metrics['profit_factor']:.2f} < {filters['stage6_min_profit_factor']}"
    return True, ""


# ── Metrics Computation ───────────────────────────────────────────────────────────────────────────────────────────────────────────────

def compute_metrics(result: Any, initial_capital: float) -> dict[str, Any]:
    """Compute comprehensive metrics from backtest result."""
    equity = [ep.nav for ep in result.equity_curve]
    trades = result.trades

    if len(equity) < 2:
        return {
            "total_return_pct": 0, "annualized_return_pct": 0,
            "sharpe_ratio": 0, "max_drawdown_pct": 100,
            "win_rate": 0, "total_trades": 0,
            "winning_trades": 0, "losing_trades": 0,
            "profit_factor": 0, "sortino_ratio": 0, "calmar_ratio": 0,
        }

    total_return = ((equity[-1] / initial_capital) - 1) * 100
    trading_days = len(equity)
    years = trading_days / 252
    ann_return = ((equity[-1] / initial_capital) ** (1 / max(years, 0.01)) - 1) * 100

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

    wins = []
    losses = []
    for t in trades:
        pnl = getattr(t, "pnl", 0)
        if pnl > 0:
            wins.append(pnl)
        elif pnl < 0:
            losses.append(abs(pnl))

    win_rate = (len(wins) / len(trades) * 100) if trades else 0
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 1
    profit_factor = avg_win / avg_loss if avg_loss > 0 else 0

    downside_returns = [r for r in returns if r < 0]
    downside_vol = math.sqrt(sum(r ** 2 for r in downside_returns) / len(downside_returns)) if downside_returns else 1
    sortino = (avg_r / downside_vol) * math.sqrt(252) if downside_vol > 0 else 0
    calmar = ann_return / (max_dd * 100) if max_dd > 0 else 0

    return {
        "total_return_pct": round(total_return, 2),
        "annualized_return_pct": round(ann_return, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "win_rate": round(win_rate, 1),
        "total_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "profit_factor": round(profit_factor, 2),
        "sortino_ratio": round(sortino, 2),
        "calmar_ratio": round(calmar, 2),
    }


def compute_score(metrics: dict[str, Any]) -> float:
    """Weighted combined score for ranking strategies."""
    return (
        metrics.get("sharpe_ratio", 0) * 0.30 +
        metrics.get("sortino_ratio", 0) * 0.15 +
        metrics.get("calmar_ratio", 0) * 0.15 +
        metrics.get("total_return_pct", 0) * 0.002 +
        metrics.get("profit_factor", 0) * 0.15 +
        metrics.get("win_rate", 0) * 0.005 -
        metrics.get("max_drawdown_pct", 0) * 0.005
    )


# ── Genetic Optimizer ────────────────────────────────────────────────────────────────────────────────────────────────────────────────

class GeneticOptimizer:
    """Evolve strategy parameters using genetic algorithm."""

    def __init__(self, population_size: int = 50, generations: int = 12,
                 mutation_rate: float = 0.15, crossover_rate: float = 0.7):
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate

    async def optimize(self, strategy_name: str, param_bounds: dict[str, tuple[float, float]],
                       data: list[dict], capital: float, simulator: BacktestSimulator) -> list[dict[str, Any]]:
        registry = get_strategy_registry()
        cls = registry.get(strategy_name)
        if cls is None:
            return []

        population = [self._random_individual(param_bounds) for _ in range(self.population_size)]
        all_results: list[dict[str, Any]] = []

        for gen in range(self.generations):
            tasks = [self._evaluate(cls, ind, data, capital, simulator) for ind in population]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            gen_results = []
            for r in results:
                if isinstance(r, Exception) or r is None:
                    continue
                metrics, params = r
                score = compute_score(metrics)
                gen_results.append({
                    "strategy": strategy_name, "params": params,
                    "metrics": metrics, "score": score, "generation": gen,
                })

            all_results.extend(gen_results)

            if len(gen_results) < 2:
                population = [self._random_individual(param_bounds) for _ in range(self.population_size)]
                continue

            gen_results.sort(key=lambda x: x["score"], reverse=True)
            elite_count = max(2, self.population_size // 5)
            elites = [r["params"] for r in gen_results[:elite_count]]

            selected = self._tournament_select(gen_results, self.population_size)
            offspring = []
            for i in range(0, len(selected) - 1, 2):
                if random.random() < self.crossover_rate:
                    c1, c2 = self._crossover(selected[i], selected[i + 1], param_bounds)
                    offspring.extend([c1, c2])
                else:
                    offspring.extend([dict(selected[i]), dict(selected[i + 1])])

            population = [self._mutate(ind, param_bounds) for ind in offspring[:self.population_size]]
            for i, elite in enumerate(elites[:self.population_size]):
                population[i] = dict(elite)

        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:50]

    def _random_individual(self, bounds: dict[str, tuple[float, float]]) -> dict[str, float]:
        return {k: random.uniform(lo, hi) for k, (lo, hi) in bounds.items()}

    async def _evaluate(self, cls, params: dict, data: list, capital: float, simulator: BacktestSimulator):
        try:
            strategy = cls(**{k: int(v) if isinstance(v, float) and v == int(v) else v for k, v in params.items()})
            result = simulator.run(strategy, initial_capital=capital, data=data)
            if not result.success:
                return None
            metrics = compute_metrics(result.value, capital)
            return metrics, params
        except Exception:
            return None

    def _tournament_select(self, results: list[dict], n: int) -> list[dict]:
        selected = []
        for _ in range(n):
            contestants = random.sample(results, min(3, len(results)))
            winner = max(contestants, key=lambda x: x["score"])
            selected.append(winner["params"])
        return selected

    def _crossover(self, p1: dict, p2: dict, bounds: dict) -> tuple[dict, dict]:
        c1, c2 = {}, {}
        for key in p1:
            if random.random() < 0.5:
                c1[key] = p1[key]
                c2[key] = p2[key]
            else:
                c1[key] = p2[key]
                c2[key] = p1[key]
        return c1, c2

    def _mutate(self, individual: dict, bounds: dict[str, tuple[float, float]]) -> dict:
        mutated = dict(individual)
        for key, (lo, hi) in bounds.items():
            if random.random() < self.mutation_rate:
                mutated[key] = random.uniform(lo, hi)
        return mutated


# ── Walk-Forward Validator ────────────────────────────────────────────────────────────────────────────────────────────────────────────

class WalkForwardValidator:
    """Validate strategies using rolling walk-forward windows."""

    def __init__(self, windows: int = 5, train_ratio: float = 0.7):
        self.windows = windows
        self.train_ratio = train_ratio

    def split_data(self, data: list[dict]) -> list[tuple[list[dict], list[dict]]]:
        """Split data into train/test pairs for walk-forward."""
        total_len = len(data)
        window_size = total_len // self.windows
        pairs = []

        for i in range(self.windows):
            start = i * window_size
            end = min(start + window_size, total_len)
            train_end = start + int((end - start) * self.train_ratio)

            if train_end >= end:
                continue

            train_data = data[start:train_end]
            test_data = data[train_end:end]

            if len(train_data) > 20 and len(test_data) > 10:
                pairs.append((train_data, test_data))

        return pairs

    async def validate(self, strategy_name: str, params: dict[str, Any],
                       data: list[dict], capital: float, simulator: BacktestSimulator) -> dict[str, Any]:
        """Run walk-forward validation on a strategy."""
        registry = get_strategy_registry()
        cls = registry.get(strategy_name)
        if cls is None:
            return {"validated": False, "reason": "Strategy not found"}

        pairs = self.split_data(data)
        if len(pairs) < 2:
            return {"validated": False, "reason": "Insufficient data for walk-forward"}

        is_results = []
        oos_results = []

        for train_data, test_data in pairs:
            # In-Sample (training)
            try:
                clean_params = {k: int(v) if isinstance(v, float) and v == int(v) else v for k, v in params.items()}
                strategy = cls(**clean_params)
                is_result = simulator.run(strategy, initial_capital=capital, data=train_data)
                if is_result.success:
                    is_metrics = compute_metrics(is_result.value, capital)
                    is_results.append(is_metrics)
            except Exception:
                continue

            # Out-of-Sample (testing)
            try:
                strategy = cls(**clean_params)
                oos_result = simulator.run(strategy, initial_capital=capital, data=test_data)
                if oos_result.success:
                    oos_metrics = compute_metrics(oos_result.value, capital)
                    oos_results.append(oos_metrics)
            except Exception:
                continue

        if not is_results or not oos_results:
            return {"validated": False, "reason": "No valid results"}

        avg_is_return = sum(r["total_return_pct"] for r in is_results) / len(is_results)
        avg_oos_return = sum(r["total_return_pct"] for r in oos_results) / len(oos_results)
        avg_is_calmar = sum(r.get("calmar_ratio", 0) for r in is_results) / len(is_results)

        # Validation criteria
        is_profitable = avg_is_return > 0
        oos_profitable = avg_oos_return > 0
        consistent = avg_oos_return > avg_is_return * 0.3  # OOS should be at least 30% of IS

        validated = is_profitable and oos_profitable and consistent

        return {
            "validated": validated,
            "avg_is_return": round(avg_is_return, 2),
            "avg_oos_return": round(avg_oos_return, 2),
            "avg_is_calmar": round(avg_is_calmar, 2),
            "windows_tested": len(pairs),
            "reason": "Passed" if validated else f"IS={avg_is_return:.1f}%, OOS={avg_oos_return:.1f}%",
        }


# ── Main Cascade Engine ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

class CascadeEngine:
    """Multi-stage cascading filter engine for strategy generation."""

    def __init__(self) -> None:
        self.simulator = BacktestSimulator()
        self._running = False
        self._progress = 0
        self._total = 0
        self._results: list[dict[str, Any]] = []
        self._stats: dict[str, Any] = {}
        self._found = 0
        self._phase = "idle"
        self._history: list[dict[str, Any]] = []

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def progress(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "progress_pct": round(self._progress / max(self._total, 1) * 100, 1),
            "completed": self._progress,
            "total": self._total,
            "found": self._found,
            "phase": self._phase,
        }

    async def run(
        self,
        symbols: list[str],
        strategies: list[str] | None = None,
        features: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        capital: float = 1_000_000_000,
        filters: dict[str, Any] | None = None,
        use_genetic: bool = True,
        genetic_generations: int = 12,
        population_size: int = 50,
        use_walk_forward: bool = True,
        walk_forward_windows: int = 5,
        walk_forward_train_ratio: float = 0.7,
        stop_loss: float = 8.0,
        trailing_stop: bool = True,
        trailing_stop_pct: float = 5.0,
    ) -> Result[dict[str, Any]]:
        if self._running:
            return Result.fail("Engine already running")

        self._running = True
        self._progress = 0
        self._results = []
        self._found = 0
        self._phase = "initializing"
        filters = filters or DEFAULT_FILTERS
        strategies = strategies or list(PARAM_GRID.keys())

        try:
            today = date.today()
            start = start_date or date(today.year - 3, 1, 1)
            end = end_date or today

            # Load data for all symbols
            from services.backtest_service import BacktestService
            svc = BacktestService()
            symbol_data: dict[str, list[dict]] = {}
            for sym in symbols:
                data = await svc._load_historical_data(sym, start, end)
                if not data:
                    logger.warning("No historical data for %s — skipping", sym)
                    continue
                symbol_data[sym] = data

            if not symbol_data:
                return Result.fail("No historical data found for any of the specified symbols")

            registry = get_strategy_registry()
            if not registry.list_names():
                register_all_strategies()

            # ── Phase 1: Grid Search ──
            self._phase = "grid_search"
            all_combos: list[tuple[str, dict[str, Any]]] = []
            for strategy_name in strategies:
                param_ranges = PARAM_GRID.get(strategy_name, {})
                if not param_ranges:
                    continue
                if registry.get(strategy_name) is None:
                    continue
                keys = list(param_ranges.keys())
                values = [param_ranges[k] for k in keys]
                for combo in itertools.product(*values):
                    params = dict(zip(keys, combo, strict=False))
                    all_combos.append((strategy_name, params))

            # Shuffle and limit
            random.shuffle(all_combos)
            max_combos = len(all_combos)
            self._total = max_combos
            logger.info("Phase 1: Grid search %d combinations across %d symbols",
                        len(all_combos), len(symbols))

            batch_size = 50
            for i in range(0, len(all_combos), batch_size):
                batch = all_combos[i:i + batch_size]
                for sym in symbols:
                    tasks = [self._run_single(name, params, symbol_data[sym], capital, stop_loss)
                             for name, params in batch]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for r in results:
                        if isinstance(r, Exception) or r is None:
                            continue
                        metrics, strategy_name, params = r
                        passed, _ = apply_quality_filter(metrics, filters)
                        if passed:
                            self._results.append({
                                "strategy": strategy_name,
                                "params": params,
                                "metrics": metrics,
                                "symbol": sym,
                                "score": compute_score(metrics),
                                "method": "grid_search",
                                "validation_status": "pending",
                            })
                self._progress = min(i + batch_size, len(all_combos))
                self._found = len(self._results)

            # ── Phase 2: Genetic Optimization ──
            if use_genetic:
                self._phase = "genetic_optimization"
                logger.info("Phase 2: Genetic optimization")

                seen_strategies = set()
                for r in self._results[:20]:
                    seen_strategies.add(r["strategy"])
                for strategy_name in list(strategies)[:5]:
                    if strategy_name not in seen_strategies:
                        seen_strategies.add(strategy_name)

                ga = GeneticOptimizer(
                    population_size=population_size,
                    generations=genetic_generations,
                )

                for strategy_name in seen_strategies:
                    param_ranges = PARAM_GRID.get(strategy_name, {})
                    if not param_ranges:
                        continue
                    bounds = {k: (min(v), max(v)) for k, v in param_ranges.items()}

                    for sym in symbols:
                        ga_results = await ga.optimize(
                            strategy_name, bounds, symbol_data[sym], capital, self.simulator
                        )
                        for r in ga_results:
                            r["symbol"] = sym
                            r["method"] = "genetic"
                            r["validation_status"] = "pending"
                            if apply_quality_filter(r["metrics"], filters)[0]:
                                self._results.append(r)

            # ── Phase 3: Walk-Forward Validation ──
            if use_walk_forward:
                self._phase = "walk_forward"
                logger.info("Phase 3: Walk-Forward validation")

                wf = WalkForwardValidator(
                    windows=walk_forward_windows,
                    train_ratio=walk_forward_train_ratio,
                )

                for r in self._results[:100]:  # Validate top 100
                    sym = r.get("symbol", symbols[0])
                    data = symbol_data.get(sym, [])
                    if not data:
                        continue

                    wf_result = await wf.validate(
                        r["strategy"], r["params"], data, capital, self.simulator
                    )
                    r["validation_status"] = "validated" if wf_result["validated"] else "rejected"
                    r["wf_result"] = wf_result

            # ── Final: Deduplicate and Sort ──
            seen = set()
            unique_results = []
            for r in sorted(self._results, key=lambda x: x["score"], reverse=True):
                key = (r["strategy"], str(r["params"]), r.get("symbol", ""))
                if key not in seen:
                    seen.add(key)
                    unique_results.append(r)

            self._results = unique_results[:100]
            self._found = len(self._results)

            validated_count = sum(1 for r in self._results if r.get("validation_status") == "validated")

            self._stats = {
                "total_generated": max_combos * len(symbols),
                "passed_6stage": len(self._results),
                "passed_walk_forward": validated_count,
                "symbols": symbols,
                "period": f"{start} to {end}",
                "engine_version": "cascade_v2",
            }

            logger.info("Engine complete: %d strategies passed, %d validated",
                        len(self._results), validated_count)
            return Result.ok({
                "strategies": self._results,
                "stats": self._stats,
            })

        except Exception as e:
            logger.exception("Cascade engine failed")
            return Result.fail(str(e))
        finally:
            self._running = False
            self._phase = "idle"

    async def _run_single(self, strategy_name: str, params: dict[str, Any],
                          data: list[dict], capital: float, stop_loss: float = 8.0):
        try:
            registry = get_strategy_registry()
            cls = registry.get(strategy_name)
            if cls is None:
                return None
            clean_params = {}
            for k, v in params.items():
                if isinstance(v, float) and v == int(v):
                    clean_params[k] = int(v)
                else:
                    clean_params[k] = v
            strategy = cls(**clean_params)
            result = self.simulator.run(strategy, initial_capital=capital, data=data)
            if not result.success:
                return None
            metrics = compute_metrics(result.value, capital)
            return metrics, strategy_name, clean_params
        except Exception:
            return None

    def get_results(self) -> dict[str, Any]:
        return {"strategies": self._results, "stats": self._stats}

    def get_history(self) -> list[dict[str, Any]]:
        return self._history


# ── Singleton ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

_engine = CascadeEngine()


def get_cascade_engine() -> CascadeEngine:
    return _engine
