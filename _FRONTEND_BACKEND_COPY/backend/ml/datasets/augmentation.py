from __future__ import annotations

from typing import Any


class DataAugmentor:
    def add_noise(self, data: Any, noise_level: float = 0.01):
        import numpy as np

        arr = np.asarray(data)
        noise = np.random.normal(0, noise_level, arr.shape)
        return arr + noise

    def jitter(self, data: Any, scale: float = 0.01):
        import numpy as np

        arr = np.asarray(data)
        return arr + np.random.uniform(-scale, scale, arr.shape)

    def scale(self, data: Any, factor_range: tuple[float, float] = (0.9, 1.1)):
        import numpy as np

        arr = np.asarray(data)
        factor = np.random.uniform(*factor_range)
        return arr * factor
