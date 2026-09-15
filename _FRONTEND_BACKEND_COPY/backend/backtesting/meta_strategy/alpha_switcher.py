from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AlphaAllocation:
    """Allocation to a single alpha in the meta-strategy."""

    alpha_id: str
    weight: float = 0.0
    regime_fitness: dict[str, float] = field(default_factory=dict)
    current_signal: float = 0.0
    is_active: bool = True


class MetaStrategy:
    """Meta-Strategy Layer: decides which alphas to activate based on regime.

    In Trend regime → momentum alphas are weighted higher
    In MeanReverting regime → mean reversion alphas are weighted higher
    In Panic → exposure is reduced / defensive alphas activated
    """

    def __init__(self) -> None:
        self._allocations: dict[str, AlphaAllocation] = {}
        self._current_regime: str = "normal"
        self._regime_fitness: dict[str, dict[str, float]] = {
            "momentum": {
                "trend": 0.9,
                "normal": 0.5,
                "mean_reverting": 0.1,
                "panic": 0.2,
                "low_liquidity": 0.3,
                "queue_lock": 0.3,
            },
            "mean_reversion": {
                "mean_reverting": 0.9,
                "normal": 0.5,
                "trend": 0.1,
                "panic": 0.3,
                "low_liquidity": 0.4,
                "queue_lock": 0.4,
            },
            "arbitrage": {
                "normal": 0.6,
                "trend": 0.4,
                "mean_reverting": 0.4,
                "panic": 0.1,
                "low_liquidity": 0.1,
                "queue_lock": 0.1,
            },
            "market_making": {
                "normal": 0.7,
                "low_liquidity": 0.8,
                "queue_lock": 0.6,
                "trend": 0.3,
                "panic": 0.2,
                "mean_reverting": 0.5,
            },
            "defensive": {
                "panic": 0.9,
                "low_liquidity": 0.7,
                "queue_lock": 0.6,
                "normal": 0.2,
                "trend": 0.1,
                "mean_reverting": 0.2,
            },
        }

    def register_alpha(self, alpha_id: str, alpha_type: str = "momentum", initial_weight: float = 0.1) -> None:
        """Register an alpha with its type for regime-based allocation."""
        fitness = self._regime_fitness.get(alpha_type, dict.fromkeys(self._regime_fitness.get("momentum", {}), 0.5))
        self._allocations[alpha_id] = AlphaAllocation(
            alpha_id=alpha_id,
            weight=initial_weight,
            regime_fitness=fitness,
        )

    def set_regime(self, regime: str) -> None:
        self._current_regime = regime
        self._rebalance()

    def update_alpha_signal(self, alpha_id: str, signal: float) -> None:
        if alpha_id in self._allocations:
            self._allocations[alpha_id].current_signal = signal

    def update_alpha_type(self, alpha_id: str, alpha_type: str) -> None:
        fitness = self._regime_fitness.get(alpha_type, dict.fromkeys(self._regime_fitness.get("momentum", {}), 0.5))
        if alpha_id in self._allocations:
            self._allocations[alpha_id].regime_fitness = fitness

    def _rebalance(self) -> None:
        """Rebalance alpha weights based on current regime."""
        if not self._allocations:
            return

        total_fitness = 0.0
        for alloc in self._allocations.values():
            fitness = alloc.regime_fitness.get(self._current_regime, 0.5)
            alloc.is_active = fitness > 0.2
            if alloc.is_active:
                total_fitness += fitness

        if total_fitness > 0:
            for alloc in self._allocations.values():
                if alloc.is_active:
                    alloc.weight = alloc.regime_fitness.get(self._current_regime, 0.5) / total_fitness
                else:
                    alloc.weight = 0.0

    def get_active_alphas(self) -> list[str]:
        return [aid for aid, a in self._allocations.items() if a.is_active]

    def get_combined_signal(self) -> float:
        """Compute the combined portfolio signal from all active alphas."""
        signal = 0.0
        for alloc in self._allocations.values():
            if alloc.is_active:
                signal += alloc.weight * alloc.current_signal
        return signal

    def get_allocation_summary(self) -> dict[str, dict[str, Any]]:
        return {
            aid: {
                "weight": a.weight,
                "is_active": a.is_active,
                "signal": a.current_signal,
                "regime_fitness": a.regime_fitness.get(self._current_regime, 0),
            }
            for aid, a in self._allocations.items()
        }

    def reduce_exposure(self, factor: float) -> None:
        """Reduce all alpha weights by a factor (e.g., 0.5 = 50% reduction)."""
        for alloc in self._allocations.values():
            alloc.weight *= factor
            if alloc.weight < 0.01:
                alloc.is_active = False

    def reset(self) -> None:
        self._allocations.clear()
        self._current_regime = "normal"
