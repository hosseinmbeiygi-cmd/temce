from __future__ import annotations

import random
from collections import deque
from typing import Any

import numpy as np

from backtesting.types import OrderEvent
from core.logging import get_logger

logger = get_logger(__name__)


class SyntheticAgent:
    """Base class for all synthetic agents in the Hybrid Market Simulator."""

    def __init__(self, agent_id: str, weight: float = 1.0) -> None:
        self.agent_id = agent_id
        self.weight = weight
        self._pnl: float = 0.0

    def observe(self, market_state: dict[str, Any]) -> None:
        """Observe the current market state. Override in subclasses."""

    def decide(self, market_state: dict[str, Any]) -> list[OrderEvent] | None:
        """Decide what orders to submit. Override in subclasses."""
        return None

    @property
    def pnl(self) -> float:
        return self._pnl

    def reset(self) -> None:
        self._pnl = 0.0


class HybridMarketMaker(SyntheticAgent):
    """Market maker that adjusts spread based on volatility and inventory."""

    def __init__(
        self,
        agent_id: str,
        weight: float = 1.0,
        base_spread_pct: float = 0.01,
        base_order_size: int = 1000,
        inventory_target: float = 0.0,
        max_inventory: float = 1_000_000_000,
    ) -> None:
        super().__init__(agent_id, weight)
        self.base_spread_pct = base_spread_pct
        self.base_order_size = base_order_size
        self.inventory_target = inventory_target
        self.max_inventory = max_inventory
        self._position: dict[str, float] = {}
        self._current_mid: float = 1000.0

    def observe(self, market_state: dict[str, Any]) -> None:
        bid = market_state.get("best_bid", 0.0)
        ask = market_state.get("best_ask", 0.0)
        if bid > 0 and ask > 0:
            self._current_mid = (bid + ask) / 2.0
        elif market_state.get("last_price", 0) > 0:
            self._current_mid = market_state["last_price"]

    def decide(self, market_state: dict[str, Any]) -> list[OrderEvent] | None:
        volatility = market_state.get("volatility", 0.02)
        spread_multiplier = 1.0 + (volatility / 0.02) * 2.0
        spread = self._current_mid * self.base_spread_pct * spread_multiplier

        inventory_adj = 0.0
        total_inv = sum(self._position.values()) if self._position else 0
        if total_inv > self.inventory_target:
            inventory_adj = self._current_mid * 0.002 * (total_inv / max(self.max_inventory, 1))
        elif total_inv < self.inventory_target:
            inventory_adj = -self._current_mid * 0.002

        bid_price = round(self._current_mid - spread / 2 + inventory_adj, 2)
        ask_price = round(self._current_mid + spread / 2 + inventory_adj, 2)
        size = int(self.base_order_size * (1.0 + random.uniform(-0.3, 0.3)))

        return [
            OrderEvent(instrument_id="", side="buy", quantity=size, price=bid_price, order_type="LIMIT"),
            OrderEvent(instrument_id="", side="sell", quantity=size, price=ask_price, order_type="LIMIT"),
        ]


class HybridNoiseTrader(SyntheticAgent):
    """Noise trader that generates random buy/sell orders."""

    def __init__(
        self,
        agent_id: str,
        weight: float = 1.0,
        min_size: int = 100,
        max_size: int = 2000,
        market_order_prob: float = 0.3,
        intensity: float = 0.5,
    ) -> None:
        super().__init__(agent_id, weight)
        self.min_size = min_size
        self.max_size = max_size
        self.market_order_prob = market_order_prob
        self.intensity = intensity
        self._last_price: float = 1000.0

    def observe(self, market_state: dict[str, Any]) -> None:
        self._last_price = market_state.get("last_price", 0) or market_state.get("midpoint", 0) or self._last_price or 1000.0

    def decide(self, market_state: dict[str, Any]) -> list[OrderEvent] | None:
        if random.random() > self.intensity:
            return None
        side = random.choice(["buy", "sell"])
        size = random.randint(self.min_size, self.max_size)
        is_market = random.random() < self.market_order_prob
        price = 0.0 if is_market else round(self._last_price * (1 + random.gauss(0, 0.001)), 2)
        return [
            OrderEvent(
                instrument_id="",
                side=side,
                quantity=size,
                price=price,
                order_type="MARKET" if is_market else "LIMIT",
            )
        ]


class HybridTrendFollower(SyntheticAgent):
    """Trend following agent that buys/sells based on recent price movement."""

    def __init__(
        self,
        agent_id: str,
        weight: float = 1.0,
        lookback: int = 20,
        order_size: int = 1000,
        threshold_pct: float = 0.005,
    ) -> None:
        super().__init__(agent_id, weight)
        self.lookback = lookback
        self.order_size = order_size
        self.threshold_pct = threshold_pct
        self._price_history: deque[float] = deque(maxlen=lookback)

    def observe(self, market_state: dict[str, Any]) -> None:
        price = market_state.get("last_price", 0) or market_state.get("midpoint", 0)
        if price > 0:
            self._price_history.append(price)

    def decide(self, market_state: dict[str, Any]) -> list[OrderEvent] | None:
        if len(self._price_history) < self.lookback:
            return None
        recent = list(self._price_history)
        trend = recent[-1] - recent[0]
        threshold = recent[0] * self.threshold_pct
        if trend > threshold:
            return [OrderEvent(instrument_id="", side="buy", quantity=self.order_size, price=round(recent[-1] * 1.001, 2), order_type="MARKET")]
        elif trend < -threshold:
            return [OrderEvent(instrument_id="", side="sell", quantity=self.order_size, price=round(recent[-1] * 0.999, 2), order_type="MARKET")]
        return None


class HybridMeanReversion(SyntheticAgent):
    """Mean reversion agent that trades based on Z-score deviations."""

    def __init__(
        self,
        agent_id: str,
        weight: float = 1.0,
        lookback: int = 50,
        order_size: int = 1000,
        entry_z: float = 1.0,
    ) -> None:
        super().__init__(agent_id, weight)
        self.lookback = lookback
        self.order_size = order_size
        self.entry_z = entry_z
        self._price_history: deque[float] = deque(maxlen=lookback)
        self._avg: float = 0.0
        self._std: float = 1.0

    def observe(self, market_state: dict[str, Any]) -> None:
        price = market_state.get("last_price", 0) or market_state.get("midpoint", 0)
        if price > 0:
            self._price_history.append(price)
        if len(self._price_history) >= 20:
            arr = np.array(self._price_history)
            self._avg = float(np.mean(arr))
            self._std = max(float(np.std(arr)), 1e-6)

    def decide(self, market_state: dict[str, Any]) -> list[OrderEvent] | None:
        if len(self._price_history) < 20 or self._std <= 0:
            return None
        current = self._price_history[-1]
        z = (current - self._avg) / self._std
        if z > self.entry_z:
            return [OrderEvent(instrument_id="", side="sell", quantity=self.order_size, price=round(current, 2), order_type="MARKET")]
        elif z < -self.entry_z:
            return [OrderEvent(instrument_id="", side="buy", quantity=self.order_size, price=round(current, 2), order_type="MARKET")]
        return None


class AgentEngine:
    """Engine that manages and runs all synthetic agents."""

    def __init__(self) -> None:
        self._agents: list[SyntheticAgent] = []

    def add_agent(self, agent: SyntheticAgent) -> None:
        self._agents.append(agent)

    def add_agents(self, agents: list[SyntheticAgent]) -> None:
        self._agents.extend(agents)

    def generate_orders(self, market_state: dict[str, Any]) -> list[OrderEvent]:
        orders: list[OrderEvent] = []
        random.shuffle(self._agents)
        for agent in self._agents:
            agent.observe(market_state)
            result = agent.decide(market_state)
            if result:
                orders.extend(result)
        return orders

    @property
    def agents(self) -> list[SyntheticAgent]:
        return list(self._agents)

    def reset(self) -> None:
        for agent in self._agents:
            agent.reset()

    def configure_from_params(self, params: dict[str, Any]) -> None:
        """Configure agents from calibration parameters."""
        for agent in self._agents:
            if isinstance(agent, HybridNoiseTrader):
                agent.intensity = params.get("arrival_rate", agent.intensity)
                agent.min_size = int(params.get("avg_trade_size", agent.min_size) * 0.5)
                agent.max_size = int(params.get("avg_trade_size", agent.max_size) * 2.0)
            elif isinstance(agent, HybridMarketMaker):
                agent.base_spread_pct = params.get("spread_pct", agent.base_spread_pct)
                agent.base_order_size = int(params.get("avg_queue", agent.base_order_size) * 0.001)
