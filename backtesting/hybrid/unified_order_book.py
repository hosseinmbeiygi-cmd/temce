from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from backtesting.types import OrderEvent


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


@dataclass
class OrderBookLevel:
    price: float
    volume: int
    orders: int = 0
    source_breakdown: dict[str, int] = field(default_factory=lambda: {"historical": 0, "strategy": 0, "agent": 0})


@dataclass
class HybridOrderEntry:
    order_id: str
    side: OrderSide
    price: float
    quantity: int
    remaining: int = 0
    order_type: OrderType = OrderType.LIMIT
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str = "historical"  # historical, strategy, agent
    agent_id: str = ""

    def __post_init__(self) -> None:
        if self.remaining == 0:
            self.remaining = self.quantity

    def __lt__(self, other: HybridOrderEntry) -> bool:
        if self.side == OrderSide.BUY:
            if self.price != other.price:
                return self.price > other.price
        else:
            if self.price != other.price:
                return self.price < other.price
        return self.timestamp < other.timestamp


@dataclass
class HybridTrade:
    buy_order_id: str
    sell_order_id: str
    price: float
    quantity: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    buyer_source: str = ""
    seller_source: str = ""


class UnifiedOrderBook:
    """Unified order book that combines real, strategy, and synthetic agent orders."""

    def __init__(self) -> None:
        self._bids: list[HybridOrderEntry] = []
        self._asks: list[HybridOrderEntry] = []
        self._trades: list[HybridTrade] = []
        self._buy_map: dict[str, HybridOrderEntry] = {}
        self._sell_map: dict[str, HybridOrderEntry] = {}
        self._entry_counter = 0

    @property
    def best_bid(self) -> float:
        while self._bids and self._bids[0].remaining <= 0:
            heapq.heappop(self._bids)
        return self._bids[0].price if self._bids else 0.0

    @property
    def best_ask(self) -> float:
        while self._asks and self._asks[0].remaining <= 0:
            heapq.heappop(self._asks)
        return self._asks[0].price if self._asks else 0.0

    @property
    def mid_price(self) -> float:
        bid = self.best_bid
        ask = self.best_ask
        if bid > 0 and ask > 0:
            return (bid + ask) / 2.0
        return bid or ask

    @property
    def spread(self) -> float:
        bid = self.best_bid
        ask = self.best_ask
        if bid > 0 and ask > 0:
            return ask - bid
        return 0.0

    @property
    def last_price(self) -> float:
        return self._trades[-1].price if self._trades else 0.0

    @property
    def trades(self) -> list[HybridTrade]:
        return list(self._trades)

    @property
    def bid_volume(self) -> int:
        return sum(e.remaining for e in self._bids if e.remaining > 0)

    @property
    def ask_volume(self) -> int:
        return sum(e.remaining for e in self._asks if e.remaining > 0)

    def add_order(self, order: OrderEvent, source: str = "strategy") -> str:
        """Add an order to the book from any source."""
        self._entry_counter += 1
        order_id = f"hybrid_{source}_{self._entry_counter}"
        side = OrderSide(order.side.upper())
        otype = OrderType(order.order_type.upper()) if order.order_type else OrderType.LIMIT
        entry = HybridOrderEntry(
            order_id=order_id,
            side=side,
            price=order.price,
            quantity=order.quantity,
            remaining=order.quantity,
            order_type=otype,
            source=source,
        )
        if side == OrderSide.BUY:
            heapq.heappush(self._bids, entry)
            self._buy_map[order_id] = entry
        else:
            heapq.heappush(self._asks, entry)
            self._sell_map[order_id] = entry
        return order_id

    def match_order(self, order: OrderEvent, source: str = "strategy") -> list[HybridTrade]:
        """Match an incoming order against the book and return resulting trades."""
        trades: list[HybridTrade] = []
        remaining = order.quantity
        side = OrderSide(order.side.upper())

        if side == OrderSide.BUY:
            while remaining > 0:
                best = self.best_ask
                if best <= 0 or (order.order_type and order.order_type.upper() == "LIMIT" and best > order.price):
                    break
                if not self._asks:
                    break
                ask_entry = self._asks[0]
                if ask_entry.remaining <= 0:
                    heapq.heappop(self._asks)
                    continue
                matched = min(remaining, ask_entry.remaining)
                trade = HybridTrade(
                    buy_order_id=f"incoming_{self._entry_counter}",
                    sell_order_id=ask_entry.order_id,
                    price=ask_entry.price,
                    quantity=matched,
                    buyer_source=source,
                    seller_source=ask_entry.source,
                )
                trades.append(trade)
                remaining -= matched
                ask_entry.remaining -= matched
                if ask_entry.remaining <= 0:
                    heapq.heappop(self._asks)
        else:
            while remaining > 0:
                best = self.best_bid
                if best <= 0 or (order.order_type and order.order_type.upper() == "LIMIT" and best < order.price):
                    break
                if not self._bids:
                    break
                bid_entry = self._bids[0]
                if bid_entry.remaining <= 0:
                    heapq.heappop(self._bids)
                    continue
                matched = min(remaining, bid_entry.remaining)
                trade = HybridTrade(
                    buy_order_id=bid_entry.order_id,
                    sell_order_id=f"incoming_{self._entry_counter}",
                    price=bid_entry.price,
                    quantity=matched,
                    buyer_source=bid_entry.source,
                    seller_source=source,
                )
                trades.append(trade)
                remaining -= matched
                bid_entry.remaining -= matched
                if bid_entry.remaining <= 0:
                    heapq.heappop(self._bids)

        self._trades.extend(trades)
        self._entry_counter += 1
        return trades

    def get_depth(self, levels: int = 10) -> dict[str, list[tuple[float, int, dict[str, int]]]]:
        """Get order book depth with source breakdown."""
        bid_levels: dict[float, tuple[int, dict[str, int]]] = {}
        ask_levels: dict[float, tuple[int, dict[str, int]]] = {}

        for e in self._bids:
            if e.remaining <= 0:
                continue
            vol, breakdown = bid_levels.get(e.price, (0, {}))
            bid_levels[e.price] = (vol + e.remaining, {**breakdown, e.source: breakdown.get(e.source, 0) + e.remaining})

        for e in self._asks:
            if e.remaining <= 0:
                continue
            vol, breakdown = ask_levels.get(e.price, (0, {}))
            ask_levels[e.price] = (vol + e.remaining, {**breakdown, e.source: breakdown.get(e.source, 0) + e.remaining})

        return {
            "bids": [(price, vol, breakdown) for price, (vol, breakdown) in sorted(bid_levels.items(), reverse=True)[:levels]],
            "asks": [(price, vol, breakdown) for price, (vol, breakdown) in sorted(ask_levels.items())[:levels]],
        }

    def get_source_mix(self) -> dict[str, float]:
        """Get the proportion of volume by source."""
        volumes: dict[str, float] = {"historical": 0.0, "strategy": 0.0, "agent": 0.0}
        for e in self._bids:
            if e.remaining > 0:
                volumes[e.source] = volumes.get(e.source, 0.0) + e.remaining
        for e in self._asks:
            if e.remaining > 0:
                volumes[e.source] = volumes.get(e.source, 0.0) + e.remaining
        total = sum(volumes.values()) or 1.0
        return {k: v / total for k, v in volumes.items()}

    def snapshot(self) -> dict[str, Any]:
        return {
            "best_bid": self.best_bid,
            "best_ask": self.best_ask,
            "mid_price": self.mid_price,
            "spread": self.spread,
            "last_price": self.last_price,
            "bid_volume": self.bid_volume,
            "ask_volume": self.ask_volume,
            "trade_count": len(self._trades),
            "source_mix": self.get_source_mix(),
        }

    def reset(self) -> None:
        self._bids.clear()
        self._asks.clear()
        self._trades.clear()
        self._buy_map.clear()
        self._sell_map.clear()
        self._entry_counter = 0
