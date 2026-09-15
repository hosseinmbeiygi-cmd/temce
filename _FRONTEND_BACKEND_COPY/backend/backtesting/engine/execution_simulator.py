from __future__ import annotations

from datetime import UTC, datetime

from backtesting.engine.cash_manager import CashManager
from backtesting.engine.commission import CommissionModel
from backtesting.engine.slippage import SlippageModel
from backtesting.types import FillEvent, OrderEvent
from core.ids import new_id
from domain.common.enum_types import OrderSide


class ExecutionSimulator:
    def __init__(self, slippage: SlippageModel, commission: CommissionModel) -> None:
        self.slippage = slippage
        self.commission = commission

    def execute(self, order: OrderEvent, cash_manager: CashManager) -> FillEvent | None:
        if order.side == OrderSide.BUY:
            cost = order.price * order.quantity
            if not cash_manager.can_afford(cost):
                return None
            cash_manager.withdraw(cost, f"buy {order.instrument_id}")
        exec_price = self.slippage.get_execution_price(order.price, order.side, order.quantity)
        commission_amount = self.commission.compute_for_order(order, exec_price, order.quantity)

        fill = FillEvent(
            order_id=order.order_id or new_id("fill"),
            instrument_id=order.instrument_id,
            side=order.side,
            quantity=order.quantity,
            price=exec_price,
            commission=commission_amount,
            timestamp=datetime.now(UTC),
        )
        return fill
