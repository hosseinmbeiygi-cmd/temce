from __future__ import annotations

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
        # Pass the order's ADV through: without it VOLUME_BASED slippage silently
        # fell back to fixed+volatility (its volume branch needs adv > 0).
        adv = int(getattr(order, "daily_volume", None) or 0)
        exec_price = self.slippage.get_execution_price(
            order.price, order.side, order.quantity, adv=adv,
        )
        commission_amount = self.commission.compute_for_order(order, exec_price, order.quantity)

        # Affordability is checked here but cash is moved exactly once, by
        # ``PortfolioAccounting.apply_fill``. Withdrawing here as well charged
        # the principal twice and understated every long backtest's cash.
        if order.side == OrderSide.BUY:
            required = exec_price * order.quantity + commission_amount
            if not cash_manager.can_afford(required):
                return None

        fill = FillEvent(
            order_id=order.order_id or new_id("fill"),
            instrument_id=order.instrument_id,
            side=order.side,
            quantity=order.quantity,
            price=exec_price,
            commission=commission_amount,
            # Simulated time of the bar being traded, not wall clock.
            timestamp=order.timestamp,
        )
        return fill
