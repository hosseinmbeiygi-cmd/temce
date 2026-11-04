from __future__ import annotations

from collections.abc import Callable
from typing import Any

from core.result import Result


class PurgedTimeSeriesCV:
    """Purged walk-forward CV for time series.

    - Uses sklearn TimeSeriesSplit with ``gap`` bars between train and test.
    - ``horizon`` (label look-ahead in bars) is REQUIRED; gap = horizon + gap_extra.
    - No embargo on test tail (train is always before test, gap suffices).
    - Model is cloned per fold via sklearn.base.clone; metric_fn used if given.
    """

    def __init__(self, n_splits: int = 5, horizon: int | None = None, gap_extra: int = 0) -> None:
        if horizon is None:
            raise ValueError("horizon (label look-ahead bars) is required")
        if horizon < 1:
            raise ValueError("horizon must be >= 1")
        self.n_splits = n_splits
        self.horizon = int(horizon)
        self.gap = int(horizon) + int(gap_extra)

    def split(self, n: int):
        from sklearn.model_selection import TimeSeriesSplit

        tss = TimeSeriesSplit(n_splits=self.n_splits, gap=self.gap)
        # TimeSeriesSplit.split needs 2D X; use dummy
        import numpy as _np

        X = _np.zeros((n, 1))
        yield from tss.split(X)

    def validate(
        self,
        model: Any,
        X: Any,
        y: Any,
        metric_fn: Callable[[Any, Any, Any], float] | None = None,
    ) -> Result[dict[str, Any]]:
        try:
            import numpy as _np
            from sklearn.base import clone

            Xa = _np.asarray(X)
            ya = _np.asarray(y)
            n = len(Xa)
            # Fail with an actionable message instead of letting TimeSeriesSplit
            # raise a generic "Too many splits" error from deep inside sklearn.
            if n < 2 * self.n_splits + 1:
                return Result.fail(
                    f"Not enough samples: {n} rows for {self.n_splits} folds "
                    f"(need at least {2 * self.n_splits + 1})"
                )
            tr_scores: list[float] = []
            te_scores: list[float] = []
            folds: list[dict[str, int]] = []
            for tr_idx, te_idx in self.split(n):
                tr_idx = _np.asarray(tr_idx)
                te_idx = _np.asarray(te_idx)
                # gap already enforced by TimeSeriesSplit, assert it
                if len(tr_idx) == 0 or len(te_idx) == 0:
                    continue
                assert int(tr_idx.max()) + self.gap < int(te_idx.min()) or self.gap == 0
                est = clone(model)
                est.fit(Xa[tr_idx], ya[tr_idx])
                if metric_fn is not None:
                    tr_s = float(metric_fn(est, Xa[tr_idx], ya[tr_idx]))
                    te_s = float(metric_fn(est, Xa[te_idx], ya[te_idx]))
                else:
                    tr_s = float(est.score(Xa[tr_idx], ya[tr_idx]))
                    te_s = float(est.score(Xa[te_idx], ya[te_idx]))
                tr_scores.append(tr_s)
                te_scores.append(te_s)
                folds.append(
                    {"train_end": int(tr_idx.max()), "test_start": int(te_idx.min()), "gap": self.gap}
                )
            if not te_scores:
                return Result.fail("No valid folds (data too short for n_splits/horizon)")
            return Result.ok(
                {
                    "train_scores": tr_scores,
                    "test_scores": te_scores,
                    "mean_train": float(_np.mean(tr_scores)),
                    "mean_test": float(_np.mean(te_scores)),
                    "gap": self.gap,
                    "horizon": self.horizon,
                    "cv_scheme": "time_series_split",
                    "folds": folds,
                }
            )
        except Exception as e:
            return Result.fail(str(e))


# Back-compat name: the old CrossValidator used shuffled KFold, which leaks
# future bars into the training fold. It is now a forward-chaining validator.
class CrossValidator(PurgedTimeSeriesCV):
    """Time-series-safe cross validator (ML-002).

    Shuffling is not merely off by default — it is refused outright, because a
    shuffled fold puts future bars in the training set and the resulting score
    says nothing about live performance. ``allow_shuffle`` exists only so call
    sites can assert on the guarantee; passing ``True`` raises.
    """

    def __init__(
        self,
        n_folds: int = 5,
        horizon: int | None = None,
        gap_extra: int = 0,
        allow_shuffle: bool = False,
    ) -> None:
        if allow_shuffle:
            raise ValueError(
                "CrossValidator never shuffles: a shuffled fold trains on future bars (ML-002)"
            )
        self.allow_shuffle = False
        # ``horizon`` stays required for the main pipeline (label look-ahead
        # bars); 1 bar is the safe floor when a caller has nothing to purge.
        super().__init__(n_splits=n_folds, horizon=1 if horizon is None else horizon, gap_extra=gap_extra)
