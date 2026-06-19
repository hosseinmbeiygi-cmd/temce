from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


@dataclass
class OrderBookEntry:
    order_id: str
    side: OrderSide
    price: float
    quantity: int
    remaining: int = 0
    order_type: OrderType = OrderType.LIMIT
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    agent_id: str = ""

    def __post_init__(self) -> None:
        if self.remaining == 0:
            self.remaining = self.quantity

    def __lt__(self, other: OrderBookEntry) -> bool:
        if self.side == OrderSide.BUY:
            if self.price != other.price:
                return self.price > other.price
        else:
            if self.price != other.price:
                return self.price < other.price
        return self.timestamp < other.timestamp


@dataclass
class Trade:
    buy_order_id: str
    sell_order_id: str
    price: float
    quantity: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    buyer_id: str = ""
    seller_id: str = ""


class OrderBook:
    def __init__(self) -> None:
        self._bids: list[OrderBookEntry] = []
        self._asks: list[OrderBookEntry] = []
        self._trades: list[Trade] = []
        self._buy_map: dict[str, OrderBookEntry] = {}
        self._sell_map: dict[str, OrderBookEntry] = {}
        self._entry_id_counter = 0

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
    def bid_volume(self) -> int:
        return sum(e.remaining for e in self._bids if e.remaining > 0)

    @property
    def ask_volume(self) -> int:
        return sum(e.remaining for e in self._asks if e.remaining > 0)

    @property
    def last_price(self) -> float:
        return self._trades[-1].price if self._trades else 0.0

    @property
    def spread(self) -> float:
        bid = self.best_bid
        ask = self.best_ask
        if bid > 0 and ask > 0:
            return ask - bid
        return 0.0

    @property
    def midpoint(self) -> float:
        bid = self.best_bid
        ask = self.best_ask
        if bid > 0 and ask > 0:
            return (bid + ask) / 2.0
        return bid or ask

    @property
    def trades(self) -> list[Trade]:
        return list(self._trades)

    def add_order(self, entry: OrderBookEntry) -> str:
        self._entry_id_counter += 1
        order_id = f"order_{self._entry_id_counter}"
        entry.order_id = order_id
        if entry.side == OrderSide.BUY:
            heapq.heappush(self._bids, entry)
            self._buy_map[order_id] = entry
        else:
            heapq.heappush(self._asks, entry)
            self._sell_map[order_id] = entry
        return order_id

    def remove_order(self, order_id: str, side: OrderSide) -> None:
        target_map = self._buy_map if side == OrderSide.BUY else self._sell_map
        if order_id in target_map:
            target_map[order_id].remaining = 0
            del target_map[order_id]

    def get_bids(self, depth: int = 10) -> list[tuple[float, int]]:
        levels: dict[float, int] = {}
        for e in self._bids:
            if e.remaining <= 0:
                continue
            levels[e.price] = levels.get(e.price, 0) + e.remaining
        sorted_levels = sorted(levels.items(), key=lambda x: -x[0])
        return sorted_levels[:depth]

    def get_asks(self, depth: int = 10) -> list[tuple[float, int]]:
        levels: dict[float, int] = {}
        for e in self._asks:
            if e.remaining <= 0:
                continue
            levels[e.price] = levels.get(e.price, 0) + e.remaining
        sorted_levels = sorted(levels.items(), key=lambda x: x[0])
        return sorted_levels[:depth]

    def snapshot(self) -> dict[str, Any]:
        return {
            "best_bid": self.best_bid,
            "best_ask": self.best_ask,
            "bid_volume": self.bid_volume,
            "ask_volume": self.ask_volume,
            "spread": self.spread,
            "midpoint": self.midpoint,
            "last_price": self.last_price,
            "trade_count": len(self._trades),
            "bids": self.get_bids(5),
            "asks": self.get_asks(5),
        }

    def reset(self) -> None:
        self._bids.clear()
        self._asks.clear()
        self._trades.clear()
        self._buy_map.clear()
        self._sell_map.clear()
        self._entry_id_counter = 0
