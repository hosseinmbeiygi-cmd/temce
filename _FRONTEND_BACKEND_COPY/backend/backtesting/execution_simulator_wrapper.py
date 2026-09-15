from __future__ import annotations

from typing import Any


class ExecutionSimulator:
    """Execution simulator for backtesting order execution."""

    def __init__(
        self,
        slippage_bps: float = 10.0,
        partial_fill_enabled: bool = False,
    ) -> None:
        self.slippage_bps = slippage_bps
        self.partial_fill_enabled = partial_fill_enabled

    def execute_market_order(
        self,
        side: str,
        quantity: int,
        price: float,
    ) -> dict[str, Any]:
        slippage = price * (self.slippage_bps / 10000)
        avg_price = price + slippage if side == "buy" else price - slippage

        filled_qty = quantity
        if self.partial_fill_enabled and quantity > 1_000_000:
            filled_qty = quantity // 2

        return {
            "filled_quantity": filled_qty,
            "avg_price": avg_price,
            "side": side,
            "slippage": slippage,
            "filled": filled_qty == quantity,
        }

    def execute_limit_order(
        self,
        side: str,
        quantity: int,
        limit_price: float,
        current_price: float,
    ) -> dict[str, Any]:
        filled = (side == "buy" and limit_price >= current_price) or (side == "sell" and limit_price <= current_price)
        return {
            "filled": filled,
            "filled_quantity": quantity if filled else 0,
            "side": side,
            "limit_price": limit_price,
            "current_price": current_price,
        }
