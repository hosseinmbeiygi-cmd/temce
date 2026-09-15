from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class AllocationDecision:
    strategy_id: str
    capital: float = 0.0
    weight: float = 0.0
    sharpe: float = 0.0
    volatility: float = 0.0
    max_drawdown: float = 0.0
    is_active: bool = True


class DynamicAllocator:
    """Capital allocation engine that distributes capital across strategies.

    Supports multiple allocation methods:
    - equal: Equal capital distribution
    - sharpe_weighted: Capital ∝ Sharpe / Volatility
    - drawdown_based: Reduce capital for strategies in drawdown
    - risk_parity: Equal risk contribution
    - dynamic: Combination of all methods based on strategy health
    """

    def __init__(self, method: str = "dynamic", max_drawdown_cutoff: float = 0.2) -> None:
        self.method = method
        self.max_drawdown_cutoff = max_drawdown_cutoff
        self._allocations: dict[str, AllocationDecision] = {}
        self._total_capital: float = 0.0

    def set_total_capital(self, capital: float) -> None:
        self._total_capital = capital

    def register_strategy(
        self,
        strategy_id: str,
        sharpe: float = 0.0,
        volatility: float = 0.2,
        max_drawdown: float = 0.0,
    ) -> None:
        self._allocations[strategy_id] = AllocationDecision(
            strategy_id=strategy_id,
            sharpe=sharpe,
            volatility=volatility,
            max_drawdown=max_drawdown,
        )

    def update_metrics(
        self,
        strategy_id: str,
        sharpe: float | None = None,
        volatility: float | None = None,
        max_drawdown: float | None = None,
    ) -> None:
        alloc = self._allocations.get(strategy_id)
        if alloc is None:
            return
        if sharpe is not None:
            alloc.sharpe = sharpe
        if volatility is not None:
            alloc.volatility = volatility
        if max_drawdown is not None:
            alloc.max_drawdown = max_drawdown

        # Auto-deactivate if drawdown exceeds cutoff
        if max_drawdown is not None and max_drawdown > self.max_drawdown_cutoff:
            alloc.is_active = False

    def reactivate_strategy(self, strategy_id: str) -> None:
        """Reactivate a strategy after drawdown recovery."""
        alloc = self._allocations.get(strategy_id)
        if alloc is not None:
            alloc.is_active = True

    def auto_reactivate(self, recovery_threshold: float = 0.05) -> None:
        """Auto-reactivate strategies whose drawdown has recovered below threshold."""
        for alloc in self._allocations.values():
            if not alloc.is_active and alloc.max_drawdown <= recovery_threshold:
                alloc.is_active = True

    def allocate(self) -> dict[str, float]:
        """Compute capital allocation for all strategies.

        Returns:
            Dict of {strategy_id: allocated_capital}
        """
        if not self._allocations:
            return {}

        if self.method == "equal":
            return self._allocate_equal()
        elif self.method == "sharpe_weighted":
            return self._allocate_sharpe_weighted()
        elif self.method == "drawdown_based":
            return self._allocate_drawdown_based()
        elif self.method == "risk_parity":
            return self._allocate_risk_parity()
        else:  # dynamic
            return self._allocate_dynamic()

    def _allocate_equal(self) -> dict[str, float]:
        active = [s for s, a in self._allocations.items() if a.is_active]
        if not active:
            return {}
        per_strategy = self._total_capital / len(active)
        return dict.fromkeys(active, per_strategy)

    def _allocate_sharpe_weighted(self) -> dict[str, float]:
        active = [(s, a) for s, a in self._allocations.items() if a.is_active]
        if not active:
            return {}

        scores: list[tuple[str, float]] = []
        for sid, alloc in active:
            vol = max(alloc.volatility, 0.01)
            score = (max(alloc.sharpe, 0) + 0.01) / vol
            scores.append((sid, score))

        total_score = sum(s for _, s in scores)
        if total_score <= 0:
            return self._allocate_equal()

        return {sid: self._total_capital * (s / total_score) for sid, s in scores}

    def _allocate_drawdown_based(self) -> dict[str, float]:
        active = [(s, a) for s, a in self._allocations.items() if a.is_active]
        if not active:
            return {}

        # Strategies with lower drawdown get more capital
        scores: list[tuple[str, float]] = []
        for sid, alloc in active:
            dd_penalty = min(alloc.max_drawdown / 0.1, 1.0)  # 0 = no penalty, 1 = full penalty
            score = max(1.0 - dd_penalty, 0.1)
            scores.append((sid, score))

        total_score = sum(s for _, s in scores)
        return {sid: self._total_capital * (s / total_score) for sid, s in scores}

    def _allocate_risk_parity(self) -> dict[str, float]:
        active = [(s, a) for s, a in self._allocations.items() if a.is_active]
        if not active:
            return {}

        vols = np.array([max(a.volatility, 0.01) for _, a in active])
        inv_vol = 1.0 / vols
        weights = inv_vol / np.sum(inv_vol)

        return {sid: self._total_capital * float(w) for (sid, _), w in zip(active, weights, strict=False)}

    def _allocate_dynamic(self) -> dict[str, float]:
        """Combine all methods for a dynamic allocation."""
        equal = self._allocate_equal()
        sharpe_w = self._allocate_sharpe_weighted()
        dd_w = self._allocate_drawdown_based()

        # Average the three methods
        combined: dict[str, float] = {}
        for sid in self._allocations:
            if not self._allocations[sid].is_active:
                continue
            eq = equal.get(sid, 0)
            sw = sharpe_w.get(sid, 0)
            dw = dd_w.get(sid, 0)
            combined[sid] = (eq + sw + dw) / 3

        total = sum(combined.values())
        if total > 0:
            combined = {k: v / total * self._total_capital for k, v in combined.items()}

        return combined

    def get_allocation(self, strategy_id: str) -> float:
        return self._allocations.get(strategy_id, AllocationDecision(strategy_id=strategy_id)).capital

    def get_summary(self) -> dict[str, dict[str, Any]]:
        return {
            sid: {
                "capital": a.capital,
                "weight": a.weight,
                "sharpe": a.sharpe,
                "volatility": a.volatility,
                "max_drawdown": a.max_drawdown,
                "is_active": a.is_active,
            }
            for sid, a in self._allocations.items()
        }

    def reset(self) -> None:
        self._allocations.clear()
        self._total_capital = 0.0
