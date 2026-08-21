from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import StrEnum

from backtesting.costs.iran_costs import DEFAULT_IRAN_COSTS, IranTransactionCosts
from backtesting.types import FillEvent


class OrderState(StrEnum):
    NEW = "NEW"
    SUBMITTED = "SUBMITTED"
    QUEUED = "QUEUED"
    PARTIAL_FILL = "PARTIAL_FILL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class QueuePosition:
    instrument_id: str
    is_buy_side: bool
    price: float
    remaining_quantity: int
    initial_quantity: int
    queue_position: int = 0
    entry_time: float = 0.0
    state: OrderState = OrderState.NEW

    @property
    def fill_ratio(self) -> float:
        return 1.0 - (self.remaining_quantity / max(self.initial_quantity, 1))


@dataclass
class QueueState:
    buy_orders: list[QueuePosition] = field(default_factory=list)
    sell_orders: list[QueuePosition] = field(default_factory=list)
    last_trade_price: float = 0.0
    last_trade_volume: int = 0
    total_buy_volume: int = 0
    total_sell_volume: int = 0


class QueueSimulation:
    def __init__(
        self,
        base_cancel_rate: float = 0.05,
        base_trade_rate: float = 0.3,
        lambda_coeff: float = 0.0001,
        cost_model: IranTransactionCosts = DEFAULT_IRAN_COSTS,
    ) -> None:
        self.base_cancel_rate = base_cancel_rate
        self.base_trade_rate = base_trade_rate
        self.lambda_coeff = lambda_coeff
        self.cost_model = cost_model
        self._queues: dict[str, QueueState] = {}

    def get_or_create_queue(self, instrument_id: str) -> QueueState:
        if instrument_id not in self._queues:
            self._queues[instrument_id] = QueueState()
        return self._queues[instrument_id]

    def add_order(
        self,
        instrument_id: str,
        is_buy: bool,
        price: float,
        quantity: int,
        current_time: float = 0.0,
    ) -> QueuePosition:
        queue = self.get_or_create_queue(instrument_id)
        pos = len(queue.buy_orders if is_buy else queue.sell_orders)
        entry = QueuePosition(
            instrument_id=instrument_id,
            is_buy_side=is_buy,
            price=price,
            remaining_quantity=quantity,
            initial_quantity=quantity,
            queue_position=pos,
            entry_time=current_time,
            state=OrderState.QUEUED,
        )
        if is_buy:
            queue.buy_orders.append(entry)
            queue.total_buy_volume += quantity
        else:
            queue.sell_orders.append(entry)
            queue.total_sell_volume += quantity
        return entry

    def fill_probability(self, volume_at_price: int) -> float:
        return 1.0 - math.exp(-self.lambda_coeff * volume_at_price)

    def simulate_step(
        self,
        instrument_id: str,
        trade_volume: int = 0,
        trade_price: float = 0.0,
    ) -> list[FillEvent]:
        queue = self._queues.get(instrument_id)
        if queue is None:
            return []

        fills: list[FillEvent] = []
        queue.last_trade_price = trade_price
        queue.last_trade_volume = trade_volume

        cancel_rate = self.base_cancel_rate + random.uniform(-0.02, 0.02)
        trade_rate = self.base_trade_rate + random.uniform(-0.05, 0.05)

        queue.buy_orders = self._process_queue_side(
            queue.buy_orders, cancel_rate, trade_rate, trade_volume, fills, is_buy=True
        )
        queue.sell_orders = self._process_queue_side(
            queue.sell_orders, cancel_rate, trade_rate, trade_volume, fills, is_buy=False
        )
        queue.total_buy_volume = sum(o.remaining_quantity for o in queue.buy_orders)
        queue.total_sell_volume = sum(o.remaining_quantity for o in queue.sell_orders)

        return fills

    def _process_queue_side(
        self,
        orders: list[QueuePosition],
        cancel_rate: float,
        trade_rate: float,
        trade_volume: int,
        fills: list[FillEvent],
        is_buy: bool,
    ) -> list[QueuePosition]:
        remaining: list[QueuePosition] = []
        for order in orders:
            if order.state in (OrderState.FILLED, OrderState.CANCELLED):
                continue

            if random.random() < cancel_rate:
                order.state = OrderState.CANCELLED
                continue

            fill_prob = self.fill_probability(order.remaining_quantity)
            fill_prob = min(fill_prob * trade_rate, 1.0)

            if random.random() < fill_prob:
                fill_qty = min(order.remaining_quantity, max(1, int(trade_volume * random.uniform(0.1, 1.0))))
                fill = FillEvent(
                    order_id="queue_fill",
                    instrument_id=order.instrument_id,
                    side="buy" if is_buy else "sell",
                    quantity=fill_qty,
                    price=order.price,
                    commission=self.cost_model.compute("buy" if is_buy else "sell", order.price, fill_qty),
                )
                fills.append(fill)
                order.remaining_quantity -= fill_qty
                if order.remaining_quantity <= 0:
                    order.state = OrderState.FILLED
                    continue
                order.state = OrderState.PARTIAL_FILL

            remaining.append(order)
        return remaining

    def get_queue_depth(self, instrument_id: str) -> tuple[int, int]:
        queue = self._queues.get(instrument_id)
        if queue is None:
            return (0, 0)
        return (queue.total_buy_volume, queue.total_sell_volume)

    def reset(self) -> None:
        self._queues.clear()
