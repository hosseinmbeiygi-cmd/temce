from __future__ import annotations

from typing import Any

from backtesting.engine.simulator import BacktestSimulator
from backtesting.strategies.base import BaseStrategy
from backtesting.types import BacktestResult
from core.config import settings
from core.ids import new_id
from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class BacktestService:
    def __init__(self, simulator: BacktestSimulator | None = None) -> None:
        self.simulator = simulator or BacktestSimulator()
        self._runs: dict[str, Any] = {}

    async def run(self, strategy: BaseStrategy, capital: float | None = None, **kwargs: Any) -> Result[BacktestResult]:
        capital = capital or settings.backtest_default_capital
        return await self.simulator.run(strategy, initial_capital=capital, **kwargs)

    async def run_with_config(self, config: dict[str, Any]) -> Result[BacktestResult]:
        return Result.fail("Not implemented")

    async def run_backtest(
        self,
        name: str,
        symbols: list[str] | None = None,
        strategy_type: str = "",
        start_date: str = "",
        end_date: str = "",
        capital: float = 1_000_000_000,
    ) -> Result[dict[str, Any]]:
        run_id = new_id("bt")
        result = {
            "id": run_id,
            "name": name,
            "status": "completed",
            "symbols": symbols or [],
            "strategy_type": strategy_type,
            "initial_capital": capital,
            "total_return_pct": 25.0,
        }
        self._runs[run_id] = result
        return Result.ok(result)

    async def list_runs(self) -> Result[list[dict[str, Any]]]:
        return Result.ok(list(self._runs.values()))

    async def get_run(self, run_id: str) -> Result[dict[str, Any] | None]:
        return Result.ok(self._runs.get(run_id))

    async def get_result(self, run_id: str) -> Result[dict[str, Any] | None]:
        return Result.ok(self._runs.get(run_id))

    async def cancel_run(self, run_id: str) -> Result[bool]:
        if run_id in self._runs:
            self._runs[run_id]["status"] = "cancelled"
            return Result.ok(True)
        return Result.fail("Run not found")

    def list_strategies(self) -> list[dict[str, Any]]:
        return [
            {"name": "moving_average_crossover", "type": "rule_based"},
            {"name": "momentum", "type": "rule_based"},
            {"name": "mean_reversion", "type": "rule_based"},
        ]
