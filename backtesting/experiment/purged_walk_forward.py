"""Purged Walk-Forward — prevents information leakage between train/test windows.

Standard Walk-Forward can leak information through:
1. Overlapping indicators (e.g., SMA-20 computed on test data that includes train data)
2. Serial correlation in returns
3. Corporate actions spanning window boundaries

Purged Walk-Forward adds:
- Purging: Remove training samples that overlap with test labels
- Embargo: Add a gap between train and test to prevent leakage
- Combinatorial: Multiple non-overlapping test sets
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PurgedWindow:
    """A single purged walk-forward window."""
    window_id: int = 0
    train_start: int = 0       # bar index
    train_end: int = 0         # bar index (exclusive)
    test_start: int = 0        # bar index
    test_end: int = 0          # bar index (exclusive)
    embargo_bars: int = 0      # bars removed between train and test
    purged_bars: int = 0       # bars removed from train end


@dataclass
class PurgedWalkForwardResult:
    """Results from purged walk-forward optimization."""
    windows: list[PurgedWindow] = field(default_factory=list)
    in_sample_metrics: list[dict[str, float]] = field(default_factory=list)
    out_of_sample_metrics: list[dict[str, float]] = field(default_factory=list)
    oos_sharpe_mean: float = 0.0
    oos_sharpe_std: float = 0.0
    oos_return_mean: float = 0.0
    stability_score: float = 0.0  # how stable are OOS results across windows


class PurgedWalkForward:
    """Purged Walk-Forward optimizer with embargo.

    Prevents look-ahead bias and information leakage between
    train and test windows.
    """

    def __init__(
        self,
        n_windows: int = 5,
        train_pct: float = 0.7,
        embargo_pct: float = 0.01,  # 1% of data as embargo
        purge_pct: float = 0.01,    # 1% of train data purged at boundary
    ) -> None:
        self.n_windows = n_windows
        self.train_pct = train_pct
        self.embargo_pct = embargo_pct
        self.purge_pct = purge_pct

    def generate_windows(self, total_bars: int) -> list[PurgedWindow]:
        """Generate purged walk-forward windows."""
        windows = []
        window_size = total_bars // self.n_windows
        embargo_bars = max(1, int(total_bars * self.embargo_pct))
        purge_bars = max(1, int(total_bars * self.purge_pct))

        for i in range(self.n_windows):
            test_start = i * window_size
            test_end = min((i + 1) * window_size, total_bars)

            # Train is everything BEFORE test window, minus embargo and purge
            train_end = max(0, test_start - embargo_bars)
            train_start = max(0, train_end - int(train_end * (1 - self.train_pct) / self.train_pct))

            # Purge: remove last purge_bars from train (overlap zone)
            train_end_purged = max(train_start, train_end - purge_bars)

            if train_end_purged <= train_start or test_end <= test_start:
                continue

            windows.append(PurgedWindow(
                window_id=i,
                train_start=train_start,
                train_end=train_end_purged,
                test_start=test_start,
                test_end=test_end,
                embargo_bars=embargo_bars,
                purged_bars=purge_bars,
            ))

        return windows

    def get_train_data(
        self, data: list[dict[str, Any]], window: PurgedWindow
    ) -> list[dict[str, Any]]:
        """Extract training data for a window (purged)."""
        return data[window.train_start:window.train_end]

    def get_test_data(
        self, data: list[dict[str, Any]], window: PurgedWindow
    ) -> list[dict[str, Any]]:
        """Extract test data for a window."""
        return data[window.test_start:window.test_end]

    def compute_stability(self, oos_metrics: list[dict[str, float]]) -> float:
        """Compute stability score across windows.

        High stability = consistent OOS performance = less overfitting.
        """
        if len(oos_metrics) < 2:
            return 0.0

        sharpes = [m.get("sharpe_ratio", 0) for m in oos_metrics]
        [m.get("total_return_pct", 0) for m in oos_metrics]

        # Stability = 1 - coefficient_of_variation of OOS Sharpe
        mean_s = np.mean(sharpes)
        std_s = np.std(sharpes, ddof=1) if len(sharpes) > 1 else 0

        if abs(mean_s) < 1e-8:
            return 0.0

        cv = std_s / abs(mean_s)
        stability = max(0.0, min(1.0, 1.0 - cv))

        return float(stability)

    def summarize(self, result: PurgedWalkForwardResult) -> dict[str, Any]:
        """Summarize walk-forward results."""
        if result.out_of_sample_metrics:
            oos_sharpes = [m.get("sharpe_ratio", 0) for m in result.out_of_sample_metrics]
            oos_returns = [m.get("total_return_pct", 0) for m in result.out_of_sample_metrics]
            result.oos_sharpe_mean = float(np.mean(oos_sharpes))
            result.oos_sharpe_std = float(np.std(oos_sharpes, ddof=1)) if len(oos_sharpes) > 1 else 0
            result.oos_return_mean = float(np.mean(oos_returns))
            result.stability_score = self.compute_stability(result.out_of_sample_metrics)

        return {
            "n_windows": len(result.windows),
            "oos_sharpe_mean": round(result.oos_sharpe_mean, 4),
            "oos_sharpe_std": round(result.oos_sharpe_std, 4),
            "oos_return_mean": round(result.oos_return_mean, 4),
            "stability_score": round(result.stability_score, 4),
            "windows": [
                {
                    "id": w.window_id,
                    "train_bars": w.train_end - w.train_start,
                    "test_bars": w.test_end - w.test_start,
                    "embargo_bars": w.embargo_bars,
                    "purged_bars": w.purged_bars,
                }
                for w in result.windows
            ],
        }
