from __future__ import annotations

from dataclasses import dataclass

from backtesting.types import FillEvent


@dataclass
class CostModel:
    commission_pct: float = 0.0035
    tax_pct: float = 0.005
    fixed_fee: float = 0.0

    def compute_commission(self, fill: FillEvent) -> float:
        return fill.price * fill.quantity * self.commission_pct

    def compute_tax(self, fill: FillEvent) -> float:
        return fill.price * fill.quantity * self.tax_pct

    def total_cost(self, fill: FillEvent) -> float:
        return self.compute_commission(fill) + self.compute_tax(fill) + self.fixed_fee
