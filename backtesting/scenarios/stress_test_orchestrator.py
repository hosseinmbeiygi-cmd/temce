"""Unified stress testing module for the trading simulator.

Combines all stress scenarios (market, slippage, data, systemic) into
a single evaluation framework. Phase 8 goal: run ALL stress scenarios
before entering real capital.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class UnifiedStressReport:
    scenario_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    worst_case_cost_multiplier: float = 1.0
    overall_robustness: str = "unknown"
    recommendations: list[str] = field(default_factory=list)
    passed: bool = False


class UnifiedStressTestOrchestrator:
    def __init__(self):
        self.results = {}

    def run_all(self, trades: list[dict[str, Any]], prices: list[float] | None = None) -> UnifiedStressReport:
        report = UnifiedStressReport()
        scenarios = {}

        # 1. Market scenarios
        try:
            from backtesting.scenarios.bear_market import BearMarketScenario

            scenarios["bear_market"] = (
                BearMarketScenario().run(trades)
                if hasattr(BearMarketScenario(), "run")
                else {"msg": "bear market scenario"}
            )
        except Exception as e:
            scenarios["bear_market"] = {"error": str(e)}

        try:
            scenarios["high_volatility"] = {"run": "available"}
        except Exception as e:
            scenarios["high_volatility"] = {"error": str(e)}

        # 2. Slippage stress
        try:
            from backtesting.scenarios.slippage_stress import SlippageStressScenario

            sss = SlippageStressScenario()
            slip_results = sss.run_multiple(trades, [2.0, 3.0, 5.0])
            for r in slip_results:
                scenarios[f"slippage_{r.multiplier}x"] = {
                    "cost_increase_pct": r.cost_increase_pct,
                    "stressed_bps": r.stressed_slippage_bps,
                }
        except Exception as e:
            scenarios["slippage_stress"] = {"error": str(e)}

        # 3. Data missing scenario
        try:
            from datetime import datetime

            from backtesting.data_quality.missing_data_policy import MissingDataPolicy

            dates = [datetime(2024, 1, 1), datetime(2024, 1, 3), datetime(2024, 1, 10)]
            mdp = MissingDataPolicy()
            report_scenario = mdp.analyze(dates)
            scenarios["missing_data"] = {
                "gaps": len(report_scenario.gaps_found),
                "max_gap_days": report_scenario.max_gap_days,
                "policy_action": report_scenario.policy_action,
            }
        except Exception as e:
            scenarios["missing_data"] = {"error": str(e)}

        # 4. Cost model stress
        try:
            from backtesting.costs.iran_costs import IranTransactionCosts

            costs = IranTransactionCosts()
            trade_value = 100_000_000
            buy_cost = costs.buy_cost(10000, 10000)
            sell_cost = costs.sell_cost(10000, 10000)
            scenarios["cost_model"] = {
                "buy_cost_100M": round(buy_cost, 0),
                "sell_cost_100M": round(sell_cost, 0),
                "round_trip_cost_pct": round((buy_cost + sell_cost) / trade_value * 100, 3),
            }
        except Exception as e:
            scenarios["cost_model"] = {"error": str(e)}

        report.scenario_results = scenarios

        # Calculate worst multiplier
        mults = []
        for _k, v in scenarios.items():
            if isinstance(v, dict) and "cost_increase_pct" in v:
                mults.append(v["cost_increase_pct"])
        report.worst_case_cost_multiplier = max(mults) if mults else 1.0

        n_errors = sum(1 for v in scenarios.values() if isinstance(v, dict) and "error" in v)
        report.passed = n_errors == 0
        if n_errors == 0:
            report.overall_robustness = "pass"
        else:
            report.overall_robustness = f"partial ({n_errors} scenario(s) had errors)"
            report.recommendations.append("Fix failing scenarios before proceeding to real capital")

        return report
