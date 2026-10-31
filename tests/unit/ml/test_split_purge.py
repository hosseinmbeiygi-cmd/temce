"""FIN-05: purging the label horizon from each training window.

A label at bar ``t`` is computed from ``close[t+horizon]``. Without a purge the
last ``horizon`` training rows look into the validation fold, so validation
scores are optimistic. The purge is opt-in at the splitter level (``0`` keeps
the old geometry for callers that want it) and wired with the dataset horizon
in ``DatasetBuilder.split``.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from ml.datasets.splitting import DataSplitter


def _features(n: int) -> SimpleNamespace:
    return SimpleNamespace(shape=(n, 3))


def test_default_split_geometry_is_unchanged() -> None:
    split = DataSplitter().time_based(_features(100), None)  # type: ignore[arg-type]

    assert split.train_idx[-1] == 69
    assert split.val_idx[0] == 70
    assert split.test_idx[0] == 85


def test_label_horizon_is_purged_from_train_end() -> None:
    split = DataSplitter().time_based(_features(100), None, label_horizon=5)  # type: ignore[arg-type]

    assert split.train_idx[-1] == 64, "last 5 train labels reach into validation"
    # Purged bars form a gap; validation keeps its original start boundary.
    assert split.val_idx[0] == 70
    assert split.val_idx[-1] == 79
    assert split.test_idx[0] == 85


def test_train_and_validation_never_share_label_windows() -> None:
    horizon = 7
    split = DataSplitter().time_based(_features(200), None, label_horizon=horizon)  # type: ignore[arg-type]

    train_last = int(split.train_idx[-1])
    val_first = int(split.val_idx[0])
    # The last training label is close[train_last + horizon], and it must fall
    # strictly before the first validation bar.
    assert train_last + horizon < val_first


def test_walk_forward_leaves_a_purge_gap() -> None:
    splits = DataSplitter().walk_forward(_features(1000), None, window=200, step=50, label_horizon=5)  # type: ignore[arg-type]

    assert splits
    first = splits[0]
    assert int(first.train_idx[-1]) == 194
    assert int(first.val_idx[0]) == 200, "the 5 purged bars sit between train and val"


def test_negative_horizon_is_rejected() -> None:
    with pytest.raises(ValueError):
        DataSplitter().time_based(_features(50), None, label_horizon=-1)  # type: ignore[arg-type]


def test_builder_wires_the_configured_horizon() -> None:
    from ml.datasets.builders import DatasetBuilder

    builder = DatasetBuilder()
    features = SimpleNamespace(shape=(100, 3))
    targets = SimpleNamespace(data=np.zeros(100))

    split = builder.split(features, targets, {"horizon": 5})  # type: ignore[arg-type]

    assert int(split.train_idx[-1]) == 64
