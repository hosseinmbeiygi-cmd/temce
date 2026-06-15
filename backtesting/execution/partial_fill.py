from __future__ import annotations

from dataclasses import dataclass, field

from backtesting.execution.order_models import Order
from backtesting.types import FillEvent
from core.ids import new_id


@dataclass
class PartialFillHandler:
    min_fill_pct: float = 0.1
    fill_steps: list[float] = field(default_factory=lambda: [0.25, 0.5, 1.0])

    def process(self, order: Order, available_liquidity: int) -> list[FillEvent]:
        fills: list[FillEvent] = []
        remaining = order.quantity
        if available_liquidity < remaining * self.min_fill_pct:
            return fills
        fill_qty = min(remaining, available_liquidity)
        fill = FillEvent(
            order_id=order.order_id or new_id("fill"),
            instrument_id=order.instrument_id,
            side=order.side,
            quantity=fill_qty,
            price=order.price,
            commission=0.0,
        )
        fills.append(fill)
        return fills
