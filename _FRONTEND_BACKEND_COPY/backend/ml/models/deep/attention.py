from __future__ import annotations

from typing import Any


class AttentionModel:
    def __init__(self, d_model: int = 64, n_heads: int = 4) -> None:
        self.d_model = d_model
        self.n_heads = n_heads
        self._params: dict[str, Any] = {}

    def forward(self, x: Any) -> Any:
        import numpy as np

        return np.mean(x, axis=-1) if hasattr(x, "shape") else x
