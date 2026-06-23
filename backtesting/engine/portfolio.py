from __future__ import annotations

from backtesting.types import FillEvent, PositionState
from core.logging import get_logger


logger = get_logger(__name__)


class PortfolioManager:
    def __init__(self) -> None:
        self._cash: float = 0.0
        self._positions: dict[str, PositionState] = {}
        self._nav: float = 0.0

    def reset(self, initial_capital: float) -> None:
        self._cash = initial_capital
        self._positions.clear()
        self._nav = initial_capital

    async def update_fill(self, fill: FillEvent) -> None:
        pos = self._positions.get(fill.instrument_id)
        if pos is None:
            pos = PositionState(instrument_id=fill.instrument_id)
            self._positions[fill.instrument_id] = pos

        cost = fill.price * fill.quantity
        if fill.side == "buy":
            total_qty = pos.quantity + fill.quantity
            total_cost = (pos.avg_price * pos.quantity) + cost
            pos.avg_price = total_cost / total_qty if total_qty > 0 else 0
            pos.quantity = total_qty
            self._cash -= cost + fill.commission
        else:
            if pos.quantity < fill.quantity:
                logger.warning("Insufficient position for sell: %s (has %d, needs %d)", fill.instrument_id, pos.quantity, fill.quantity)
                # Option 1: Raise error. Option 2: Cap at available.
                # We'll cap it to prevent negative quantity unless shorting is explicitly handled.
                fill.quantity = pos.quantity
            
            pnl = (fill.price - pos.avg_price) * fill.quantity
            pos.realized_pnl += pnl
            pos.quantity -= fill.quantity
            self._cash += (fill.price * fill.quantity) - fill.commission

        self._nav = self.get_nav()

    async def mark_to_market(self, prices: dict[str, float]) -> None:
        for inst_id, pos in self._positions.items():
            price = prices.get(inst_id)
            if price is not None:
                pos.current_price = price
        self._nav = self.get_nav()

    def get_nav(self) -> float:
        positions_value = self.get_positions_value()
        return self._cash + positions_value

    def get_cash(self) -> float:
        return self._cash

    def get_positions_value(self) -> float:
        total = 0.0
        for pos in self._positions.values():
            price = pos.current_price if pos.current_price > 0 else pos.avg_price
            total += pos.quantity * price
        return total

    def get_positions(self) -> dict[str, int]:
        """Return current position quantities keyed by instrument_id."""
        return {inst_id: pos.quantity for inst_id, pos in self._positions.items()}

    def get_position(self, instrument_id: str) -> int:
        """Return current position quantity for a single instrument."""
        pos = self._positions.get(instrument_id)
        return pos.quantity if pos else 0

    def adjust_positions(self, instrument_id: str, factor: float) -> None:
        """Adjust positions by a corporate action factor (e.g. split)."""
        pos = self._positions.get(instrument_id)
        if pos is None or pos.quantity == 0:
            return
        pos.quantity = round(pos.quantity * factor)
        pos.avg_price = pos.avg_price / factor if factor != 0 else pos.avg_price
        self._nav = self.get_nav()
