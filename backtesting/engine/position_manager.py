from __future__ import annotations

from backtesting.types import FillEvent, PositionState


class PositionManager:
    def __init__(self) -> None:
        self._positions: dict[str, PositionState] = {}

    def reset(self) -> None:
        self._positions.clear()

    def get_position(self, instrument_id: str) -> PositionState | None:
        return self._positions.get(instrument_id)

    def get_positions(self) -> dict[str, PositionState]:
        return dict(self._positions)

    def update(self, fill: FillEvent) -> None:
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
        else:
            pnl = (fill.price - pos.avg_price) * fill.quantity
            pos.realized_pnl += pnl
            pos.quantity -= fill.quantity

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
