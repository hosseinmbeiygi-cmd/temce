from __future__ import annotations

from dataclasses import dataclass

from backtesting.types import FillEvent


@dataclass
class CostModel:
    """Legacy flat cost model.

    .. deprecated::
        Use :class:`backtesting.costs.iran_costs.IranTransactionCosts` — the
        canonical single source of truth for Iranian costs (audit F1/F2/F3).
    """

    commission_pct: float = 0.0035
    tax_pct: float = 0.005
    fixed_fee: float = 0.0

    def compute_commission(self, fill: FillEvent) -> float:
        return fill.price * fill.quantity * self.commission_pct

    def compute_tax(self, fill: FillEvent) -> float:
        return fill.price * fill.quantity * self.tax_pct

    def total_cost(self, fill: FillEvent, side: str = "sell") -> float:
        """Total cost for a fill. Tax applies on the sell side only (audit F3)."""
        tax = self.compute_tax(fill) if side in ("sell", "SELL") else 0.0
        return self.compute_commission(fill) + tax + self.fixed_fee
