from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from domain.common.enum_types import OrderSide


@dataclass
class OrderBookEntry:
    order_id: str
    side: OrderSide
    price: float
    quantity: int
    remaining: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class OrderMatchingEngine:
    def __init__(self) -> None:
        self._bids: list[OrderBookEntry] = []
        self._asks: list[OrderBookEntry] = []
        self._trades: list[dict[str, Any]] = []
        self._last_price: float = 0.0

    def add_order(self, entry: OrderBookEntry) -> list[dict[str, Any]]:
        if entry.side == OrderSide.BUY:
            self._bids.append(entry)
            self._bids.sort(key=lambda o: o.price, reverse=True)
            return self._match()
        else:
            self._asks.append(entry)
            self._asks.sort(key=lambda o: o.price)
            return self._match()

    def _match(self) -> list[dict[str, Any]]:
        trades: list[dict[str, Any]] = []
        while self._bids and self._asks:
            best_bid = self._bids[0]
            best_ask = self._asks[0]
            if best_bid.price < best_ask.price:
                break
            trade_price = best_ask.price
            trade_qty = min(best_bid.remaining, best_ask.remaining)
            trade = {
                "buy_order_id": best_bid.order_id,
                "sell_order_id": best_ask.order_id,
                "price": trade_price,
                "quantity": trade_qty,
                "timestamp": datetime.now(UTC),
            }
            trades.append(trade)
            self._trades.append(trade)
            self._last_price = trade_price
            best_bid.remaining -= trade_qty
            best_ask.remaining -= trade_qty
            if best_bid.remaining <= 0:
                self._bids.pop(0)
            if best_ask.remaining <= 0:
                self._asks.pop(0)
        return trades

    def get_last_price(self) -> float:
        return self._last_price

    def get_order_book_depth(self, levels: int = 5) -> dict[str, list[tuple[float, int]]]:
        bids = [(o.price, o.remaining) for o in self._bids[:levels]]
        asks = [(o.price, o.remaining) for o in self._asks[:levels]]
        return {"bids": bids, "asks": asks}

    def reset(self) -> None:
        self._bids.clear()
        self._asks.clear()
        self._trades.clear()
        self._last_price = 0.0
