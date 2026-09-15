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


# ── Strategy Parameter Ranges ──────────────────────────────────────────────────────────────────────────────────────────────────────

STRATEGY_PARAM_RANGES: dict[str, dict[str, list[Any]]] = {
    "moving_average_cross": {
        "fast_period": [3, 5, 7, 10, 12, 15],
        "slow_period": [15, 20, 25, 30, 40, 50, 60],
    },
    "momentum": {
        "lookback": [5, 10, 15, 20, 25, 30, 40],
        "threshold_pct": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0],
    },
    "breakout": {
        "lookback": [10, 15, 20, 25, 30, 40],
        "breakout_pct": [0.0, 0.5, 1.0, 1.5, 2.0],
    },
}


# ── 6-Stage Filter Thresholds ─────────────────────────────────────────────────────────────────────────────────────────────────────

DEFAULT_FILTERS = {
    "stage1_min_return": 5.0,
    "stage2_max_drawdown": 25.0,
    "stage3_min_sharpe": 0.5,
    "stage4_min_win_rate": 40.0,
    "stage5_min_trades": 5,
    "stage6_min_profit_factor": 1.2,
}


def _compute_enhanced_metrics(result: Any, initial_capital: float) -> dict[str, Any]:
    """Compute comprehensive metrics from backtest result."""
    equity = [ep.nav for ep in result.equity_curve]
    trades = result.trades

    if len(equity) < 2:
        return {
            "total_return_pct": 0,
            "sharpe_ratio": 0,
            "max_drawdown_pct": 100,
            "win_rate": 0,
            "total_trades": 0,
            "profit_factor": 0,
            "sortino_ratio": 0,
            "calmar_ratio": 0,
            "annualized_return_pct": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "avg_win": 0,
            "avg_loss": 0,
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
    downside_vol = math.sqrt(sum(r**2 for r in downside_returns) / len(downside_returns)) if downside_returns else 1
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
        "avg_win": round(avg_win, 0),
        "avg_loss": round(avg_loss, 0),
    }


def _apply_6stage_filter(metrics: dict[str, Any], filters: dict[str, Any]) -> tuple[bool, str]:
    if metrics["total_return_pct"] < filters["stage1_min_return"]:
        return False, f"Stage 1: Return {metrics['total_return_pct']:.1f}% < {filters['stage1_min_return']}%"
    if metrics["max_drawdown_pct"] > filters["stage2_max_drawdown"]:
        return False, f"Stage 2: Drawdown {metrics['max_drawdown_pct']:.1f}% > {filters['stage2_max_drawdown']}%"
    if metrics["sharpe_ratio"] < filters["stage3_min_sharpe"]:
        return False, f"Stage 3: Sharpe {metrics['sharpe_ratio']:.2f} < {filters['stage3_min_sharpe']}"
    if metrics["win_rate"] < filters["stage4_min_win_rate"]:
        return False, f"Stage 4: Win rate {metrics['win_rate']:.1f}% < {filters['stage4_min_win_rate']}%"
    if metrics["total_trades"] < filters["stage5_min_trades"]:
        return False, f"Stage 5: Trades {metrics['total_trades']} < {filters['stage5_min_trades']}"
    if metrics["profit_factor"] < filters["stage6_min_profit_factor"]:
        return False, f"Stage 6: Profit factor {metrics['profit_factor']:.2f} < {filters['stage6_min_profit_factor']}"
    return True, ""


def _compute_combined_score(metrics: dict[str, Any]) -> float:
    """Weighted combined score for ranking strategies."""
    return (
        metrics.get("sharpe_ratio", 0) * 0.30
        + metrics.get("sortino_ratio", 0) * 0.15
        + metrics.get("calmar_ratio", 0) * 0.15
        + metrics.get("total_return_pct", 0) * 0.002
        + metrics.get("profit_factor", 0) * 0.15
        + metrics.get("win_rate", 0) * 0.005
        - metrics.get("max_drawdown_pct", 0) * 0.005
    )


# ── Genetic Algorithm Optimizer ────────────────────────────────────────────────────────────────────────────────────────────────────


class GeneticOptimizer:
    """Evolve strategy parameters using genetic algorithm."""

    def __init__(
        self,
        population_size: int = 30,
        generations: int = 10,
        mutation_rate: float = 0.15,
        crossover_rate: float = 0.7,
    ) -> None:
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self._simulator: BacktestSimulator | None = None

    async def optimize(
        self,
        strategy_name: str,
        param_bounds: dict[str, tuple[float, float]],
        data: list[dict],
        capital: float,
        simulator: BacktestSimulator,
    ) -> list[dict[str, Any]]:
        """Run genetic optimization and return top results."""
        self._simulator = simulator
        registry = get_strategy_registry()
        cls = registry.get(strategy_name)
        if cls is None:
            return []

        # Initialize population
        population = [self._random_individual(param_bounds) for _ in range(self.population_size)]
        all_results: list[dict[str, Any]] = []

        for gen in range(self.generations):
            # Evaluate fitness — run in thread pool
            tasks = [asyncio.to_thread(self._evaluate_sync, cls, ind, data, capital) for ind in population]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            gen_results = []
            for r in results:
                if isinstance(r, Exception) or r is None:
                    continue
                metrics, params = r
                passed, _ = _apply_6stage_filter(metrics, DEFAULT_FILTERS)
                score = _compute_combined_score(metrics)
                gen_results.append(
                    {
                        "strategy": strategy_name,
                        "params": params,
                        "metrics": metrics,
                        "score": score,
                        "generation": gen,
                    }
                )

            all_results.extend(gen_results)

            # Selection + crossover + mutation
            if len(gen_results) < 2:
                population = [self._random_individual(param_bounds) for _ in range(self.population_size)]
                continue

            gen_results.sort(key=lambda x: x["score"], reverse=True)
            elite_count = max(2, self.population_size // 5)
            elites = [r["params"] for r in gen_results[:elite_count]]

            # Tournament selection
            selected = self._tournament_select(gen_results, self.population_size)

            # Crossover
            offspring = []
            for i in range(0, len(selected) - 1, 2):
                if random.random() < self.crossover_rate:
                    c1, c2 = self._crossover(selected[i], selected[i + 1], param_bounds)
                    offspring.extend([c1, c2])
                else:
                    offspring.extend([dict(selected[i]), dict(selected[i + 1])])

            # Mutation
            population = [self._mutate(ind, param_bounds) for ind in offspring[: self.population_size]]
            # Keep elites
            for i, elite in enumerate(elites[: self.population_size]):
                population[i] = dict(elite)

        # Sort all results by score
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:20]

    def _random_individual(self, bounds: dict[str, tuple[float, float]]) -> dict[str, float]:
        return {k: random.uniform(lo, hi) for k, (lo, hi) in bounds.items()}

    async def _evaluate(self, cls, params: dict, data: list, capital: float, simulator: BacktestSimulator):
        return self._evaluate_sync(cls, params, data, capital)

    def _evaluate_sync(self, cls, params: dict, data: list, capital: float):
        try:
            strategy = cls(**{k: int(v) if isinstance(v, float) and v == int(v) else v for k, v in params.items()})
            result = self._simulator.run(strategy, initial_capital=capital, data=data)
            if not result.success:
                return None
            metrics = _compute_enhanced_metrics(result.value, capital)
            return metrics, params
        except Exception as e:
            logger.warning("Genetic evaluation failed for %s: %s", cls.__name__, e)
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


# ── Main Strategy Generator ───────────────────────────────────────────────────────────────────────────────────────────────────────


class StrategyGenerator:
    """Auto-generate, optimize, and filter trading strategies."""

    def __init__(self) -> None:
        self.simulator = BacktestSimulator()
        self._running = False
        self._progress = 0
        self._total = 0
        self._results: list[dict[str, Any]] = []
        self._stats: dict[str, Any] = {}
        self._history: list[dict[str, Any]] = []

    async def _load_all_symbols(self) -> list[str]:
        """Load all symbols with available data from the database."""
        try:
            from sqlalchemy import text

            from core.database import async_session_factory

            if async_session_factory is None:
                return ["فولاد"]

            async with async_session_factory() as session:
                result = await session.execute(
                    text("""
                    SELECT symbol
                    FROM (
                        SELECT symbol
                        FROM brsapi_historical_daily
                        WHERE price_close IS NOT NULL AND price_close > 0
                        UNION ALL
                        SELECT symbol
                        FROM quotes
                        WHERE price_close IS NOT NULL AND price_close > 0
                    ) combined
                    GROUP BY symbol
                    HAVING COUNT(*) > 10
                    ORDER BY COUNT(*) DESC
                """)
                )
                rows = result.fetchall()
                symbols = [row[0] for row in rows]
                if symbols:
                    logger.info("Loaded %d symbols from database", len(symbols))
                    return symbols
        except Exception as e:
            logger.warning("Failed to load symbols from database: %s", e)

        return ["فولاد"]

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

    async def generate(
        self,
        symbols: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        capital: float = 1_000_000_000,
        max_combinations: int = 5000,
        use_genetic: bool = True,
        genetic_generations: int = 8,
        filters: dict[str, Any] | None = None,
    ) -> Result[dict[str, Any]]:
        if self._running:
            return Result.fail("Strategy generation already in progress")

        self._running = True
        self._progress = 0
        self._results = []
        self._phase = "initializing"
        self._found = 0
        filters = filters or DEFAULT_FILTERS
        if not symbols:
            symbols = await self._load_all_symbols()

        try:
            today = date.today()
            start = start_date or date(today.year - 2, 1, 1)
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
            for strategy_name, param_ranges in STRATEGY_PARAM_RANGES.items():
                cls = registry.get(strategy_name)
                if cls is None:
                    continue
                keys = list(param_ranges.keys())
                values = [param_ranges[k] for k in keys]
                for combo in itertools.product(*values):
                    params = dict(zip(keys, combo, strict=False))
                    all_combos.append((strategy_name, params))

            if len(all_combos) > max_combinations:
                random.shuffle(all_combos)
                all_combos = all_combos[:max_combinations]

            self._total = len(all_combos) * len(symbols)
            logger.info(
                "Phase 1: Grid search %d combinations × %d symbols = %d total runs",
                len(all_combos),
                len(symbols),
                self._total,
            )

            # Build all (combo, symbol) work items
            work_items = [
                (strategy_name, params, sym, symbol_data[sym], capital)
                for strategy_name, params in all_combos
                for sym in symbols
                if sym in symbol_data
            ]

            # Run in thread pool for true concurrency — batch to avoid event loop starvation
            import concurrent.futures

            executor = concurrent.futures.ThreadPoolExecutor(max_workers=16)
            completed = 0
            all_task_results = []

            batch_size = 50
            for batch_start in range(0, len(work_items), batch_size):
                batch = work_items[batch_start : batch_start + batch_size]
                loop = asyncio.get_event_loop()
                futures = [loop.run_in_executor(executor, self._run_single_sync, *item) for item in batch]
                batch_results = await asyncio.gather(*futures, return_exceptions=True)
                all_task_results.extend(batch_results)
                completed += len(batch)
                self._progress = completed
                self._found = len(self._results)

            executor.shutdown(wait=False)
            results = all_task_results
            for r in results:
                if isinstance(r, Exception) or r is None:
                    continue
                metrics, strategy_name, params, sym = r
                passed, _ = _apply_6stage_filter(metrics, filters)
                if passed:
                    self._results.append(
                        {
                            "strategy": strategy_name,
                            "params": params,
                            "metrics": metrics,
                            "symbol": sym,
                            "score": _compute_combined_score(metrics),
                            "method": "grid_search",
                        }
                    )
            self._progress = self._total
            self._found = len(self._results)

            # ── Phase 2: Genetic Optimization (top strategies) ──
            if use_genetic:
                self._phase = "genetic_optimization"
                logger.info("Phase 2: Genetic optimization on top strategies")

                # Get unique strategy names from grid search results
                seen_strategies = set()
                for r in self._results[:10]:
                    seen_strategies.add(r["strategy"])

                # Also optimize strategies that performed well
                for strategy_name in list(STRATEGY_PARAM_RANGES.keys())[:5]:
                    if strategy_name not in seen_strategies:
                        seen_strategies.add(strategy_name)

                ga = GeneticOptimizer(
                    population_size=20,
                    generations=genetic_generations,
                    mutation_rate=0.15,
                )

                # Build GA work items
                ga_work = []
                for strategy_name in seen_strategies:
                    param_ranges = STRATEGY_PARAM_RANGES.get(strategy_name, {})
                    if not param_ranges:
                        continue
                    bounds = {k: (min(v), max(v)) for k, v in param_ranges.items()}
                    for sym in symbols:
                        if sym in symbol_data:
                            ga_work.append((strategy_name, bounds, symbol_data[sym], capital, sym))

                async def _run_ga(item):
                    strategy_name, bounds, data, cap, sym = item
                    ga_results = await ga.optimize(strategy_name, bounds, data, cap, self.simulator)
                    for r in ga_results:
                        r["symbol"] = sym
                        r["method"] = "genetic"
                    return ga_results

                ga_tasks = [_run_ga(item) for item in ga_work]
                ga_all = await asyncio.gather(*ga_tasks, return_exceptions=True)
                for r in ga_all:
                    if isinstance(r, Exception) or not isinstance(r, list):
                        continue
                    self._results.extend(r)

            # Deduplicate and sort
            seen = set()
            unique_results = []
            for r in sorted(self._results, key=lambda x: x["score"], reverse=True):
                key = (r["strategy"], str(r["params"]), r.get("symbol", ""))
                if key not in seen:
                    seen.add(key)
                    unique_results.append(r)

            self._results = unique_results[:50]
            self._found = len(self._results)

            self._stats = {
                "total_combinations": len(all_combos),
                "passed_filter": len(self._results),
                "symbols": symbols,
                "period": f"{start} to {end}",
                "filters": filters,
                "genetic_used": use_genetic,
            }

            # Save to history
            self._history.append(
                {
                    "timestamp": date.today().isoformat(),
                    "stats": self._stats,
                    "top_strategies": [
                        {
                            "strategy": r["strategy"],
                            "params": r["params"],
                            "metrics": r["metrics"],
                            "symbol": r.get("symbol", ""),
                        }
                        for r in self._results[:10]
                    ],
                }
            )

            logger.info("Generation complete: %d strategies passed filter", len(self._results))
            return Result.ok(
                {
                    "strategies": self._results,
                    "stats": self._stats,
                }
            )

        except Exception as e:
            logger.exception("Strategy generation failed")
            return Result.fail(str(e))
        finally:
            self._running = False
            self._phase = "idle"

    def _run_single_sync(
        self,
        strategy_name: str,
        params: dict[str, Any],
        sym: str,
        data: list[dict],
        capital: float,
        timeout: float = 15.0,
    ) -> tuple[dict[str, Any], str, dict[str, Any], str] | None:
        """Synchronous single run — executed in thread pool."""
        import concurrent.futures

        _executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:

            def _run():
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
                clean_params["instrument_id"] = sym
                strategy = cls(**clean_params)
                sim = BacktestSimulator()
                result = sim.run(strategy, initial_capital=capital, data=data)
                if not result.success:
                    return None
                metrics = _compute_enhanced_metrics(result.value, capital)
                return metrics, strategy_name, clean_params, sym

            future = _executor.submit(_run)
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            logger.warning("Grid search TIMEOUT for %s %s on %s", strategy_name, params, sym)
            return None
        except Exception as e:
            logger.warning("Grid search failed for %s (%s): %s", strategy_name, params, e)
            return None
        finally:
            _executor.shutdown(wait=False)

    async def _run_single(
        self, strategy_name: str, params: dict[str, Any], data: list[dict], capital: float
    ) -> tuple[dict[str, Any], str, dict[str, Any]] | None:
        try:
            registry = get_strategy_registry()
            cls = registry.get(strategy_name)
            if cls is None:
                return None
            # Convert float params to int where needed
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
            metrics = _compute_enhanced_metrics(result.value, capital)
            return metrics, strategy_name, clean_params
        except Exception as e:
            logger.warning("Grid search failed for %s (%s): %s", strategy_name, params, e)
            return None

    def get_results(self) -> dict[str, Any]:
        return {
            "strategies": self._results,
            "stats": self._stats,
        }

    def get_history(self) -> list[dict[str, Any]]:
        return self._history

    def export_csv(self) -> str:
        """Export results as CSV string."""
        if not self._results:
            return ""
        headers = [
            "rank",
            "strategy",
            "symbol",
            "method",
            "return_pct",
            "sharpe",
            "sortino",
            "calmar",
            "max_dd",
            "win_rate",
            "profit_factor",
            "trades",
            "params",
        ]
        rows = [",".join(headers)]
        for i, r in enumerate(self._results):
            m = r["metrics"]
            row = [
                str(i + 1),
                r["strategy"],
                r.get("symbol", ""),
                r.get("method", ""),
                str(m.get("total_return_pct", 0)),
                str(m.get("sharpe_ratio", 0)),
                str(m.get("sortino_ratio", 0)),
                str(m.get("calmar_ratio", 0)),
                str(m.get("max_drawdown_pct", 0)),
                str(m.get("win_rate", 0)),
                str(m.get("profit_factor", 0)),
                str(m.get("total_trades", 0)),
                str(r["params"]),
            ]
            rows.append(",".join(row))
        return "\n".join(rows)


# Global singleton
_generator = StrategyGenerator()


def get_strategy_generator() -> StrategyGenerator:
    return _generator
