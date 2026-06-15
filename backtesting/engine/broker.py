from __future__ import annotations

from backtesting.types import FillEvent, OrderEvent
from core.ids import new_id


class Broker:
    def __init__(self, commission_pct: float = 0.0035, slippage_bps: float = 10.0) -> None:
        self.commission_pct = commission_pct
        self.slippage_bps = slippage_bps

    async def submit_order(self, order: OrderEvent) -> FillEvent | None:
        slippage = order.price * (self.slippage_bps / 10000) if order.price > 0 else 0
        exec_price = order.price + slippage if order.side == "buy" else order.price - slippage
        commission = exec_price * order.quantity * self.commission_pct

        return FillEvent(
            order_id=order.order_id or new_id("ord"),
            instrument_id=order.instrument_id,
            side=order.side,
            quantity=order.quantity,
            price=exec_price,
            commission=commission,
            slippage=slippage,
        )
