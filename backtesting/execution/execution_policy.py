from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backtesting.costs.iran_costs import DEFAULT_IRAN_COSTS, IranTransactionCosts
from backtesting.execution.order_models import Order
from backtesting.types import FillEvent
from domain.common.enum_types import OrderSide


class ExecutionPolicy(ABC):
    @abstractmethod
    def execute(self, order: Order, market_data: dict[str, Any]) -> FillEvent | None: ...


class MarketExecutionPolicy(ExecutionPolicy):
    def __init__(self, cost_model: IranTransactionCosts = DEFAULT_IRAN_COSTS) -> None:
        self.cost_model = cost_model

    def execute(self, order: Order, market_data: dict[str, Any]) -> FillEvent | None:
        price = market_data.get("close", order.price)
        return FillEvent(
            order_id=order.order_id,
            instrument_id=order.instrument_id,
            side=order.side,
            quantity=order.quantity,
            price=price,
            commission=self.cost_model.compute(order.side, price, order.quantity),
        )


class LimitExecutionPolicy(ExecutionPolicy):
    def __init__(self, cost_model: IranTransactionCosts = DEFAULT_IRAN_COSTS) -> None:
        self.cost_model = cost_model

    def execute(self, order: Order, market_data: dict[str, Any]) -> FillEvent | None:
        high = market_data.get("high", order.price)
        low = market_data.get("low", order.price)
        if order.side == OrderSide.BUY and low <= order.price:
            fill_price = min(order.price, high)
            return FillEvent(
                order_id=order.order_id,
                instrument_id=order.instrument_id,
                side=order.side,
                quantity=order.quantity,
                price=fill_price,
                commission=self.cost_model.compute(order.side, fill_price, order.quantity),
            )
        if order.side == OrderSide.SELL and high >= order.price:
            fill_price = max(order.price, low)
            return FillEvent(
                order_id=order.order_id,
                instrument_id=order.instrument_id,
                side=order.side,
                quantity=order.quantity,
                price=fill_price,
                commission=self.cost_model.compute(order.side, fill_price, order.quantity),
            )
        return None
