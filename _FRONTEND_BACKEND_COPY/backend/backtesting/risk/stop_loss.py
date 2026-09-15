from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backtesting.types import PositionState


@dataclass
class StopLoss:
    pct: float = 2.0
    absolute: float = 0.0
    trailing: bool = False
    _highest_prices: dict[str, float] = field(default_factory=dict)
    _entry_prices: dict[str, float] = field(default_factory=dict)

    def set_entry_price(self, instrument_id: str, price: float) -> None:
        """Record entry price for percentage-based stop loss."""
        self._entry_prices[instrument_id] = price

    def should_stop_out(self, position: PositionState, current_price: float) -> bool:
        if position.quantity == 0:
            return False
        entry = position.avg_price
        if entry <= 0:
            return False
        inst_id = position.instrument_id
        if self.trailing:
            highest = self._highest_prices.get(inst_id, 0.0)
            self._highest_prices[inst_id] = max(highest, current_price)
            stop_price = self._highest_prices[inst_id] * (1 - self.pct / 100)
            return current_price <= stop_price
        if self.absolute > 0:
            return current_price <= self.absolute
        stop_price = entry * (1 - self.pct / 100)
        return current_price <= stop_price

    def get_stop_price(self, entry_price: float) -> float:
        if self.absolute > 0:
            return self.absolute
        if self.trailing:
            highest = max(self._highest_prices.values()) if self._highest_prices else 0
            if highest > 0:
                return highest * (1 - self.pct / 100)
        return entry_price * (1 - self.pct / 100)

    def is_triggered(self, positions: dict[str, int], event: Any) -> bool:
        """Check if stop loss is triggered for any position based on event price."""
        payload = getattr(event, "payload", {}) if event else {}
        price = payload.get("price", 0)
        inst_id = getattr(event, "instrument_id", "")
        if price <= 0:
            return False
        for iid, qty in positions.items():
            if qty > 0 and iid == inst_id:
                # Trailing mode
                if self.trailing:
                    highest = self._highest_prices.get(iid, 0.0)
                    self._highest_prices[iid] = max(highest, price)
                    stop = self._highest_prices[iid] * (1 - self.pct / 100)
                    if price <= stop:
                        return True
                # Absolute mode
                elif self.absolute > 0 and price <= self.absolute:
                    return True
                # Percentage mode (BUG FIX #1): check against entry price
                elif self.pct > 0 and self.absolute <= 0:
                    entry = self._entry_prices.get(iid, 0)
                    if entry <= 0:
                        entry = payload.get("entry_price", 0)
                    if entry > 0:
                        stop = entry * (1 - self.pct / 100)
                        if price <= stop:
                            return True
        return False

    def reset(self) -> None:
        self._highest_prices.clear()
        self._entry_prices.clear()
