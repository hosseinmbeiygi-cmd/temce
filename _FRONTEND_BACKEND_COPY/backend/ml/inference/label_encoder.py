from __future__ import annotations

from typing import Any


class LabelEncoder:
    def __init__(self) -> None:
        self._classes: list[Any] = []
        self._mapping: dict[Any, int] = {}

    def fit(self, y: Any) -> None:
        self._classes = sorted(set(y))
        self._mapping = {cls: i for i, cls in enumerate(self._classes)}

    def transform(self, y: Any) -> Any:
        import numpy as np

        return np.array([self._mapping[val] for val in y])

    def inverse_transform(self, y: Any) -> Any:
        import numpy as np

        reverse = {i: cls for cls, i in self._mapping.items()}
        return np.array([reverse[int(val)] for val in y])
