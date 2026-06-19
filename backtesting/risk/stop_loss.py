from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backtesting.types import PositionState


@dataclass
class StopLoss:
    pct: float = 2.0
    absolute: float = 0.0
    trailing: bool = False
    _highest_price: float = 0.0

    def should_stop_out(self, position: PositionState, current_price: float) -> bool:
        if position.quantity == 0:
            return False
        entry = position.avg_price
        if entry <= 0:
            return False
        if self.trailing:
            self._highest_price = max(self._highest_price, current_price)
            stop_price = self._highest_price * (1 - self.pct / 100)
            return current_price <= stop_price
        if self.absolute > 0:
            return current_price <= self.absolute
        stop_price = entry * (1 - self.pct / 100)
        return current_price <= stop_price

    def get_stop_price(self, entry_price: float) -> float:
        if self.absolute > 0:
            return self.absolute
        if self.trailing and self._highest_price > 0:
            return self._highest_price * (1 - self.pct / 100)
        return entry_price * (1 - self.pct / 100)

    def is_triggered(self, positions: dict[str, int], event: Any) -> bool:
        """Check if stop loss is triggered for any position based on event price."""
        payload = getattr(event, "payload", {}) if event else {}
        price = payload.get("price", 0)
        if price <= 0:
            return False
        for inst_id, qty in positions.items():
            if qty > 0 and inst_id == getattr(event, "instrument_id", ""):
                if self._highest_price > 0:
                    self._highest_price = max(self._highest_price, price)
                else:
                    self._highest_price = price
                if self.trailing:
                    stop = self._highest_price * (1 - self.pct / 100)
                    if price <= stop:
                        return True
                elif self.absolute > 0 and price <= self.absolute:
                    return True
        return False

    def reset(self) -> None:
        self._highest_price = 0.0
