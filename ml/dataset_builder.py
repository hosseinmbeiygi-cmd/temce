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

    def normalize(self, data: list[float]) -> list[float]:
        arr = np.array(data, dtype=float)
        mean = np.mean(arr)
        std = np.std(arr)
        if std == 0:
            return [0.0] * len(data)
        return ((arr - mean) / std).tolist()

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
