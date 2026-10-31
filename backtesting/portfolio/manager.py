from __future__ import annotations

from backtesting.position_manager import consume_lots_fifo, lots_avg_price
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

    def update_fill_sync(self, fill: FillEvent) -> None:
        """Synchronous version of update_fill — for deterministic sync backtests."""
        pos = self._positions.get(fill.instrument_id)
        if pos is None:
            pos = PositionState(instrument_id=fill.instrument_id)
            self._positions[fill.instrument_id] = pos

        cost = fill.price * fill.quantity
        if fill.side == "buy":
            # FIFO tax lot: record the actual fill price, oldest-first.
            pos.lots.append((fill.quantity, fill.price))
            pos.quantity += fill.quantity
            pos.avg_price = lots_avg_price(pos.lots)
            self._cash -= cost + fill.commission
        else:
            if pos.quantity < fill.quantity:
                logger.warning("Insufficient position for sell: %s (has %d, needs %d)", fill.instrument_id, pos.quantity, fill.quantity)
                fill.quantity = pos.quantity

            # FIFO: realize PnL against the oldest lots, not a blended average.
            pos.realized_pnl += consume_lots_fifo(pos, fill.quantity, fill.price)
            pos.avg_price = lots_avg_price(pos.lots)
            self._cash += (fill.price * fill.quantity) - fill.commission

        self._nav = self.get_nav()

    def mark_to_market_sync(self, prices: dict[str, float]) -> None:
        """Synchronous version of mark_to_market — for deterministic sync backtests."""
        for inst_id, pos in self._positions.items():
            price = prices.get(inst_id)
            if price is not None:
                pos.current_price = price
        self._nav = self.get_nav()

    async def update_fill(self, fill: FillEvent) -> None:
        self.update_fill_sync(fill)

    async def mark_to_market(self, prices: dict[str, float]) -> None:
        self.mark_to_market_sync(prices)

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

    def get_open_lots(self, instrument_id: str) -> list[tuple[int, float]]:
        """Return the open tax lots (quantity, fill_price) in FIFO order."""
        pos = self._positions.get(instrument_id)
        return list(pos.lots) if pos else []

    def adjust_positions(self, instrument_id: str, factor: float) -> None:
        """Scale a position for a corporate action (e.g. split).

        Lot quantities and their cost basis scale together, so a 2:1 split
        turns one lot of 100 @ 10 into 200 @ 5 and FIFO realized PnL stays
        correct after the action.
        """
        pos = self._positions.get(instrument_id)
        if pos is None or pos.quantity == 0 or factor == 0:
            return
        pos.lots = [(int(round(qty * factor)), price / factor) for qty, price in pos.lots]
        pos.quantity = sum(qty for qty, _ in pos.lots)
        pos.avg_price = lots_avg_price(pos.lots)
        self._nav = self.get_nav()
