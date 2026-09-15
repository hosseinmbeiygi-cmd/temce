from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from backtesting.execution.fill_simulator import FillSimulator
from backtesting.market.market_engine import MarketEngine
from backtesting.types import FillEvent, OrderEvent
from core.ids import new_id
from core.logging import get_logger

logger = get_logger(__name__)


class OrderStatus(StrEnum):
    NEW = "NEW"
    SUBMITTED = "SUBMITTED"
    QUEUED = "QUEUED"
    PARTIAL_FILL = "PARTIAL_FILL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class ActiveOrder:
    """Represents an order being tracked by the OrderManager."""

    order_id: str
    instrument_id: str
    side: str
    quantity: int
    price: float
    order_type: str = "MARKET"
    remaining: int = 0
    filled: int = 0
    status: OrderStatus = OrderStatus.NEW
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    filled_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.remaining == 0:
            self.remaining = self.quantity


class OrderManager:
    """Manages the lifecycle of orders during a backtest.

    Provides OrderAPI methods for strategies:
    - ctx.orders.market(instrument, qty) — submit market order
    - ctx.orders.limit(instrument, qty, price) — submit limit order
    - ctx.orders.cancel(order_id) — cancel an order
    - ctx.orders.stop(instrument, qty, stop_price) — submit stop order
    """

    def __init__(self) -> None:
        self._orders: dict[str, ActiveOrder] = {}
        self._pending: list[ActiveOrder] = []

    # ── OrderAPI Methods (called by strategies) ──────────────

    def market(self, instrument_id: str, quantity: int, side: str | None = None) -> OrderEvent:
        """Submit a market order.

        Args:
            instrument_id: Instrument to trade
            quantity: Order quantity (positive)
            side: 'buy' or 'sell' (auto-detected from sign if None)

        Returns:
            OrderEvent that gets processed by the execution simulator
        """
        if side is None:
            side = "buy" if quantity > 0 else "sell"
        order_id = new_id("order")
        return OrderEvent(
            instrument_id=instrument_id,
            side=side,
            quantity=abs(quantity),
            price=0.0,
            order_type="MARKET",
            order_id=order_id,
        )

    def limit(self, instrument_id: str, quantity: int, price: float, side: str | None = None) -> OrderEvent:
        """Submit a limit order.

        Args:
            instrument_id: Instrument to trade
            quantity: Order quantity
            price: Limit price
            side: 'buy' or 'sell'

        Returns:
            OrderEvent
        """
        if side is None:
            side = "buy" if quantity > 0 else "sell"
        order_id = new_id("order")
        return OrderEvent(
            instrument_id=instrument_id,
            side=side,
            quantity=abs(quantity),
            price=price,
            order_type="LIMIT",
            order_id=order_id,
        )

    def cancel(self, order_id: str) -> None:
        """Cancel an active order."""
        order = self._orders.get(order_id)
        if order and order.status in (
            OrderStatus.NEW,
            OrderStatus.SUBMITTED,
            OrderStatus.QUEUED,
            OrderStatus.PARTIAL_FILL,
        ):
            order.status = OrderStatus.CANCELLED
            logger.debug("Order %s cancelled", order_id)

    def stop(self, instrument_id: str, quantity: int, stop_price: float, side: str | None = None) -> OrderEvent:
        """Submit a stop order (becomes market when stop_price is hit)."""
        if side is None:
            side = "buy" if quantity > 0 else "sell"
        order_id = new_id("order")
        return OrderEvent(
            instrument_id=instrument_id,
            side=side,
            quantity=abs(quantity),
            price=stop_price,
            order_type="STOP",
            order_id=order_id,
        )

    # ── Internal Methods ────────────────────────────────────

    def submit(self, order_event: OrderEvent) -> ActiveOrder:
        """Submit an order event to the manager for tracking."""
        order = ActiveOrder(
            order_id=order_event.order_id or new_id("order"),
            instrument_id=order_event.instrument_id,
            side=order_event.side,
            quantity=order_event.quantity,
            price=order_event.price,
            order_type=order_event.order_type or "MARKET",
            status=OrderStatus.SUBMITTED,
        )
        self._orders[order.order_id] = order
        self._pending.append(order)
        logger.debug("Order submitted: %s %s %d @ %.2f", order.side, order.instrument_id, order.quantity, order.price)
        return order

    def process_pending(
        self,
        market_engine: MarketEngine,
        fill_simulator: FillSimulator,
    ) -> list[FillEvent]:
        """Process all pending orders through the execution simulator.

        Args:
            market_engine: Current market state
            fill_simulator: Execution simulator

        Returns:
            List of FillEvents from executed orders
        """
        fills: list[FillEvent] = []
        remaining_pending: list[ActiveOrder] = []

        for order in self._pending:
            if order.status == OrderStatus.CANCELLED:
                continue

            state = market_engine.get_state(order.instrument_id)
            if state is None:
                remaining_pending.append(order)
                continue

            market_data = {
                "bid": state.best_bid,
                "ask": state.best_ask,
                "close": state.last_trade or state.best_ask or state.best_bid,
                "bid_volume": state.bid_volume,
                "ask_volume": state.ask_volume,
            }

            fill = fill_simulator.simulate_fill(
                order=order,
                market_data=market_data,
            )

            if fill:
                order.filled += fill.quantity
                order.remaining -= fill.quantity
                order.status = OrderStatus.FILLED if order.remaining <= 0 else OrderStatus.PARTIAL_FILL
                order.filled_at = datetime.now(UTC)
                fills.append(fill)

                if order.remaining > 0:
                    remaining_pending.append(order)
            else:
                if order.order_type == "MARKET":
                    # Market orders should always fill; force fill at market price
                    fallback_price = market_data.get("close", order.price)
                    fallback_fill = FillEvent(
                        order_id=order.order_id,
                        instrument_id=order.instrument_id,
                        side=order.side,
                        quantity=order.remaining,
                        price=fallback_price,
                        commission=fill_simulator.cost_model.compute(order.side, fallback_price, order.remaining),
                    )
                    order.filled += fallback_fill.quantity
                    order.remaining = 0
                    order.status = OrderStatus.FILLED
                    order.filled_at = datetime.now(UTC)
                    fills.append(fallback_fill)
                else:
                    remaining_pending.append(order)
                    order.status = OrderStatus.QUEUED

        self._pending = remaining_pending
        return fills

    def get_order(self, order_id: str) -> ActiveOrder | None:
        return self._orders.get(order_id)

    def active_orders(self) -> list[ActiveOrder]:
        return [
            o
            for o in self._orders.values()
            if o.status in (OrderStatus.NEW, OrderStatus.SUBMITTED, OrderStatus.QUEUED, OrderStatus.PARTIAL_FILL)
        ]

    def filled_orders(self) -> list[ActiveOrder]:
        return [o for o in self._orders.values() if o.status == OrderStatus.FILLED]

    def reset(self) -> None:
        self._orders.clear()
        self._pending.clear()
