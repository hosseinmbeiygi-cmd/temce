from __future__ import annotations

from typing import Any

import numpy as np


class DatasetBuilder:
    """Dataset builder for ML feature engineering and data preparation."""

    def build_feature_list(self, features: list[str]) -> list[str]:
        return list(features)

    def train_test_split(self, data: list[Any], test_size: float = 0.2) -> tuple[list[Any], list[Any]]:
        split_idx = int(len(data) * (1 - test_size))
        return data[:split_idx], data[split_idx:]

    def walk_forward_splits(
        self, n: int, n_splits: int = 5, horizon: int = 1, gap_extra: int = 0,
        mode: str = "expanding",
    ) -> list[tuple[list[int], list[int]]]:
        """Walk-forward (expanding/rolling) index splits with gap=horizon+gap_extra."""
        from sklearn.model_selection import TimeSeriesSplit

        gap = int(horizon) + int(gap_extra)
        tss = TimeSeriesSplit(n_splits=n_splits, gap=gap)
        import numpy as _np

        out = []
        for tr, te in tss.split(_np.zeros((n, 1))):
            out.append((list(map(int, tr)), list(map(int, te))))
        return out

    def make_target(self, prices: list[float], horizon: int = 1) -> list[int | None]:
        """Binary forward-return label; last `horizon` rows are None (dropped)."""
        y: list[int | None] = []
        for i in range(len(prices)):
            if i + horizon >= len(prices):
                y.append(None)
            else:
                y.append(1 if prices[i + horizon] > prices[i] else 0)
        return y

    @staticmethod
    def _fit_stats(train: list[float]) -> dict[str, float]:
        """Compute scaling statistics from the training partition only."""
        arr = np.array(train, dtype=float)
        if arr.size == 0:
            return {"mean": 0.0, "std": 0.0}
        return {"mean": float(np.mean(arr)), "std": float(np.std(arr))}

    @staticmethod
    def _apply(data: list[float], stats: dict[str, float]) -> list[float]:
        """Scale ``data`` with pre-fitted stats (zero variance → zeros)."""
        mean = float(stats.get("mean", 0.0))
        std = float(stats.get("std", 0.0))
        if std == 0:
            return [0.0] * len(data)
        return [(float(v) - mean) / std for v in data]

    def fit_normalize(
        self, data: list[float], test_size: float = 0.2
    ) -> tuple[list[float], list[float], dict[str, float]]:
        """Split first, then fit scaling stats on the TRAIN partition only.

        Fitting on the whole series would let test-period values (e.g. a price
        outlier) leak into the mean/std used to scale the training data
        (ML-001 leakage).  Returns ``(train_scaled, test_scaled, stats)``.
        Stats dict also carries version/date/train_range for ml_artifacts/.
        """
        import datetime as _dt

        train, test = self.train_test_split(data, test_size=test_size)
        stats = self._fit_stats(train)
        stats.update(
            {
                "version": "v1",
                "fitted_at": _dt.datetime.now(_dt.UTC).isoformat(),
                "n_train": len(train),
            }
        )
        return self._apply(train, stats), self._apply(test, stats), stats

    def apply_normalization(self, data: list[float], stats: dict[str, float]) -> list[float]:
        """Scale ``data`` using previously fitted stats (inference-safe)."""
        return self._apply(data, stats)

    def create_sequences(self, data: list[Any], sequence_length: int = 5) -> tuple[list[list[Any]], list[Any]]:
        X, y = [], []
        for i in range(len(data) - sequence_length):
            X.append(data[i : i + sequence_length])
            y.append(data[i + sequence_length])
        return X, y

    def validate(self, data: dict[str, list[Any]]) -> bool:
        if not data:
            return False
        lengths = [len(v) for v in data.values()]
        return len(set(lengths)) == 1
