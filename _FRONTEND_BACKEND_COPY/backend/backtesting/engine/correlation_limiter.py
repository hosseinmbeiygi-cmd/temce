"""Correlation-based position limiter (roadmap v1:108 + v2:84-86).

Checks 20-day return correlation before opening a new position.
If correlation > threshold with existing holdings, reduce new position size
linearly with correlation.
"""

from __future__ import annotations

import math


class CorrelationLimiter:
    def __init__(self, window: int = 20, threshold: float = 0.5, max_corr: float = 0.7) -> None:
        self.window = window
        self.threshold = threshold
        self.max_corr = max_corr

    @staticmethod
    def _returns(prices: list[float]) -> list[float]:
        return [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices)) if prices[i - 1] != 0]

    @staticmethod
    def _pearson(a: list[float], b: list[float]) -> float:
        n = min(len(a), len(b))
        if n < 2:
            return 0.0
        a, b = a[-n:], b[-n:]
        ma, mb = sum(a) / n, sum(b) / n
        num = sum((x - ma) * (y - mb) for x, y in zip(a, b, strict=False))
        da = math.sqrt(sum((x - ma) ** 2 for x in a))
        db = math.sqrt(sum((y - mb) ** 2 for y in b))
        if da == 0 or db == 0:
            return 0.0
        return num / (da * db)

    def correlation(self, prices_a: list[float], prices_b: list[float]) -> float:
        ra = self._returns(prices_a)
        rb = self._returns(prices_b)
        # use last window returns
        if len(ra) > self.window:
            ra = ra[-self.window :]
        if len(rb) > self.window:
            rb = rb[-self.window :]
        return self._pearson(ra, rb)

    def scale_factor(self, corr: float) -> float:
        """Linear reduction: 1.0 at threshold -> 0.0 at max_corr."""
        if corr <= self.threshold:
            return 1.0
        if corr >= self.max_corr:
            return 0.0
        # linear interpolation
        return 1.0 - (corr - self.threshold) / (self.max_corr - self.threshold)

    def check(self, new_prices: list[float], existing_prices_map: dict[str, list[float]]) -> tuple[float, float]:
        """Return (max_corr, scale_factor) vs all existing positions."""
        if not existing_prices_map:
            return 0.0, 1.0
        max_corr = 0.0
        for prices in existing_prices_map.values():
            c = abs(self.correlation(new_prices, prices))
            max_corr = max(max_corr, c)
        return max_corr, self.scale_factor(max_corr)
