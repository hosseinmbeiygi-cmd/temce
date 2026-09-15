from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from backtesting.costs.iran_costs import DEFAULT_IRAN_COSTS, IranTransactionCosts, normalize_side
from backtesting.engine.clock import Clock
from backtesting.engine.data_layer import DataLake, InMemoryDataLake
from backtesting.engine.event_builder import EventBuilder, EventType, MarketEvent
from backtesting.hybrid.agent_engine import AgentEngine
from backtesting.hybrid.order_merge import OrderMergeLayer
from backtesting.hybrid.price_formation import PriceFormation
from backtesting.hybrid.unified_order_book import UnifiedOrderBook
from backtesting.market.market_engine import MarketEngine
from backtesting.microstructure.impact_model import ImpactModel
from backtesting.types import BacktestResult, FillEvent, OrderEvent
from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


@dataclass
class HybridResult:
    """Result of a hybrid market simulation."""

    price_series: list[float] = field(default_factory=list)
    historical_price_series: list[float] = field(default_factory=list)
    divergence_series: list[float] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    fills: list[FillEvent] = field(default_factory=list)
    source_mix_history: list[dict[str, float]] = field(default_factory=list)
    regime_history: list[dict[str, Any]] = field(default_factory=list)
    total_events: int = 0
    total_agent_orders: int = 0
    total_strategy_orders: int = 0
    final_price: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_backtest_result(
        self, strategy_name: str = "HybridStrategy", initial_capital: float = 1_000_000_000
    ) -> BacktestResult:
        # Fills carry commission now (audit F2) — deduct it so hybrid P&L is
        # consistent with the portfolio-based backtest paths.
        gross = sum(f.price * f.quantity for f in self.fills)
        costs = sum((f.commission or 0.0) for f in self.fills)
        nav = initial_capital + gross - costs
        return BacktestResult(
            strategy_name=strategy_name,
            initial_capital=initial_capital,
            final_capital=nav,
            total_return=nav - initial_capital,
            total_return_pct=((nav / initial_capital) - 1) * 100 if initial_capital > 0 else 0.0,
            total_trades=len(self.fills),
            trades=self.fills,
            metadata={
                "price_divergence_max": max(self.divergence_series) if self.divergence_series else 0.0,
                "total_events": self.total_events,
                "total_agent_orders": self.total_agent_orders,
                "total_strategy_orders": self.total_strategy_orders,
                **self.metadata,
            },
        )


class HybridMarketSimulator:
    """Core hybrid simulation engine that combines:
    - Historical market replay
    - Synthetic agent orders (ABM)
    - Strategy orders
    - Market impact modeling
    - Price formation (anchored or endogenous)
    """

    def __init__(
        self,
        data_lake: DataLake | None = None,
        event_builder: EventBuilder | None = None,
        market_engine: MarketEngine | None = None,
        agent_engine: AgentEngine | None = None,
        order_merge: OrderMergeLayer | None = None,
        order_book: UnifiedOrderBook | None = None,
        price_formation: PriceFormation | None = None,
        impact_model: ImpactModel | None = None,
        clock: Clock | None = None,
        flow_mix: dict[str, float] | None = None,
        cost_model: IranTransactionCosts = DEFAULT_IRAN_COSTS,
    ) -> None:
        self.data_lake = data_lake or InMemoryDataLake()
        self.event_builder = event_builder or EventBuilder()
        self.market_engine = market_engine or MarketEngine()
        self.agent_engine = agent_engine or AgentEngine()
        self.order_merge = order_merge or OrderMergeLayer()
        self.order_book = order_book or UnifiedOrderBook()
        self.price_formation = price_formation or PriceFormation(mode="anchored")
        self.impact_model = impact_model or ImpactModel()
        self.clock = clock or Clock()
        self.cost_model = cost_model

        # Default flow mix: what proportion of orders come from each source
        self.flow_mix = flow_mix or {"real": 0.8, "agent": 0.15, "strategy": 0.05}

        self._running = False
        self._event_count = 0
        self._agent_order_count = 0
        self._strategy_order_count = 0
        self._regime = "normal"
        self._historical_price: float = 0.0
        self._adv: int = 1_000_000

    @property
    def regime(self) -> str:
        return self._regime

    @regime.setter
    def regime(self, value: str) -> None:
        self._regime = value
        logger.debug("Regime changed to: %s", value)

    def set_flow_mix(self, real: float, agent: float, strategy: float) -> None:
        total = real + agent + strategy
        if total <= 0:
            self.flow_mix = {"real": 0.0, "agent": 0.0, "strategy": 0.0}
            return
        self.flow_mix = {"real": real / total, "agent": agent / total, "strategy": strategy / total}

    def update_flow_mix_for_regime(self, regime: str) -> None:
        mixes = {
            "normal": {"real": 0.8, "agent": 0.15, "strategy": 0.05},
            "trend": {"real": 0.7, "agent": 0.2, "strategy": 0.1},
            "panic": {"real": 0.6, "agent": 0.3, "strategy": 0.1},
            "low_liquidity": {"real": 0.7, "agent": 0.25, "strategy": 0.05},
            "queue_lock": {"real": 0.75, "agent": 0.2, "strategy": 0.05},
        }
        mix = mixes.get(regime, {"real": 0.8, "agent": 0.15, "strategy": 0.05})
        self.flow_mix = mix

    async def run(
        self,
        market_ids: list[str] | None = None,
        instrument_ids: list[str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        strategy_orders_fn: Any = None,
        initial_capital: float = 1_000_000_000,
        enable_agents: bool = True,
        enable_strategy: bool = True,
        flow_update_freq: int = 100,
    ) -> Result[HybridResult]:
        """Run the hybrid simulation.

        Args:
            market_ids: Markets to simulate
            instrument_ids: Specific instruments to simulate
            start_time: Simulation start
            end_time: Simulation end
            strategy_orders_fn: Callable(market_state) -> list[OrderEvent]
            initial_capital: Starting capital
            enable_agents: Whether to run synthetic agents
            enable_strategy: Whether to run strategy
            flow_update_freq: How often to log flow mix stats
        """
        try:
            self._reset()
            result = HybridResult()

            # Build timeline from data lake
            timeline = await self._build_timeline(market_ids, instrument_ids, start_time, end_time)
            if not timeline:
                return Result.ok(result)

            logger.info(
                "Hybrid simulation starting: %s events, agents=%s", len(timeline), len(self.agent_engine.agents)
            )

            for i, event in enumerate(timeline):
                if not self._running:
                    break

                self._event_count += 1
                self.clock.jump_to(event.timestamp)

                # Update market state from historical event
                self._apply_historical_event(event)

                # Track historical price
                if event.event_type == EventType.TRADE:
                    self._historical_price = event.payload.get("price", self._historical_price)
                    self.price_formation.set_historical_price(self._historical_price)

                # Build market state dict for agents
                market_state = self._build_market_state(event)

                # Generate agent orders
                agent_orders: list[OrderEvent] = []
                if enable_agents:
                    agent_orders = self.agent_engine.generate_orders(market_state)
                    self._agent_order_count += len(agent_orders)

                # Generate strategy orders
                strategy_orders: list[OrderEvent] = []
                if enable_strategy and strategy_orders_fn:
                    try:
                        strategy_orders = strategy_orders_fn(market_state) or []
                    except Exception:
                        strategy_orders = []
                    self._strategy_order_count += len(strategy_orders)

                # Merge all orders into unified flow
                self.order_merge.add_historical_event(event)
                if agent_orders:
                    self.order_merge.add_agent_orders(agent_orders, event.timestamp)
                if strategy_orders:
                    self.order_merge.add_strategy_orders(strategy_orders, event.timestamp)

                # Process the merged flow
                fills = self._process_merged_flow(event)
                result.fills.extend(fills)

                # Track price divergence
                if self._historical_price > 0:
                    sim_price = self.price_formation.current_price
                    if sim_price > 0:
                        divergence = abs(sim_price - self._historical_price) / self._historical_price * 100
                        result.divergence_series.append(divergence)
                        result.price_series.append(sim_price)
                        result.historical_price_series.append(self._historical_price)

                # Track source mix periodically
                if i % flow_update_freq == 0:
                    result.source_mix_history.append(self.order_book.get_source_mix())

            # Build final result
            result.total_events = self._event_count
            result.total_agent_orders = self._agent_order_count
            result.total_strategy_orders = self._strategy_order_count
            result.final_price = self.price_formation.current_price
            result.metadata = {
                "regime": self._regime,
                "flow_mix": dict(self.flow_mix),
                "n_agents": len(self.agent_engine.agents),
                "simulation_time": str(self.clock.current_time),
            }

            logger.info(
                "Hybrid simulation complete: %s events, %s agent orders, %s fills, final price=%.2f",
                self._event_count,
                self._agent_order_count,
                len(result.fills),
                result.final_price,
            )
            return Result.ok(result)

        except Exception as e:
            logger.error("Hybrid simulation failed: %s", e)
            return Result.fail(str(e))

    async def run_with_strategy(
        self,
        strategy_orders_fn: Any,
        backtest_fn: Any | None = None,
        market_ids: list[str] | None = None,
        instrument_ids: list[str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> Result[HybridResult]:
        """Run hybrid simulation with a strategy, then optionally run the pricing impact analysis."""
        return await self.run(
            market_ids=market_ids,
            instrument_ids=instrument_ids,
            start_time=start_time,
            end_time=end_time,
            strategy_orders_fn=strategy_orders_fn,
        )

    def _build_market_state(self, event: MarketEvent) -> dict[str, Any]:
        inst_id = event.instrument_id
        state = self.market_engine.get_state(inst_id)
        inst_state: dict[str, Any] = {
            "instrument_id": inst_id,
            "market_id": event.market_id,
            "event_type": str(event.event_type),
            "timestamp": event.timestamp,
        }
        if state:
            inst_state.update(
                {
                    "best_bid": state.best_bid,
                    "best_ask": state.best_ask,
                    "bid_volume": state.bid_volume,
                    "ask_volume": state.ask_volume,
                    "last_price": state.last_trade,
                    "volume": state.volume,
                    "midpoint": (state.best_bid + state.best_ask) / 2
                    if state.best_bid > 0 and state.best_ask > 0
                    else 0,
                    "spread": state.best_ask - state.best_bid if state.best_bid > 0 and state.best_ask > 0 else 0,
                }
            )
        inst_state["payload"] = dict(event.payload)
        return inst_state

    def _apply_historical_event(self, event: MarketEvent) -> None:
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

    def _process_merged_flow(self, event: MarketEvent) -> list[FillEvent]:
        fills: list[FillEvent] = []

        while True:
            merged = self.order_merge.pop_next()
            if merged is None:
                break

            if merged.source == "historical" and merged.event:
                # Historical events just update market state (already done)
                pass

            elif merged.source in ("agent", "strategy") and merged.order:
                order = merged.order
                # Match against the unified order book
                trades = self.order_book.match_order(order, source=merged.source)

                for trade in trades:
                    fill = FillEvent(
                        order_id=trade.buy_order_id,
                        instrument_id=order.instrument_id or "",
                        side=normalize_side(order.side),
                        quantity=trade.quantity,
                        price=trade.price,
                        commission=self.cost_model.compute(order.side, trade.price, trade.quantity),
                        slippage=0.0,
                    )
                    fills.append(fill)

                    # Apply market impact
                    if self._historical_price > 0 and self._adv > 0:
                        impact_price = self.price_formation.apply_impact_from_order(
                            order_side="buy",
                            order_quantity=trade.quantity,
                            order_price=trade.price,
                            adv=self._adv,
                            eta=self.impact_model.eta,
                            alpha=self.impact_model.alpha,
                        )
                        simulate_trade_event = self.event_builder.build_trade(
                            event_id=f"hybrid_trade_{self._event_count}",
                            timestamp=merged.timestamp,
                            instrument_id=event.instrument_id,
                            market_id=event.market_id,
                            price=impact_price,
                            volume=trade.quantity,
                        )
                        self.market_engine.update_trade(
                            simulate_trade_event.instrument_id,
                            price=impact_price,
                            volume=trade.quantity,
                        )

        return fills

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
        logger.info("Built hybrid timeline with %s events", len(timeline))
        return timeline

    def stop(self) -> None:
        self._running = False

    def _reset(self) -> None:
        self.clock.reset()
        self.market_engine.reset()
        self.agent_engine.reset()
        self.order_merge.clear()
        self.order_book.reset()
        self.price_formation.reset()
        self._running = True
        self._event_count = 0
        self._agent_order_count = 0
        self._strategy_order_count = 0
        self._historical_price = 0.0
