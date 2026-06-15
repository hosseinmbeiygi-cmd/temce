from __future__ import annotations

import numpy as np

from ml.types import FeatureMatrix, SplitMeta, TargetVector


class DataSplitter:
    def time_based(
        self, features: FeatureMatrix, targets: TargetVector, train_ratio: float = 0.7, val_ratio: float = 0.15
    ) -> SplitMeta:
        n = features.shape[0]
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))
        return SplitMeta(
            train_idx=np.arange(0, train_end),
            val_idx=np.arange(train_end, val_end),
            test_idx=np.arange(val_end, n),
        )

    def walk_forward(
        self, features: FeatureMatrix, targets: TargetVector, window: int = 500, step: int = 100
    ) -> list[SplitMeta]:
        n = features.shape[0]
        splits = []
        for start in range(0, n - window, step):
            train_end = start + window
            val_end = min(train_end + step, n)
            splits.append(
                SplitMeta(
                    train_idx=np.arange(start, train_end),
                    val_idx=np.arange(train_end, val_end),
                    test_idx=None,
                )
            )
        return splits

    def purged(
        self, features: FeatureMatrix, targets: TargetVector, n_folds: int = 5, purge_pct: float = 0.1
    ) -> list[SplitMeta]:
        n = features.shape[0]
        fold_size = n // n_folds
        purge_size = int(fold_size * purge_pct)
        splits = []
        for i in range(n_folds):
            val_start = i * fold_size
            val_end = (i + 1) * fold_size
            train_end = val_start - purge_size
            splits.append(
                SplitMeta(
                    train_idx=np.arange(0, max(0, train_end)),
                    val_idx=np.arange(val_start, min(val_end, n)),
                    test_idx=None,
                )
            )
        return splits
