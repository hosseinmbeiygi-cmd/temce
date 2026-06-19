from __future__ import annotations

from typing import Any

import numpy as np


class SimulationValidator:
    """Validates that hybrid simulation output matches real market characteristics."""

    @staticmethod
    def compare_spread_distribution(
        real_spreads: list[float],
        sim_spreads: list[float],
    ) -> dict[str, float]:
        if not real_spreads or not sim_spreads:
            return {"ks_statistic": 1.0, "similarity": 0.0}

        # Use numpy-based distribution comparison (no scipy dependency needed)
        real_hist, _ = np.histogram(real_spreads, bins=50, density=True)
        sim_hist, _ = np.histogram(sim_spreads, bins=50, density=True)

        # Bhattacharyya distance as similarity measure
        bc = np.sum(np.sqrt(real_hist * sim_hist))
        similarity = float(bc)

        return {
            "ks_statistic": float(1.0 - similarity),
            "similarity": similarity,
            "real_mean": float(np.mean(real_spreads)),
            "sim_mean": float(np.mean(sim_spreads)),
            "real_std": float(np.std(real_spreads)),
            "sim_std": float(np.std(sim_spreads)),
        }

    @staticmethod
    def compare_volatility(
        real_returns: list[float],
        sim_returns: list[float],
    ) -> dict[str, float]:
        if not real_returns or not sim_returns:
            return {"similarity": 0.0}

        real_vol = float(np.std(real_returns))
        sim_vol = float(np.std(sim_returns))
        vol_ratio = min(real_vol, sim_vol) / max(real_vol, sim_vol) if max(real_vol, sim_vol) > 0 else 0.0

        return {
            "real_volatility": real_vol,
            "sim_volatility": sim_vol,
            "volatility_ratio": vol_ratio,
            "similarity": vol_ratio,
        }

    @staticmethod
    def compare_order_flow_imbalance(
        real_imbalances: list[float],
        sim_imbalances: list[float],
    ) -> dict[str, float]:
        if not real_imbalances or not sim_imbalances:
            return {"similarity": 0.0}

        real_mean = float(np.mean(real_imbalances))
        sim_mean = float(np.mean(sim_imbalances))
        real_std = float(np.std(real_imbalances))
        sim_std = float(np.std(sim_imbalances))

        mean_diff = abs(real_mean - sim_mean) / max(abs(real_mean) + 0.001, 0.001)
        std_ratio = min(real_std, sim_std) / max(real_std, sim_std) if max(real_std, sim_std) > 0 else 0.0
        similarity = (1.0 - min(mean_diff, 1.0)) * 0.5 + std_ratio * 0.5

        return {
            "real_mean_imbalance": real_mean,
            "sim_mean_imbalance": sim_mean,
            "similarity": similarity,
        }

    @staticmethod
    def compare_trade_size_distribution(
        real_sizes: list[float],
        sim_sizes: list[float],
    ) -> dict[str, float]:
        if not real_sizes or not sim_sizes:
            return {"similarity": 0.0}

        real_log = np.log([max(s, 1) for s in real_sizes])
        sim_log = np.log([max(s, 1) for s in sim_sizes])

        real_mu = float(np.mean(real_log))
        real_sigma = float(np.std(real_log))
        sim_mu = float(np.mean(sim_log))
        sim_sigma = float(np.std(sim_log))

        mu_sim = 1.0 - min(abs(real_mu - sim_mu) / max(abs(real_mu) + 0.001, 0.001), 1.0)
        sigma_sim = min(real_sigma, sim_sigma) / max(real_sigma, sim_sigma, 0.001)

        return {
            "real_mu": real_mu,
            "sim_mu": sim_mu,
            "similarity": mu_sim * 0.5 + sigma_sim * 0.5,
        }

    def validate_all(
        self,
        real_data: dict[str, list[float]],
        sim_data: dict[str, list[float]],
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}

        if "spreads" in real_data and "spreads" in sim_data:
            results["spread"] = self.compare_spread_distribution(real_data["spreads"], sim_data["spreads"])

        if "returns" in real_data and "returns" in sim_data:
            results["volatility"] = self.compare_volatility(real_data["returns"], sim_data["returns"])

        if "imbalances" in real_data and "imbalances" in sim_data:
            results["imbalance"] = self.compare_order_flow_imbalance(real_data["imbalances"], sim_data["imbalances"])

        if "trade_sizes" in real_data and "trade_sizes" in sim_data:
            results["trade_size"] = self.compare_trade_size_distribution(real_data["trade_sizes"], sim_data["trade_sizes"])

        if results:
            scores = [v["similarity"] for v in results.values()]
            results["overall_similarity"] = float(np.mean(scores))
        else:
            results["overall_similarity"] = 0.0

        return results
