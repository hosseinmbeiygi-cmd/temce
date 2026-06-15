from __future__ import annotations


class FeatureNormalizer:
    def __init__(self) -> None:
        self._means: dict[str, float] = {}
        self._stds: dict[str, float] = {}

    def fit(self, features: dict[str, list[float]]) -> None:
        import numpy as np

        for name, vals in features.items():
            arr = np.array(vals)
            self._means[name] = float(np.mean(arr))
            self._stds[name] = float(np.std(arr)) or 1.0

    def transform(self, features: dict[str, list[float]]) -> dict[str, list[float]]:
        import numpy as np

        result = {}
        for name, vals in features.items():
            arr = np.array(vals, dtype=float)
            mean = self._means.get(name, 0.0)
            std = self._stds.get(name, 1.0)
            result[name] = ((arr - mean) / std).tolist()
        return result
