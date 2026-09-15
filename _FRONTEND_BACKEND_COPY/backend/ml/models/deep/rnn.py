from __future__ import annotations

from typing import Any


class RNNModel:
    def __init__(self, hidden_size: int = 64, num_layers: int = 2) -> None:
        self.hidden_size = hidden_size
        self.num_layers = num_layers

    def forward(self, x: Any) -> Any:
        import numpy as np

        return np.mean(x, axis=0) if hasattr(x, "shape") else x
