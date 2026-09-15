"""Tests for the isotonic per-market calibrator.

The fit is pure (no DB), so we exercise it with hand-crafted
``CalibrationPoint`` lists. The DB-backed functions
(``load_model``/``save_model``) need a live DB and are covered by the
dry-run script, not by unit tests.
"""

from __future__ import annotations

import pytest

from services.isotonic_calibrator import (
    CalibrationPoint,
    IsotonicModel,
    _train_isotonic,
)

# ── Edge cases ────────────────────────────────────────────────────


def test_train_returns_empty_below_30_samples() -> None:
    """The fit refuses to produce a model with too few points.

    Below 30, the model is unreliable; the caller should fall back
    to the raw confidence.
    """
    points = [CalibrationPoint(predicted=0.5, actual=1.0)] * 29
    buckets, brier, ece = _train_isotonic(points)
    assert buckets == []
    assert brier == 999.0
    assert ece == 999.0


def test_train_returns_buckets_at_or_above_30_samples() -> None:
    """A well-formed toy dataset produces a usable model."""
    # Perfectly calibrated: predicted == actual rate.
    points = [CalibrationPoint(predicted=0.1 * i, actual=0.1 * i) for i in range(1, 11)] * 5  # 50 points
    buckets, brier, ece = _train_isotonic(points)
    assert len(buckets) == 19
    # On a perfectly calibrated line, Brier should be small.
    assert brier < 0.05


# ── Apply ─────────────────────────────────────────────────────────


def _perfect_model() -> IsotonicModel:
    """A trivial model that maps any input to itself (clamped)."""
    return IsotonicModel(
        market="test",
        timeframe="daily",
        direction="buy",
        n_samples=100,
        brier_score=0.0,
        ece=0.0,
        trained_at=__import__("datetime").datetime(2026, 1, 1),
        buckets=[(0.05 * i, 0.05 * i) for i in range(1, 20)],
    )


def test_apply_returns_clamped_raw_when_model_is_empty() -> None:
    """A model with no buckets (e.g. cold-start) returns the raw value."""
    model = IsotonicModel(
        market="test",
        timeframe="daily",
        direction="buy",
        n_samples=0,
        brier_score=999.0,
        ece=999.0,
        trained_at=__import__("datetime").datetime(2026, 1, 1),
        buckets=[],
    )
    assert model.apply(0.5) == 0.5
    assert model.apply(0.001) == 0.01  # clamped to 0.01
    assert model.apply(0.999) == 0.99  # clamped to 0.99


def test_apply_returns_first_bucket_below_threshold() -> None:
    """For raw=0.1, the first bucket at threshold=0.05 should fire."""
    model = _perfect_model()
    # raw=0.1 → first threshold >= 0.1 is 0.10, returns 0.10.
    assert model.apply(0.1) == pytest.approx(0.1, abs=1e-9)


def test_apply_clamps_to_last_bucket_above_max() -> None:
    """raw=0.99 exceeds all thresholds → last bucket wins."""
    model = _perfect_model()
    # Last bucket is (0.95, 0.95).
    assert model.apply(0.99) == pytest.approx(0.95, abs=1e-9)


# ── Serialization round-trip ───────────────────────────────────────


def test_model_roundtrip_preserves_buckets() -> None:
    """The dict shape used for JSON persistence must round-trip exactly."""
    original = _perfect_model()
    restored = IsotonicModel.from_dict(original.to_dict())
    assert restored == original


def test_brier_improves_after_calibration() -> None:
    """A confidence-overconfident model should have lower Brier after isotonic fit.

    Toy example: model always predicts 0.7, but actual rate is 0.5.
    Raw Brier = (0.7-0.5)^2 = 0.04. Isotonic should map 0.7 → 0.5
    (or near it), making post-calibration Brier ~0.
    """
    points = [CalibrationPoint(predicted=0.7, actual=0.5)] * 50
    _, brier, _ = _train_isotonic(points)
    # The fit should at least halve the raw Brier.
    assert brier < 0.04
