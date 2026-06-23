from __future__ import annotations

from backtesting.engine.cash_manager import CashManager
from backtesting.engine.position_manager import PositionManager
from backtesting.types import FillEvent


class PortfolioAccounting:
    def __init__(self, cash_manager: CashManager, position_manager: PositionManager) -> None:
        self.cash_manager = cash_manager
        self.position_manager = position_manager
        self._nav_history: list[float] = []

    def reset(self) -> None:
        self._nav_history.clear()

    def apply_fill(self, fill: FillEvent) -> None:
        self.position_manager.update(fill)
        cost = fill.price * fill.quantity + fill.commission
        if fill.side == "buy":
            self.cash_manager.withdraw(cost, f"buy {fill.instrument_id}")
        else:
            revenue = fill.price * fill.quantity - fill.commission
            self.cash_manager.deposit(revenue, f"sell {fill.instrument_id}")

    def mark_to_market(self, prices: dict[str, float]) -> None:
        nav = self.get_nav(prices)
        self._nav_history.append(nav)

    def get_nav(self, prices: dict[str, float] | None = None) -> float:
        positions_value = self.position_manager.get_total_value(prices or {})
        return self.cash_manager.cash + positions_value

    def get_nav_history(self) -> list[float]:
        return list(self._nav_history)

    def get_total_pnl(self) -> float:
        if not self._nav_history:
            return 0.0
        return self._nav_history[-1] - self._nav_history[0]
