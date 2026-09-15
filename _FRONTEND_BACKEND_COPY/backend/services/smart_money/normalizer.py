from __future__ import annotations


class MinMaxClipped:
    def __call__(self, x: float, a: float, b: float) -> float:
        if b <= a:
            return 0.0
        val = (x - a) / (b - a)
        if val < 0:
            return 0.0
        if val > 1:
            return 1.0
        return val


class ZScoreSigmoid:
    def __init__(self, mu: float = 0.0, sigma: float = 1.0) -> None:
        self.mu = mu
        self.sigma = sigma if sigma > 0 else 1.0

    def __call__(self, x: float) -> float:
        import math

        z = (x - self.mu) / self.sigma
        return 1.0 / (1.0 + math.exp(-z))
