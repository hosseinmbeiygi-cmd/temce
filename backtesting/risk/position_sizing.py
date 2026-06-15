from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PositionSizing:
    risk_per_trade_pct: float = 1.0
    max_position_pct: float = 10.0
    fixed_qty: int = 0

    def compute_quantity(self, capital: float, price: float, volatility: float = 0.0) -> int:
        if self.fixed_qty > 0:
            return self.fixed_qty
        max_capital_at_risk = capital * (self.risk_per_trade_pct / 100)
        max_capital_per_position = capital * (self.max_position_pct / 100)
        if price <= 0:
            return 0
        qty_from_risk = int(max_capital_at_risk / (price * volatility)) if volatility > 0 else int(max_capital_at_risk)
        qty_from_max = int(max_capital_per_position / price)
        return max(0, min(qty_from_risk, qty_from_max))

    def compute_kelly_fraction(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        if avg_loss == 0:
            return 0.0
        b = avg_win / abs(avg_loss)
        p = win_rate
        q = 1 - p
        kelly = (b * p - q) / b if b > 0 else 0.0
        return max(0.0, min(kelly, self.max_position_pct / 100))
