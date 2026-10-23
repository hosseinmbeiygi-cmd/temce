"""PROPOSED TEST — not placed in tests/ (per audit instruction).

Guard we propose for `services/backtest_framework.py::VectorizedBacktest`:
a signal must be reproducible from data up to t-1. The practical check is a
*truncation rerun*: rebuilding the signal on data[:t] and re-running the engine
must not change the equity path before t in a way that depends on prices after t.

This file currently FAILS, which documents the missing guard (audit B4).
It is written only under audit_out/ and is not part of the test suite.
"""
from __future__ import annotations

from services.backtest_framework import VectorizedBacktest


def _future_seen_signal(closes):
    """Cheating signal: knows tomorrow's close (this is what must be rejected)."""
    n = len(closes)
    return [1 if i + 1 < n and closes[i + 1] > closes[i] else 0 for i in range(n)]


def test_vectorized_engine_rejects_future_derived_signal():
    closes = [100, 101, 99, 103, 98, 104, 97, 105]
    signals = _future_seen_signal(closes)
    res = VectorizedBacktest().run(closes, signals)
    # A guard would flag this as look-ahead (signal uses closes[i+1]).
    assert res.get("lookahead_detected") is True, (
        "VectorizedBacktest has no signal-origin guard — a signal built from "
        "closes[i+1] is silently accepted (backtest_framework.py run(): "
        "'strategy_returns.append(signals[i - 1] * returns[i])')"
    )


def test_truncation_rerun_is_stable():
    """Signal must be buildable from data[:t]; re-running on a prefix must not
    change the engine output up to that prefix."""
    closes = [100, 101, 99, 103, 98, 104, 97, 105]
    signals = _future_seen_signal(closes)
    full = VectorizedBacktest().run(closes, signals)
    # truncate to first 6 bars; the signal for those bars must be recomputable
    sub_closes = closes[:6]
    sub_signals = _future_seen_signal(sub_closes)
    sub = VectorizedBacktest().run(sub_closes, sub_signals)
    assert full["final_equity"] == sub["final_equity"], (
        "engine result depends on data beyond the evaluated window — no "
        "truncation guard exists"
    )
