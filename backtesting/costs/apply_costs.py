"""apply_costs — backtest cost handler for Phase 2-3.

Single entry point that applies Iranian real-market transaction costs
(broker 0.4%, sell tax 0.5%, CSD clearing 0.085%) to a list of trades.

Usage::

    apply_costs(trades, fee_version="real") -> list[TradeWithCost]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backtesting.costs.iran_costs import IranTransactionCosts


@dataclass
class TradeWithCost:
    """A trade with computed transaction costs."""

    symbol: str
    side: str
    quantity: int
    price: float
    commission: float = 0.0
    tax: float = 0.0
    clearing: float = 0.0
    total_cost: float = 0.0
    net_price: float = 0.0
    pnl_gross: float = 0.0
    pnl_net: float = 0.0
    slippage: float = 0.0
    max_drawdown: float = 0.0


_COST_ENGINE = IranTransactionCosts()


def apply_costs(
    trades: list[dict[str, Any]],
    fee_version: str = "real",
    **kwargs: Any,
) -> list[TradeWithCost]:
    """Apply Iranian market costs to a list of trades.

    Args:
        trades: List of trade dicts with keys ``symbol``, ``side``, ``quantity``,
            ``price``, and optionally ``pnl_gross``.
        fee_version: ``"real"`` (default) uses canonical Iranian rates. Legacy
            values are accepted but deprecated.
        **kwargs: Forwarded to the cost model (e.g. ``slippage_bps``).

    Returns:
        List of ``TradeWithCost`` objects with costs computed.
    """
    results: list[TradeWithCost] = []
    for t in trades:
        side = t.get("side", "buy")
        qty = int(t.get("quantity", 0))
        price = float(t.get("price", 0))
        symbol = t.get("symbol", "?")

        total_cost = _COST_ENGINE.compute(side, price, qty)
        commission = price * qty * _COST_ENGINE.broker_pct
        tax = price * qty * _COST_ENGINE.sell_tax_pct if side == "sell" else 0.0
        clearing = price * qty * _COST_ENGINE.clearing_fee_pct

        pnl_gross = float(t.get("pnl_gross", 0.0))
        net_price = price + (total_cost / qty) if qty > 0 else price
        slippage = float(kwargs.get("slippage_bps", 0)) * price * qty / 10000

        results.append(
            TradeWithCost(
                symbol=symbol,
                side=side,
                quantity=qty,
                price=price,
                commission=commission,
                tax=tax,
                clearing=clearing,
                total_cost=total_cost,
                net_price=net_price,
                pnl_gross=pnl_gross,
                pnl_net=pnl_gross - total_cost - slippage,
                slippage=slippage,
                max_drawdown=float(t.get("max_drawdown", 0.0)),
            )
        )
    return results
