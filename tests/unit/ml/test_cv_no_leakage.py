"""Regression tests for Phase 1 plan fixes M1/M3 (.claude/plan.md).

CVTrainer.cross_validate and HyperparameterTuner.optimize used
``cross_val_score(model, X, y, cv=<int>)``, which defaults to sklearn's
contiguous-block K-Fold: on time-ordered data, a fold's training set can
include blocks that come chronologically AFTER its validation block — the
model is partly trained on the future. Both now route through
``CrossValidator`` (``TimeSeriesSplit``-based, forward-chaining).

StackingEnsembleModel's out-of-fold stacking had the same bug via
``KFold(shuffle=False)`` and now uses ``TimeSeriesSplit``.
"""

from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin


class _RecordingModel(RegressorMixin, BaseEstimator):
    """Records the time-index range it was trained/validated on each call,
    so a test can assert no fold ever trains on an index that is >= the
    smallest validation index for that same fold (the hallmark of
    contiguous-block K-Fold leaking "future" rows into training).

    Inherits ``BaseEstimator``/``RegressorMixin`` because sklearn >=1.6's
    ``cross_validate``/``check_cv`` requires ``__sklearn_tags__``, which only
    real sklearn estimator base classes provide. ``sklearn.clone()`` creates
    a fresh instance per fold, so recordings go on a class-level list shared
    across clones rather than an instance attribute.
    """

    train_val_ranges: list[tuple[float, float, float]] = []

    def __init__(self) -> None:
        self._train_max = -1.0

    def fit(self, X, y):
        self._train_max = float(np.asarray(X)[:, -1].max())
        return self

    def predict(self, X):
        return np.zeros(len(X))

    def score(self, X, y):
        X = np.asarray(X)
        val_min = float(X[:, -1].min())
        type(self).train_val_ranges.append((self._train_max, val_min, float(X[:, -1].max())))
        return 0.0


def _make_time_indexed_data(n: int = 60):
    rng = np.random.default_rng(0)
    time_idx = np.arange(n).reshape(-1, 1).astype(float)
    X = np.hstack([rng.normal(size=(n, 3)), time_idx])
    y = rng.normal(size=n)
    return X, y


class TestCVTrainerUsesForwardChaining:
    def test_cross_validate_never_trains_on_rows_at_or_after_validation(self):
        """For every fold, the model's training-time max index must be
        strictly less than that fold's validation-time min index — proving
        no fold trains on data chronologically at-or-after what it's
        scored against (the leak contiguous-block K-Fold permits).
        """
        from ml.training.cv_trainer import CVTrainer

        X, y = _make_time_indexed_data()
        _RecordingModel.train_val_ranges = []
        model = _RecordingModel()
        CVTrainer(n_folds=4).cross_validate(model, X, y)

        assert _RecordingModel.train_val_ranges, "model must have been scored at least once"
        # cross_validate(return_train_score=True) scores each fold twice: once
        # on the held-out validation block (val_min starts right after
        # train_max — the real leakage check) and once on the training block
        # itself for the reported train_score (val_min == 0, same block the
        # model trained on — not a leak, just re-scoring the training data).
        held_out_scores = [
            (train_max, val_min)
            for train_max, val_min, _val_max in _RecordingModel.train_val_ranges
            if val_min > 0
        ]
        assert held_out_scores, "at least one fold must have a true held-out validation score"
        for train_max, val_min in held_out_scores:
            assert train_max < val_min, (
                f"fold trained up to index {train_max} but validated starting "
                f"at index {val_min} — training saw rows at/after validation"
            )

    def test_source_no_longer_calls_cross_val_score_with_bare_int_cv(self):
        import inspect

        import ml.training.cv_trainer as mod

        src = inspect.getsource(mod.CVTrainer.cross_validate)
        assert "cross_val_score(" not in src
        assert "CrossValidator(" in src


class TestHyperparameterTunerUsesForwardChaining:
    def test_optimize_source_uses_cross_validator(self):
        import inspect

        import ml.training.hyperparameter_tuning as mod

        src = inspect.getsource(mod.HyperparameterTuner.optimize)
        assert "cross_val_score(" not in src
        assert "CrossValidator(" in src

    def test_optimize_runs_and_returns_a_result(self):
        from ml.training.hyperparameter_tuning import HyperparameterTuner

        class LinearlyScaledModel(RegressorMixin, BaseEstimator):
            def __init__(self, scale: float = 1.0) -> None:
                self.scale = scale

            def fit(self, X, y):
                return self

            def predict(self, X):
                return self.scale * np.asarray(X)[:, 0]

        X, y = _make_time_indexed_data(n=80)
        y = X[:, 0] * 2.0  # best scale is 2.0

        tuner = HyperparameterTuner(n_trials=10, n_folds=4)
        out = tuner.optimize(LinearlyScaledModel, {"scale": [0.5, 1.0, 2.0, 3.0]}, X, y)
        assert out["best_params"]["scale"] in (0.5, 1.0, 2.0, 3.0)


class TestStackingEnsembleUsesTimeSeriesSplit:
    def test_fit_source_uses_timeseriessplit_not_kfold(self):
        import inspect

        import ml.models.shallow.boosting_models as mod

        src = inspect.getsource(mod.StackingEnsembleModel.fit)
        assert "= TimeSeriesSplit(" in src
        assert "= KFold(" not in src
        assert "from sklearn.model_selection import KFold" not in src

    def test_fit_excludes_uncovered_rows_from_meta_learner(self, monkeypatch):
        """The meta-learner must be fit only on rows that actually received an
        out-of-fold prediction. TimeSeriesSplit never holds out the leading
        block, so with no gap exactly ``n - len(first_val_block)`` rows are
        covered; the fit must see that many rows — not all ``n`` (which would
        mean the uncovered leading rows were fed in as fabricated zeros).
        """
        import sklearn.linear_model as sklm

        from ml.models.shallow.boosting_models import StackingEnsembleModel

        fitted_rows: dict[str, int] = {}
        real_ridge = sklm.Ridge

        class RecordingRidge(real_ridge):  # type: ignore[misc, valid-type]
            def fit(self, X, y, *args, **kwargs):
                fitted_rows["n"] = len(np.asarray(X))
                return super().fit(X, y, *args, **kwargs)

        monkeypatch.setattr(sklm, "Ridge", RecordingRidge)

        rng = np.random.default_rng(1)
        n = 300
        X = rng.normal(size=(n, 5))
        y = X[:, 0] * 2 + rng.normal(size=n) * 0.1

        model = StackingEnsembleModel(params={"task": "regression"})
        model.fit(X, y)

        from sklearn.model_selection import TimeSeriesSplit

        n_folds = min(5, max(2, n // 50))
        first_val_idx = next(iter(TimeSeriesSplit(n_splits=n_folds).split(X)))[1]
        expected_covered = n - len(first_val_idx)

        assert "n" in fitted_rows, "meta-learner was never fit"
        assert fitted_rows["n"] == expected_covered, (
            f"meta-learner fit on {fitted_rows['n']} rows; expected only the "
            f"{expected_covered} OOF-covered rows (leading block of "
            f"{len(first_val_idx)} rows must be dropped, not zero-filled)"
        )
        assert fitted_rows["n"] < n

        preds = model.predict(X)
        assert preds.predictions.shape == (n,)
        assert not np.isnan(preds.predictions).any()

    def test_gap_param_embargoes_rows_before_validation(self, monkeypatch):
        """Passing ``gap`` must embargo that many rows between each fold's
        train end and validation start (plan.md M1/M3: the gapped splitter).

        ``gap`` does NOT change which rows are validated (sklearn keeps the
        validation blocks fixed); it drops the ``gap`` rows immediately before
        each validation block from that fold's training set. So the property
        to assert is the train->validation embargo, not the covered count.
        """
        import sklearn.model_selection as skms

        from ml.models.shallow.boosting_models import StackingEnsembleModel

        seen_gaps: list[int] = []
        real_tss = skms.TimeSeriesSplit

        class RecordingTSS(real_tss):  # type: ignore[misc, valid-type]
            def __init__(self, *args, **kwargs):
                seen_gaps.append(int(kwargs.get("gap", 0)))
                super().__init__(*args, **kwargs)

        monkeypatch.setattr(skms, "TimeSeriesSplit", RecordingTSS)

        rng = np.random.default_rng(2)
        n = 400
        X = rng.normal(size=(n, 5))
        y = X[:, 0] * 2 + rng.normal(size=n) * 0.1
        StackingEnsembleModel(params={"task": "regression", "gap": 20}).fit(X, y)

        assert seen_gaps, "ensemble never constructed a TimeSeriesSplit"
        assert seen_gaps[0] == 20, (
            f"gap param not forwarded to TimeSeriesSplit (saw {seen_gaps[0]})"
        )

        # And the gapped splitter really does leave >= gap rows between the
        # end of each training block and the start of its validation block.
        for train_idx, val_idx in real_tss(n_splits=5, gap=20).split(X):
            assert val_idx.min() - train_idx.max() - 1 >= 20

