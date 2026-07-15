from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backtesting.types import PositionState


@dataclass
class TakeProfit:
    pct: float = 5.0
    absolute: float = 0.0
    _entry_prices: dict[str, float] = field(default_factory=dict)

    def set_entry_price(self, instrument_id: str, price: float) -> None:
        """Record entry price for percentage-based take profit."""
        self._entry_prices[instrument_id] = price

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
        """Check if take profit is triggered for any position based on event price."""
        payload = getattr(event, "payload", {}) if event else {}
        price = payload.get("price", 0)
        inst_id = getattr(event, "instrument_id", "")
        if price <= 0:
            return False
        for iid, qty in positions.items():
            if qty > 0 and iid == inst_id:
                # Absolute mode
                if self.absolute > 0 and price >= self.absolute:
                    return True
                # Percentage mode (BUG FIX #2): check against entry price
                elif self.pct > 0 and self.absolute <= 0:
                    entry = self._entry_prices.get(iid, 0)
                    if entry <= 0:
                        entry = payload.get("entry_price", 0)
                    if entry > 0:
                        target = entry * (1 + self.pct / 100)
                        if price >= target:
                            return True
        return False

    def reset(self) -> None:
        self._entry_prices.clear()
