from __future__ import annotations

from typing import Any


class BenchmarkRunner:
    def __init__(self, n_runs: int = 5) -> None:
        self.n_runs = n_runs

    def benchmark(self, model: Any, X: Any, y: Any) -> dict[str, float]:
        import time

        import numpy as np

        times = []
        for _ in range(self.n_runs):
            start = time.perf_counter()
            model.predict(X)
            times.append(time.perf_counter() - start)
        return {
            "mean": float(np.mean(times)),
            "std": float(np.std(times)),
            "min": float(np.min(times)),
            "max": float(np.max(times)),
        }
