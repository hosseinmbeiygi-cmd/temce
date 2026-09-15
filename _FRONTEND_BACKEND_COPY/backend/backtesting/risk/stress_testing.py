from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np


@dataclass
class StressScenario:
    name: str
    market_drop_pct: float
    volatility_shock_pct: float
    liquidity_drop_pct: float = 0.0


@dataclass
class HistoricalScenario:
    name: str
    start_date: datetime
    end_date: datetime
    market_drop_pct: float
    volatility_shock_pct: float


@dataclass
class StressTesting:
    scenarios: list[StressScenario] = field(default_factory=list)
    historical_scenarios: list[HistoricalScenario] = field(default_factory=list)

    def add_scenario(self, scenario: StressScenario) -> None:
        self.scenarios.append(scenario)

    def add_historical_scenario(self, scenario: HistoricalScenario) -> None:
        self.historical_scenarios.append(scenario)

    def add_default_iran_scenarios(self) -> None:
        defaults = [
            StressScenario(name="فتنه 88", market_drop_pct=10.0, volatility_shock_pct=30.0),
            StressScenario(name="برجام", market_drop_pct=8.0, volatility_shock_pct=20.0),
            StressScenario(name="تحریم نفت", market_drop_pct=12.0, volatility_shock_pct=25.0),
            StressScenario(name="کرونا", market_drop_pct=15.0, volatility_shock_pct=40.0),
            StressScenario(name="جهش ارز 97", market_drop_pct=18.0, volatility_shock_pct=35.0),
            StressScenario(name="شوک بهمن 99", market_drop_pct=20.0, volatility_shock_pct=50.0),
            StressScenario(name="بحران جهانی", market_drop_pct=25.0, volatility_shock_pct=60.0),
        ]
        self.scenarios.extend(defaults)

    def add_default_historical_scenarios(self) -> None:
        defaults = [
            HistoricalScenario(
                name="شوک ارزی 97",
                start_date=datetime(2018, 4, 1),
                end_date=datetime(2018, 9, 1),
                market_drop_pct=18.0,
                volatility_shock_pct=35.0,
            ),
            HistoricalScenario(
                name="کرونا 98",
                start_date=datetime(2020, 2, 1),
                end_date=datetime(2020, 5, 1),
                market_drop_pct=15.0,
                volatility_shock_pct=40.0,
            ),
            HistoricalScenario(
                name="تحریم 1400",
                start_date=datetime(2021, 5, 1),
                end_date=datetime(2021, 8, 1),
                market_drop_pct=12.0,
                volatility_shock_pct=25.0,
            ),
        ]
        self.historical_scenarios.extend(defaults)

    def run(self, portfolio_value: float, positions: dict[str, Any] | None = None) -> list[dict[str, Any]]:
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
                    "survived": new_value > portfolio_value * 0.5,
                }
            )
        return results

    def run_historical_scenario(self, portfolio_value: float, scenario: HistoricalScenario) -> dict[str, Any]:
        new_value = portfolio_value * (1 - scenario.market_drop_pct / 100)
        impact = portfolio_value - new_value
        survived = new_value > portfolio_value * 0.5
        return {
            "scenario": scenario.name,
            "market_drop_pct": scenario.market_drop_pct,
            "volatility_shock_pct": scenario.volatility_shock_pct,
            "portfolio_before": portfolio_value,
            "portfolio_after": new_value,
            "impact": impact,
            "impact_pct": scenario.market_drop_pct,
            "details": {"start_date": str(scenario.start_date.date()), "end_date": str(scenario.end_date.date())},
            "survived": survived,
        }

    def run_all_historical(self, portfolio_value: float) -> list[dict[str, Any]]:
        return [self.run_historical_scenario(portfolio_value, hs) for hs in self.historical_scenarios]

    def run_worst_case(self, portfolio_value: float) -> dict[str, Any]:
        results = self.run(portfolio_value)
        worst = max(results, key=lambda r: r["impact_pct"])
        return worst

    def run_monte_carlo(
        self, portfolio_value: float, n_simulations: int = 10000, seed: int | None = None
    ) -> dict[str, float]:
        if seed is not None:
            np.random.seed(seed)
        daily_vol = 0.02
        shocks = np.random.normal(0, daily_vol, n_simulations)
        shocked_values = portfolio_value * (1 + shocks)
        return {
            "mean": float(np.mean(shocked_values)),
            "std": float(np.std(shocked_values)),
            "var_95": float(np.percentile(shocked_values, 5)),
            "var_99": float(np.percentile(shocked_values, 1)),
            "cvar_95": float(np.mean(shocked_values[shocked_values <= np.percentile(shocked_values, 5)])),
            "worst_case": float(np.min(shocked_values)),
        }

    def clear(self) -> None:
        self.scenarios.clear()
        self.historical_scenarios.clear()
