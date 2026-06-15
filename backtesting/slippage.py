from __future__ import annotations


class SlippageModel:
    """Slippage model for backtesting price impact calculations."""

    def __init__(self, slippage_bps: float = 10.0) -> None:
        self.slippage_bps = slippage_bps

    def calculate(self, price: float, quantity: int) -> float:
        return price * quantity * (self.slippage_bps / 10000)

    def slippage_pct(self) -> float:
        return self.slippage_bps / 10000

    def adjust_price(self, price: float, side: str) -> float:
        slippage = price * (self.slippage_bps / 10000)
        return price + slippage if side == "buy" else price - slippage
