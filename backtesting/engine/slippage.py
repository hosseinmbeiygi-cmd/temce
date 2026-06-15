from __future__ import annotations

from dataclasses import dataclass

from backtesting.constants import SlippageMode


@dataclass
class SlippageModel:
    mode: SlippageMode = SlippageMode.FIXED
    fixed_bps: float = 10.0
    volume_impact_pct: float = 0.1
    volatility_impact_pct: float = 0.05

    def compute_slippage(self, price: float, order_size: int = 0, adv: int = 0, volatility: float = 0.0) -> float:
        if self.mode == SlippageMode.NONE:
            return 0.0
        slippage = price * (self.fixed_bps / 10000)
        if self.mode == SlippageMode.VOLUME_BASED and adv > 0:
            slippage += price * (order_size / adv) * self.volume_impact_pct
        slippage += price * volatility * self.volatility_impact_pct
        if self.mode == SlippageMode.PERCENT:
            slippage = price * (self.fixed_bps / 10000)
        return slippage

    def get_execution_price(
        self, price: float, side: str, order_size: int = 0, adv: int = 0, volatility: float = 0.0
    ) -> float:
        slip = self.compute_slippage(price, order_size, adv, volatility)
        return price + slip if side == "buy" else price - slip
