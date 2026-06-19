from __future__ import annotations

from datetime import datetime

from backtesting.engine.clock import Clock
from backtesting.engine.data_layer import DataLake, InMemoryDataLake
from backtesting.engine.event_builder import EventBuilder, EventType, MarketEvent
from backtesting.engine.unified_timeline import UnifiedTimeline
from backtesting.execution.fill_simulator import FillSimulator
from backtesting.execution.order_models import Order
from backtesting.market.market_engine import MarketEngine
from backtesting.market.rule_engine import MarketRuleEngine
from backtesting.microstructure.microstructure_engine import MicrostructureEngine
from backtesting.portfolio import PortfolioManager
from backtesting.risk import DrawdownControl, StopLoss, TakeProfit
from backtesting.strategies.base import BaseStrategy
from backtesting.types import BacktestResult, EquityPoint, FillEvent
from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class ReplayEngine:
    def __init__(
        self,
        clock: Clock | None = None,
        data_lake: DataLake | None = None,
        event_builder: EventBuilder | None = None,
        market_engine: MarketEngine | None = None,
        rule_engine: MarketRuleEngine | None = None,
        fill_simulator: FillSimulator | None = None,
        portfolio: PortfolioManager | None = None,
        stop_loss: StopLoss | None = None,
        take_profit: TakeProfit | None = None,
        drawdown_control: DrawdownControl | None = None,
        microstructure_engine: MicrostructureEngine | None = None,
    ) -> None:
        self.clock = clock or Clock()
        self.data_lake = data_lake or InMemoryDataLake()
        self.event_builder = event_builder or EventBuilder()
        self.rule_engine = rule_engine or MarketRuleEngine()
        self.market_engine = market_engine or MarketEngine(self.rule_engine)
        self.fill_simulator = fill_simulator or FillSimulator()
        self.portfolio = portfolio or PortfolioManager()
        self.stop_loss = stop_loss or StopLoss()
        self.take_profit = take_profit or TakeProfit()
        self.drawdown_control = drawdown_control or DrawdownControl()
        self.microstructure = microstructure_engine
        self._running = False
        self._event_count = 0

    @property
    def event_count(self) -> int:
        return self._event_count

    async def run(
        self,
        strategy: BaseStrategy,
        initial_capital: float = 1_000_000_000,
        market_ids: list[str] | None = None,
        instrument_ids: list[str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> Result[BacktestResult]:
        try:
            self._reset(initial_capital)
            strategy.reset()

            timeline = await self._build_timeline(market_ids, instrument_ids, start_time, end_time)
            stats = timeline.get_stats()
            logger.info("Replaying %s events across %s instruments", stats.total_events, len(stats.instrument_counts))

            equity_curve: list[EquityPoint] = []
            all_fills: list[FillEvent] = []

            for event in timeline:
                if not self._running:
                    break
                self._event_count += 1
                self.clock.jump_to(event.timestamp)
                fills = await self._process_event(event, strategy)
                all_fills.extend(fills)

                if event.event_type in (EventType.TRADE, EventType.QUOTE):
                    nav = self.portfolio.get_nav()
                    self.drawdown_control.update(nav)
                    equity_curve.append(
                        EquityPoint(
                            timestamp=event.timestamp,
                            nav=nav,
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
                metadata={
                    "event_count": self._event_count,
                    "markets": list(stats.market_counts.keys()),
                    "instruments": list(stats.instrument_counts.keys()),
                    "time_span_start": str(stats.time_span_start),
                    "time_span_end": str(stats.time_span_end),
                },
            )
            return Result.ok(result)
        except Exception as e:
            logger.error("Replay engine failed: %s", e)
            return Result.fail(str(e))

    async def _build_timeline(
        self,
        market_ids: list[str] | None = None,
        instrument_ids: list[str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> UnifiedTimeline:
        timeline = UnifiedTimeline()
        markets = market_ids or await self.data_lake.get_available_markets()

        for market_id in markets:
            async for chunk in self.data_lake.load_chunk(market_id, instrument_ids, start_time, end_time):
                for record in chunk.records:
                    event = self.event_builder.from_raw(record)
                    timeline.add_event(event)

                for inst_id in chunk.instrument_ids:
                    if self.market_engine.get_state(inst_id) is None:
                        self.market_engine.add_instrument(inst_id, market_id)

        logger.info("Built timeline with %s events", len(timeline))
        return timeline

    async def _process_event(
        self,
        event: MarketEvent,
        strategy: BaseStrategy,
    ) -> list[FillEvent]:
        fills: list[FillEvent] = []

        if self.microstructure:
            ms_fills = self.microstructure.process_event(event, self.market_engine)
            fills.extend(ms_fills)

        if event.event_type == EventType.QUOTE:
            p = event.payload
            self.market_engine.update_quote(
                event.instrument_id,
                bid=p.get("bid", 0.0),
                ask=p.get("ask", 0.0),
                bid_vol=p.get("bid_volume", 0),
                ask_vol=p.get("ask_volume", 0),
            )

        elif event.event_type == EventType.TRADE:
            p = event.payload
            self.market_engine.update_trade(
                event.instrument_id,
                price=p["price"],
                volume=p["volume"],
                value=p.get("value", 0.0),
            )

            if self.microstructure:
                active_fills = self.microstructure.process_active_orders(event.instrument_id, event)
                fills.extend(active_fills)

        elif event.event_type == EventType.SESSION_START:
            from domain.markets.enums import MarketStatus
            self.market_engine.set_session_state(event.instrument_id, "open", MarketStatus.OPEN)
            self.market_engine.update_price_limits(event.instrument_id)

        elif event.event_type == EventType.SESSION_END:
            from domain.markets.enums import MarketStatus
            self.market_engine.set_session_state(event.instrument_id, "closed", MarketStatus.CLOSED)

        elif event.event_type == EventType.CORPORATE_ACTION:
            p = event.payload
            adjustment = p.get("adjustment_factor", 1.0)
            if adjustment != 1.0:
                self.portfolio.adjust_positions(event.instrument_id, adjustment)

        orders: list[Order] = strategy.on_event(event)

        # If on_event returned nothing and this is a TRADE, also try on_bar
        # so bar-based strategies (e.g. MovingAverageCross) work with ReplayEngine
        if not orders and event.event_type == EventType.TRADE:
            bar = {
                "close": event.payload.get("price", 0.0),
                "high": event.payload.get("price", 0.0),
                "low": event.payload.get("price", 0.0),
                "open": event.payload.get("price", 0.0),
                "volume": event.payload.get("volume", 0),
                "instrument_id": event.instrument_id,
                "market_id": event.market_id,
                "timestamp": event.timestamp,
            }
            orders = strategy.on_bar(bar)

        for order in orders:
            valid, msg = self.market_engine.check_order(order)
            if not valid:
                logger.warning("Order rejected: %s", msg)
                continue

            if self.stop_loss and self.stop_loss.is_triggered(self.portfolio.get_positions(), event):
                logger.info("Stop loss triggered for %s", order.instrument_id)
                continue

            if self.take_profit and self.take_profit.is_triggered(self.portfolio.get_positions(), event):
                logger.info("Take profit triggered for %s", order.instrument_id)
                continue

            fill = self.fill_simulator.simulate_fill(order, event.payload)
            if fill:
                if self.microstructure:
                    state = self.market_engine.get_state(order.instrument_id)
                    if state:
                        adv = max(state.volume, 1_000_000)
                        fill = self.microstructure.impact_model.apply_to_fill(fill, adv)
                fills.append(fill)
                await self.portfolio.update_fill(fill)

        return fills

    def stop(self) -> None:
        self._running = False

    def _reset(self, initial_capital: float) -> None:
        self.clock.reset()
        self.market_engine.reset()
        self.portfolio.reset(initial_capital)
        if self.microstructure:
            self.microstructure.reset()
        self._running = True
        self._event_count = 0
