from __future__ import annotations

"""Slippage Stress Scenario — 3x to 5x normal slippage for resilience testing."""

from dataclasses import dataclass
from typing import Any


@dataclass
class SlippageStressResult:
    scenario_name: str
    multiplier: float
    original_slippage_bps: float
    stressed_slippage_bps: float
    original_execution_cost: float
    stressed_execution_cost: float
    cost_increase_pct: float


class SlippageStressScenario:
    def __init__(self, base_slippage_bps: float = 10.0):
        self.base_slippage_bps = base_slippage_bps

    def run(self, trades: list[dict[str, Any]], multiplier: float = 3.0) -> SlippageStressResult:
        total_orig = sum(self._cost(t, self.base_slippage_bps) for t in trades)
        total_stress = sum(self._cost(t, self.base_slippage_bps * multiplier) for t in trades)
        incr = ((total_stress - total_orig) / total_orig * 100) if total_orig != 0 else 0
        return SlippageStressResult(
            scenario_name=f"slippage_{multiplier}x",
            multiplier=multiplier,
            original_slippage_bps=self.base_slippage_bps,
            stressed_slippage_bps=self.base_slippage_bps * multiplier,
            original_execution_cost=round(total_orig, 0),
            stressed_execution_cost=round(total_stress, 0),
            cost_increase_pct=round(incr, 2),
        )

    def run_multiple(
        self, trades: list[dict[str, Any]], multipliers: list[float] | None = None
    ) -> list[SlippageStressResult]:
        if multipliers is None:
            multipliers = [1.0, 2.0, 3.0, 5.0]
        return [self.run(trades, m) for m in multipliers]

    @staticmethod
    def _cost(trade: dict[str, Any], slippage_bps: float) -> float:
        price = trade.get("price", 0) or trade.get("avg_price", 0)
        qty = trade.get("quantity", 0)
        return price * qty * (slippage_bps / 10000)
