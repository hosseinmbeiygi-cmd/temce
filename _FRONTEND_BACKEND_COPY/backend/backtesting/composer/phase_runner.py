"""Phase Runner: executes strategy combinations in batches with pre-test filtering."""

from __future__ import annotations

import asyncio
from typing import Any

from backtesting.composer.pre_filter import PreTestFilter
from backtesting.composer.quality_filter import QualityFilter
from backtesting.composer.strategy_composer import StrategyBlueprint
from backtesting.engine.simulator import BacktestSimulator
from backtesting.strategies.registry import get_strategy_registry, register_all_strategies
from core.logging import get_logger

logger = get_logger(__name__)


# ── Mapping: indicator conditions → strategy parameters ───────────────────────────

INDICATOR_TO_STRATEGY: dict[str, str] = {
    "rsi": "rsi_reversion",
    "macd": "moving_average_cross",
    "ema_crossover": "moving_average_cross",
    "stochastic": "rsi_reversion",
    "williams_r": "rsi_reversion",
    "cci": "rsi_reversion",
    "adx": "momentum",
    "half_trend": "half_trend",
    "parabolic_sar": "breakout",
    "ichimoku": "moving_average_cross",
    "squeeze_momentum": "squeeze_momentum",
    "atr": "volatility_breakout",
    "bollinger_bw": "volatility_breakout",
    "keltner_position": "volatility_breakout",
    "compression_ratio": "volatility_breakout",
    "relative_volume": "momentum",
    "obv": "momentum",
    "vwap": "moving_average_cross",
    "supply_dryness": "momentum",
    "clv": "momentum",
    "recovery_ratio": "momentum",
    "support_resistance": "support_resistance",
    "breakout_quality": "breakout",
    "relative_strength": "momentum",
    "buyer_power": "momentum",
    "net_real_flow": "momentum",
    "supply_absorption": "momentum",
    "smart_money_phase": "phase",
}


def _blueprint_to_strategy_params(blueprint: StrategyBlueprint) -> dict[str, Any]:
    """Convert a StrategyBlueprint to strategy constructor params."""
    params: dict[str, Any] = {}

    # Entry indicator params
    for k, v in blueprint.entry_params.items():
        params[k] = v

    # Map entry condition to strategy-specific params
    entry_cond = blueprint.entry_condition
    exit_cond = blueprint.exit_condition

    if entry_cond == "oversold":
        params.setdefault("oversold", 30.0)
    if entry_cond == "overbought":
        params.setdefault("overbought", 70.0)
    if exit_cond == "overbought":
        params.setdefault("overbought", 70.0)
    if exit_cond == "oversold":
        params.setdefault("oversold", 30.0)

    # EMA crossover params
    if blueprint.entry_indicator == "ema_crossover":
        params["fast_period"] = params.pop("fast", 10)
        params["slow_period"] = params.pop("slow", 30)
    if blueprint.exit_indicator == "ema_crossover":
        params["fast_period"] = params.pop("fast", 10)
        params["slow_period"] = params.pop("slow", 30)

    return params


def _get_strategy_name_for_indicator(indicator_id: str) -> str:
    """Map an indicator ID to the best strategy type to use."""
    return INDICATOR_TO_STRATEGY.get(indicator_id, "momentum")


class PhaseRunner:
    """Runs strategy combinations in phases with pre-test filtering.

    Each phase processes a batch of combinations, running backtests
    and storing results that pass the quality filter.
    """

    def __init__(
        self,
        pre_filter: PreTestFilter | None = None,
        quality_filter: QualityFilter | None = None,
    ) -> None:
        self.pre_filter = pre_filter or PreTestFilter()
        self.quality_filter = quality_filter or QualityFilter()
        self._running = False
        self._cancel_event = asyncio.Event()
        self._progress: dict[str, Any] = {}

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def progress(self) -> dict[str, Any]:
        return self._progress

    async def run_batch(
        self,
        blueprints: list[StrategyBlueprint],
        data: list[dict[str, Any]],
        capital: float = 1_000_000_000,
        symbol: str = "",
        max_workers: int = 4,
    ) -> list[dict[str, Any]]:
        """Run a batch of blueprints through backtest + quality filter.

        Returns list of results that passed the quality filter.
        """
        self._running = True
        self._cancel_event.clear()
        self._progress = {"phase": "running", "total": len(blueprints), "tested": 0, "passed": 0}

        # Step 1: Pre-test filter
        valid_blueprints = self.pre_filter.filter_batch(blueprints)
        len(blueprints) - len(valid_blueprints)
        logger.info(
            "Pre-test filter: %d → %d (%.0f%% filtered out)",
            len(blueprints),
            len(valid_blueprints),
            (1 - len(valid_blueprints) / max(1, len(blueprints))) * 100,
        )

        # Step 2: Run backtests
        results: list[dict[str, Any]] = []
        semaphore = asyncio.Semaphore(max_workers)

        async def _run_one(bp: StrategyBlueprint) -> dict[str, Any] | None:
            if self._cancel_event.is_set():
                return None
            async with semaphore:
                return await self._execute_single(bp, data, capital, symbol)

        tasks = [_run_one(bp) for bp in valid_blueprints]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in batch_results:
            if isinstance(r, Exception) or r is None:
                continue
            # Step 3: Quality filter
            passed, reason = self.quality_filter.should_keep(r["metrics"])
            if passed:
                r["score"] = self.quality_filter.compute_score(r["metrics"])
                results.append(r)
                self._progress["passed"] = self._progress.get("passed", 0) + 1
            self._progress["tested"] = self._progress.get("tested", 0) + 1

        self._running = False
        self._progress["phase"] = "completed"

        return results

    def cancel(self) -> None:
        self._cancel_event.set()

    async def _execute_single(
        self,
        blueprint: StrategyBlueprint,
        data: list[dict[str, Any]],
        capital: float,
        symbol: str,
    ) -> dict[str, Any]:
        """Execute a single blueprint and return metrics."""
        registry = get_strategy_registry()
        if not registry.list_names():
            register_all_strategies()

        strategy_name = _get_strategy_name_for_indicator(blueprint.entry_indicator)
        strategy_cls = registry.get(strategy_name)

        if strategy_cls is None:
            return {"metrics": {"total_return_pct": 0}, "blueprint": blueprint.to_dict()}

        params = _blueprint_to_strategy_params(blueprint)
        params["instrument_id"] = symbol
        params["sizing_method"] = blueprint.sizing_method
        params["sizing_value"] = blueprint.sizing_value

        try:
            strategy = strategy_cls(**params)
            simulator = BacktestSimulator()
            result = simulator.run(strategy, initial_capital=capital, data=data)

            if not result.success:
                return {"metrics": {"total_return_pct": 0}, "blueprint": blueprint.to_dict()}

            bt_result = result.value
            metrics = self._compute_metrics(bt_result, capital)

            return {
                "blueprint": blueprint.to_dict(),
                "metrics": metrics,
                "symbol": symbol,
                "strategy_type": strategy_name,
            }
        except Exception as e:
            return {"metrics": {"total_return_pct": 0}, "blueprint": blueprint.to_dict(), "error": str(e)}

    def _compute_metrics(self, result: Any, initial_capital: float) -> dict[str, Any]:
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
            }

        total_return = ((equity[-1] / initial_capital) - 1) * 100
        trading_days = len(equity)
        years = trading_days / 252
        ann_return = ((equity[-1] / initial_capital) ** (1 / max(years, 0.01)) - 1) * 100

        returns = [(equity[i] / equity[i - 1]) - 1 for i in range(1, len(equity))]
        avg_r = sum(returns) / len(returns) if returns else 0
        std_r = (sum((r - avg_r) ** 2 for r in returns) / len(returns)) ** 0.5 if returns else 1
        sharpe = (avg_r / std_r) * (252**0.5) if std_r > 0 else 0

        peak = equity[0]
        max_dd = 0.0
        for nav in equity:
            if nav > peak:
                peak = nav
            dd = (peak - nav) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

        # Pair trades for PnL
        wins: list[float] = []
        losses: list[float] = []
        open_buys: dict[str, list[tuple[float, int]]] = {}
        for t in trades:
            key = getattr(t, "instrument_id", "") or "default"
            if str(getattr(t, "side", "")) == "buy":
                open_buys.setdefault(key, []).append((t.price, t.quantity))
            elif str(getattr(t, "side", "")) == "sell":
                buys = open_buys.get(key, [])
                if buys:
                    bp, bq = buys.pop(0)
                    pnl = (t.price - bp) * min(bq, t.quantity)
                    if pnl > 0:
                        wins.append(pnl)
                    else:
                        losses.append(abs(pnl))

        win_rate = (len(wins) / (len(wins) + len(losses)) * 100) if (wins or losses) else 0
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 1
        pf = avg_win / avg_loss if avg_loss > 0 else 0

        downside = [r for r in returns if r < 0]
        down_vol = (sum(r**2 for r in downside) / len(downside)) ** 0.5 if downside else 1
        sortino = (avg_r / down_vol) * (252**0.5) if down_vol > 0 else 0
        calmar = ann_return / (max_dd * 100) if max_dd > 0 else 0

        return {
            "total_return_pct": round(total_return, 2),
            "annualized_return_pct": round(ann_return, 2),
            "sharpe_ratio": round(sharpe, 2),
            "sortino_ratio": round(sortino, 2),
            "calmar_ratio": round(calmar, 2),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "win_rate": round(win_rate, 1),
            "total_trades": len(trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "profit_factor": round(pf, 2),
            "avg_win": round(avg_win, 0),
            "avg_loss": round(avg_loss, 0),
        }
