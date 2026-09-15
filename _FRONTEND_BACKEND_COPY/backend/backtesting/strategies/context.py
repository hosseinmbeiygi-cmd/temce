from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backtesting.engine.clock import Clock
from backtesting.engine.event_builder import MarketEvent
from backtesting.market.market_engine import InstrumentState, MarketEngine
from backtesting.orders.manager import OrderManager
from backtesting.portfolio import PortfolioManager


@dataclass
class StrategyContext:
    """Context object passed to strategies.

    Provides a clean API for strategies to interact with the simulation:
    - market: access market state (best bid/ask, last trade, etc.)
    - portfolio: access positions, cash, PnL
    - orders: submit market/limit/cancel orders
    - clock: access current simulation time
    """

    market_engine: MarketEngine
    portfolio: PortfolioManager
    order_api: OrderManager
    clock: Clock
    current_event: MarketEvent | None = None

    # Convenience properties
    @property
    def time(self) -> Any:
        return self.clock.now

    @property
    def market(self) -> MarketEngine:
        return self.market_engine

    @property
    def orders(self) -> OrderManager:
        return self.order_api

    @property
    def cash(self) -> float:
        return self.portfolio.get_cash()

    @property
    def nav(self) -> float:
        return self.portfolio.get_nav()

    def position(self, instrument_id: str) -> int:
        """Get current position for an instrument."""
        return self.portfolio.get_position(instrument_id)

    def state(self, instrument_id: str) -> InstrumentState | None:
        """Get current market state for an instrument."""
        return self.market_engine.get_state(instrument_id)

    def instrument_ids(self) -> list[str]:
        """Get all instrument IDs being tracked."""
        return [s.instrument_id for s in self.market_engine.get_all_states()]

    def __repr__(self) -> str:
        return f"StrategyContext(time={self.time}, nav={self.nav:.2f})"
