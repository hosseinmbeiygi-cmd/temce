from __future__ import annotations

from typing import Any


class TCNModel:
    def __init__(self, n_filters: int = 64, kernel_size: int = 3) -> None:
        self.n_filters = n_filters
        self.kernel_size = kernel_size

    def forward(self, x: Any) -> Any:
        import numpy as np

        return np.mean(x, axis=-1) if hasattr(x, "shape") else x
