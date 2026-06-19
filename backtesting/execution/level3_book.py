from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from core.ids import new_id
from core.logging import get_logger

logger = get_logger(__name__)


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


@dataclass
class BookOrder:
    """Individual order in the Level-3 book (price-time priority)."""
    order_id: str
    side: OrderSide
    price: float
    quantity: int
    remaining: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    agent_id: str = ""
    source: str = "strategy"
    is_hidden: bool = False
    display_quantity: int = 0
    total_quantity: int = 0

    def __post_init__(self) -> None:
        if self.remaining == 0:
            self.remaining = self.quantity
        if self.total_quantity == 0:
            self.total_quantity = self.quantity
        if self.display_quantity == 0:
            self.display_quantity = self.quantity

    @property
    def is_filled(self) -> bool:
        return self.remaining <= 0

    @property
    def fill_ratio(self) -> float:
        return 1.0 - (self.remaining / max(self.total_quantity, 1))

    def reduce(self, qty: int) -> int:
        """Reduce remaining quantity by qty, return actual reduction."""
        reduction = min(self.remaining, qty)
        self.remaining -= reduction
        return reduction


@dataclass
class PriceLevel:
    """FIFO queue of orders at a single price level."""
    price: float
    orders: deque[BookOrder] = field(default_factory=deque)
    total_volume: int = 0

    def add_order(self, order: BookOrder) -> None:
        self.orders.append(order)
        self.total_volume += order.remaining

    def remove_order(self, order_id: str) -> BookOrder | None:
        for i, o in enumerate(self.orders):
            if o.order_id == order_id:
                self.total_volume -= o.remaining
                return self.orders[i]
        return None

    def remove_and_rebuild(self, order_id: str) -> bool:
        """Remove an order by rebuilding the deque (for non-front orders)."""
        found = False
        new_orders: deque[BookOrder] = deque()
        for o in self.orders:
            if o.order_id == order_id:
                self.total_volume -= o.remaining
                found = True
            else:
                new_orders.append(o)
        self.orders = new_orders
        return found

    @property
    def volume_ahead(self, target_order_id: str) -> int:
        """Compute total volume ahead of the target order in the FIFO queue."""
        vol = 0
        for o in self.orders:
            if o.order_id == target_order_id:
                break
            vol += o.remaining
        return vol

    @property
    def front_order(self) -> BookOrder | None:
        return self.orders[0] if self.orders else None

    @property
    def is_empty(self) -> bool:
        return not self.orders

    def clean(self) -> None:
        """Remove filled/cancelled orders from front of queue."""
        while self.orders and self.orders[0].remaining <= 0:
            done = self.orders.popleft()
            self.total_volume -= done.remaining if done.remaining > 0 else 0

    def snapshot(self) -> dict[str, Any]:
        return {
            "price": self.price,
            "volume": self.total_volume,
            "order_count": len(self.orders),
        }


@dataclass
class IcebergOrder(BookOrder):
    """An iceberg order that only shows a portion of its total size."""
    peak_size: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.peak_size == 0:
            self.peak_size = self.display_quantity
        self.display_quantity = min(self.peak_size, self.remaining)

    def refresh_peak(self) -> None:
        """Replenish the visible peak when it's fully consumed."""
        if self.remaining > 0:
            self.display_quantity = min(self.peak_size, self.remaining)


class Level3OrderBook:
    """Full Level-3 order book with individual order tracking and FIFO per price level.

    Structure:
    - Price levels (bids/asks)
    - Each level has a FIFO deque of individual orders
    - Order index for O(1) lookup by order_id
    - Supports market orders, limit orders, cancels
    """

    def __init__(self) -> None:
        self._bids: dict[float, PriceLevel] = {}  # price → level
        self._asks: dict[float, PriceLevel] = {}
        self._order_index: dict[str, BookOrder] = {}
        self._trade_log: list[dict[str, Any]] = []
        self._entry_counter: int = 0

    # ── Order Insertion ─────────────────────────────────

    def add_limit_order(
        self,
        side: str,
        price: float,
        quantity: int,
        agent_id: str = "",
        source: str = "strategy",
        is_hidden: bool = False,
    ) -> BookOrder:
        """Add a limit order to the book.

        Returns:
            The created BookOrder
        """
        self._entry_counter += 1
        side_enum = OrderSide(side.upper())
        order = BookOrder(
            order_id=new_id("l3"),
            side=side_enum,
            price=price,
            quantity=quantity,
            remaining=quantity,
            agent_id=agent_id,
            source=source,
            is_hidden=is_hidden,
        )
        levels = self._bids if side_enum == OrderSide.BUY else self._asks

        if price not in levels:
            levels[price] = PriceLevel(price=price)
        levels[price].add_order(order)
        self._order_index[order.order_id] = order
        return order

    def add_iceberg_order(
        self,
        side: str,
        price: float,
        total_quantity: int,
        peak_size: int,
        agent_id: str = "",
    ) -> IcebergOrder:
        """Add an iceberg order that only shows peak_size at a time."""
        self._entry_counter += 1
        side_enum = OrderSide(side.upper())
        order = IcebergOrder(
            order_id=new_id("iceberg"),
            side=side_enum,
            price=price,
            quantity=total_quantity,
            remaining=total_quantity,
            agent_id=agent_id,
            source="iceberg",
            peak_size=peak_size,
        )
        levels = self._bids if side_enum == OrderSide.BUY else self._asks
        if price not in levels:
            levels[price] = PriceLevel(price=price)
        levels[price].add_order(order)
        self._order_index[order.order_id] = order
        return order

    # ── Matching ────────────────────────────────────────

    def execute_market_order(self, side: str, quantity: int, agent_id: str = "") -> list[dict[str, Any]]:
        """Execute a market order against the book.

        Args:
            side: 'buy' or 'sell'
            quantity: Order size

        Returns:
            List of fills [{'price': ..., 'quantity': ..., 'order_id': ...}]
        """
        fills: list[dict[str, Any]] = []
        remaining = quantity
        levels = self._asks if side.upper() == "BUY" else self._bids
        sorted_prices = sorted(levels.keys(), reverse=(side.upper() != "BUY"))

        for price in sorted_prices:
            if remaining <= 0:
                break
            level = levels[price]
            level.clean()
            while level.orders and remaining > 0:
                top = level.orders[0]
                trade_qty = min(top.remaining, remaining)
                top.remaining -= trade_qty
                level.total_volume -= trade_qty
                remaining -= trade_qty

                fill = {
                    "price": price,
                    "quantity": trade_qty,
                    "order_id": top.order_id,
                    "side": side,
                    "aggressive": True,
                }
                fills.append(fill)
                self._trade_log.append(fill)

                if top.remaining <= 0:
                    level.orders.popleft()
                    # Refresh iceberg if applicable
                    if isinstance(top, IcebergOrder) and top.total_quantity > 0:
                        top.refresh_peak()
                        if top.remaining > 0:
                            level.orders.append(top)  # new slice goes to back of queue (loses time priority)

            if level.is_empty:
                del levels[price]

        return fills

    def process_limit_order(self, side: str, price: float, quantity: int) -> list[dict[str, Any]]:
        """Process a limit order: match if possible, otherwise add to book."""
        if side.upper() == "BUY":
            best_ask = self.best_ask
            if best_ask > 0 and price >= best_ask:
                return self.execute_market_order("buy", quantity)
        else:
            best_bid = self.best_bid
            if best_bid > 0 and price <= best_bid:
                return self.execute_market_order("sell", quantity)

        order = self.add_limit_order(side, price, quantity)
        return [{"order_id": order.order_id, "status": "queued", "price": price, "quantity": quantity}]

    # ── Cancellation ────────────────────────────────────

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order by ID.

        Returns:
            True if order was found and cancelled
        """
        order = self._order_index.get(order_id)
        if order is None:
            return False

        levels = self._bids if order.side == OrderSide.BUY else self._asks
        level = levels.get(order.price)
        if level:
            level.remove_and_rebuild(order_id)
            if level.is_empty:
                del levels[order.price]

        del self._order_index[order_id]
        return True

    # ── Query ───────────────────────────────────────────

    @property
    def best_bid(self) -> float:
        bids = sorted(self._bids.keys(), reverse=True)
        for price in bids:
            level = self._bids[price]
            level.clean()
            if not level.is_empty:
                return price
            del self._bids[price]
        return 0.0

    @property
    def best_ask(self) -> float:
        asks = sorted(self._asks.keys())
        for price in asks:
            level = self._asks[price]
            level.clean()
            if not level.is_empty:
                return price
            del self._asks[price]
        return 0.0

    @property
    def spread(self) -> float:
        bid = self.best_bid
        ask = self.best_ask
        return ask - bid if bid > 0 and ask > 0 else 0.0

    @property
    def mid_price(self) -> float:
        bid = self.best_bid
        ask = self.best_ask
        return (bid + ask) / 2 if bid > 0 and ask > 0 else 0.0

    def get_depth(self, levels: int = 10) -> dict[str, list[dict[str, Any]]]:
        """Get aggregated order book depth."""
        bid_levels: list[dict[str, Any]] = []
        for price in sorted(self._bids.keys(), reverse=True)[:levels]:
            level = self._bids[price]
            level.clean()
            if not level.is_empty:
                bid_levels.append(level.snapshot())

        ask_levels: list[dict[str, Any]] = []
        for price in sorted(self._asks.keys())[:levels]:
            level = self._asks[price]
            level.clean()
            if not level.is_empty:
                ask_levels.append(level.snapshot())

        return {"bids": bid_levels, "asks": ask_levels}

    def queue_position(self, order_id: str) -> tuple[int, int] | None:
        """Get (position_in_queue, volume_ahead) for an order.

        Returns:
            Tuple of (index, volume_ahead) or None if order not found
        """
        order = self._order_index.get(order_id)
        if order is None:
            return None
        levels = self._bids if order.side == OrderSide.BUY else self._asks
        level = levels.get(order.price)
        if level is None:
            return None
        vol_ahead = level.volume_ahead(order_id)
        idx = next((i for i, o in enumerate(level.orders) if o.order_id == order_id), -1)
        return (idx, vol_ahead)

    def total_bid_volume(self) -> int:
        return sum(level.total_volume for level in self._bids.values())

    def total_ask_volume(self) -> int:
        return sum(level.total_volume for level in self._asks.values())

    @property
    def trade_count(self) -> int:
        return len(self._trade_log)

    def snapshot(self) -> dict[str, Any]:
        return {
            "best_bid": self.best_bid,
            "best_ask": self.best_ask,
            "spread": self.spread,
            "mid_price": self.mid_price,
            "bid_volume": self.total_bid_volume(),
            "ask_volume": self.total_ask_volume(),
            "trade_count": self.trade_count,
            "depth": self.get_depth(5),
        }

    def reset(self) -> None:
        self._bids.clear()
        self._asks.clear()
        self._order_index.clear()
        self._trade_log.clear()
        self._entry_counter = 0
