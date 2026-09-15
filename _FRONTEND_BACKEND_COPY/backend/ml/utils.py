from __future__ import annotations

from typing import Any


def ensure_numpy_array(data: Any):
    import numpy as np

    if isinstance(data, np.ndarray):
        return data
    return np.array(data)


def ensure_dataframe(data: Any):
    import pandas as pd

    if isinstance(data, pd.DataFrame):
        return data
    return pd.DataFrame(data)


def train_test_split(features, targets, test_size: float = 0.2, shuffle: bool = True):
    from sklearn.model_selection import train_test_split as sk_split

    return sk_split(features, targets, test_size=test_size, shuffle=shuffle)
