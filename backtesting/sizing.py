from __future__ import annotations


class PositionSizer:
    """Position sizer for backtesting position sizing calculations."""

    def __init__(self, method: str = "fixed", value: float = 0.0) -> None:
        self.method = method
        self.value = value

    def calculate(
        self,
        capital: float,
        price: float,
        win_rate: float = 0.5,
        avg_win: float = 0.1,
        avg_loss: float = 0.05,
        stop_loss_pct: float = 1.0,
    ) -> float:
        if self.method == "fixed":
            return self.value / price
        elif self.method == "percent":
            return (capital * self.value / 100.0) / price
        elif self.method == "kelly":
            kelly_pct = (win_rate * avg_win - (1 - win_rate) * avg_loss) / max(avg_win * avg_loss, 1e-12)
            kelly_pct = max(0, min(kelly_pct, self.value))
            return (capital * kelly_pct) / price
        elif self.method == "risk_based":
            risk_amount = capital * (self.value / 100.0)
            risk_per_share = price * (stop_loss_pct / 100.0)
            if risk_per_share <= 0:
                return 0.0
            return risk_amount / risk_per_share
        return 0.0
