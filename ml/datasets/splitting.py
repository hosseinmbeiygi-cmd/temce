from __future__ import annotations

import numpy as np

from ml.types import FeatureMatrix, SplitMeta, TargetVector


class DataSplitter:
    def time_based(
        self,
        features: FeatureMatrix,
        targets: TargetVector,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        label_horizon: int = 0,
    ) -> SplitMeta:
        """Chronological split with an optional purge gap (audit FIN-05).

        A target at bar ``t`` looks ``label_horizon`` bars into the future, so
        the last ``label_horizon`` training rows would peek into the validation
        window and inflate validation scores. Those rows are dropped, which
        leaves a gap between train and validation (and between validation and
        test); ``0`` reproduces the historical geometry exactly.
        """
        if label_horizon < 0:
            raise ValueError("label_horizon must be >= 0")
        n = features.shape[0]
        train_boundary = int(n * train_ratio)
        val_boundary = int(n * (train_ratio + val_ratio))
        train_end = max(1, train_boundary - label_horizon)
        val_end = min(n, max(train_end + 1, val_boundary - label_horizon))
        return SplitMeta(
            train_idx=np.arange(0, train_end),
            # Validation starts at the original boundary: the purged rows sit
            # in the gap instead of shortening the window silently.
            val_idx=np.arange(train_boundary, val_end),
            test_idx=np.arange(val_boundary, n),
        )

    def walk_forward(
        self,
        features: FeatureMatrix,
        targets: TargetVector,
        window: int = 500,
        step: int = 100,
        label_horizon: int = 0,
    ) -> list[SplitMeta]:
        """Rolling split whose train window ends ``label_horizon`` bars before
        validation starts, so no training label reaches into the future fold."""
        if label_horizon < 0:
            raise ValueError("label_horizon must be >= 0")
        n = features.shape[0]
        splits = []
        for start in range(0, n - window, step):
            train_end = start + window - label_horizon
            val_start = start + window
            val_end = min(val_start + step, n)
            if train_end <= start or val_start >= val_end:
                continue
            splits.append(
                SplitMeta(
                    train_idx=np.arange(start, train_end),
                    val_idx=np.arange(val_start, val_end),
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
