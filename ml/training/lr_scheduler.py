from __future__ import annotations


class LearningRateScheduler:
    def __init__(self, initial_lr: float = 0.01, decay_factor: float = 0.1, decay_epochs: int = 10) -> None:
        self.initial_lr = initial_lr
        self.decay_factor = decay_factor
        self.decay_epochs = decay_epochs

    def get_lr(self, epoch: int) -> float:
        return self.initial_lr * (self.decay_factor ** (epoch // self.decay_epochs))

    def step_decay(self, epoch: int) -> float:
        import math

        return self.initial_lr * math.exp(-0.1 * epoch)
