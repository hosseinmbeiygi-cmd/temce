from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backtesting.abm.order_book import OrderBookEntry


class Agent(ABC):
    def __init__(self, agent_id: str, initial_capital: float = 1_000_000_000) -> None:
        self.agent_id = agent_id
        self.capital = initial_capital
        self.position: dict[str, int] = {}
        self._pnl: float = 0.0

    @abstractmethod
    def observe(self, environment: Any) -> None: ...

    @abstractmethod
    def decide(self) -> list[OrderBookEntry] | None: ...

    def act(self, environment: Any) -> list[Any]:
        self.observe(environment)
        orders = self.decide()
        trades = []
        if orders:
            for order in orders:
                result = environment.submit_order(
                    side=order.side.value,
                    price=order.price,
                    quantity=order.quantity,
                    order_type=order.order_type.value,
                    agent_id=self.agent_id,
                )
                trades.extend(result)
                for t in result:
                    self._update_pnl(t)
        return trades

    def _update_pnl(self, trade: Any) -> None:
        if trade.buyer_id == self.agent_id:
            cost = trade.price * trade.quantity
            self.capital -= cost
            self.position[trade.buy_order_id] = self.position.get(trade.buy_order_id, 0) + trade.quantity
        elif trade.seller_id == self.agent_id:
            revenue = trade.price * trade.quantity
            self.capital += revenue
            self.position[trade.sell_order_id] = self.position.get(trade.sell_order_id, 0) - trade.quantity
        self._pnl = self.capital

    @property
    def pnl(self) -> float:
        return self._pnl

    def reset(self) -> None:
        self.position.clear()
        self._pnl = 0.0

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.agent_id})"
