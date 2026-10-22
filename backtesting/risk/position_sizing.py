from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PositionSizing:
    risk_per_trade_pct: float = 1.0
    max_position_pct: float = 10.0
    fixed_qty: int = 0
    # RISK-004: full Kelly is famously over-aggressive because the edge inputs
    # (win rate, average win/loss) are themselves noisy estimates — betting the
    # full Kelly stake on a noisy edge is what turns a good strategy into a
    # ruin event. Quarter Kelly is the practitioner default; ``1.0`` restores
    # the classic full-Kelly stake.
    kelly_fraction: float = 0.25

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

    def compute_full_kelly(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """Unscaled Kelly fraction (kept for reporting/diagnostics).

        BUG FIX #6: standard Kelly formula for fractional payoffs,
        ``f* = p - q * (avg_loss / avg_win)``, clamped to ``[0, max]``.
        """
        if avg_loss <= 0 or avg_win <= 0:
            return 0.0
        if not 0.0 <= win_rate <= 1.0:
            return 0.0
        p = win_rate
        q = 1 - p
        kelly = p - q * (avg_loss / avg_win)
        return max(0.0, min(kelly, self.max_position_pct / 100))

    def compute_kelly_fraction_value(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """Kelly stake actually used for sizing (RISK-004 fractional Kelly)."""
        return self.compute_full_kelly(win_rate, avg_win, avg_loss) * self.kelly_fraction

    def compute_kelly_fraction(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """Backwards-compatible alias for the unscaled Kelly fraction."""
        return self.compute_full_kelly(win_rate, avg_win, avg_loss)
