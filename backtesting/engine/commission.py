from __future__ import annotations

from dataclasses import dataclass

from backtesting.costs.iran_costs import BROKER_PCT, CLEARING_FEE_PCT, SELL_TAX_PCT, normalize_side
from backtesting.models.iran_costs import IranCommissionModel
from backtesting.types import FillEvent, OrderEvent


@dataclass
class CommissionModel:
    # Default rates single-sourced from backtesting.costs.iran_costs (audit F1).
    broker_pct: float = BROKER_PCT
    tax_pct: float = SELL_TAX_PCT
    clearing_fee_pct: float = CLEARING_FEE_PCT
    fee_per_order: float = 0.0
    tiered_tiers: list[tuple[float, float]] | None = None
    iran_mode: bool = False
    iran_model: IranCommissionModel | None = None

    def compute(self, fill: FillEvent, side: str = "sell") -> dict[str, float]:
        if self.iran_mode:
            model = self.iran_model or IranCommissionModel()
            if normalize_side(side) == "buy":
                return model.compute_buy(fill.price, fill.quantity)
            return model.compute_sell(fill.price, fill.quantity)

        principal = fill.price * fill.quantity
        broker = principal * self.broker_pct
        # Tax is charged on the SELL side only (Iranian market rule — audit F3).
        tax = principal * self.tax_pct if normalize_side(side) == "sell" else 0.0
        clearing = principal * self.clearing_fee_pct
        total = broker + tax + clearing + self.fee_per_order
        return {"broker": broker, "tax": tax, "fee": self.fee_per_order, "clearing": clearing, "total": total}

    def compute_for_order(self, order: OrderEvent, fill_price: float, fill_qty: int) -> float:
        if self.iran_mode:
            model = self.iran_model or IranCommissionModel()
            side = normalize_side(order.side)
            costs = model.compute_buy(fill_price, fill_qty) if side == "buy" else model.compute_sell(fill_price, fill_qty)
            return costs["total"]
        side = normalize_side(order.side)
        principal = fill_price * fill_qty
        broker = principal * self.broker_pct
        # Tax on SELL side only — fixes charging tax on buys (audit F3).
        tax = principal * self.tax_pct if side == "sell" else 0.0
        clearing = principal * self.clearing_fee_pct
        return broker + tax + clearing + self.fee_per_order
