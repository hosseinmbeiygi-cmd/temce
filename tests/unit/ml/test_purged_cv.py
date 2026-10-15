"""P0: purged time-series CV must kill look-ahead leakage."""
import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.model_selection import cross_val_score


class ThresholdOnTime(BaseEstimator, ClassifierMixin):
    """Fits a threshold on time index. KFold sees future regime in train
    (scores high); forward-chaining early folds train only on y=0 past."""

    def fit(self, X, y):
        Xa = np.asarray(X).ravel()
        ya = np.asarray(y)
        best_t, best_s = 0, -1
        for t in np.unique(Xa)[::5]:
            s = float(np.mean((Xa > t).astype(int) == ya))
            if s > best_s:
                best_s, best_t = s, t
        self.t_ = best_t
        return self

    def predict(self, X):
        return (np.asarray(X).ravel() > self.t_).astype(int)


def test_kfold_is_fooled_by_leak_but_purged_cv_is_not():
    n, horizon = 600, 5
    X = np.arange(n).reshape(-1, 1).astype(float)
    y = (np.arange(n) > n // 2).astype(int)  # regime shift in future half
    kfold_mean = float(np.mean(cross_val_score(ThresholdOnTime(), X, y, cv=5)))
    assert kfold_mean > 0.9, kfold_mean
    from ml.evaluation.cross_validation import PurgedTimeSeriesCV

    res = PurgedTimeSeriesCV(n_splits=5, horizon=horizon).validate(ThresholdOnTime(), X, y)
    assert res.success, res.error
    assert res.value["mean_test"] < kfold_mean - 0.1, res.value


def test_gap_holds_on_all_folds():
    from ml.evaluation.cross_validation import PurgedTimeSeriesCV

    n, horizon, gap_extra = 200, 5, 2
    cv = PurgedTimeSeriesCV(n_splits=4, horizon=horizon, gap_extra=gap_extra)
    for tr, te in cv.split(n):
        assert int(max(tr)) + (horizon + gap_extra) <= int(min(te))


def test_no_valid_folds_fails():
    from ml.evaluation.cross_validation import PurgedTimeSeriesCV
    from sklearn.dummy import DummyClassifier

    res = PurgedTimeSeriesCV(n_splits=5, horizon=5).validate(
        DummyClassifier(), [[1.0], [2.0]], [0, 1]
    )
    assert not res.success
