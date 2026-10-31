from __future__ import annotations

from backtesting.types import FillEvent, PositionState


def lots_avg_price(lots: list[tuple[int, float]]) -> float:
    """Quantity-weighted average fill price of the open lots."""
    total_qty = sum(qty for qty, _ in lots)
    if total_qty <= 0:
        return 0.0
    return sum(qty * price for qty, price in lots) / total_qty


def consume_lots_fifo(pos: PositionState, quantity: int, price: float) -> float:
    """Deduct ``quantity`` from the oldest lots first; return realized PnL.

    Lots are drained oldest-first (FIFO), so a sell realizes PnL against the
    original purchase prices rather than a blended average.  If the sell exceeds
    the held quantity only the available shares are consumed.
    """
    remaining = quantity
    realized = 0.0
    while remaining > 0 and pos.lots:
        lot_qty, lot_price = pos.lots[0]
        take = min(remaining, lot_qty)
        realized += (price - lot_price) * take
        remaining -= take
        if take == lot_qty:
            pos.lots.pop(0)
        else:
            pos.lots[0] = (lot_qty - take, lot_price)

    pos.quantity -= quantity - remaining  # clamp to what was actually held
    if pos.quantity < 0:
        pos.quantity = 0
    return realized


class PositionManager:
    def __init__(self) -> None:
        self._positions: dict[str, PositionState] = {}

    def reset(self) -> None:
        self._positions.clear()

    def get_position(self, instrument_id: str) -> PositionState | None:
        return self._positions.get(instrument_id)

    def get_positions(self) -> dict[str, PositionState]:
        return dict(self._positions)

    def get_open_lots(self, instrument_id: str) -> list[tuple[int, float]]:
        """Return the open tax lots (quantity, fill_price) in FIFO order."""
        pos = self._positions.get(instrument_id)
        return list(pos.lots) if pos else []

    def update(self, fill: FillEvent) -> None:
        pos = self._positions.get(fill.instrument_id)
        if pos is None:
            pos = PositionState(instrument_id=fill.instrument_id)
            self._positions[fill.instrument_id] = pos

        if fill.side == "buy":
            pos.lots.append((fill.quantity, fill.price))
            pos.quantity += fill.quantity
        else:
            pos.realized_pnl += consume_lots_fifo(pos, fill.quantity, fill.price)

        pos.avg_price = lots_avg_price(pos.lots)

    def get_total_value(self, prices: dict[str, float]) -> float:
        total = 0.0
        for inst_id, pos in self._positions.items():
            price = prices.get(inst_id, pos.avg_price)
            total += pos.quantity * price
        return total

    def get_total_realized_pnl(self) -> float:
        return sum(p.realized_pnl for p in self._positions.values())

    def get_position_count(self) -> int:
        return len(self._positions)
