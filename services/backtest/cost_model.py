"""Cost model — delegates to domain/trading/iran_costs (single source of truth)."""

from __future__ import annotations

from domain.trading import iran_costs as _iran


def apply_costs(price: float, qty: int, fee_pct: float | None = None, slippage_bps: int = 15) -> dict[str, float]:
    gross = price * qty
    # Canonical TSE cost (buy side by default); fee_pct override kept only for
    # explicit stress scenarios, otherwise single-sourced from iran_costs.
    commission = gross * fee_pct if fee_pct is not None else _iran.buy_cost(price, qty)
    slippage = gross * slippage_bps / 10000
    net = gross - commission - slippage
    return {"gross": gross, "commission": commission, "slippage": slippage, "net": net}
