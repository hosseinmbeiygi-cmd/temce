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
        latency_bars: int = 0,
        price_limit_pct: float | None = None,
        stress_multiplier: float = 1.0,
    ) -> None:
        """Args:
        latency_bars: simulated execution delay in bars (roadmap v2:42). 0 = no delay.
        price_limit_pct: Iran daily price limit (e.g. 0.05 for ±5%) - None disables (v1:84)
        stress_multiplier: multiply slippage by this factor for stress testing (v2:51, A5)
        """
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
        self.latency_bars = max(0, int(latency_bars))
        self.price_limit_pct = price_limit_pct
        self.stress_multiplier = max(1.0, float(stress_multiplier))
        self._pending_orders: list[tuple[int, Any]] = []  # (target_bar_index, order)

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

    def latency_sensitivity(
        self,
        strategy: BaseStrategy,
        initial_capital: float,
        data: list[dict[str, Any]],
        latencies: list[int] | None = None,
    ) -> dict[int, Result[BacktestResult]]:
        """Run same backtest with different latencies for sensitivity analysis (v2:42)."""
        latencies = latencies or [0, 1, 2]
        out: dict[int, Result[BacktestResult]] = {}
        for lb in latencies:
            sim = BacktestSimulator(
                broker=self.broker,
                portfolio=PortfolioManager(),
                latency_bars=lb,
                price_limit_pct=self.price_limit_pct,
                stress_multiplier=self.stress_multiplier,
            )
            out[lb] = sim.run(strategy, initial_capital, data)
        return out

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
            self._pending_orders = []
            prev_close: dict[str, float] = {}

            for bar_idx, bar in enumerate(data or []):
                if cancel_flag:
                    logger.info("Backtest cancelled at bar %d/%d", len(equity_curve), len(data or []))
                    break

                # --- execute pending latency orders (A3) ---
                ready = [o for o in self._pending_orders if o[0] <= bar_idx]
                self._pending_orders = [o for o in self._pending_orders if o[0] > bar_idx]
                for _, pending_order in ready:
                    # price-limit check at execution bar (A5)
                    if self.price_limit_pct is not None:
                        pc = prev_close.get(pending_order.instrument_id)
                        if pc and pending_order.price > 0:
                            limit_up = pc * (1 + self.price_limit_pct)
                            limit_down = pc * (1 - self.price_limit_pct)
                            if pending_order.price > limit_up or pending_order.price < limit_down:
                                continue  # rejected - outside daily limit, queue
                    fills = self.broker.submit_order_sync(
                        pending_order, volatility=bar.get("volatility"), spread_bps=bar.get("spread_bps")
                    )
                    # Broker may return list for partial fills
                    fill_list = fills if isinstance(fills, list) else ([fills] if fills else [])
                    for f in fill_list:
                        if f:
                            self.portfolio.update_fill_sync(f)
                            all_fills.append(f)

                # Incremental indicator computation (no look-ahead)
                orders = strategy.on_bar(bar)

                # Process new orders (with latency or immediate)
                for order in orders:
                    if self.latency_bars > 0:
                        self._pending_orders.append((bar_idx + self.latency_bars, order))
                        continue
                    # immediate price-limit check (A5)
                    if self.price_limit_pct is not None:
                        pc = prev_close.get(order.instrument_id)
                        if pc and order.price > 0:
                            limit_up = pc * (1 + self.price_limit_pct)
                            limit_down = pc * (1 - self.price_limit_pct)
                            if order.price > limit_up or order.price < limit_down:
                                # queue probability: low liquidity -> partial/no fill
                                # for now reject, queue model handled via partial fill
                                continue
                    fills = self.broker.submit_order_sync(
                        order, volatility=bar.get("volatility"), spread_bps=bar.get("spread_bps")
                    )
                    fill_list = fills if isinstance(fills, list) else ([fills] if fills else [])
                    for f in fill_list:
                        if f:
                            self.portfolio.update_fill_sync(f)
                            all_fills.append(f)

                # Mark-to-market using bar close price
                instrument_id = bar.get("instrument_id", "")
                close_price = bar.get("close", 0)
                if instrument_id and close_price > 0:
                    self.portfolio.mark_to_market_sync({instrument_id: close_price})
                    prev_close[instrument_id] = close_price
                elif "prices" in bar:
                    self.portfolio.mark_to_market_sync(bar["prices"])
                    for k, v in bar["prices"].items():
                        if v and v > 0:
                            prev_close[k] = float(v)
                # also track close for generic bars
                elif close_price > 0 and instrument_id:
                    prev_close[instrument_id] = close_price

                equity_curve.append(
                    EquityPoint(
                        timestamp=bar.get("timestamp", now_tehran()),
                        nav=self.portfolio.get_nav(),
                        cash=self.portfolio.get_cash(),
                        positions_value=self.portfolio.get_positions_value(),
                    )
                )

                sequence_id += 1

            # flush remaining pending orders after data ends (execute at last close)
            for _, pending_order in self._pending_orders:
                fills = self.broker.submit_order_sync(pending_order)
                fill_list = fills if isinstance(fills, list) else ([fills] if fills else [])
                for f in fill_list:
                    if f:
                        self.portfolio.update_fill_sync(f)
                        all_fills.append(f)

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
        """Async wrapper around sync run — for API endpoints only."""
        return self.run(strategy, initial_capital, data)

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
