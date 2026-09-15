from __future__ import annotations

import numpy as np
import pandas as pd

from core.logging import get_logger

logger = get_logger(__name__)


class SequenceWindower:
    """Convert flat tabular data to sequences for deep learning models.

    Creates sliding windows over feature rows so that each sample
    becomes a (window_size, num_features) matrix instead of a flat vector.
    """

    def create_sequences(
        self,
        X: np.ndarray | pd.DataFrame,
        y: np.ndarray | pd.Series,
        window_size: int = 20,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Create sliding-window sequences from tabular data.

        Args:
            X: Feature matrix of shape (N, F).
            y: Target vector of shape (N,) or (N, 1).
            window_size: Number of past timesteps per sample.

        Returns:
            X_seq: Array of shape (N - window_size, window_size, F).
            y_seq: Array of shape (N - window_size,).
        """
        X_arr = X.values.astype(np.float64) if isinstance(X, pd.DataFrame) else np.asarray(X, dtype=np.float64)

        y_arr = y.values.astype(np.float64) if isinstance(y, pd.Series) else np.asarray(y, dtype=np.float64).ravel()

        n_samples, n_features = X_arr.shape

        if n_samples < window_size:
            logger.warning(
                "Not enough samples (%d) for window_size=%d — returning empty arrays",
                n_samples,
                window_size,
            )
            return np.empty((0, window_size, n_features)), np.empty((0,))

        n_seq = n_samples - window_size
        X_seq = np.empty((n_seq, window_size, n_features), dtype=np.float64)
        y_seq = np.empty(n_seq, dtype=np.float64)

        for i in range(n_seq):
            X_seq[i] = X_arr[i : i + window_size]
            y_seq[i] = y_arr[i + window_size]

        logger.info(
            "Created %d sequences: shape X=%s, y=%s",
            n_seq,
            X_seq.shape,
            y_seq.shape,
        )
        return X_seq, y_seq
