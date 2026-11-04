"""Comprehensive behavioral regression suite for ``WalkForwardOptimizer`` (F8/F9, R1–R5).

All tests are behavioral: they drive the real ``optimize`` code path and only
substitute the expensive/IO collaborators (per-combo evaluation, simulator,
metrics). No ``inspect.getsource`` / regex source-code matching is used.

Layers
------
1. Behavioral unit tests — purge/embargo gap, WFE math (R1), DSR trials (R2).
2. Lookahead & leakage guards — per-fold slice isolation.
3. Edge cases & degenerate folds — short/collapsed history, all-negative
   Sharpe, zero-variance series.
5. Async concurrency & fault tolerance — no deadlock, per-combo failure
   isolation.

(API contract/integration lives in tests/unit/apps/api/test_walk_forward_api.py.)
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

import backtesting.optimization.walk_forward as wf
from backtesting.optimization.walk_forward import WalkForwardOptimizer
from backtesting.strategies.registry import register_all_strategies

# ── Minimal duck-typed simulator doubles ─────────────────────────────────────


@dataclass
class _EP:  # equity-curve point
    nav: float


@dataclass
class _Trade:
    pnl: float


@dataclass
class _Val:
    equity_curve: list
    trades: list


@dataclass
class _Run:
    success: bool
    value: Any


class _RecordingSimulator:
    """Deterministic simulator that records the exact data slice per run()."""

    def __init__(self, slope: float = 0.01) -> None:
        self.slices: list[list[dict[str, Any]]] = []
        self._slope = slope

    def run(self, strategy: Any, *, initial_capital: float, data: list[dict[str, Any]]) -> _Run:
        self.slices.append(data)
        n = max(len(data), 2)
        curve = [_EP(100.0 + self._slope * i) for i in range(n)]
        return _Run(True, _Val(curve, [_Trade(1.0) for _ in range(max(n // 2, 1))]))


class _FaultySimulator(_RecordingSimulator):
    """Raises for one parameter set, succeeds otherwise (IS fault isolation)."""

    def __init__(self, fail_fast_period: int) -> None:
        super().__init__()
        self._fail_fast_period = fail_fast_period

    def run(self, strategy: Any, *, initial_capital: float, data: list[dict[str, Any]]) -> _Run:
        if getattr(strategy, "fast_period", None) == self._fail_fast_period:
            raise RuntimeError("boom: injected combo failure")
        return super().run(strategy, initial_capital=initial_capital, data=data)


# ── Fixtures / helpers ───────────────────────────────────────────────────────


def _series(n: int = 1200, start_price: float = 100.0) -> list[dict[str, Any]]:
    """Synthetic daily OHLCV series (>= 1000 bars by default)."""
    register_all_strategies()
    start = datetime(2021, 1, 1, tzinfo=UTC)
    return [
        {
            "timestamp": start + timedelta(days=i),
            "open": start_price,
            "high": start_price + 1.0,
            "low": start_price - 1.0,
            "close": start_price + i * 0.01,
            "prices": {"X": start_price + i * 0.01},
            "instrument_id": "X",
            "volume": 1000,
        }
        for i in range(n)
    ]


def _index_of(series: list[dict[str, Any]], row: dict[str, Any]) -> int:
    """Position of a row in the parent series (rows are unique by timestamp)."""
    return series.index(row)


def _patch_is_eval_recording(
    monkeypatch: pytest.MonkeyPatch, train_slices: list[list[dict[str, Any]]]
) -> None:
    """Patch the IS combo sweep to record the exact ``train_data`` slice it gets."""

    async def fake_eval(self, cls, combo, keys, train_data, capital, simulator):  # noqa: ANN001
        train_slices.append(train_data)
        return (1.0, dict(zip(keys, combo, strict=False)), 0.0)

    monkeypatch.setattr(wf.WalkForwardOptimizer, "_eval_combo", fake_eval)


def _unique_in_order(items: list) -> list:
    out: list = []
    for item in items:
        if not out or out[-1] is not item:
            out.append(item)
    return out


# ── Layer 1: behavioral unit tests ───────────────────────────────────────────


class TestBackwardCompatibleDefaults:
    def test_default_gap_fractions_are_pinned(self):
        """Consumers constructing with only (windows, train_ratio, max_workers)
        — e.g. apps/api/endpoints/backtests.py — must keep the 0.01 defaults."""
        opt = WalkForwardOptimizer()
        assert opt.embargo_pct == 0.01
        assert opt.purge_pct == 0.01

    def test_result_contract_keys_present(self, monkeypatch):
        data = _series()
        sim = _RecordingSimulator()
        train_slices: list = []
        _patch_is_eval_recording(monkeypatch, train_slices)

        opt = WalkForwardOptimizer(windows=4, embargo_pct=0.02, purge_pct=0.02)
        out = asyncio.run(
            opt.optimize(
                "moving_average_cross",
                {"fast_period": [5, 10], "slow_period": [20, 30]},
                data,
                1_000_000.0,
                sim,
            )
        )
        assert "error" not in out
        for key in (
            "strategy", "best_params", "oos_results", "avg_oos_sharpe",
            "walk_forward_efficiency", "embargo_bars", "purged_bars",
            "deflated_sharpe", "n_windows", "is_sharpes", "oos_sharpes",
        ):
            assert key in out
        assert len(out["is_sharpes"]) == len(out["oos_sharpes"]) == out["n_windows"]


class TestEmbargoAndPurgeGap:
    """Layer 1.1 — purge/embargo gap integrity, zero IS/OOS overlap."""

    def test_train_test_gap_is_purge_plus_embargo_and_nonoverlapping(self, monkeypatch):
        data = _series(1200)
        sim = _RecordingSimulator()
        train_slices: list = []
        _patch_is_eval_recording(monkeypatch, train_slices)

        windows, ratio = 5, 0.7
        opt = WalkForwardOptimizer(windows=windows, train_ratio=ratio, embargo_pct=0.05, purge_pct=0.05)
        out = asyncio.run(
            opt.optimize(
                "moving_average_cross",
                {"fast_period": [5, 10], "slow_period": [20, 30]},
                data,
                1_000_000.0,
                sim,
            )
        )
        assert "error" not in out

        embargo_bars = out["embargo_bars"]
        purge_bars = out["purged_bars"]
        assert embargo_bars > 0 and purge_bars > 0
        window_size = len(data) // windows

        unique_train = _unique_in_order(train_slices)
        assert len(unique_train) == len(sim.slices) == out["n_windows"]

        for w, (tr, te) in enumerate(zip(unique_train, sim.slices, strict=True)):
            split = int(window_size * ratio)
            expected_train_len = split - purge_bars
            expected_test_start_off = split + embargo_bars

            assert len(tr) == expected_train_len
            assert len(te) == window_size - expected_test_start_off

            # Index-level separation: gap is exactly purge + embargo, no overlap.
            base = w * window_size
            assert _index_of(data, tr[-1]) == base + expected_train_len - 1
            assert _index_of(data, te[0]) == base + expected_test_start_off
            # Exclusive gap (bars dropped between the two folds) is exactly
            # purge + embargo; the inclusive index distance is +1 and must at
            # least satisfy the spec's >= (purge_bars + embargo_bars) bound.
            exclusive_gap = expected_test_start_off - expected_train_len
            assert exclusive_gap == purge_bars + embargo_bars
            assert _index_of(data, te[0]) - _index_of(data, tr[-1]) >= purge_bars + embargo_bars

            train_ts = {r["timestamp"] for r in tr}
            test_ts = {r["timestamp"] for r in te}
            assert train_ts.isdisjoint(test_ts)
            assert max(train_ts) < min(test_ts)


class TestWalkForwardEfficiency:
    """Layer 1.2 — WFE = mean(OOS Sharpe) / mean(IS Sharpe), no positive-only bias."""

    @staticmethod
    def _optimize_with_sharpes(
        monkeypatch: pytest.MonkeyPatch,
        is_values: list[float],
        oos_values: list[float],
        windows: int,
    ) -> dict[str, Any]:
        data = _series(1200)
        sim = _RecordingSimulator()
        is_iter: Iterator[float] = iter(is_values)
        oos_iter: Iterator[float] = iter(oos_values)

        async def fake_optimize_window(self, cls, all_combos, keys, train_data, capital, simulator):  # noqa: ANN001
            return (dict(zip(keys, all_combos[0], strict=False)), 1.0, next(is_iter))

        def fake_metrics(equity, trades):  # noqa: ANN001
            return {
                "return_pct": 1.0, "sharpe": next(oos_iter),
                "max_dd": 0.0, "win_rate": 100.0, "trades": 10,
            }

        monkeypatch.setattr(wf.WalkForwardOptimizer, "_optimize_window", fake_optimize_window)
        monkeypatch.setattr(wf, "_compute_metrics", fake_metrics)

        opt = WalkForwardOptimizer(windows=windows, embargo_pct=0.02, purge_pct=0.02)
        return asyncio.run(
            opt.optimize(
                "moving_average_cross",
                {"fast_period": [5, 10], "slow_period": [20]},
                data,
                1_000_000.0,
                sim,
            )
        )

    def test_wfe_is_dimensionless_oos_over_is_mean(self, monkeypatch):
        is_values = [2.0, -1.0]
        oos_values = [1.0, 1.0]
        out = self._optimize_with_sharpes(monkeypatch, is_values, oos_values, windows=2)

        assert out["is_sharpes"] == is_values
        assert out["oos_sharpes"] == oos_values
        is_mean = sum(is_values) / len(is_values)          # 0.5, not positive-only 1.0
        oos_mean = sum(oos_values) / len(oos_values)        # 1.0
        assert out["walk_forward_efficiency"] == pytest.approx(round(oos_mean / max(is_mean, 0.01), 3))
        assert abs(out["walk_forward_efficiency"]) < 10   # not sqrt(252)-scaled

    def test_all_negative_sharpes_do_not_flip_sign(self, monkeypatch):
        out = self._optimize_with_sharpes(monkeypatch, [-0.5, -0.8], [-0.2, -0.3], windows=2)
        # IS mean < 0 -> no meaningful efficiency ratio; must be 0, never a
        # positive/absurd value produced by dividing by a flipped sign.
        assert out["walk_forward_efficiency"] == 0

    def test_zero_mean_is_sharpe_is_guarded(self, monkeypatch):
        out = self._optimize_with_sharpes(monkeypatch, [0.0, 0.0], [1.0, 1.0], windows=2)
        assert out["walk_forward_efficiency"] == 0        # no ZeroDivisionError


class TestDeflatedSharpeTrials:
    """Layer 1.3 — DSR n_trials = grid_size * executed windows (R2)."""

    def test_dsr_n_trials_counts_all_folds(self, monkeypatch):
        data = _series(1200)
        sim = _RecordingSimulator()
        train_slices: list = []
        _patch_is_eval_recording(monkeypatch, train_slices)

        grid = {"fast_period": [5, 10], "slow_period": [20, 30]}
        opt = WalkForwardOptimizer(windows=4, embargo_pct=0.02, purge_pct=0.02)
        out = asyncio.run(opt.optimize("moving_average_cross", grid, data, 1_000_000.0, sim))

        grid_size = len(grid["fast_period"]) * len(grid["slow_period"])
        assert out["deflated_sharpe"]["n_trials"] == grid_size * out["n_windows"]


# ── Layer 2: lookahead & leakage guards ──────────────────────────────────────


class TestLookaheadLeakageGuards:
    def test_train_slice_bounded_and_disjoint_from_oos(self, monkeypatch):
        """The IS slice handed to _eval_combo must end strictly before the OOS
        slice begins (no shared bars, no reach past train_end)."""
        data = _series(1200)
        sim = _RecordingSimulator()
        train_slices: list = []
        _patch_is_eval_recording(monkeypatch, train_slices)

        opt = WalkForwardOptimizer(windows=4, train_ratio=0.7, embargo_pct=0.03, purge_pct=0.03)
        out = asyncio.run(
            opt.optimize(
                "moving_average_cross",
                {"fast_period": [5], "slow_period": [20]},
                data,
                1_000_000.0,
                sim,
            )
        )
        assert "error" not in out
        unique_train = _unique_in_order(train_slices)
        for tr, te in zip(unique_train, sim.slices, strict=True):
            assert tr, "train slice must not be empty"
            train_ts = {r["timestamp"] for r in tr}
            test_ts = {r["timestamp"] for r in te}
            assert train_ts.isdisjoint(test_ts)
            assert max(train_ts) < min(test_ts)

    def test_oos_does_not_leak_back_into_embargo(self, monkeypatch):
        """The first OOS bar must sit exactly embargo_bars after train_end,
        i.e. the embargo gap is never consumed by the OOS window."""
        data = _series(1200)
        sim = _RecordingSimulator()
        train_slices: list = []
        _patch_is_eval_recording(monkeypatch, train_slices)

        opt = WalkForwardOptimizer(windows=3, train_ratio=0.7, embargo_pct=0.05, purge_pct=0.0)
        out = asyncio.run(
            opt.optimize(
                "moving_average_cross",
                {"fast_period": [5], "slow_period": [20]},
                data,
                1_000_000.0,
                sim,
            )
        )
        assert "error" not in out
        unique_train = _unique_in_order(train_slices)
        for tr, te in zip(unique_train, sim.slices, strict=True):
            # train[-1] and test[0] are inclusive endpoints, so the dropped-bar
            # count is the inclusive index distance minus 1 and must equal the
            # full embargo + purge gap (OOS never consumes the embargo).
            dropped = _index_of(data, te[0]) - _index_of(data, tr[-1]) - 1
            assert dropped == out["embargo_bars"] + out["purged_bars"]


# ── Layer 3: edge cases & degenerate folds ───────────────────────────────────


class TestShortHistoryAndCollapsedFolds:
    def test_window_too_small_returns_error_not_exception(self):
        opt = WalkForwardOptimizer(windows=50)  # 400 // 50 = 8 < 20 guard
        out = asyncio.run(
            opt.optimize("moving_average_cross", {"fast_period": [5]}, _series(400), 1_000.0, _RecordingSimulator())
        )
        assert out == {"error": "Not enough data for walk-forward optimization"}

    def test_collapsed_fold_is_skipped_gracefully(self):
        # gap dominates the window -> empty train/test -> schema returns an
        # error dict, never an unhandled IndexError.
        opt = WalkForwardOptimizer(windows=4, train_ratio=0.7, embargo_pct=0.6, purge_pct=0.6)
        out = asyncio.run(
            opt.optimize(
                "moving_average_cross",
                {"fast_period": [5], "slow_period": [20]},
                _series(400),
                1_000.0,
                _RecordingSimulator(),
            )
        )
        assert out == {"error": "No valid walk-forward results"}


class TestDegenerateMetrics:
    def test_flat_series_zero_variance_no_nan(self):
        equity = [100.0] * 50
        metrics = wf._compute_metrics(equity, [_Trade(1.0)])
        assert metrics["sharpe"] == 0
        for value in metrics.values():
            assert math.isfinite(float(value))

    def test_monotonic_loss_series_is_finite(self):
        equity = [100.0 - i for i in range(50)]
        metrics = wf._compute_metrics(equity, [_Trade(-1.0)])
        for value in metrics.values():
            assert math.isfinite(float(value))


# ── Layer 5: async concurrency & fault tolerance ─────────────────────────────


class TestConcurrencyAndFaultTolerance:
    def test_parallel_evaluation_completes_without_deadlock(self, monkeypatch):
        data = _series(1200)
        sim = _RecordingSimulator()
        calls = {"n": 0}

        async def fake_eval(self, cls, combo, keys, train_data, capital, simulator):  # noqa: ANN001
            calls["n"] += 1
            await asyncio.sleep(0)  # force cooperative scheduling
            return (1.0, dict(zip(keys, combo, strict=False)), 0.0)

        monkeypatch.setattr(wf.WalkForwardOptimizer, "_eval_combo", fake_eval)

        grid = {"fast_period": [5, 10], "slow_period": [20, 30]}  # 4 combos
        opt = WalkForwardOptimizer(windows=3, max_workers=4, embargo_pct=0.02, purge_pct=0.02)
        out = asyncio.run(opt.optimize("moving_average_cross", grid, data, 1_000_000.0, sim))

        assert "error" not in out
        assert calls["n"] == 4 * out["n_windows"]

    def test_faulty_combo_does_not_abort_run(self):
        """A single exploding parameter set must be isolated by _eval_combo's
        guard; remaining combos/windows still complete."""
        data = _series(1200)
        sim = _FaultySimulator(fail_fast_period=5)
        opt = WalkForwardOptimizer(windows=3, embargo_pct=0.02, purge_pct=0.02)
        out = asyncio.run(
            opt.optimize(
                "moving_average_cross",
                {"fast_period": [5, 10], "slow_period": [20]},
                data,
                1_000_000.0,
                sim,
            )
        )
        assert "error" not in out
        assert out["n_windows"] == 3
        assert out["best_params"]["fast_period"] == 10  # the healthy combo wins
