"""Single Source of Truth — Tehran Stock Exchange transaction costs.

Broker 0.4% per side, CSD clearing 0.085% per side, sell tax 0.5% (sell only).
All cost modules must delegate to these functions — no local fee formulas.
"""
from __future__ import annotations

BROKER_PCT = 0.004
CLEARING_FEE_PCT = 0.00085
SELL_TAX_PCT = 0.005

# ── Stock-option contracts (TSE/IFB derivatives board) ──────────────────────
# Sources: SEO derivatives fee schedule via broker disclosures
# (e.g. optionist.ir, armanbroker.ir): a flat 0.00125 (0.125%) of contract
# value per side (premium × contract size), identical for calls and puts.
# The 0.5% transfer tax does NOT apply to premium open/close trades — only
# to PHYSICAL settlement (share delivery on exercise), modelled explicitly.
OPTION_BUY_PCT = 0.00125
OPTION_SELL_PCT = 0.00125


def buy_cost(price: float, quantity: int) -> float:
    principal = max(float(price), 0.0) * max(int(quantity), 0)
    return principal * BROKER_PCT + principal * CLEARING_FEE_PCT


def sell_cost(price: float, quantity: int) -> float:
    principal = max(float(price), 0.0) * max(int(quantity), 0)
    return principal * BROKER_PCT + principal * SELL_TAX_PCT + principal * CLEARING_FEE_PCT


def compute(side: str, price: float, quantity: int) -> float:
    return sell_cost(price, quantity) if str(side).lower() == "sell" else buy_cost(price, quantity)


def round_trip_cost(buy_price: float, buy_qty: int, sell_price: float, sell_qty: int) -> float:
    return buy_cost(buy_price, buy_qty) + sell_cost(sell_price, sell_qty)


def option_buy_cost(premium_value: float) -> float:
    """Buyer-side fee for one option leg: 0.125% of premium × size."""
    return max(float(premium_value), 0.0) * OPTION_BUY_PCT


def option_sell_cost(premium_value: float, physical_settlement: bool = False) -> float:
    """Seller-side fee: 0.125% of premium × size, plus 0.5% transfer tax
    ONLY on physical settlement (share delivery), never on premium closes."""
    cost = max(float(premium_value), 0.0) * OPTION_SELL_PCT
    if physical_settlement:
        cost += max(float(premium_value), 0.0) * SELL_TAX_PCT
    return cost
