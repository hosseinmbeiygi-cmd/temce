from __future__ import annotations

from backtesting.hybrid.agent_engine import (
    HybridMarketMaker,
    HybridMeanReversion,
    HybridNoiseTrader,
    HybridTrendFollower,
    SyntheticAgent,
)


class RegimeAwareMarketMaker(HybridMarketMaker):
    """Market maker that adjusts spread and size based on market regime."""

    def __init__(
        self,
        agent_id: str,
        weight: float = 1.0,
        base_spread_pct: float = 0.01,
        base_order_size: int = 1000,
        inventory_target: float = 0.0,
        max_inventory: float = 1_000_000_000,
    ) -> None:
        super().__init__(agent_id, weight, base_spread_pct, base_order_size, inventory_target, max_inventory)
        self._current_regime: str = "normal"

    def set_regime(self, regime: str) -> None:
        self._current_regime = regime

    def decide(self, market_state: dict) -> list | None:
        regime = self._current_regime
        spread_multipliers = {
            "panic": 3.0,
            "low_liquidity": 2.0,
            "queue_lock": 2.5,
            "trend": 1.2,
            "mean_reverting": 0.8,
            "normal": 1.0,
        }
        mult = spread_multipliers.get(regime, 1.0)
        old_spread_pct = self.base_spread_pct
        self.base_spread_pct = old_spread_pct * mult

        size_multipliers = {
            "panic": 0.3,
            "low_liquidity": 0.5,
            "queue_lock": 0.7,
            "normal": 1.0,
            "trend": 1.5,
            "mean_reverting": 1.2,
        }
        size_mult = size_multipliers.get(regime, 1.0)
        old_size = self.base_order_size
        self.base_order_size = int(old_size * size_mult)

        result = super().decide(market_state)

        self.base_spread_pct = old_spread_pct
        self.base_order_size = old_size
        return result


class RegimeAwareNoiseTrader(HybridNoiseTrader):
    """Noise trader that adjusts intensity based on regime."""

    def __init__(
        self,
        agent_id: str,
        weight: float = 1.0,
        min_size: int = 100,
        max_size: int = 2000,
        market_order_prob: float = 0.3,
        intensity: float = 0.5,
    ) -> None:
        super().__init__(agent_id, weight, min_size, max_size, market_order_prob, intensity)
        self._current_regime: str = "normal"

    def set_regime(self, regime: str) -> None:
        self._current_regime = regime

    def decide(self, market_state: dict) -> list | None:
        intensity_mult = {
            "panic": 2.0,
            "low_liquidity": 1.5,
            "queue_lock": 0.5,
            "trend": 1.3,
            "normal": 1.0,
            "mean_reverting": 0.8,
        }
        old_intensity = self.intensity
        self.intensity = old_intensity * intensity_mult.get(self._current_regime, 1.0)
        result = super().decide(market_state)
        self.intensity = old_intensity
        return result


class RegimeAwareTrendFollower(HybridTrendFollower):
    """Trend follower that adjusts threshold based on regime."""

    def __init__(
        self,
        agent_id: str,
        weight: float = 1.0,
        lookback: int = 20,
        order_size: int = 1000,
        threshold_pct: float = 0.005,
    ) -> None:
        super().__init__(agent_id, weight, lookback, order_size, threshold_pct)
        self._current_regime: str = "normal"

    def set_regime(self, regime: str) -> None:
        self._current_regime = regime

    def decide(self, market_state: dict) -> list | None:
        threshold_mult = {"trend": 0.5, "panic": 0.7, "normal": 1.0, "mean_reverting": 2.0, "low_liquidity": 1.5}
        old_threshold = self.threshold_pct
        self.threshold_pct = old_threshold * threshold_mult.get(self._current_regime, 1.0)
        result = super().decide(market_state)
        self.threshold_pct = old_threshold
        return result


class RegimeAwareAgentFactory:
    """Factory for creating regime-aware agents."""

    @staticmethod
    def create_default_agents(agent_id_prefix: str = "regime") -> list[SyntheticAgent]:
        return [
            RegimeAwareMarketMaker(agent_id=f"{agent_id_prefix}_mm1", weight=1.0),
            RegimeAwareMarketMaker(agent_id=f"{agent_id_prefix}_mm2", weight=0.8),
            RegimeAwareNoiseTrader(agent_id=f"{agent_id_prefix}_nt1", intensity=0.4),
            RegimeAwareNoiseTrader(agent_id=f"{agent_id_prefix}_nt2", intensity=0.3),
            RegimeAwareTrendFollower(agent_id=f"{agent_id_prefix}_tf1", lookback=20),
            RegimeAwareTrendFollower(agent_id=f"{agent_id_prefix}_tf2", lookback=50),
            HybridMeanReversion(agent_id=f"{agent_id_prefix}_mr1", lookback=50),
            HybridMeanReversion(agent_id=f"{agent_id_prefix}_mr2", lookback=100),
        ]
