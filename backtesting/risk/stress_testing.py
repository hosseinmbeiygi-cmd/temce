from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class StressScenario:
    name: str
    market_drop_pct: float
    volatility_shock_pct: float
    liquidity_drop_pct: float = 0.0


@dataclass
class StressTesting:
    scenarios: list[StressScenario] = field(default_factory=list)

    def add_scenario(self, scenario: StressScenario) -> None:
        self.scenarios.append(scenario)

    def run(self, portfolio_value: float, positions: dict[str, Any]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for scenario in self.scenarios:
            new_value = portfolio_value * (1 - scenario.market_drop_pct / 100)
            impact = portfolio_value - new_value
            results.append(
                {
                    "scenario": scenario.name,
                    "market_drop_pct": scenario.market_drop_pct,
                    "volatility_shock_pct": scenario.volatility_shock_pct,
                    "portfolio_before": portfolio_value,
                    "portfolio_after": new_value,
                    "impact": impact,
                    "impact_pct": scenario.market_drop_pct,
                }
            )
        return results

    def run_monte_carlo(self, portfolio_value: float, n_simulations: int = 10000) -> dict[str, float]:
        daily_vol = 0.02
        shocks = np.random.normal(0, daily_vol, n_simulations)
        shocked_values = portfolio_value * (1 + shocks)
        return {
            "mean": float(np.mean(shocked_values)),
            "std": float(np.std(shocked_values)),
            "var_95": float(np.percentile(shocked_values, 5)),
            "worst_case": float(np.min(shocked_values)),
        }

    def clear(self) -> None:
        self.scenarios.clear()
