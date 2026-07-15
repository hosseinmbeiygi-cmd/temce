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
        if price <= 0:
            return 0
        max_capital_per_position = capital * (self.max_position_pct / 100)
        qty_from_max = int(max_capital_per_position / price)
        # BUG FIX #5: When volatility=0, fall back to max position by capital
        if volatility > 0:
            max_capital_at_risk = capital * (self.risk_per_trade_pct / 100)
            qty_from_risk = int(max_capital_at_risk / (price * volatility))
            return max(0, min(qty_from_risk, qty_from_max))
        return max(0, qty_from_max)

    def compute_kelly_fraction(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        # BUG FIX #6: Standard Kelly formula for fractional payoffs
        if avg_loss <= 0 or avg_win <= 0:
            return 0.0
        p = win_rate
        q = 1 - p
        kelly = p - q * (avg_loss / avg_win)
        return max(0.0, min(kelly, self.max_position_pct / 100))
