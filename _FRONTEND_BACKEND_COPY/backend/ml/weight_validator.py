"""Purged walk-forward validation for the regime weight optimizers.

Fixes audit finding **F6**: the weight files previously reported only the
IN-SAMPLE R² (``model.score(X, y)`` on the same rows used for fitting), which
has no decision value — it can look arbitrarily good due to overfitting.

``PurgedWeightValidator`` re-uses the project's existing
:class:`backtesting.experiment.purged_walk_forward.PurgedWalkForward` to split
each regime's rows into **chronological, purged, embargoed** train/test
windows. The Ridge model is re-fitted inside every window and scored on the
out-of-sample (test) fold; the reported ``r2_oos_mean`` is the honest
estimate, while ``r2_is_mean`` is kept alongside so a large IS-vs-OOS gap
exposes classic overfitting.

Why this fixes look-ahead bias
------------------------------
- Rows are sorted by ``trade_date`` and split strictly in time — a model
  fitted on window *t* never sees rows whose dates are at/after the test
  fold.
- The **embargo** removes a buffer of bars between train and test, so
  overlapping indicators (SMA/MACD windows) and serial correlation cannot
  leak across the boundary.
- The **purge** trims the tail of the train fold that overlaps the test
  labels.

When validation cannot be computed (too few rows, no valid window), the
validator returns ``provisional=True`` — the consumer should treat those
weights as unvalidated (in-sample only) until real as-of snapshots
accumulate (the early-snapshot look-ahead caveat in ``train_weight_optimizer``).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from backtesting.experiment.purged_walk_forward import PurgedWalkForward
from core.logging import get_logger

logger = get_logger(__name__)


def _stability(values: list[float]) -> float:
    """Consistency of OOS R² across windows: ``1 - coefficient of variation``.

    Values near 1 mean the model performs consistently out-of-sample across
    time; low/negative values mean its usefulness is window-dependent.
    """
    if len(values) < 2:
        return 0.0
    mean = float(np.mean(values))
    std = float(np.std(values, ddof=1))
    if abs(mean) < 1e-9:
        return 0.0
    return round(max(0.0, min(1.0, 1.0 - std / abs(mean))), 4)


class PurgedWeightValidator:
    """Validate a regime's Ridge weights with purged walk-forward OOS R²."""

    def __init__(
        self,
        n_windows: int = 4,
        train_pct: float = 0.6,
        embargo_pct: float = 0.02,
        purge_pct: float = 0.02,
        alpha: float = 1.0,
        min_train_rows: int = 10,
        min_test_rows: int = 3,
    ) -> None:
        self.n_windows = n_windows
        self.train_pct = train_pct
        self.embargo_pct = embargo_pct
        self.purge_pct = purge_pct
        self.alpha = alpha
        self.min_train_rows = min_train_rows
        self.min_test_rows = min_test_rows

    def validate(self, X: pd.DataFrame, y: pd.Series, dates: pd.Series) -> dict[str, Any]:
        """Run purged walk-forward validation on a regime's rows.

        ``X``, ``y`` and ``dates`` must be aligned (same length/order). Rows
        are sorted chronologically before windowing, so the train/test split
        is strictly temporal.

        Returns a dict with ``r2_oos_mean`` (the honest R²), ``r2_is_mean``
        (overfit comparison), per-window details, and a ``provisional`` flag.
        Never raises — a small/insufficient dataset yields ``provisional=True``.
        """
        if len(X) < self.min_train_rows + self.min_test_rows:
            return self._provisional(len(X), "too_few_rows")

        data = X.copy()
        data["__y"] = y.to_numpy()
        data["__date"] = pd.to_datetime(dates)
        data = data.sort_values("__date").reset_index(drop=True)

        pfw = PurgedWalkForward(
            n_windows=self.n_windows,
            train_pct=self.train_pct,
            embargo_pct=self.embargo_pct,
            purge_pct=self.purge_pct,
        )
        windows = pfw.generate_windows(len(data))

        oos_r2s: list[float] = []
        is_r2s: list[float] = []
        used: list[dict[str, Any]] = []

        for w in windows:
            train = data.iloc[w.train_start : w.train_end]
            test = data.iloc[w.test_start : w.test_end]
            if len(train) < self.min_train_rows or len(test) < self.min_test_rows:
                continue

            # Structural leak guard: the test fold must start strictly after
            # the (already purged) train fold — this is what the embargo does.
            if w.test_start < w.train_end:
                logger.warning("weight validation window %d overlaps — skipped", w.window_id)
                continue

            x_tr = train.drop(columns=["__y", "__date"])
            y_tr = train["__y"]
            x_te = test.drop(columns=["__y", "__date"])
            y_te = test["__y"]
            try:
                model = Ridge(alpha=self.alpha)
                model.fit(x_tr, y_tr)
                is_r2 = float(model.score(x_tr, y_tr))
                oos_r2 = float(model.score(x_te, y_te))
            except Exception as exc:  # noqa: BLE001 — one bad fold must not kill training
                logger.debug("weight validation window %s skipped (%s)", w.window_id, exc)
                continue

            oos_r2s.append(oos_r2)
            is_r2s.append(is_r2)
            used.append(
                {
                    "id": w.window_id,
                    "train_start": w.train_start,
                    "train_end": w.train_end,
                    "test_start": w.test_start,
                    "test_end": w.test_end,
                    "train_bars": len(train),
                    "test_bars": len(test),
                    "embargo_bars": w.embargo_bars,
                    "purged_bars": w.purged_bars,
                    "r2_is": round(is_r2, 4),
                    "r2_oos": round(oos_r2, 4),
                }
            )

        if not used:
            return self._provisional(len(X), "no_valid_windows")

        return {
            "provisional": False,
            "reason": None,
            "n_windows": len(used),
            "r2_is_mean": round(float(np.mean(is_r2s)), 4),
            "r2_oos_mean": round(float(np.mean(oos_r2s)), 4),
            "r2_oos_std": round(float(np.std(oos_r2s, ddof=1)) if len(oos_r2s) > 1 else 0.0, 4),
            "r2_oos_worst": round(min(oos_r2s), 4),
            "stability_score": _stability(oos_r2s),
            "rows": int(len(X)),
            "windows": used,
        }

    def _provisional(self, rows: int, reason: str) -> dict[str, Any]:
        """Unvalidated result — the weights should be treated as provisional."""
        logger.warning(
            "Purged weight validation skipped (%s, %d rows) — weights are PROVISIONAL "
            "(in-sample only until genuine as-of snapshots accumulate)",
            reason,
            rows,
        )
        return {
            "provisional": True,
            "reason": reason,
            "n_windows": 0,
            "r2_is_mean": None,
            "r2_oos_mean": None,
            "r2_oos_std": None,
            "r2_oos_worst": None,
            "stability_score": None,
            "rows": int(rows),
            "windows": [],
        }
