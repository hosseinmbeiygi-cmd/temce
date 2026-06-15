from __future__ import annotations

from dataclasses import dataclass

from backtesting.models.iran_costs import IranCommissionModel
from backtesting.types import FillEvent, OrderEvent


@dataclass
class CommissionModel:
    broker_pct: float = 0.0035
    tax_pct: float = 0.005
    fee_per_order: float = 0.0
    tiered_tiers: list[tuple[float, float]] | None = None
    iran_mode: bool = False
    iran_model: IranCommissionModel | None = None

    def compute(self, fill: FillEvent, side: str = "sell") -> dict[str, float]:
        if self.iran_mode:
            model = self.iran_model or IranCommissionModel()
            if side == "buy":
                return model.compute_buy(fill.price, fill.quantity)
            return model.compute_sell(fill.price, fill.quantity)

        principal = fill.price * fill.quantity
        broker = principal * self.broker_pct
        tax = principal * self.tax_pct
        total = broker + tax + self.fee_per_order
        return {"broker": broker, "tax": tax, "fee": self.fee_per_order, "total": total}

    def compute_for_order(self, order: OrderEvent, fill_price: float, fill_qty: int) -> float:
        if self.iran_mode:
            model = self.iran_model or IranCommissionModel()
            side = "buy" if order.side.value == "buy" else "sell"
            costs = model.compute_buy(fill_price, fill_qty) if side == "buy" else model.compute_sell(fill_price, fill_qty)
            return costs["total"]
        return fill_price * fill_qty * (self.broker_pct + self.tax_pct) + self.fee_per_order
