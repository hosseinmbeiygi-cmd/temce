from __future__ import annotations

from typing import Any

from backtesting.engine.broker import Broker
from backtesting.engine.portfolio import PortfolioManager
from backtesting.strategies.base import BaseStrategy
from backtesting.types import BacktestResult, EquityPoint, FillEvent
from core.logging import get_logger
from core.result import Result
from core.time import now_tehran

logger = get_logger(__name__)


class BacktestSimulator:
    def __init__(self, broker: Broker | None = None, portfolio: PortfolioManager | None = None) -> None:
        self.broker = broker or Broker()
        self.portfolio = portfolio or PortfolioManager()

    async def run(
        self, strategy: BaseStrategy, initial_capital: float = 1_000_000_000, data: list[dict[str, Any]] | None = None
    ) -> Result[BacktestResult]:
        try:
            self.portfolio.reset(initial_capital)
            strategy.reset()
            equity_curve: list[EquityPoint] = []
            all_fills: list[FillEvent] = []

            for bar in data or []:
                orders = strategy.on_bar(bar)
                for order in orders:
                    fill = await self.broker.submit_order(order)
                    if fill:
                        await self.portfolio.update_fill(fill)
                        all_fills.append(fill)

                if "prices" in bar:
                    await self.portfolio.mark_to_market(bar["prices"])

                equity_curve.append(
                    EquityPoint(
                        timestamp=bar.get("timestamp", now_tehran()),
                        nav=self.portfolio.get_nav(),
                        cash=self.portfolio.get_cash(),
                        positions_value=self.portfolio.get_positions_value(),
                    )
                )

            result = BacktestResult(
                strategy_name=strategy.__class__.__name__,
                initial_capital=initial_capital,
                final_capital=self.portfolio.get_nav(),
                total_return=self.portfolio.get_nav() - initial_capital,
                total_return_pct=((self.portfolio.get_nav() / initial_capital) - 1) * 100,
                total_trades=len(all_fills),
                equity_curve=equity_curve,
                trades=all_fills,
            )
            return Result.ok(result)
        except Exception as e:
            logger.error("Backtest failed: %s", e)
            return Result.fail(str(e))
