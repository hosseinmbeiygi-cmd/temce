from __future__ import annotations

import numpy as np

from backtesting.types import FillEvent


class ImpactModel:
    def __init__(
        self,
        eta: float = 0.1,
        alpha: float = 0.6,
        permanent_impact_pct: float = 0.02,
        use_sqrt_law: bool = True,
    ) -> None:
        self.eta = eta
        self.alpha = alpha
        self.permanent_impact_pct = permanent_impact_pct
        self.use_sqrt_law = use_sqrt_law

    def calculate_impact(self, quantity: int, adv: float, price: float = 1.0) -> float:
        participation = quantity / max(adv, 1)
        impact = self.eta * participation**self.alpha if self.use_sqrt_law else self.eta * participation
        return impact

    def get_execution_price(self, quantity: int, adv: float, price: float, side: str) -> float:
        impact_pct = self.calculate_impact(quantity, adv, price)
        if side == "buy":
            return price * (1.0 + impact_pct)
        return price * (1.0 - impact_pct)

    def apply_to_fill(self, fill: FillEvent, adv: float) -> FillEvent:
        impact_pct = self.calculate_impact(fill.quantity, adv, fill.price)
        adjusted_price = fill.price * (1.0 + impact_pct) if fill.side == "buy" else fill.price * (1.0 - impact_pct)
        from dataclasses import replace

        return replace(fill, price=round(adjusted_price, 2))

    def calibrate_from_data(self, trade_sizes: list[float], price_moves: list[float], adv: float) -> None:
        if len(trade_sizes) < 5 or len(price_moves) < 5:
            return
        log_sizes = np.log([max(s / adv, 1e-10) for s in trade_sizes])
        log_moves = np.log([max(abs(m), 1e-10) for m in price_moves])
        coeffs = np.polyfit(log_sizes, log_moves, 1)
        self.alpha = float(coeffs[0])
        self.eta = float(np.exp(coeffs[1]))
