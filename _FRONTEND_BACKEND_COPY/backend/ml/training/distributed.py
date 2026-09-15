from __future__ import annotations

from typing import Any


class DistributedTrainer:
    def __init__(self, n_workers: int = 4) -> None:
        self.n_workers = n_workers

    def train_parallel(self, model: Any, X: Any, y: Any) -> None:
        chunk_size = len(X) // self.n_workers
        chunks = [(X[i : i + chunk_size], y[i : i + chunk_size]) for i in range(0, len(X), chunk_size)]
        for chunk_X, chunk_y in chunks:
            model.fit(chunk_X, chunk_y)
