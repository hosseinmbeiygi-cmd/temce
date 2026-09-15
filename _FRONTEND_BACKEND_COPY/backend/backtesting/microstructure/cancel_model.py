from __future__ import annotations

import numpy as np


class CancelModel:
    def __init__(self, base_cancel_rate: float = 0.12, lambda_c: float = 0.001, min_cancel: int = 0) -> None:
        self.base_cancel_rate = base_cancel_rate
        self.lambda_c = lambda_c
        self.min_cancel = min_cancel

    def estimate_cancel(self, prev_volume: int, current_volume: int, trade_volume: int) -> int:
        delta = prev_volume - current_volume
        cancel = max(self.min_cancel, delta - trade_volume)
        return cancel

    def estimate_cancel_rate(self, queue_size: int) -> float:
        return self.base_cancel_rate + self.lambda_c * queue_size

    def sample_cancel_events(self, queue_size: int, time_step_minutes: float = 1.0) -> int:
        rate = self.estimate_cancel_rate(queue_size)
        expected = rate * time_step_minutes
        # ``random`` from the stdlib has no poisson() method. Use NumPy's
        # Poisson sampler so cancellation counts have the requested
        # distribution instead of a biased uniform fallback.
        return int(np.random.poisson(max(expected, 0.0)))

    def calibrate_from_data(self, cancel_volumes: list[int], queue_sizes: list[int]) -> None:
        if len(cancel_volumes) < 2 or len(queue_sizes) < 2:
            return
        total_cancel = sum(cancel_volumes)
        avg_queue = sum(queue_sizes) / len(queue_sizes)
        if avg_queue > 0:
            self.base_cancel_rate = total_cancel / (avg_queue * len(cancel_volumes))
        self.lambda_c = self.base_cancel_rate * 0.01
