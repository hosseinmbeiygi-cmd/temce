from __future__ import annotations

from dataclasses import dataclass

from backtesting.types import PositionState


@dataclass
class TakeProfit:
    pct: float = 5.0
    absolute: float = 0.0

    def should_take_profit(self, position: PositionState, current_price: float) -> bool:
        if position.quantity == 0 or position.avg_price <= 0:
            return False
        if self.absolute > 0:
            return current_price >= self.absolute
        target = position.avg_price * (1 + self.pct / 100)
        return current_price >= target

    def get_target_price(self, entry_price: float) -> float:
        if self.absolute > 0:
            return self.absolute
        return entry_price * (1 + self.pct / 100)
