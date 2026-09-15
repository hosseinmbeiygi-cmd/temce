from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class StressScenario:
    name: str
    description: str
    depth_reduction_pct: float = 0.0
    volatility_multiplier: float = 1.0
    spread_multiplier: float = 1.0
    impact_multiplier: float = 1.0
    price_shock_pct: float = 0.0


class AlphaStressTest:
    """Stress tests alpha signals under various adverse market scenarios."""

    def __init__(self) -> None:
        self.scenarios: list[StressScenario] = [
            StressScenario("liquidity_shock", "70% depth reduction", depth_reduction_pct=0.7),
            StressScenario(
                "high_volatility",
                "2x volatility spike",
                volatility_multiplier=2.0,
                spread_multiplier=2.0,
                impact_multiplier=2.0,
            ),
            StressScenario("queue_lock", "Bid/ask limit lock", spread_multiplier=5.0, depth_reduction_pct=0.5),
            StressScenario(
                "flash_crash", "5% flash crash", price_shock_pct=-0.05, volatility_multiplier=3.0, impact_multiplier=3.0
            ),
            StressScenario(
                "combined_shock",
                "Liquidity + volatility + crash",
                depth_reduction_pct=0.5,
                volatility_multiplier=2.0,
                price_shock_pct=-0.03,
                spread_multiplier=2.0,
            ),
        ]

    def run(
        self,
        alpha_id: str,
        base_signal: list[float],
        base_returns: list[float],
        evaluator: Any,
    ) -> dict[str, dict[str, float]]:
        """Run all stress scenarios on an alpha signal.

        Args:
            alpha_id: Alpha identifier
            base_signal: Original alpha signal
            base_returns: Original forward returns
            evaluator: FastAlphaEvaluator instance

        Returns:
            Dict of {scenario_name: metrics_dict}
        """
        results: dict[str, dict[str, float]] = {}
        base_metrics = evaluator.evaluate(base_signal, base_returns)
        results["base"] = {
            "sharpe": base_metrics.sharpe,
            "ic": base_metrics.information_coefficient,
            "hit_rate": base_metrics.hit_rate,
            "max_dd": base_metrics.max_drawdown,
        }

        for scenario in self.scenarios:
            stressed_returns = self._apply_scenario(base_returns, scenario)
            metrics = evaluator.evaluate(base_signal, stressed_returns)
            results[scenario.name] = {
                "sharpe": metrics.sharpe,
                "ic": metrics.information_coefficient,
                "hit_rate": metrics.hit_rate,
                "max_dd": metrics.max_drawdown,
                "sharpe_decay": metrics.sharpe - base_metrics.sharpe if base_metrics.sharpe != 0 else 0,
            }

        return results

    def run_all(
        self,
        alphas: dict[str, tuple[list[float], list[float]]],
        evaluator: Any,
    ) -> dict[str, dict[str, dict[str, float]]]:
        """Run stress tests for multiple alphas.

        Args:
            alphas: Dict of {alpha_id: (signal, returns)}
            evaluator: FastAlphaEvaluator instance

        Returns:
            Dict of {alpha_id: {scenario: metrics}}
        """
        results: dict[str, dict[str, dict[str, float]]] = {}
        for alpha_id, (signal, returns) in alphas.items():
            results[alpha_id] = self.run(alpha_id, signal, returns, evaluator)
        return results

    def _apply_scenario(self, returns: list[float], scenario: StressScenario) -> list[float]:
        """Apply stress scenario transformations to return series."""
        stressed = np.array(returns)

        # Volatility multiplier
        if scenario.volatility_multiplier != 1.0:
            stressed = stressed * scenario.volatility_multiplier

        # Price shock
        if scenario.price_shock_pct != 0.0:
            shock_idx = len(stressed) // 2
            shock_size = abs(scenario.price_shock_pct)
            for i in range(shock_idx, min(shock_idx + 5, len(stressed))):
                stressed[i] -= np.sign(scenario.price_shock_pct) * shock_size

        # Impact multiplier (increases trade costs)
        if scenario.impact_multiplier != 1.0:
            costs = np.random.randn(len(stressed)) * 0.001 * (scenario.impact_multiplier - 1.0)
            stressed = stressed - costs

        return stressed.tolist()

    def select_robust_alphas(
        self, stress_results: dict[str, dict[str, dict[str, float]]], min_sharpe_under_stress: float = 0.5
    ) -> list[str]:
        """Select alphas that remain profitable under stress.

        Args:
            stress_results: Results from run_all
            min_sharpe_under_stress: Minimum sharpe in worst scenario

        Returns:
            List of robust alpha IDs
        """
        robust: list[str] = []
        for alpha_id, scenarios in stress_results.items():
            worst_sharpe = min(v["sharpe"] for v in scenarios.values())
            if worst_sharpe >= min_sharpe_under_stress:
                robust.append(alpha_id)
        return robust
