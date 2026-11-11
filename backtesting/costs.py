from __future__ import annotations

import warnings
from dataclasses import dataclass

from backtesting.costs.iran_costs import IranTransactionCosts
from backtesting.types import FillEvent


@dataclass
class CostModel:
    """Legacy flat cost model — DEPRECATED.

    Delegates to :class:`backtesting.costs.iran_costs.IranTransactionCosts`,
    the canonical single source of truth. Will be removed; use
    IranTransactionCosts (injected into Broker) directly.
    """

    commission_pct: float = 0.0035
    tax_pct: float = 0.005
    fixed_fee: float = 0.0

    def __post_init__(self) -> None:
        warnings.warn(
            "backtesting.costs.CostModel is deprecated; use "
            "backtesting.costs.iran_costs.IranTransactionCosts",
            DeprecationWarning,
            stacklevel=2,
        )
        self._canon = IranTransactionCosts()

    def compute_commission(self, fill: FillEvent) -> float:
        return self._canon.buy_cost(fill.price, fill.quantity)

    def compute_tax(self, fill: FillEvent) -> float:
        return fill.price * fill.quantity * self.tax_pct

    def total_cost(self, fill: FillEvent, side: str = "sell") -> float:
        """Total cost for a fill. Tax applies on the sell side only (audit F3)."""
        return self._canon.compute(side, fill.price, fill.quantity) + self.fixed_fee
