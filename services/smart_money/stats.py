"""Shared statistical primitives for smart_money layers (DRY — audit P2).

Single source of truth for the sample mean/std used by the buyer-power,
microstructure and breakout-quality layers, plus single-pass column
extraction from dict-row histories.

Legacy semantics preserved exactly:

    - zscore: n < 2 → (0.0, 1.0); zero std (constant series) → 1.0
    - extract_columns: per-row ``row.get(name, default)`` incl. missing keys
    - open_return: zero/missing open → 0.0 return
    - nz_or_one: legacy ``x or 1.0`` (falsy 0.0 → 1.0)

NumPy reductions below 8 elements are sequential (no pairwise blocks), so
results are bit-identical to the legacy Python loops for short windows; for
longer series only float summation-order ulps may differ, which the parity
suite (tests/unit/services/test_smart_money_layers_parity.py) bounds at
rel=1e-12.
"""

from __future__ import annotations

from operator import itemgetter
from typing import Any, Callable

import numpy as np


def zscore(vals: "list[float] | np.ndarray") -> tuple[float, float]:
    """Sample mean and std (ddof=1) with legacy edge semantics.

    Returns:
        (mu, std) — Python floats; std is never 0.0.
    """
    arr = np.asarray(vals, dtype=np.float64)
    if arr.size < 2:
        return 0.0, 1.0
    mu = float(arr.mean())
    std = float(arr.std(ddof=1))
    return mu, (std or 1.0)


def _single_getter(key: str) -> "Callable[[dict[str, Any]], Any]":
    """itemgetter equivalent for a single key (itemgetter('k') returns the value itself)."""
    def _get(q: dict[str, Any]) -> tuple[Any]:
        return (q[key],)
    return _get


def extract_columns(history: list[dict[str, Any]], columns: dict[str, Any]) -> dict[str, np.ndarray]:
    """Column extraction from a list of dict rows (hot path — profiled).

    Single pass over ``history``: complete rows go through one
    ``operator.itemgetter`` call (fast path); rows with missing keys fall
    back to ``row.get(name, default)`` for that row only. Rows are collected
    into one float64 matrix (single ``np.asarray`` call).

    Args:
        columns: mapping of column name → default value (legacy
            ``row.get(name, default)`` semantics, incl. missing keys).

    Returns:
        Mapping of column name → float64 ndarray of length ``len(history)``.
    """
    if not history:
        return {name: np.empty(0, dtype=np.float64) for name in columns}

    keys = list(columns)
    col_items = list(columns.items())
    getter = itemgetter(*keys) if len(keys) > 1 else _single_getter(keys[0])

    rows_out: list[Any] = []
    append = rows_out.append
    for q in history:
        try:
            append(getter(q))
        except KeyError:
            append(tuple(q.get(name, default) for name, default in col_items))

    mat = np.asarray(rows_out, dtype=np.float64)
    if mat.ndim == 1:  # single-column extraction returns scalars per row
        mat = mat.reshape(-1, 1)
    return {name: mat[:, idx] for idx, name in enumerate(keys)}


def nz_or_one(arr: np.ndarray) -> np.ndarray:
    """Legacy ``x or 1.0`` semantics: falsy (0.0) → 1.0."""
    return np.where(arr != 0.0, arr, 1.0)


def open_return(close: np.ndarray, open_: np.ndarray) -> np.ndarray:
    """Legacy ``(c - o) / o if o else 0.0`` per row."""
    safe_open = np.where(open_ != 0.0, open_, 1.0)
    return np.where(open_ != 0.0, (close - open_) / safe_open, 0.0)
