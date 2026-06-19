from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np

from backtesting.abm.agent import Agent
from backtesting.abm.environment import MarketEnvironment
from backtesting.abm.order_book import Trade
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SimulationResult:
    price_series: list[float] = field(default_factory=list)
    volume_series: list[int] = field(default_factory=list)
    spread_series: list[float] = field(default_factory=list)
    bid_volume_series: list[int] = field(default_factory=list)
    ask_volume_series: list[int] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
    agent_pnls: dict[str, float] = field(default_factory=dict)
    final_mid: float = 0.0
    total_trades: int = 0
    total_volume: int = 0
    steps: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class Simulation:
    def __init__(
        self,
        environment: MarketEnvironment | None = None,
        random_seed: int = 42,
    ) -> None:
        self.environment = environment or MarketEnvironment()
        self.agents: list[Agent] = []
        self._step = 0
        self._time: datetime | None = None
        self._time_step = timedelta(seconds=1)
        random.seed(random_seed)
        np.random.seed(random_seed)

    def add_agent(self, agent: Agent) -> None:
        self.agents.append(agent)

    def add_agents(self, agents: list[Agent]) -> None:
        self.agents.extend(agents)

    def set_time(self, start_time: datetime, step_seconds: int = 1) -> None:
        self._time = start_time
        self._time_step = timedelta(seconds=step_seconds)

    def step(self) -> None:
        random.shuffle(self.agents)
        for agent in self.agents:
            agent.act(self.environment)
        if self._time is not None:
            self._time += self._time_step
        self._step += 1

    def run(self, n_steps: int) -> SimulationResult:
        result = SimulationResult(steps=n_steps)
        for i in range(n_steps):
            self.step()
            snap = self.environment.snapshot()
            if snap.get("last_price", 0) > 0:
                result.price_series.append(snap["last_price"])
            elif snap.get("midpoint", 0) > 0:
                result.price_series.append(snap["midpoint"])
            result.spread_series.append(snap.get("spread", 0))
            result.bid_volume_series.append(snap.get("bid_volume", 0))
            result.ask_volume_series.append(snap.get("ask_volume", 0))
            if i % 100 == 0 and i > 0:
                logger.info("ABM step %s/%s, price=%.2f, trades=%s", i, n_steps, result.price_series[-1] if result.price_series else 0, len(self.environment.trades))

        result.trades = list(self.environment.trades)
        result.total_trades = len(result.trades)
        result.total_volume = sum(t.quantity for t in result.trades)
        result.final_mid = self.environment.mid_price
        for agent in self.agents:
            result.agent_pnls[agent.agent_id] = agent.pnl
        result.metadata = {
            "n_agents": len(self.agents),
            "n_steps": n_steps,
        }
        logger.info("ABM completed: %s trades, final price=%.2f", result.total_trades, result.final_mid)
        return result

    def reset(self) -> None:
        self.environment.reset()
        for agent in self.agents:
            agent.reset()
        self._step = 0

    def get_state(self) -> dict[str, Any]:
        return {
            "step": self._step,
            "agents": len(self.agents),
            "environment": self.environment.snapshot(),
        }
