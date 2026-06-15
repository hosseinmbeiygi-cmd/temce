from __future__ import annotations

from backtesting.types import FillEvent, PositionState


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
            pnl = (fill.price - pos.avg_price) * fill.quantity
            pos.realized_pnl += pnl
            pos.quantity -= fill.quantity
            self._cash += cost - fill.commission

        self._nav = self.get_nav()

    async def mark_to_market(self, prices: dict[str, float]) -> None:
        self._nav = self.get_nav()
        for inst_id, pos in self._positions.items():
            price = prices.get(inst_id, pos.avg_price)
            pos.current_price = price if price else pos.avg_price

    def get_nav(self) -> float:
        positions_value = self.get_positions_value()
        return self._cash + positions_value

    def get_cash(self) -> float:
        return self._cash

    def get_positions_value(self) -> float:
        total = 0.0
        for pos in self._positions.values():
            total += pos.quantity * pos.avg_price
        return total
