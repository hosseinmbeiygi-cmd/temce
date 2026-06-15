from __future__ import annotations

from typing import Any


class DataLoader:
    def __init__(self, data: Any, batch_size: int = 32, shuffle: bool = True) -> None:
        self.data = data
        self.batch_size = batch_size
        self.shuffle = shuffle
        self._index = 0

    def __iter__(self):
        import numpy as np

        indices = np.arange(len(self.data))
        if self.shuffle:
            np.random.shuffle(indices)
        self._indices = indices
        self._index = 0
        return self

    def __next__(self):
        if self._index >= len(self._indices):
            raise StopIteration
        batch_indices = self._indices[self._index : self._index + self.batch_size]
        self._index += self.batch_size
        return self.data[batch_indices]
