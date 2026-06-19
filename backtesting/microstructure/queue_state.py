from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from backtesting.types import FillEvent


class SimulatedOrderStatus(StrEnum):
    ACTIVE = "active"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"


@dataclass
class SimulatedOrder:
    order_id: str
    side: str
    price: float
    quantity: int
    remaining: int = 0
    queue_ahead: int = 0
    entry_time: float = 0.0
    status: SimulatedOrderStatus = SimulatedOrderStatus.ACTIVE
    instrument_id: str = ""

    def __post_init__(self) -> None:
        if self.remaining == 0:
            self.remaining = self.quantity

    @property
    def fill_ratio(self) -> float:
        return 1.0 - (self.remaining / max(self.quantity, 1))

    def update_queue_position(self, trade_volume: int, cancel_volume: int) -> bool:
        reduction = trade_volume + cancel_volume
        self.queue_ahead = max(0, self.queue_ahead - reduction)
        if self.queue_ahead <= 0 and self.remaining > 0:
            return True
        return False


@dataclass
class QueueState:
    instrument_id: str = ""
    bid_queue_volume: int = 0
    ask_queue_volume: int = 0
    bid_trade_flow: int = 0
    ask_trade_flow: int = 0
    cancel_rate_bid: float = 0.0
    cancel_rate_ask: float = 0.0
    queue_decay: float = 0.0
    prev_bid_volume: int = 0
    prev_ask_volume: int = 0
    bids: list[SimulatedOrder] = field(default_factory=list)
    asks: list[SimulatedOrder] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_bid_volume(self) -> int:
        return sum(o.remaining for o in self.bids if o.status == SimulatedOrderStatus.ACTIVE)

    @property
    def total_ask_volume(self) -> int:
        return sum(o.remaining for o in self.asks if o.status == SimulatedOrderStatus.ACTIVE)

    def add_order(self, order: SimulatedOrder) -> None:
        if order.side == "buy":
            order.queue_ahead = self.total_bid_volume
            self.bids.append(order)
            self.bid_queue_volume += order.remaining
        else:
            order.queue_ahead = self.total_ask_volume
            self.asks.append(order)
            self.ask_queue_volume += order.remaining

    def update_from_trade(self, trade_volume: int, trade_price: float, side: str) -> list[FillEvent]:
        fills: list[FillEvent] = []
        target_orders = self.bids if side == "buy" else self.asks
        remaining_trade = trade_volume

        for order in target_orders:
            if order.status != SimulatedOrderStatus.ACTIVE or order.remaining <= 0:
                continue
            order.queue_ahead = max(0, order.queue_ahead - remaining_trade)
            if order.queue_ahead <= 0:
                fill_qty = min(order.remaining, remaining_trade)
                fill = FillEvent(
                    order_id=order.order_id,
                    instrument_id=order.instrument_id,
                    side=order.side,
                    quantity=fill_qty,
                    price=trade_price,
                    commission=0.0,
                )
                fills.append(fill)
                order.remaining -= fill_qty
                remaining_trade -= fill_qty
                if order.remaining <= 0:
                    order.status = SimulatedOrderStatus.FILLED
                else:
                    order.status = SimulatedOrderStatus.PARTIAL
            if remaining_trade <= 0:
                break

        if side == "buy":
            self.bid_trade_flow += trade_volume
            self.bid_queue_volume = self.total_bid_volume
        else:
            self.ask_trade_flow += trade_volume
            self.ask_queue_volume = self.total_ask_volume

        return fills

    def estimate_cancel_volume(self, current_volume: int, trade_volume: int, side: str) -> int:
        prev = self.prev_bid_volume if side == "buy" else self.prev_ask_volume
        delta = prev - current_volume
        cancel = max(0, delta - trade_volume)
        return cancel

    def snapshot(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "bid_queue_volume": self.bid_queue_volume,
            "ask_queue_volume": self.ask_queue_volume,
            "bid_trade_flow": self.bid_trade_flow,
            "ask_trade_flow": self.ask_trade_flow,
            "cancel_rate_bid": self.cancel_rate_bid,
            "cancel_rate_ask": self.cancel_rate_ask,
            "active_bids": sum(1 for o in self.bids if o.status == SimulatedOrderStatus.ACTIVE),
            "active_asks": sum(1 for o in self.asks if o.status == SimulatedOrderStatus.ACTIVE),
        }
