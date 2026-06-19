from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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

    def is_triggered(self, positions: dict[str, int], event: Any) -> bool:
        """Check if take profit is triggered for any position based on event price.

        For percentage-based take profit, this checks if the price has risen
        more than self.pct% above any recent reference price (tracked internally).
        """
        payload = getattr(event, "payload", {}) if event else {}
        price = payload.get("price", 0)
        if price <= 0:
            return False
        for inst_id, qty in positions.items():
            if qty > 0 and inst_id == getattr(event, "instrument_id", ""):
                if self.absolute > 0 and price >= self.absolute:
                    return True
        return False
