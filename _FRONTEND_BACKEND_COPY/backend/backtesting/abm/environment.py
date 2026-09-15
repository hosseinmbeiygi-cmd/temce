from __future__ import annotations

from datetime import datetime
from typing import Any

from backtesting.abm.matching_engine import MatchingEngine
from backtesting.abm.order_book import OrderBook, OrderBookEntry, OrderSide, OrderType, Trade


class MarketEnvironment:
    def __init__(self, matching_engine: MatchingEngine | None = None) -> None:
        self.orderbook = OrderBook()
        self.matching_engine = matching_engine or MatchingEngine()
        self._price_history: list[float] = []
        self._current_time: datetime | None = None

    @property
    def last_price(self) -> float:
        return self.orderbook.last_price

    @property
    def best_bid(self) -> float:
        return self.orderbook.best_bid

    @property
    def best_ask(self) -> float:
        return self.orderbook.best_ask

    @property
    def mid_price(self) -> float:
        return self.orderbook.midpoint

    @property
    def spread(self) -> float:
        return self.orderbook.spread

    @property
    def bid_volume(self) -> int:
        return self.orderbook.bid_volume

    @property
    def ask_volume(self) -> int:
        return self.orderbook.ask_volume

    @property
    def trades(self) -> list[Trade]:
        return self.orderbook.trades

    @property
    def price_history(self) -> list[float]:
        return list(self._price_history)

    def submit_order(
        self,
        side: str,
        price: float,
        quantity: int,
        order_type: str = "LIMIT",
        agent_id: str = "",
    ) -> list[Trade]:
        entry = OrderBookEntry(
            order_id="",
            side=OrderSide(side.upper()),
            price=price,
            quantity=quantity,
            order_type=OrderType(order_type.upper()),
            agent_id=agent_id,
        )
        trades = self.matching_engine.match(entry, self.orderbook)
        if entry.remaining > 0 and entry.order_type == OrderType.LIMIT:
            self.orderbook.add_order(entry)
        if trades:
            self._price_history.append(trades[-1].price)
        return trades

    def submit_market_order(self, side: str, quantity: int, agent_id: str = "") -> list[Trade]:
        price = self.best_ask if side.upper() == "BUY" else self.best_bid
        if price <= 0:
            return []
        return self.submit_order(side, price, quantity, "MARKET", agent_id)

    def cancel_order(self, order_id: str, side: str) -> None:
        self.orderbook.remove_order(order_id, OrderSide(side.upper()))

    def snapshot(self) -> dict[str, Any]:
        snap = self.orderbook.snapshot()
        snap["price_history_len"] = len(self._price_history)
        return snap

    def reset(self) -> None:
        self.orderbook.reset()
        self._price_history.clear()
