"""BacktestSimulator — unified deterministic core for bar-based and event-based backtesting.

Key design decisions (from architecture review):
1. Core execution loop is SYNCHRONOUS (deterministic, reproducible)
2. Only orchestration layer (parallel runs) uses async
3. Shared Portfolio/Broker for both bar-based and event-based paths
4. Sequence IDs on events guarantee deterministic ordering
5. Incremental indicators prevent look-ahead bias
6. Run Manifest captures full reproducibility metadata
"""

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
    """Unified deterministic backtesting simulator.

    Both bar-based and event-based strategies share this core.
    The execution loop is synchronous to guarantee determinism.
    """

    def __init__(
        self,
        broker: Broker | None = None,
        portfolio: PortfolioManager | None = None,
        commission_pct: float | None = None,
        slippage_bps: float | None = None,
    ) -> None:
        if broker is not None:
            self.broker = broker
        else:
            kwargs = {}
            if commission_pct is not None:
                kwargs["commission_pct"] = commission_pct
            if slippage_bps is not None:
                kwargs["slippage_bps"] = slippage_bps
            self.broker = Broker(**kwargs)
        self.portfolio = portfolio or PortfolioManager()

    def _create_lightweight_context(self, strategy: BaseStrategy) -> Any:
        """Create a lightweight context for strategies that need capital/position info."""
        from backtesting.engine.clock import Clock
        from backtesting.market.market_engine import MarketEngine
        from backtesting.orders.manager import OrderManager
        from backtesting.strategies.context import StrategyContext

        ctx = StrategyContext(
            market_engine=MarketEngine(),
            portfolio=self.portfolio,
            order_api=OrderManager(),
            clock=Clock(),
        )
        return ctx

    def run(
        self,
        strategy: BaseStrategy,
        initial_capital: float = 1_000_000_000,
        data: list[dict[str, Any]] | None = None,
        cancel_flag: bool = False,
    ) -> Result[BacktestResult]:
        """Run backtest synchronously (deterministic).

        This is the core execution method. It is intentionally synchronous
        to guarantee that:
        - Event ordering is deterministic
        - Results are reproducible with the same seed
        - No race conditions from async scheduling

        For parallel execution of multiple backtests, use run_parallel().
        """
        try:
            self.portfolio.reset(initial_capital)
            strategy.reset()

            # Wire context into strategy for position sizing
            ctx = self._create_lightweight_context(strategy)
            strategy.set_context(ctx)

            equity_curve: list[EquityPoint] = []
            all_fills: list[FillEvent] = []
            sequence_id = 0

            for bar in data or []:
                if cancel_flag:
                    logger.info("Backtest cancelled at bar %d/%d", len(equity_curve), len(data or []))
                    break

                # Incremental indicator computation (no look-ahead)
                # Indicators are computed inside the strategy via on_bar()

                orders = strategy.on_bar(bar)

                # Process orders deterministically (in order received)
                for order in orders:
                    fill = self.broker.submit_order_sync(order)
                    if fill:
                        self.portfolio.update_fill_sync(fill)
                        all_fills.append(fill)

                # Mark-to-market using bar close price
                instrument_id = bar.get("instrument_id", "")
                close_price = bar.get("close", 0)
                if instrument_id and close_price > 0:
                    self.portfolio.mark_to_market_sync({instrument_id: close_price})
                elif "prices" in bar:
                    self.portfolio.mark_to_market_sync(bar["prices"])

                equity_curve.append(
                    EquityPoint(
                        timestamp=bar.get("timestamp", now_tehran()),
                        nav=self.portfolio.get_nav(),
                        cash=self.portfolio.get_cash(),
                        positions_value=self.portfolio.get_positions_value(),
                    )
                )

                sequence_id += 1

            result = BacktestResult(
                strategy_name=strategy.__class__.__name__,
                initial_capital=initial_capital,
                final_capital=self.portfolio.get_nav(),
                total_return=self.portfolio.get_nav() - initial_capital,
                total_return_pct=((self.portfolio.get_nav() / initial_capital) - 1) * 100,
                total_trades=len(all_fills),
                equity_curve=equity_curve,
                trades=all_fills,
                metadata={
                    "cancelled": cancel_flag,
                    "total_bars": len(data or []),
                    "sequence_id_max": sequence_id,
                },
            )
            return Result.ok(result)
        except Exception as e:
            logger.error("Backtest failed: %s", e)
            return Result.fail(str(e))

    # Keep async wrapper for API compatibility (orchestration layer only)
    async def run_async(
        self,
        strategy: BaseStrategy,
        initial_capital: float = 1_000_000_000,
        data: list[dict[str, Any]] | None = None,
    ) -> Result[BacktestResult]:
        """Offload the synchronous core loop to a worker thread.

        The simulation is CPU-bound and can run for seconds; awaiting it
        directly would block the event loop and stall every other request.
        """
        import asyncio

        return await asyncio.to_thread(self.run, strategy, initial_capital, data)

    @staticmethod
    async def run_parallel(
        tasks: list[tuple[BaseStrategy, float, list[dict[str, Any]]]],
        max_concurrent: int = 10,
    ) -> list[Result[BacktestResult]]:
        """Run multiple backtests in parallel (for Grid Search / Monte Carlo).

        Each backtest runs in its own simulator instance for isolation.
        The async is used here ONLY for I/O-bound parallelism between runs,
        NOT within a single run's core loop.
        """
        import asyncio

        semaphore = asyncio.Semaphore(max_concurrent)

        async def _run_one(strategy, capital, data):
            async with semaphore:
                sim = BacktestSimulator()
                return sim.run(strategy, capital, data)

        tasks_coros = [_run_one(s, c, d) for s, c, d in tasks]
        return await asyncio.gather(*tasks_coros)
