from __future__ import annotations

from typing import Any

from backtesting.engine.event_builder import EventType, MarketEvent
from backtesting.market.market_engine import MarketEngine
from backtesting.microstructure.auction_engine import AuctionEngine, AuctionResult
from backtesting.microstructure.cancel_model import CancelModel
from backtesting.microstructure.hidden_liquidity import HiddenLiquidityModel
from backtesting.microstructure.impact_model import ImpactModel
from backtesting.microstructure.latency_model import LatencyModel
from backtesting.microstructure.order_arrival_model import OrderArrivalModel
from backtesting.microstructure.queue_state import QueueState, SimulatedOrder, SimulatedOrderStatus
from backtesting.types import FillEvent
from core.ids import new_id
from core.logging import get_logger

logger = get_logger(__name__)


class MicrostructureEngine:
    def __init__(
        self,
        queue_model: QueueState | None = None,
        cancel_model: CancelModel | None = None,
        arrival_model: OrderArrivalModel | None = None,
        impact_model: ImpactModel | None = None,
        latency_model: LatencyModel | None = None,
        auction_engine: AuctionEngine | None = None,
        hidden_liquidity: HiddenLiquidityModel | None = None,
    ) -> None:
        self.cancel_model = cancel_model or CancelModel()
        self.arrival_model = arrival_model or OrderArrivalModel()
        self.impact_model = impact_model or ImpactModel()
        self.latency_model = latency_model or LatencyModel()
        self.auction_engine = auction_engine or AuctionEngine()
        self.hidden_liquidity = hidden_liquidity or HiddenLiquidityModel()
        self._queues: dict[str, QueueState] = {}
        self._active_orders: dict[str, list[SimulatedOrder]] = {}
        self._prev_queue_state: dict[str, dict[str, int]] = {}

    def get_or_create_queue(self, instrument_id: str) -> QueueState:
        if instrument_id not in self._queues:
            queue = QueueState(instrument_id=instrument_id)
            self._queues[instrument_id] = queue
            self._active_orders[instrument_id] = []
            self._prev_queue_state[instrument_id] = {"bid": 0, "ask": 0}
        return self._queues[instrument_id]

    def process_event(
        self,
        event: MarketEvent,
        market_engine: MarketEngine | None = None,
    ) -> list[FillEvent]:
        fills: list[FillEvent] = []
        inst_id = event.instrument_id
        queue = self.get_or_create_queue(inst_id)

        effective_ts = self.latency_model.apply_to_timestamp(event.timestamp)

        if event.event_type == EventType.QUOTE:
            p = event.payload
            self._prev_queue_state[inst_id] = {
                "bid": queue.bid_queue_volume,
                "ask": queue.ask_queue_volume,
            }
            bid_vol = p.get("bid_volume", 0)
            ask_vol = p.get("ask_volume", 0)
            hidden_bid, hidden_ask = self.hidden_liquidity.estimate_total_depth(bid_vol, ask_vol)
            queue.prev_bid_volume = bid_vol
            queue.prev_ask_volume = ask_vol
            queue.bid_queue_volume = hidden_bid
            queue.ask_queue_volume = hidden_ask

            new_bids = self.arrival_model.sample_arrivals(hidden_bid)
            new_asks = self.arrival_model.sample_arrivals(hidden_ask)
            for _ in range(new_bids):
                qty = self.arrival_model.sample_quantity()
                price = self.arrival_model.sample_price_offset(p.get("bid", 0))
                order = SimulatedOrder(
                    order_id=new_id("arrival"),
                    side="buy",
                    price=price,
                    quantity=qty,
                    instrument_id=inst_id,
                )
                queue.add_order(order)
            for _ in range(new_asks):
                qty = self.arrival_model.sample_quantity()
                price = self.arrival_model.sample_price_offset(p.get("ask", 0))
                order = SimulatedOrder(
                    order_id=new_id("arrival"),
                    side="sell",
                    price=price,
                    quantity=qty,
                    instrument_id=inst_id,
                )
                queue.add_order(order)

            self._update_cancel_rates(queue, inst_id)

        elif event.event_type == EventType.TRADE:
            p = event.payload
            trade_vol = p.get("volume", 0)
            trade_price = p.get("price", 0)

            impact_price = self.impact_model.get_execution_price(
                trade_vol, adv=1000000, price=trade_price, side="buy"
            )

            trade_fills = queue.update_from_trade(trade_vol, impact_price, "buy")
            for f in trade_fills:
                f.slippage = impact_price - trade_price
            fills.extend(trade_fills)

            trade_fills_sell = queue.update_from_trade(trade_vol, impact_price, "sell")
            for f in trade_fills_sell:
                f.slippage = impact_price - trade_price
            fills.extend(trade_fills_sell)

            new_arrivals = self.arrival_model.sample_arrivals(queue.bid_queue_volume + queue.ask_queue_volume)
            if new_arrivals > 0 and market_engine:
                state = market_engine.get_state(inst_id)
                if state:
                    ref_price = state.last_trade or trade_price
                    for _ in range(new_arrivals):
                        side = "buy"
                        qty = self.arrival_model.sample_quantity()
                        price = self.arrival_model.sample_price_offset(ref_price)
                        order = SimulatedOrder(
                            order_id=new_id("arrival"),
                            side=side,
                            price=price,
                            quantity=qty,
                            instrument_id=inst_id,
                        )
                        queue.add_order(order)

        elif event.event_type == EventType.AUCTION:
            p = event.payload
            auction_price = p.get("auction_price", 0.0)
            auction_volume = p.get("auction_volume", 0)
            fills.extend(self._process_auction_fills(inst_id, auction_price, auction_volume))

        return fills

    def process_active_orders(self, instrument_id: str, event: MarketEvent) -> list[FillEvent]:
        fills: list[FillEvent] = []
        queue = self._queues.get(instrument_id)
        if queue is None:
            return fills

        orders = self._active_orders.get(instrument_id, [])
        for order in orders:
            if order.status not in (SimulatedOrderStatus.ACTIVE, SimulatedOrderStatus.PARTIAL):
                continue

            cancel = self.cancel_model.estimate_cancel(
                queue.prev_bid_volume if order.side == "buy" else queue.prev_ask_volume,
                queue.bid_queue_volume if order.side == "buy" else queue.ask_queue_volume,
                0,
            )
            filled = order.update_queue_position(
                event.payload.get("volume", 0),
                cancel,
            )
            if filled:
                impact = self.impact_model.calculate_impact(
                    order.remaining,
                    adv=1000000,
                    price=event.payload.get("price", 0),
                )
                exec_price = event.payload.get("price", 0) * (1 + impact if order.side == "buy" else 1 - impact)
                fill = FillEvent(
                    order_id=order.order_id,
                    instrument_id=instrument_id,
                    side=order.side,
                    quantity=order.remaining,
                    price=round(exec_price, 2),
                    commission=0.0,
                    slippage=impact,
                )
                fills.append(fill)
                order.status = SimulatedOrderStatus.FILLED
                order.remaining = 0

        return fills

    def process_auction(
        self,
        instrument_id: str,
        bids: dict[float, int],
        asks: dict[float, int],
        reference_price: float | None = None,
    ) -> AuctionResult:
        return self.auction_engine.calculate_opening_auction(bids, asks, reference_price)

    def estimate_queue_lifetime(self, instrument_id: str) -> float:
        queue = self._queues.get(instrument_id)
        if queue is None:
            return 0.0
        total_queue = queue.bid_queue_volume + queue.ask_queue_volume
        total_flow = queue.bid_trade_flow + queue.ask_trade_flow
        avg_cancel_rate = (queue.cancel_rate_bid + queue.cancel_rate_ask) / 2
        drain_rate = (total_flow / max(queue.bid_trade_flow + queue.ask_trade_flow, 1)) if queue.bid_trade_flow + queue.ask_trade_flow > 0 else 0
        total_drain = drain_rate + avg_cancel_rate
        if total_drain <= 0:
            return float("inf")
        return total_queue / total_drain

    def get_queue_snapshot(self, instrument_id: str) -> dict[str, Any] | None:
        queue = self._queues.get(instrument_id)
        if queue is None:
            return None
        return queue.snapshot()

    def reset(self) -> None:
        self._queues.clear()
        self._active_orders.clear()
        self._prev_queue_state.clear()

    def _update_cancel_rates(self, queue: QueueState, inst_id: str) -> None:
        prev = self._prev_queue_state.get(inst_id, {"bid": 0, "ask": 0})
        cancel_bid = self.cancel_model.estimate_cancel(
            prev.get("bid", 0), queue.bid_queue_volume, queue.bid_trade_flow
        )
        cancel_ask = self.cancel_model.estimate_cancel(
            prev.get("ask", 0), queue.ask_queue_volume, queue.ask_trade_flow
        )
        queue.cancel_rate_bid = cancel_bid / max(queue.bid_queue_volume, 1)
        queue.cancel_rate_ask = cancel_ask / max(queue.ask_queue_volume, 1)

    def _process_auction_fills(self, instrument_id: str, price: float, volume: int) -> list[FillEvent]:
        fills: list[FillEvent] = []
        queue = self._queues.get(instrument_id)
        if queue is None:
            return fills
        fills.extend(queue.update_from_trade(volume, price, "buy"))
        fills.extend(queue.update_from_trade(volume, price, "sell"))
        return fills
