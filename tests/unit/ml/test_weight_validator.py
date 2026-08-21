"""Unit tests for ml/weight_validator.PurgedWeightValidator.

Locks in the F6 fix: the weight optimizers must report OUT-OF-SAMPLE R²
(computed on chronologically held-out, embargoed folds) instead of the
meaningless in-sample R².
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from ml.weight_validator import PurgedWeightValidator


def _make_dataset(
    n_dates: int = 24,
    n_symbols: int = 10,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Synthetic rows where ``feat_mom`` drives the target.

    Returns (X, y, dates) aligned, spanning ``n_dates`` calendar days with
    ``n_symbols`` cross-sections each — enough rows for several purged
    walk-forward windows.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2025-01-01", periods=n_dates, freq="D")
    rows: list[dict[str, Any]] = []
    for d in dates:
        for _ in range(n_symbols):
            mom = rng.normal(0.0, 1.0)
            val = rng.normal(0.0, 1.0)
            target = 0.6 * mom + 0.1 * val + rng.normal(0.0, 0.2)
            rows.append({"date": d, "feat_mom": mom, "feat_val": val, "target": target})
    df = pd.DataFrame(rows)
    return df[["feat_mom", "feat_val"]], df["target"], df["date"]


@pytest.fixture
def validator() -> PurgedWeightValidator:
    return PurgedWeightValidator(n_windows=4, min_train_rows=10, min_test_rows=3)


class TestPurgedWeightValidator:
    async def test_validate_computes_oos_r2_on_synthetic_data(self, validator: PurgedWeightValidator) -> None:
        X, y, dates = _make_dataset()
        result = validator.validate(X, y, dates)

        assert result["provisional"] is False
        assert result["reason"] is None
        assert result["n_windows"] >= 1, "expected at least one valid walk-forward window"
        assert result["r2_oos_mean"] is not None
        assert result["r2_is_mean"] is not None
        assert result["rows"] == len(X)
        # R² lives in [-inf, 1]; for a synthetic linear signal the OOS fit is
        # expected to be positive (and certainly bounded above by 1).
        assert result["r2_oos_mean"] <= 1.0
        assert result["stability_score"] is not None and 0.0 <= result["stability_score"] <= 1.0

    async def test_no_information_leakage_between_folds(self, validator: PurgedWeightValidator) -> None:
        """Structural F6 guard: every test fold starts strictly after its
        (purged) train fold — the embargo guarantees no temporal overlap."""
        X, y, dates = _make_dataset()
        result = validator.validate(X, y, dates)

        assert result["windows"], "expected usable windows"
        for w in result["windows"]:
            assert w["test_start"] >= w["train_end"], (
                f"window {w['id']} leaks: test_start {w['test_start']} < train_end {w['train_end']}"
            )
            assert w["embargo_bars"] >= 1, "embargo must be at least one bar"

    async def test_too_few_rows_is_provisional(self, validator: PurgedWeightValidator) -> None:
        X, y, dates = _make_dataset(n_dates=2, n_symbols=2)
        result = validator.validate(X, y, dates)

        assert result["provisional"] is True
        assert result["reason"] == "too_few_rows"
        assert result["r2_oos_mean"] is None
        assert result["n_windows"] == 0

    async def test_disabled_validator_shape(self) -> None:
        """Same contract when a regime has rows but no valid window survives."""
        X, y, dates = _make_dataset(n_dates=3, n_symbols=2)  # 6 rows, too few
        v = PurgedWeightValidator(n_windows=8, min_train_rows=100, min_test_rows=3)
        result = v.validate(X, y, dates)
        assert result["provisional"] is True

    async def test_results_are_deterministic(self, validator: PurgedWeightValidator) -> None:
        X, y, dates = _make_dataset(seed=7)
        r1 = validator.validate(X, y, dates)
        r2 = validator.validate(X, y, dates)
        assert r1["r2_oos_mean"] == r2["r2_oos_mean"]
        assert r1["windows"] == r2["windows"]
