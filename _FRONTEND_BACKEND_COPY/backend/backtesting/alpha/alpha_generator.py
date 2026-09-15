from __future__ import annotations

from typing import Any

import numpy as np


class AlphaGenerator:
    """Generates alpha signals from microstructure features.

    Supports three generation methods:
    1. feature_combination: Combine features using arithmetic operations
    2. templates: Use predefined alpha templates (mean reversion, momentum, etc.)
    3. symbolic: Random formula generation (simplified)
    """

    def __init__(self, seed: int = 42) -> None:
        self._rng = np.random.RandomState(seed)
        self._alpha_counter = 0

    @staticmethod
    def mean_reversion(price: float, rolling_mean: float) -> float:
        if rolling_mean <= 0:
            return 0.0
        return -(price - rolling_mean) / rolling_mean

    @staticmethod
    def momentum(price: float, price_lag: float) -> float:
        if price_lag <= 0:
            return 0.0
        return (price - price_lag) / price_lag

    @staticmethod
    def zscore_alpha(feature_value: float, mean: float, std: float) -> float:
        if std <= 0:
            return 0.0
        return (feature_value - mean) / std

    @staticmethod
    def imbalance_alpha(imbalance: float, spread: float) -> float:
        if spread <= 0:
            return 0.0
        return imbalance / spread

    def generate_combination_alpha(self, features: dict[str, Any], template: str = "zscore") -> float:
        """Generate alpha using a template."""
        if template == "mean_reversion":
            price = features.get("mid_price", 0) or features.get("last_price", 0)
            mean = features.get("rolling_mean_20", price)
            return self.mean_reversion(price, mean)
        elif template == "momentum":
            price = features.get("mid_price", 0) or features.get("last_price", 0)
            lag = features.get("price_lag_20", price)
            return self.momentum(price, lag)
        elif template == "zscore":
            feature_name = str(features.get("_feature_name", "queue_imbalance"))
            value = features.get(feature_name, 0)
            mean = features.get(f"{feature_name}_mean", 0)
            std = features.get(f"{feature_name}_std", 1)
            return self.zscore_alpha(value, mean, std)
        elif template == "imbalance_spread":
            imb = features.get("queue_imbalance", 0)
            sprd = features.get("spread", 0.01)
            return self.imbalance_alpha(imb, sprd)
        return 0.0

    def generate_all_templates(self, features: dict[str, float]) -> dict[str, float]:
        """Generate all template alphas at once."""
        alphas: dict[str, float] = {}
        alphas["alpha_mr"] = self.generate_combination_alpha(features, "mean_reversion")
        alphas["alpha_mom"] = self.generate_combination_alpha(features, "momentum")
        alphas["alpha_imb"] = self.generate_combination_alpha(features, "imbalance_spread")
        if "queue_imbalance_mean" in features:
            alphas["alpha_z_imb"] = self.generate_combination_alpha(
                {**features, "_feature_name": "queue_imbalance"}, "zscore"
            )
        if "spread_mean" in features:
            alphas["alpha_z_spread"] = self.generate_combination_alpha(
                {**features, "_feature_name": "spread"}, "zscore"
            )
        return alphas

    def generate_random_alpha(self, feature_names: list[str]) -> tuple[str, str]:
        """Generate a random alpha formula (returns name and formula description)."""
        self._alpha_counter += 1
        name = f"alpha_{self._alpha_counter:04d}"
        ops = ["+", "-", "*", "/"]
        f1, f2 = self._rng.choice(feature_names, 2, replace=False)
        op = self._rng.choice(ops)
        formula = f"{f1} {op} {f2}"
        return name, formula

    def reset(self) -> None:
        self._alpha_counter = 0
