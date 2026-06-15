from __future__ import annotations

from typing import Any


class OptimizerFactory:
    @staticmethod
    def create(name: str, **kwargs: Any) -> Any:
        if name == "sgd":

            class SGDOptimizer:
                def __init__(self, lr: float = 0.01) -> None:
                    self.lr = lr

                def step(self, params: Any) -> Any:
                    return params - self.lr * params

            return SGDOptimizer(**kwargs)
        if name == "adam":

            class AdamOptimizer:
                def __init__(self, lr: float = 0.001) -> None:
                    self.lr = lr
                    self.beta1 = 0.9
                    self.beta2 = 0.999
                    self.t = 0

                def step(self, params: Any) -> Any:
                    self.t += 1
                    return params

            return AdamOptimizer(**kwargs)
        raise ValueError(f"Unknown optimizer: {name}")
