from __future__ import annotations


class CrossSectionalFeatures:
    def rank(self, values: list[float]) -> list[float]:
        sorted_vals = sorted(values)
        return [sorted_vals.index(v) + 1 for v in values]

    def zscore(self, values: list[float]) -> list[float]:
        import numpy as np

        arr = np.array(values)
        mean, std = np.mean(arr), np.std(arr)
        if std == 0:
            return [0.0] * len(values)
        return ((arr - mean) / std).tolist()

    def relative_strength(self, values: list[float]) -> list[float]:
        if not values:
            return []
        base = values[0]
        return [v / base - 1 if base != 0 else 0.0 for v in values]
