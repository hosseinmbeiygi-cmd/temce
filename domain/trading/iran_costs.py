"""Single Source of Truth — Tehran Stock Exchange transaction costs.

Broker 0.4% per side, CSD clearing 0.085% per side, sell tax 0.5% (sell only).
All cost modules must delegate to these functions — no local fee formulas.
"""
from __future__ import annotations

BROKER_PCT = 0.004
CLEARING_FEE_PCT = 0.00085
SELL_TAX_PCT = 0.005


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
