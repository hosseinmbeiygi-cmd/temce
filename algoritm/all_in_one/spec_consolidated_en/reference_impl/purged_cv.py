"""Purged + embargoed walk-forward splits.

Each sample has a decision index and a label_end index (when its label is fully resolved).
A training sample is kept only if label_end + embargo < test_start  (past-only training).
"""
from __future__ import annotations
from typing import Iterator, Sequence, Tuple


def purged_walk_forward(decision: Sequence[int], label_end: Sequence[int], n_splits: int,
                        min_train: int, embargo: int) -> Iterator[Tuple[list, list]]:
    n = len(decision)
    order = sorted(range(n), key=lambda i: decision[i])
    start = min_train
    if start >= n:
        raise ValueError("min_train too large")
    size = max(1, (n - start) // n_splits)
    for k in range(n_splits):
        a = start + k * size
        b = n if k == n_splits - 1 else a + size
        test = order[a:b]
        if not test:
            continue
        test_start = min(decision[i] for i in test)
        train = [i for i in order[:a] if label_end[i] + embargo < test_start]
        yield train, test
