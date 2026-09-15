from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RebalanceFrequency(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class RebalanceCost:
    commission_pct: float = 0.0035
    slippage_bps: float = 0.0
    tax_pct: float = 0.0

    def total_cost_pct(self) -> float:
        return self.commission_pct + self.slippage_bps / 10000.0 + self.tax_pct


@dataclass
class RebalanceRule:
    frequency_days: int | None = None  # None = derive from frequency enum
    threshold_pct: float = 5.0
    frequency: RebalanceFrequency = RebalanceFrequency.DAILY
    min_trade_value: float = 0.0
    max_turnover_pct: float = 100.0
    cost: RebalanceCost = field(default_factory=RebalanceCost)

    def __post_init__(self) -> None:
        if self.frequency_days is None:
            mapping = {
                RebalanceFrequency.DAILY: 1,
                RebalanceFrequency.WEEKLY: 7,
                RebalanceFrequency.MONTHLY: 30,
            }
            self.frequency_days = mapping.get(self.frequency, 30)


@dataclass
class RebalanceResult:
    trades: list[dict[str, Any]] = field(default_factory=list)
    total_cost: float = 0.0
    triggered_by: str = ""
    turnover_pct: float = 0.0


class Rebalancer:
    def __init__(self, rule: RebalanceRule | None = None) -> None:
        self.rule = rule or RebalanceRule()
        self._days_since_rebalance = 0
        self._rebalance_count = 0
        self._total_costs: float = 0.0
        self._history: list[dict[str, Any]] = []

    @property
    def rebalance_count(self) -> int:
        return self._rebalance_count

    def should_rebalance(self, current_weights: dict[str, float], target_weights: dict[str, float]) -> tuple[bool, str]:
        """Check if rebalance is needed. Returns (should_rebalance, reason)."""
        self._days_since_rebalance += 1

        # Check frequency-based trigger
        if self._days_since_rebalance >= self.rule.frequency_days:
            self._days_since_rebalance = 0
            return (True, "daily")

        # Check threshold-based trigger
        for inst, target in target_weights.items():
            current = current_weights.get(inst, 0.0)
            if target > 0 and abs(current - target) / target * 100 > self.rule.threshold_pct:
                self._days_since_rebalance = 0
                return (True, "threshold")

        return (False, "")

    def compute_trades(
        self, current: dict[str, float], target: dict[str, float], total_capital: float
    ) -> RebalanceResult:
        trades: list[dict[str, Any]] = []
        total_cost = 0.0
        total_turnover = 0.0

        for inst, target_w in target.items():
            target_value = total_capital * target_w
            current_value = current.get(inst, 0.0)
            diff = target_value - current_value

            if abs(diff) <= self.rule.min_trade_value:
                continue

            if abs(diff) > self.rule.min_trade_value:
                trades.append(
                    {
                        "instrument_id": inst,
                        "side": "buy" if diff > 0 else "sell",
                        "value": abs(diff),
                    }
                )
                trade_cost = abs(diff) * self.rule.cost.total_cost_pct()
                total_cost += trade_cost
                total_turnover += abs(diff)

        turnover_pct = (total_turnover / total_capital * 100.0) if total_capital > 0 else 0.0

        # Apply max turnover limit
        if turnover_pct > self.rule.max_turnover_pct:
            scale = self.rule.max_turnover_pct / turnover_pct
            for t in trades:
                t["value"] *= scale
            total_cost *= scale
            total_turnover *= scale
            turnover_pct = self.rule.max_turnover_pct

        return RebalanceResult(
            trades=trades,
            total_cost=total_cost,
            turnover_pct=turnover_pct,
        )

    def rebalance(
        self,
        current: dict[str, float],
        target: dict[str, float],
        total_capital: float,
    ) -> RebalanceResult | None:
        """Execute a full rebalance cycle. Returns None if no rebalance needed.

        current can be absolute values or weights (ratios < 1).
        """
        # Determine if current values are weights (all < 1) or absolute values
        is_weight = all(v < 1 for v in current.values()) if current else False
        weights = (
            current if is_weight else {k: v / total_capital if total_capital > 0 else 0 for k, v in current.items()}
        )
        should, reason = self.should_rebalance(weights, target)

        if not should:
            return None

        result = self.compute_trades(current, target, total_capital)
        result.triggered_by = reason

        self._rebalance_count += 1
        self._total_costs += result.total_cost
        self._history.append(
            {
                "rebalance_id": self._rebalance_count,
                "triggered_by": reason,
                "trades": result.trades,
                "total_cost": result.total_cost,
                "turnover_pct": result.turnover_pct,
            }
        )

        return result

    def get_history(self) -> list[dict[str, Any]]:
        return list(self._history)

    def get_total_costs(self) -> float:
        return self._total_costs

    def reset(self) -> None:
        self._days_since_rebalance = 0
        self._rebalance_count = 0
        self._total_costs = 0.0
        self._history.clear()
