from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ValueAtRisk:
    confidence: float = 0.95
    horizon_days: int = 1

    def compute(self, returns: list[float]) -> float:
        if len(returns) < 2:
            return 0.0
        arr = np.array(returns)
        var = float(np.percentile(arr, (1 - self.confidence) * 100))
        return var * np.sqrt(self.horizon_days)

    def compute_parametric(self, returns: list[float]) -> float:
        if len(returns) < 2:
            return 0.0
        from scipy.stats import norm

        mu = np.mean(returns)
        sigma = np.std(returns)
        z = norm.ppf(1 - self.confidence)
        var = mu + z * sigma
        return float(var * np.sqrt(self.horizon_days))

    def compute_historical(self, returns: list[float]) -> float:
        return self.compute(returns)
