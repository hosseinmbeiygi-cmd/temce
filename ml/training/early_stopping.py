from __future__ import annotations


class EarlyStopping:
    def __init__(self, patience: int = 5, min_delta: float = 0.001) -> None:
        self.patience = patience
        self.min_delta = min_delta
        self.best_score: float | None = None
        self.counter = 0
        self.should_stop = False

    def step(self, score: float) -> None:
        if self.best_score is None:
            self.best_score = score
            return
        if score < self.best_score + self.min_delta:
            self.counter += 1
        else:
            self.best_score = score
            self.counter = 0
        if self.counter >= self.patience:
            self.should_stop = True
