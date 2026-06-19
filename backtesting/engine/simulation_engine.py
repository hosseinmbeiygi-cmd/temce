from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import datetime

from backtesting.analytics.engine import AnalyticsEngine
from backtesting.engine.clock import Clock
from backtesting.engine.data_layer import DataLake, InMemoryDataLake
from backtesting.engine.event_builder import EventBuilder, EventType, MarketEvent
from backtesting.engine.event_bus import EventBus
from backtesting.engine.market_state import MarketState
from backtesting.execution.fill_simulator import FillSimulator
from backtesting.execution.latency_model import LatencyModel
from backtesting.execution.level3_book import Level3OrderBook
from backtesting.execution.market_impact import MarketImpactModel
from backtesting.market.market_engine import MarketEngine
from backtesting.market.rule_engine import MarketRuleEngine
from backtesting.orders.manager import OrderManager
from backtesting.portfolio import PortfolioManager
from backtesting.strategies.context import StrategyContext
from backtesting.strategies.engine import IStrategy, StrategyEngine
from backtesting.types import BacktestResult, EquityPoint, FillEvent, OrderEvent
from core.ids import new_id
from core.logging import get_logger
from core.result import Result
from domain.common.enum_types import OrderSide

logger = get_logger(__name__)


class SimulationEngine:
    """High-level simulation kernel that orchestrates all engines.

    Flow:
        DataLake → EventBuilder → Timeline
            │
            ▼
        EventBus ──► MarketEngine ──► MarketState (read-only for strategies)
            │
            ▼
        StrategyEngine ──► OrderManager ──► Level3OrderBook
            │                                    │
            ▼                                    ▼
        FillSimulator ◄─────── MatchingEngine
            │
            ▼
        PortfolioManager ──► AnalyticsEngine

    Features:
    - Multiple strategy support via StrategyEngine
    - Level-3 order book for queue position tracking
    - Market impact model for large orders
    - Latency model for realistic order timing
    - Read-only MarketState for strategies
    - Event bus for decoupled component communication
    """

    def __init__(
        self,
        data_lake: DataLake | None = None,
        event_builder: EventBuilder | None = None,
        event_bus: EventBus | None = None,
        market_engine: MarketEngine | None = None,
        rule_engine: MarketRuleEngine | None = None,
        fill_simulator: FillSimulator | None = None,
        order_book: Level3OrderBook | None = None,
        impact_model: MarketImpactModel | None = None,
        latency_model: LatencyModel | None = None,
        portfolio: PortfolioManager | None = None,
        analytics: AnalyticsEngine | None = None,
        clock: Clock | None = None,
        mode: str = "EVENT",
    ) -> None:
        self.data_lake = data_lake or InMemoryDataLake()
        self.event_builder = event_builder or EventBuilder()
        self.event_bus = event_bus or EventBus()
        self.rule_engine = rule_engine or MarketRuleEngine()
        self.market_engine = market_engine or MarketEngine(self.rule_engine)
        self.market_state = MarketState(self.market_engine)
        self.fill_simulator = fill_simulator or FillSimulator()
        self.order_book = order_book or Level3OrderBook()
        self.impact_model = impact_model or MarketImpactModel()
        self.latency_model = latency_model or LatencyModel()
        self.portfolio = portfolio or PortfolioManager()
        self.analytics = analytics or AnalyticsEngine()
        self.clock = clock or Clock()
        self.mode = mode

        self.strategy_engine = StrategyEngine()
        self.order_manager = OrderManager()

        self._running = False
        self._event_count = 0
        self._strategy_fn: Callable[[StrategyContext], list[OrderEvent]] | None = None

    # ── Strategy Registration ──────────────────────────────

    def add_strategy(self, strategy: IStrategy) -> None:
        """Register a strategy with full lifecycle (on_start, on_event, on_fill, on_end)."""
        self.strategy_engine.add_strategy(strategy)

    def set_strategy_fn(self, strategy_fn: Callable[[StrategyContext], list[OrderEvent]]) -> None:
        """Set a simple lambda/function strategy (no lifecycle hooks)."""
        self._strategy_fn = strategy_fn

    # ── Main Loop ──────────────────────────────────────────

    async def run(
        self,
        initial_capital: float = 1_000_000_000,
        market_ids: list[str] | None = None,
        instrument_ids: list[str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> Result[BacktestResult]:
        """Run the full simulation pipeline.

        Steps:
        1. Build timeline from data lake
        2. For each event: update market state → run strategies → match orders → update portfolio
        3. Compute analytics
        """
        try:
            self._reset(initial_capital)

            ctx = StrategyContext(
                market_engine=self.market_engine,
                portfolio=self.portfolio,
                order_api=self.order_manager,
                clock=self.clock,
            )
            self.strategy_engine.set_context(ctx)

            timeline = await self._build_timeline(market_ids, instrument_ids, start_time, end_time)
            logger.info("SimulationEngine: %s events to process across %s instruments",
                        len(timeline), len(self.market_engine.get_all_states()))

            self.strategy_engine.on_start()

            all_fills: list[FillEvent] = []
            equity_curve: list[EquityPoint] = []

            for event in timeline:
                if not self._running:
                    break
                self._event_count += 1
                self.clock.jump_to(event.timestamp)

                # 1. Publish to event bus (decoupled subscribers)
                self.event_bus.publish(event)

                # 2. Update market engine state
                self._update_market_state(event)

                # 3. Update Level-3 order book with trade/quote events
                self._update_order_book(event)

                # 4. Collect orders from strategies
                orders = self._collect_orders(event)

                # 5. Submit orders → Level-3 book → fills
                fills = self._execute_orders(orders, event)

                # 6. Update portfolio with fills
                for fill in fills:
                    await self.portfolio.update_fill(fill)
                    all_fills.append(fill)

                # 7. Notify strategies about fills
                self.strategy_engine.notify_fills(fills)

                # 8. Record equity point
                if event.event_type in (EventType.TRADE, EventType.QUOTE):
                    nav = self.portfolio.get_nav()
                    equity_curve.append(EquityPoint(
                        timestamp=event.timestamp,
                        nav=nav,
                        cash=self.portfolio.get_cash(),
                        positions_value=self.portfolio.get_positions_value(),
                    ))

            self.strategy_engine.on_end()

            result = BacktestResult(
                strategy_name="SimulationEngine",
                initial_capital=initial_capital,
                final_capital=self.portfolio.get_nav(),
                total_return=self.portfolio.get_nav() - initial_capital,
                total_return_pct=((self.portfolio.get_nav() / initial_capital) - 1) * 100,
                total_trades=len(all_fills),
                equity_curve=equity_curve,
                trades=all_fills,
                metadata={
                    "event_count": self._event_count,
                    "instruments": len(self.market_engine.get_all_states()),
                    "mode": self.mode,
                    "order_book_fills": self.order_book.trade_count,
                },
            )
            return Result.ok(result)
        except Exception as e:
            logger.error("SimulationEngine failed: %s", e, exc_info=True)
            return Result.fail(str(e))

    # ── Internal Steps ─────────────────────────────────────

    def _collect_orders(self, event: MarketEvent) -> list[OrderEvent]:
        orders: list[OrderEvent] = []

        # From StrategyEngine (IStrategy lifecycle)
        strategy_orders = self.strategy_engine.on_event(event)
        orders.extend(strategy_orders)

        # From simple strategy_fn
        if self._strategy_fn:
            ctx = self.strategy_engine.context
            if ctx:
                ctx.current_event = event
                fn_orders = self._strategy_fn(ctx)
                orders.extend(fn_orders)

        return orders

    def _execute_orders(
        self,
        orders: list[OrderEvent],
        event: MarketEvent,
    ) -> list[FillEvent]:
        """Execute orders through the Level-3 order book.

        Market orders → match immediately against book
        Limit orders → add to book if not immediately matchable
        """
        fills: list[FillEvent] = []
        delayed_ts = self.latency_model.apply_latency(event.timestamp)
        buy_sell = {OrderSide.BUY: "buy", OrderSide.SELL: "sell"}

        for order in orders:
            valid, msg = self.market_engine.check_order(order)
            if not valid:
                logger.warning("Order rejected: %s", msg)
                continue

            side = buy_sell.get(order.side, "buy")
            order_type = str(order.order_type).upper()

            if "MARKET" in order_type:
                book_fills = self.order_book.execute_market_order(side, order.quantity)

                for bf in book_fills:
                    fills.append(FillEvent(
                        order_id=order.order_id or new_id("fill"),
                        instrument_id=order.instrument_id,
                        side=order.side,
                        quantity=bf["quantity"],
                        price=bf["price"],
                        commission=0.0,
                        timestamp=delayed_ts,
                    ))

            elif "LIMIT" in order_type:
                book_fills = self.order_book.process_limit_order(side, order.price, order.quantity)
                for bf in book_fills:
                    if bf.get("status") == "queued":
                        continue
                    fills.append(FillEvent(
                        order_id=order.order_id or new_id("fill"),
                        instrument_id=order.instrument_id,
                        side=order.side,
                        quantity=bf["quantity"],
                        price=bf["price"],
                        commission=0.0,
                        timestamp=delayed_ts,
                    ))

            else:
                state = self.market_engine.get_state(order.instrument_id)
                market_data = {
                    "bid": state.best_bid if state else 0.0,
                    "ask": state.best_ask if state else 0.0,
                    "close": state.last_trade if state else 0.0,
                }
                fill = self.fill_simulator.simulate_fill(order, market_data)
                if fill:
                    fill.timestamp = delayed_ts
                    fills.append(fill)

        # Per-instrument market impact
        if fills:
            inst_qty: dict[str, int] = defaultdict(int)
            for f in fills:
                inst_qty[f.instrument_id] += f.quantity

            inst_adv: dict[str, int] = defaultdict(int)
            for s in self.market_engine.get_all_states():
                inst_adv[s.instrument_id] = s.volume or 1_000_000

            for fill in fills:
                qty = inst_qty[fill.instrument_id]
                adv = inst_adv.get(fill.instrument_id, 1_000_000)
                impact = self.impact_model.compute_impact(qty, adv, fill.price)
                adjustment = impact["total"] / max(inst_qty[fill.instrument_id], 1)
                if fill.side == OrderSide.BUY:
                    fill.price += adjustment
                else:
                    fill.price -= adjustment

        return fills

    def _update_market_state(self, event: MarketEvent) -> None:
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
        elif event.event_type == EventType.SESSION_START:
            from domain.markets.enums import MarketStatus
            self.market_engine.set_session_state(event.instrument_id, "open", MarketStatus.OPEN)
            self.market_engine.update_price_limits(event.instrument_id)
        elif event.event_type == EventType.SESSION_END:
            from domain.markets.enums import MarketStatus
            self.market_engine.set_session_state(event.instrument_id, "closed", MarketStatus.CLOSED)

    def _update_order_book(self, event: MarketEvent) -> None:
        if event.event_type == EventType.TRADE:
            p = event.payload
            if self.order_book.total_ask_volume() > 0:
                self.order_book.execute_market_order("buy", p.get("volume", 0))

    async def _build_timeline(
        self,
        market_ids: list[str] | None = None,
        instrument_ids: list[str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[MarketEvent]:
        timeline: list[MarketEvent] = []
        markets = market_ids or await self.data_lake.get_available_markets()

        for market_id in markets:
            async for chunk in self.data_lake.load_chunk(market_id, instrument_ids, start_time, end_time):
                for record in chunk.records:
                    event = self.event_builder.from_raw(record)
                    timeline.append(event)
                for inst_id in chunk.instrument_ids:
                    if self.market_engine.get_state(inst_id) is None:
                        self.market_engine.add_instrument(inst_id, market_id)

        timeline.sort(key=lambda e: (e.timestamp, e.priority))
        return timeline

    def stop(self) -> None:
        self._running = False

    def reset(self) -> None:
        self._reset(0.0)

    def _reset(self, initial_capital: float) -> None:
        self.clock.reset()
        self.market_engine.reset()
        self.portfolio.reset(initial_capital)
        self.order_book.reset()
        self.order_manager.reset()
        self.strategy_engine.reset()
        self.event_bus.clear()
        self._running = True
        self._event_count = 0
