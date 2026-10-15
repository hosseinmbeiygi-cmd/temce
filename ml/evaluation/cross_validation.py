from __future__ import annotations

from typing import Any, Callable

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
        idx = range(n)
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
                    "folds": folds,
                }
            )
        except Exception as e:
            return Result.fail(str(e))


# Back-compat name: old CrossValidator used KFold (leaky). Keep alias that
# requires horizon so old call sites fail loudly and migrate.
class CrossValidator(PurgedTimeSeriesCV):
    def __init__(self, n_folds: int = 5, horizon: int | None = None, gap_extra: int = 0) -> None:
        if horizon is None:
            raise ValueError("CrossValidator now requires horizon=... (label look-ahead bars)")
        super().__init__(n_splits=n_folds, horizon=horizon, gap_extra=gap_extra)
