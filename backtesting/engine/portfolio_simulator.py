from __future__ import annotations

import asyncio
from typing import Any

from backtesting.engine.broker import Broker
from backtesting.engine.portfolio import PortfolioManager
from backtesting.portfolio.allocator import Allocator
from backtesting.portfolio.rebalancer import Rebalancer
from backtesting.strategies.base import BaseStrategy
from backtesting.types import BacktestResult, EquityPoint, FillEvent, OrderEvent
from core.logging import get_logger
from core.result import Result
from core.time import now_tehran
from domain.common.enum_types import OrderSide, OrderType

logger = get_logger(__name__)


class PortfolioBacktestSimulator:
    """Multi-instrument portfolio backtest simulator.

    Runs a strategy across multiple instruments simultaneously,
    allocates capital, and optionally rebalances.
    """

    def __init__(
        self,
        broker: Broker | None = None,
        portfolio: PortfolioManager | None = None,
        allocator: Allocator | None = None,
        rebalancer: Rebalancer | None = None,
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
        self.allocator = allocator or Allocator(method="equal")
        self.rebalancer = rebalancer

    async def run(
        self,
        strategy: BaseStrategy,
        initial_capital: float,
        data_by_instrument: dict[str, list[dict[str, Any]]],
        cancel_event: asyncio.Event | None = None,
        target_weights: dict[str, float] | None = None,
    ) -> Result[BacktestResult]:
        """Run portfolio backtest across multiple instruments.

        Args:
            strategy: Strategy instance to generate signals
            initial_capital: Starting capital
            data_by_instrument: {instrument_id: [bar_dict, ...]} - aligned by timestamp
            cancel_event: Optional cancellation event
            target_weights: Target allocation weights (for rebalancing)
        """
        try:
            self.portfolio.reset(initial_capital)
            strategy.reset()

            instruments = list(data_by_instrument.keys())
            if not instruments:
                return Result.fail("No instrument data provided")

            # Allocate initial capital
            weights = target_weights or {inst: 1.0 / len(instruments) for inst in instruments}
            self.allocator.allocate(initial_capital, instruments, [weights.get(i, 0) for i in instruments])

            # Align timestamps across instruments
            all_timestamps: set[str] = set()
            for bars in data_by_instrument.values():
                for bar in bars:
                    ts = bar.get("timestamp", "")
                    if ts:
                        all_timestamps.add(ts)
            sorted_timestamps = sorted(all_timestamps)

            # Build lookup: instrument_id -> {timestamp: bar}
            bar_lookup: dict[str, dict[str, dict[str, Any]]] = {}
            for inst, bars in data_by_instrument.items():
                bar_lookup[inst] = {bar.get("timestamp", ""): bar for bar in bars}

            equity_curve: list[EquityPoint] = []
            all_fills: list[FillEvent] = []
            day_count = 0

            for ts in sorted_timestamps:
                if cancel_event is not None and cancel_event.is_set():
                    break

                # Process each instrument for this timestamp
                for inst in instruments:
                    bar = bar_lookup[inst].get(ts)
                    if bar is None:
                        continue

                    # Run strategy on this bar
                    bar_with_id = {**bar, "instrument_id": inst}
                    orders = strategy.on_bar(bar_with_id)

                    for order in orders:
                        fill = await self.broker.submit_order(order)
                        if fill:
                            await self.portfolio.update_fill(fill)
                            all_fills.append(fill)

                    # Mark to market
                    close_price = bar.get("close", 0)
                    if close_price > 0:
                        await self.portfolio.mark_to_market({inst: close_price})

                # Check rebalancing
                if self.rebalancer and target_weights:
                    current_nav = self.portfolio.get_nav()
                    current_positions = self.portfolio.get_positions()
                    current_values = {
                        inst: current_positions.get(inst, 0) * data_by_instrument[inst][-1].get("close", 0)
                        for inst in instruments
                    }
                    current_total = sum(current_values.values()) or 1.0
                    current_w = {inst: v / current_total for inst, v in current_values.items()}

                    if self.rebalancer.should_rebalance(current_w, target_weights):
                        trades = self.rebalancer.compute_trades(current_values, {inst: current_nav * w for inst, w in target_weights.items()}, current_nav)
                        for trade in trades:
                            inst_id = trade["instrument_id"]
                            side = OrderSide.BUY if trade["side"] == "buy" else OrderSide.SELL
                            # Get current price for this instrument
                            bars = data_by_instrument.get(inst_id, [])
                            price = bars[-1].get("close", 0) if bars else 0
                            if price > 0:
                                qty = int(trade["value"] / price)
                                if qty > 0:
                                    order = OrderEvent(
                                        instrument_id=inst_id,
                                        side=side,
                                        quantity=qty,
                                        price=price,
                                        order_type=OrderType.MARKET,
                                    )
                                    fill = await self.broker.submit_order(order)
                                    if fill:
                                        await self.portfolio.update_fill(fill)
                                        all_fills.append(fill)

                day_count += 1

                equity_curve.append(
                    EquityPoint(
                        timestamp=ts or now_tehran(),
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
                metadata={"instruments": instruments, "allocation_method": self.allocator.method},
            )
            return Result.ok(result)
        except Exception as e:
            logger.error("Portfolio backtest failed: %s", e)
            return Result.fail(str(e))
