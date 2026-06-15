from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from backtesting.execution.order_models import Order
from backtesting.types import FillEvent
from core.ids import new_id


@dataclass
class FillSimulator:
    fill_probability: float = 1.0
    partial_fill_enabled: bool = False

    def simulate_fill(self, order: Order, market_data: dict[str, Any]) -> FillEvent | None:
        import random

        if random.random() > self.fill_probability:
            return None
        price = market_data.get("close", order.price)
        return FillEvent(
            order_id=order.order_id or new_id("fill"),
            instrument_id=order.instrument_id,
            side=order.side,
            quantity=order.quantity,
            price=price,
            commission=0.0,
            timestamp=datetime.now(UTC),
        )
