from __future__ import annotations

import math
import random


class OrderArrivalModel:
    def __init__(self, lambda_rate: float = 0.02, min_orders: int = 0, max_orders: int = 50) -> None:
        self.lambda_rate = lambda_rate
        self.min_orders = min_orders
        self.max_orders = max_orders

    def sample_arrivals(self, queue_size: int) -> int:
        lam = self.lambda_rate * max(queue_size, 1)
        k = 0
        p = 1.0
        threshold = random.random()
        while p > threshold and k < self.max_orders:
            k += 1
            p *= lam / k
        return max(self.min_orders, min(k, self.max_orders))

    def sample_quantity(self, avg_trade_size: float = 10000) -> int:
        return max(1, int(random.expovariate(1.0 / max(avg_trade_size, 1))))

    def sample_price_offset(self, reference_price: float, max_deviation_pct: float = 0.01) -> float:
        deviation = reference_price * max_deviation_pct * (random.random() * 2 - 1)
        return reference_price + deviation

    @staticmethod
    def poisson_probability(k: int, lam: float) -> float:
        return (lam ** k) * math.exp(-lam) / math.factorial(k)
