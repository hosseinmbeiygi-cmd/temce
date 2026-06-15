"""Normalization utilities for quantitative analysis.

All normalizers map raw indicator values into [0,1] or comparable Z-Score space
so that scores from different markets and indicators can be combined fairly.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


class ZScoreNormalizer:
    """Z-Score normalisation: Z = (x - mu) / sigma.

    When sigma is zero (flat series) returns 0.0.
    """

    def __init__(self, mu: float = 0.0, sigma: float = 1.0) -> None:
        self.mu = mu
        self.sigma = sigma if sigma > 0 else 1.0

    def __call__(self, x: float) -> float:
        return (x - self.mu) / self.sigma

    @classmethod
    def fit(cls, values: Sequence[float]) -> ZScoreNormalizer:
        """Fit from a sample (population std)."""
        n = len(values)
        if n == 0:
            return cls(mu=0.0, sigma=1.0)
        mu = sum(values) / n
        var = sum((v - mu) ** 2 for v in values) / n
        sigma = math.sqrt(var) if var > 0 else 1.0
        return cls(mu=mu, sigma=sigma)


class MinMaxClipped:
    """Min-Max scaling clipped to [0,1]: (x - a) / (b - a).

    Values below a map to 0, above b map to 1.
    """

    def __init__(self, a: float = 0.0, b: float = 1.0) -> None:
        self.a = a
        self.b = b
        self._range = b - a

    def __call__(self, x: float) -> float:
        if self._range <= 0:
            return 0.5
        val = (x - self.a) / self._range
        if val < 0.0:
            return 0.0
        if val > 1.0:
            return 1.0
        return val

    @classmethod
    def fit(cls, values: Sequence[float], pad: float = 0.0) -> MinMaxClipped:
        """Fit using min/max of sample, with optional padding."""
        if not values:
            return cls(a=0.0, b=1.0)
        lo, hi = min(values), max(values)
        if hi == lo:
            hi = lo + 1.0
        return cls(a=lo - pad, b=hi + pad)


class SigmoidNormalizer:
    """Sigmoid (logistic) normalizer: 1 / (1 + exp(-Z)).

    Transforms any real-valued Z-Score into (0,1).
    """

    def __call__(self, z: float) -> float:
        # Clip to avoid overflow
        if z > 50:
            return 1.0
        if z < -50:
            return 0.0
        return 1.0 / (1.0 + math.exp(-z))


class RobustScaler:
    """Robust scaling using median and IQR, mapped to [0,1] via sigmoid.

    Less sensitive to outliers than Z-Score.
    """

    def __init__(self, median: float = 0.0, iqr: float = 1.0) -> None:
        self.median = median
        self.iqr = iqr if iqr > 0 else 1.0

    def __call__(self, x: float) -> float:
        z = (x - self.median) / self.iqr
        return 1.0 / (1.0 + math.exp(-z))

    @classmethod
    def fit(cls, values: Sequence[float]) -> RobustScaler:
        """Fit from a sample."""
        if not values:
            return cls()
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        median = sorted_vals[n // 2] if n % 2 else (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0
        q1 = sorted_vals[n // 4]
        q3 = sorted_vals[3 * n // 4]
        iqr = q3 - q1
        if iqr == 0:
            iqr = 1.0
        return cls(median=median, iqr=iqr)
