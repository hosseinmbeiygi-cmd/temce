"""Canonical Iranian-market transaction cost model.

Single source of truth for Iranian brokerage costs (audit finding F1).

All other cost classes in ``backtesting`` should delegate their **rates** to
this module, and every fill producer should charge costs through
``IranTransactionCosts.compute(side, price, quantity)`` so that all backtest
paths converge on identical transaction-cost behaviour (audit finding F2).

Iranian market rules encoded here:
- Broker fee:     0.4% per side (reduced from 0.5% in recent years)
- Sell tax:       0.5% on SELL proceeds only (audit finding F3)
- CSD clearing:   0.085% per side (سپرده‌گذاری مرکزی)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Rates single-sourced from the canonical module (P1-3) — no local copies.
from domain.trading.iran_costs import (
    BROKER_PCT,
    CLEARING_FEE_PCT,
    SELL_TAX_PCT,
)


def normalize_side(side: Any) -> str:
    """Return a lowercase 'buy'/'sell' string for enum or plain-string sides."""
    if hasattr(side, "value"):  # StrEnum / Enum
        return str(side.value).lower()
    return str(side).lower()


@dataclass(frozen=True)
class IranTransactionCosts:
    """Canonical Iranian transaction cost model.

    ``compute(side, price, quantity)`` returns the total cost of a single
    fill. Tax (0.5%) is applied on the SELL side only; broker fee and the
    CSD clearing fee are applied on both sides.
    """

    broker_pct: float = BROKER_PCT
    sell_tax_pct: float = SELL_TAX_PCT
    clearing_fee_pct: float = CLEARING_FEE_PCT
    min_commission: float = 0.0

    def buy_cost(self, price: float, quantity: int) -> float:
        principal = max(float(price), 0.0) * max(int(quantity), 0)
        broker = max(principal * self.broker_pct, self.min_commission)
        return broker + principal * self.clearing_fee_pct

    def sell_cost(self, price: float, quantity: int) -> float:
        principal = max(float(price), 0.0) * max(int(quantity), 0)
        broker = max(principal * self.broker_pct, self.min_commission)
        return broker + principal * self.sell_tax_pct + principal * self.clearing_fee_pct

    def compute(self, side: Any, price: float, quantity: int) -> float:
        """Total transaction cost for a single fill. Tax only on sell (F3)."""
        if normalize_side(side) == "sell":
            return self.sell_cost(price, quantity)
        return self.buy_cost(price, quantity)

    def round_trip_cost(
        self,
        buy_price: float,
        buy_qty: int,
        sell_price: float,
        sell_qty: int,
    ) -> float:
        return self.buy_cost(buy_price, buy_qty) + self.sell_cost(sell_price, sell_qty)


# Default canonical instance (frozen → safe to share across engines)
DEFAULT_IRAN_COSTS = IranTransactionCosts()
