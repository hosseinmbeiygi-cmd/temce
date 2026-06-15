from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RebalanceRule:
    frequency_days: int = 30
    threshold_pct: float = 5.0


class Rebalancer:
    def __init__(self, rule: RebalanceRule | None = None) -> None:
        self.rule = rule or RebalanceRule()
        self._days_since_rebalance = 0

    def should_rebalance(self, current_weights: dict[str, float], target_weights: dict[str, float]) -> bool:
        self._days_since_rebalance += 1
        if self._days_since_rebalance >= self.rule.frequency_days:
            self._days_since_rebalance = 0
            return True
        for inst, target in target_weights.items():
            current = current_weights.get(inst, 0.0)
            if target > 0 and abs(current - target) / target * 100 > self.rule.threshold_pct:
                self._days_since_rebalance = 0
                return True
        return False

    def compute_trades(
        self, current: dict[str, float], target: dict[str, float], total_capital: float
    ) -> list[dict[str, Any]]:
        trades: list[dict[str, Any]] = []
        for inst, target_w in target.items():
            target_value = total_capital * target_w
            current_value = current.get(inst, 0.0)
            diff = target_value - current_value
            if abs(diff) > 0.01 * total_capital:
                trades.append(
                    {
                        "instrument_id": inst,
                        "side": "buy" if diff > 0 else "sell",
                        "value": abs(diff),
                    }
                )
        return trades

    def reset(self) -> None:
        self._days_since_rebalance = 0
