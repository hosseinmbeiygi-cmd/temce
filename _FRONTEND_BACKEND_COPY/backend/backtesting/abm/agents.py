from __future__ import annotations

import random
from collections import deque

import numpy as np

from backtesting.abm.agent import Agent
from backtesting.abm.environment import MarketEnvironment
from backtesting.abm.order_book import OrderBookEntry, OrderSide, OrderType


class MarketMaker(Agent):
    def __init__(
        self,
        agent_id: str,
        initial_capital: float = 1_000_000_000,
        spread_pct: float = 0.01,
        order_size: int = 1000,
        inventory_target: int = 0,
    ) -> None:
        super().__init__(agent_id, initial_capital)
        self.spread_pct = spread_pct
        self.order_size = order_size
        self.inventory_target = inventory_target
        self._mid = 0.0

    def observe(self, environment: MarketEnvironment) -> None:
        bid = environment.best_bid
        ask = environment.best_ask
        if bid > 0 and ask > 0:
            self._mid = (bid + ask) / 2.0
        elif environment.last_price > 0:
            self._mid = environment.last_price
        elif self._mid <= 0:
            self._mid = 1000.0

    def decide(self) -> list[OrderBookEntry] | None:
        spread = self._mid * self.spread_pct
        inventory_adj = 0.0
        current_inv = sum(self.position.values()) if self.position else 0
        if current_inv > self.inventory_target:
            inventory_adj = self._mid * 0.002
        elif current_inv < self.inventory_target:
            inventory_adj = -self._mid * 0.002

        bid_price = round(self._mid - spread / 2 + inventory_adj, 2)
        ask_price = round(self._mid + spread / 2 + inventory_adj, 2)

        bid = OrderBookEntry(
            order_id="",
            side=OrderSide.BUY,
            price=bid_price,
            quantity=self.order_size,
            order_type=OrderType.LIMIT,
            agent_id=self.agent_id,
        )
        ask = OrderBookEntry(
            order_id="",
            side=OrderSide.SELL,
            price=ask_price,
            quantity=self.order_size,
            order_type=OrderType.LIMIT,
            agent_id=self.agent_id,
        )
        return [bid, ask]


class NoiseTrader(Agent):
    def __init__(
        self,
        agent_id: str,
        initial_capital: float = 1_000_000_000,
        min_size: int = 100,
        max_size: int = 2000,
        market_order_prob: float = 0.3,
    ) -> None:
        super().__init__(agent_id, initial_capital)
        self.min_size = min_size
        self.max_size = max_size
        self.market_order_prob = market_order_prob
        self._last_price = 0.0

    def observe(self, environment: MarketEnvironment) -> None:
        self._last_price = environment.last_price or environment.mid_price or self._last_price or 1000.0

    def decide(self) -> list[OrderBookEntry] | None:
        side = random.choice([OrderSide.BUY, OrderSide.SELL])
        size = random.randint(self.min_size, self.max_size)
        is_market = random.random() < self.market_order_prob
        price = 0.0 if is_market else (self._last_price * (1 + random.gauss(0, 0.001)))
        return [
            OrderBookEntry(
                order_id="",
                side=side,
                price=round(price, 2) if not is_market else self._last_price,
                quantity=size,
                order_type=OrderType.MARKET if is_market else OrderType.LIMIT,
                agent_id=self.agent_id,
            )
        ]


class TrendFollower(Agent):
    def __init__(
        self,
        agent_id: str,
        initial_capital: float = 1_000_000_000,
        lookback: int = 20,
        order_size: int = 1000,
        threshold_pct: float = 0.005,
    ) -> None:
        super().__init__(agent_id, initial_capital)
        self.lookback = lookback
        self.order_size = order_size
        self.threshold_pct = threshold_pct
        self._price_history: deque[float] = deque(maxlen=lookback)

    def observe(self, environment: MarketEnvironment) -> None:
        price = environment.last_price or environment.mid_price
        if price > 0:
            self._price_history.append(price)

    def decide(self) -> list[OrderBookEntry] | None:
        if len(self._price_history) < self.lookback:
            return None
        recent = list(self._price_history)
        trend = recent[-1] - recent[0]
        threshold = recent[0] * self.threshold_pct
        if trend > threshold:
            return [
                OrderBookEntry(
                    order_id="",
                    side=OrderSide.BUY,
                    price=round(recent[-1] * 1.001, 2),
                    quantity=self.order_size,
                    order_type=OrderType.MARKET,
                    agent_id=self.agent_id,
                )
            ]
        elif trend < -threshold:
            return [
                OrderBookEntry(
                    order_id="",
                    side=OrderSide.SELL,
                    price=round(recent[-1] * 0.999, 2),
                    quantity=self.order_size,
                    order_type=OrderType.MARKET,
                    agent_id=self.agent_id,
                )
            ]
        return None


class MeanReversionAgent(Agent):
    def __init__(
        self,
        agent_id: str,
        initial_capital: float = 1_000_000_000,
        lookback: int = 50,
        order_size: int = 1000,
        entry_z: float = 1.0,
    ) -> None:
        super().__init__(agent_id, initial_capital)
        self.lookback = lookback
        self.order_size = order_size
        self.entry_z = entry_z
        self._price_history: deque[float] = deque(maxlen=lookback)
        self._avg = 0.0
        self._std = 0.0

    def observe(self, environment: MarketEnvironment) -> None:
        price = environment.last_price or environment.mid_price
        if price > 0:
            self._price_history.append(price)
        if len(self._price_history) >= 20:
            arr = np.array(self._price_history)
            self._avg = float(np.mean(arr))
            self._std = max(float(np.std(arr)), 1e-6)

    def decide(self) -> list[OrderBookEntry] | None:
        if len(self._price_history) < 20 or self._std <= 0:
            return None
        current = self._price_history[-1]
        z = (current - self._avg) / self._std
        if z > self.entry_z:
            return [
                OrderBookEntry(
                    order_id="",
                    side=OrderSide.SELL,
                    price=round(current, 2),
                    quantity=self.order_size,
                    order_type=OrderType.MARKET,
                    agent_id=self.agent_id,
                )
            ]
        elif z < -self.entry_z:
            return [
                OrderBookEntry(
                    order_id="",
                    side=OrderSide.BUY,
                    price=round(current, 2),
                    quantity=self.order_size,
                    order_type=OrderType.MARKET,
                    agent_id=self.agent_id,
                )
            ]
        return None
