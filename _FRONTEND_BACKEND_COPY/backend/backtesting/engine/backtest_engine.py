from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backtesting.engine.cash_manager import CashManager
from backtesting.engine.clock import Clock
from backtesting.engine.commission import CommissionModel
from backtesting.engine.event_loop import EventLoop
from backtesting.engine.execution_simulator import ExecutionSimulator
from backtesting.engine.portfolio_accounting import PortfolioAccounting
from backtesting.engine.position_manager import PositionManager
from backtesting.engine.slippage import SlippageModel
from backtesting.strategies.base import BaseStrategy
from backtesting.types import BacktestResult, EquityPoint
from core.logging import get_logger

logger = get_logger(__name__)


class BacktestEngine:
    def __init__(
        self,
        initial_capital: float = 1_000_000_000,
        commission: CommissionModel | None = None,
        slippage: SlippageModel | None = None,
    ) -> None:
        self.initial_capital = initial_capital
        self.commission = commission or CommissionModel()
        self.slippage = slippage or SlippageModel()
        self.clock = Clock()
        self.event_loop = EventLoop(self.clock)
        self.cash_manager = CashManager(initial_capital)
        self.position_manager = PositionManager()
        self.execution = ExecutionSimulator(self.slippage, self.commission)
        self.accounting = PortfolioAccounting(self.cash_manager, self.position_manager)

    def reset(self) -> None:
        self.clock.reset()
        self.cash_manager.reset(self.initial_capital)
        self.position_manager.reset()
        self.accounting.reset()
        self.event_loop.reset()

    async def run(self, strategy: BaseStrategy, data: list[dict[str, Any]]) -> BacktestResult:
        self.reset()
        strategy.reset()
        equity_curve: list[EquityPoint] = []
        all_fills: list[Any] = []

        for bar in data:
            orders = strategy.on_bar(bar) if hasattr(strategy, "on_bar") else []
            for order in orders:
                fill = self.execution.execute(order, self.cash_manager)
                if fill:
                    self.accounting.apply_fill(fill)
                    all_fills.append(fill)
            if "prices" in bar:
                self.accounting.mark_to_market(bar["prices"])
            equity_curve.append(
                EquityPoint(
                    timestamp=bar.get("timestamp", datetime.now(UTC)),
                    nav=self.accounting.get_nav(),
                    cash=self.cash_manager.cash,
                    positions_value=self.position_manager.get_total_value(bar.get("prices", {})),
                )
            )

        result = BacktestResult(
            strategy_name=strategy.name,
            initial_capital=self.initial_capital,
            final_capital=self.accounting.get_nav(),
            total_return=self.accounting.get_nav() - self.initial_capital,
            total_return_pct=((self.accounting.get_nav() / self.initial_capital) - 1) * 100,
            total_trades=len(all_fills),
            equity_curve=equity_curve,
            trades=all_fills,
        )
        return result
