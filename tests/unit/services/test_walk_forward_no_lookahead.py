"""STEP 7C-2 — walk-forward validation must not read data outside its window.

The guarantee under test, stated precisely:

    changing the price history *after* a window's training footprint must not
    change that window's fitted parameters, its training labels, or its
    in-window predictions.

Why the fixture is built the way it is
--------------------------------------
``prepare_training_data`` asserts that every feature was built from a *prefix*
of the ``closes`` array it is handed (``metadata['closes_count']`` /
``metadata['last_price']``).  So a stale feature list plus a rewritten array is
*refused*, not silently misread — which is one half of the proof.  The other
half needs the feature sequence rebuilt from the rewritten history: bars beyond
the footprint then feed only the later folds, never the first one.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from ml.models.base import BaseModel
from ml.models.registry import model_registry
from ml.types import FeatureMatrix, PredictionResult, TargetVector
from services.backtest_framework import WalkForwardEngine
from services.signal_feature_pipeline import SignalFeaturePipeline
from services.walk_forward_validator import WalkForwardValidator

FIRST_CLOSE = 21  # the stock extractor needs >= 20 bars before it emits features
NUM_CLOSES = 240
NUM_WINDOWS = 2
TRAIN_RATIO = 0.7
SEQUENCE_LENGTH = 5

#: Fitted-parameter log, appended by ``_WindowMeanModel.fit`` in call order.
FITTED: list[dict[str, Any]] = []


class _WindowMeanModel(BaseModel):
    """Deterministic stand-in whose only fitted parameters come from its slice.

    ``threshold`` is the training-column mean and ``label_mean`` the training
    label mean, so two runs are directly comparable and nothing can reach
    outside the matrix it was handed.
    """

    def __init__(self, name: str = "", params: dict[str, Any] | None = None) -> None:
        super().__init__(name, params)
        self.threshold: float = 0.0
        self.label_mean: float = 0.0

    def fit(self, X: FeatureMatrix, y: TargetVector, **kwargs: Any) -> None:
        values = np.asarray(X.values, dtype=float)
        labels = np.asarray(y.values, dtype=float)
        self.threshold = float(values[:, 0].mean())
        self.label_mean = float(labels.mean()) if labels.size else 0.0
        FITTED.append(
            {
                "rows": int(values.shape[0]),
                "cols": int(values.shape[1]),
                "threshold": self.threshold,
                "label_mean": self.label_mean,
            }
        )
        self._is_fitted = True

    def predict(self, X: FeatureMatrix) -> PredictionResult:
        values = np.asarray(X.values, dtype=float)
        preds = np.where(values[:, 0] > self.threshold, 1.0, 0.0)
        return PredictionResult(predictions=preds, model_id=self.name)

    def save(self, path: str) -> None:  # pragma: no cover - unused
        raise NotImplementedError

    def load(self, path: str) -> None:  # pragma: no cover - unused
        raise NotImplementedError


@pytest.fixture
def window_model():
    """Register the probe model so the real validator can build it."""
    FITTED.clear()
    model_registry.register("wf_no_lookahead_probe", _WindowMeanModel)
    try:
        yield "wf_no_lookahead_probe"
    finally:
        model_registry._builders.pop("wf_no_lookahead_probe", None)
        FITTED.clear()


def _closes() -> list[float]:
    """Deterministic series that rises and falls, so both labels occur."""
    out: list[float] = []
    price = 1_000.0
    for i in range(NUM_CLOSES):
        price *= 1.0 + (0.008 if i % 3 else -0.006)
        out.append(round(price, 6))
    return out


async def _feature_sequence(closes: list[float]) -> list[Any]:
    """One feature per prefix length, exactly as the pipeline produces them."""
    pipeline = SignalFeaturePipeline()
    feats = []
    for count in range(FIRST_CLOSE, len(closes) + 1):
        prefix = closes[:count]
        feats.append(
            await pipeline.extract(
                "GOLD",
                "stock",
                {
                    "closes": prefix,
                    "highs": [p * 1.01 for p in prefix],
                    "lows": [p * 0.99 for p in prefix],
                    "volumes": [1_000_000.0] * len(prefix),
                    "values": [1_000_000_000.0] * len(prefix),
                },
            )
        )
    return feats


def _rewrite_after(closes: list[float], footprint: int) -> list[float]:
    """Copy of ``closes`` whose bars after ``footprint`` run *downward*.

    A pure rescaling would preserve every next-bar return sign and therefore
    could not change a label; this flips the direction instead, so a fold that
    legitimately reads those bars must change and a fold that must not read
    them provably does not.
    """
    mutated = list(closes)
    anchor = closes[footprint]
    for index in range(footprint + 1, len(mutated)):
        mutated[index] = round(anchor * 0.995 ** (index - footprint), 6)
    return mutated


def _train_footprint(train_features: list[Any]) -> int:
    """Highest closes index a window can read (its labels and its own bars)."""
    return max(int(f.metadata["closes_count"]) for f in train_features) - 1


def _window_slices(features: list[Any]):
    """Mirror ``WalkForwardValidator.validate_model``'s split arithmetic."""
    n = len(features)
    window_size = n // NUM_WINDOWS
    train_size = int(window_size * TRAIN_RATIO)
    windows = []
    for w in range(NUM_WINDOWS):
        start = w * window_size
        train_end = start + train_size
        test_end = min(start + window_size, n)
        windows.append((features[start:train_end], features[train_end:test_end]))
    return windows


def _prepare(features: list[Any], closes: list[float], sequence_length: int = SEQUENCE_LENGTH):
    return SignalFeaturePipeline.prepare_training_data(
        features, closes=closes, sequence_length=sequence_length
    )


# ── Level 1: the (X, y) builder is window-local ──────────────────────────


class TestTrainingDataIsWindowLocal:
    async def test_features_and_labels_ignore_every_bar_after_the_window(self) -> None:
        closes = _closes()
        features = await _feature_sequence(closes)
        train = _window_slices(features)[0][0]
        footprint = _train_footprint(train)
        # 21 + 77 - 2: the slice's own bars plus one look-ahead step.
        assert footprint == FIRST_CLOSE + len(train) - 2

        fm_a, tv_a = _prepare(train, closes)
        fm_b, tv_b = _prepare(train, _rewrite_after(closes, footprint))

        pd.testing.assert_frame_equal(fm_a.data, fm_b.data)
        pd.testing.assert_series_equal(tv_a.data, tv_b.data)

    async def test_the_boundary_is_exactly_at_the_footprint(self) -> None:
        """One bar inside is read; the very next bar is not."""
        closes = _closes()
        features = await _feature_sequence(closes)
        train = _window_slices(features)[0][0]
        footprint = _train_footprint(train)

        outside = _rewrite_after(closes, footprint)
        fm_out, tv_out = _prepare(train, outside)
        fm_ref, tv_ref = _prepare(train, closes)
        pd.testing.assert_series_equal(tv_ref.data, tv_out.data)

        inside = list(closes)
        inside[footprint] = round(inside[footprint] * 1.5, 6)
        with pytest.raises(ValueError, match="misaligned with `closes`"):
            _prepare(train, inside)

    async def test_later_folds_do_consume_the_rewritten_bars(self) -> None:
        """Non-vacuity: the rewritten history is real data for fold 2.

        The features are rebuilt from the rewritten closes so the pair stays
        self-consistent; fold 1's training slice is unchanged because its
        prefixes never reach the rewritten bars.
        """
        closes = _closes()
        features = await _feature_sequence(closes)
        footprint = _train_footprint(_window_slices(features)[0][0])

        rewritten = _rewrite_after(closes, footprint)
        alt_features = await _feature_sequence(rewritten)

        first_train_a, _ = _window_slices(features)[0]
        first_train_b, _ = _window_slices(alt_features)[0]
        second_train_a, _ = _window_slices(features)[1]
        second_train_b, _ = _window_slices(alt_features)[1]

        # Fold 1 saw only untouched prefixes...
        _, tv_first_a = _prepare(first_train_a, closes)
        _, tv_first_b = _prepare(first_train_b, rewritten)
        pd.testing.assert_series_equal(tv_first_a.data, tv_first_b.data)

        # ...while fold 2's labels moved with the rewritten bars.
        _, tv_second_a = _prepare(second_train_a, closes)
        _, tv_second_b = _prepare(second_train_b, rewritten)
        assert list(tv_second_a.data) != list(tv_second_b.data)

    async def test_mismatched_closes_array_is_refused_not_leaked(self) -> None:
        closes = _closes()
        features = await _feature_sequence(closes)
        train = _window_slices(features)[0][0]

        tampered = list(closes)
        tampered[FIRST_CLOSE + 10] *= 1.5  # a bar the slice was built from

        with pytest.raises(ValueError, match="misaligned with `closes`"):
            _prepare(train, tampered)

    async def test_a_window_running_past_the_end_of_history_is_refused(self) -> None:
        """Features built from more bars than ``closes`` holds cannot be trained."""
        closes = _closes()
        features = await _feature_sequence(closes)
        truncated = closes[:200]  # features keep going to closes_count 240

        with pytest.raises(ValueError, match="missing valid 'closes_count'"):
            _prepare(features[170:], truncated)

    async def test_the_final_bar_alone_cannot_produce_a_label(self) -> None:
        """y_{t+1} must exist — the builder refuses to invent an edge label.

        Repeating the last real feature puts a ``closes_count == len(closes)``
        row in a non-final position, which is exactly what a label would need a
        future bar for.
        """
        closes = _closes()
        features = await _feature_sequence(closes)
        final = closes[:200]
        last = features[179]  # built from all 200 bars
        assert int(last.metadata["closes_count"]) == 200

        with pytest.raises(ValueError, match="no future bar"):
            _prepare([last, last], final, sequence_length=1)


# ── Level 2: fitted parameters and in-window predictions ─────────────────


class TestFittedParametersAreWindowLocal:
    async def test_sklearn_coefficients_and_predictions_are_bit_identical(self) -> None:
        from sklearn.linear_model import LogisticRegression

        closes = _closes()
        features = await _feature_sequence(closes)
        train = _window_slices(features)[0][0]
        footprint = _train_footprint(train)

        fm_a, tv_a = _prepare(train, closes)
        fm_b, tv_b = _prepare(train, _rewrite_after(closes, footprint))

        model_a = LogisticRegression(max_iter=500)
        model_b = LogisticRegression(max_iter=500)
        model_a.fit(fm_a.values, tv_a.values)
        model_b.fit(fm_b.values, tv_b.values)

        np.testing.assert_array_equal(model_a.coef_, model_b.coef_)
        np.testing.assert_array_equal(
            model_a.predict(fm_a.values), model_b.predict(fm_b.values)
        )

    async def test_probe_model_fitted_state_does_not_move_with_future_bars(self) -> None:
        closes = _closes()
        features = await _feature_sequence(closes)
        train = _window_slices(features)[0][0]

        fm, tv = _prepare(train, closes)
        model_a = _WindowMeanModel("a")
        model_a.fit(fm, tv)
        preds_a = model_a.predict(fm).predictions

        fm_b, tv_b = _prepare(train, _rewrite_after(closes, _train_footprint(train)))
        model_b = _WindowMeanModel("b")
        model_b.fit(fm_b, tv_b)

        assert model_a.threshold == model_b.threshold
        assert model_a.label_mean == model_b.label_mean
        np.testing.assert_array_equal(preds_a, model_b.predict(fm_b).predictions)


# ── Level 3: the real validator ──────────────────────────────────────────


class TestWalkForwardValidatorNoLookahead:
    async def test_first_window_fit_and_predictions_survive_future_rewrites(
        self, window_model
    ) -> None:
        closes = _closes()
        features = await _feature_sequence(closes)
        footprint = _train_footprint(_window_slices(features)[0][0])
        rewritten = _rewrite_after(closes, footprint)
        alt_features = await _feature_sequence(rewritten)

        validator = WalkForwardValidator()

        FITTED.clear()
        clean = await validator.validate_model(
            "gold", window_model, features, closes=closes,
            num_windows=NUM_WINDOWS, train_ratio=TRAIN_RATIO,
        )
        clean_fitted = list(FITTED)

        FITTED.clear()
        altered = await validator.validate_model(
            "gold", window_model, alt_features, closes=rewritten,
            num_windows=NUM_WINDOWS, train_ratio=TRAIN_RATIO,
        )
        altered_fitted = list(FITTED)

        assert clean.success is True, clean.error
        assert altered.success is True, altered.error
        assert len(clean_fitted) == len(altered_fitted) == NUM_WINDOWS

        # Fold 1's fitted parameters are identical...
        assert clean_fitted[0] == altered_fitted[0]
        # ...while fold 2's label distribution really did move, which proves the
        # assertion above is about isolation rather than an inert fixture.
        assert clean_fitted[1]["threshold"] != altered_fitted[1]["threshold"]
        assert clean_fitted[1]["label_mean"] != altered_fitted[1]["label_mean"]

        assert (
            clean.value.windows[0]["train_acc_pct"]
            == altered.value.windows[0]["train_acc_pct"]
        )
        assert clean.value.windows[0]["train_size"] == altered.value.windows[0]["train_size"]

    async def test_windows_are_disjoint_and_ordered(self, window_model) -> None:
        closes = _closes()
        features = await _feature_sequence(closes)
        for train, test in _window_slices(features):
            assert train and test
            assert {id(x) for x in train}.isdisjoint(id(x) for x in test)

        result = await WalkForwardValidator().validate_model(
            "gold", window_model, features, closes=closes,
            num_windows=NUM_WINDOWS, train_ratio=TRAIN_RATIO,
        )

        assert result.success is True, result.error
        for window in result.value.windows:
            assert window["train_size"] > 0
            assert window["test_size"] > 0

    async def test_insufficient_data_fails_cleanly(self) -> None:
        """Regression: this path returned ``Result.err``, which does not exist."""
        closes = _closes()[:40]
        features = await _feature_sequence(closes)

        result = await WalkForwardValidator().validate_model(
            "gold", "anything", features, closes=closes, num_windows=NUM_WINDOWS
        )

        assert result.success is False
        assert "Not enough data" in (result.error or "")

    async def test_every_window_failing_fails_cleanly(self, window_model) -> None:
        """Regression for the same missing ``Result.err`` on the empty path."""
        closes = _closes()
        features = await _feature_sequence(closes)

        result = await WalkForwardValidator().validate_model(
            "gold", "not_registered_at_all", features, closes=closes,
            num_windows=NUM_WINDOWS,
        )

        assert result.success is False
        assert result.error == "No windows completed successfully"


# ── Level 4: the framework engine's split contract ───────────────────────


class TestWalkForwardEngineSplit:
    def test_rolling_windows_are_disjoint_and_time_ordered(self) -> None:
        data = list(range(100))
        pairs = WalkForwardEngine(windows=5, train_ratio=0.6, mode="rolling").split(data)

        assert len(pairs) == 5
        for train, test in pairs:
            assert train and test
            assert max(train) < min(test)  # the test block is always later
            assert set(train).isdisjoint(test)

    def test_expanding_train_grows_and_stays_disjoint(self) -> None:
        pairs = WalkForwardEngine(windows=4, mode="expanding").split(list(range(120)))

        train_sizes = [len(t) for t, _ in pairs]
        assert train_sizes == sorted(train_sizes)
        for train, test in pairs:
            assert set(train).isdisjoint(test)
            assert max(train) < min(test)

    def test_each_fold_only_receives_its_own_slice(self) -> None:
        """``evaluate`` hands the train and test blocks separately, never merged."""
        seen: list[list[int]] = []

        def _fit(slice_data: list[int], **kwargs: Any) -> dict[str, float]:
            seen.append(list(slice_data))
            return {"sharpe_ratio": 1.0, "total_return_pct": 5.0}

        WalkForwardEngine(windows=3, train_ratio=0.7).evaluate(_fit, list(range(60)))

        assert len(seen) == 6  # train + test per fold
        for fold in range(3):
            train, test = seen[fold * 2], seen[fold * 2 + 1]
            start = fold * 20
            assert len(train) == 14  # floor(20-bar window * 0.7)
            assert train[0] == start
            assert train[-1] == start + 13
            # the training block never reaches its own test block or beyond
            assert max(train) < min(test)
            assert test == list(range(start + 14, start + 20))
