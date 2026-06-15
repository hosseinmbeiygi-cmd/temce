from __future__ import annotations

from typing import Any


class AutoencoderModel:
    def __init__(self, encoding_dim: int = 32) -> None:
        self.encoding_dim = encoding_dim

    def fit(self, X: Any) -> None:
        pass

    def transform(self, X: Any) -> Any:
        import numpy as np

        return np.array(X)[:, : self.encoding_dim] if hasattr(X, "__len__") else X
