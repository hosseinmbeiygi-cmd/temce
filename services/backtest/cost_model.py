"""Cost model — فاز 2-3."""

from __future__ import annotations


def apply_costs(price: float, qty: int, fee_pct: float = 0.00125, slippage_bps: int = 15) -> dict[str, float]:
    gross = price * qty
    commission = gross * fee_pct
    slippage = gross * slippage_bps / 10000
    net = gross - commission - slippage
    return {"gross": gross, "commission": commission, "slippage": slippage, "net": net}
