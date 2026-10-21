"""Behavioral tests for wiring the acceptance gate onto walk-forward results.

Covers the adapter that flattens a raw ``WalkForwardOptimizer`` payload into the
scalars ``evaluate_acceptance`` compares, and the per-threshold evidence report
the API returns (RELIABILITY_REPORT item 8: every ``acceptance.yaml`` threshold
must reference a specific part of the raw output).

All tests are behavioral: they call the public helpers and assert on returned
values — no source inspection or regex matching of the implementation.
"""

from __future__ import annotations

import json
import math
import re

import pytest

from core.config.acceptance_loader import (
    evaluate_walk_forward_result,
    walk_forward_metrics,
)

# ── Fixtures ────────────────────────────────────────────────────────────────

# Sources that aggregate the per-fold rows of ``oos_results``.
_AGGREGATE_SOURCE = re.compile(r"^(max|sum)\((\w+)\[\*\]\.(\w+)\)$")


def _fold(window: int, max_dd: float, trades: int, gross_profit: float, gross_loss: float) -> dict:
    return {
        "window": window,
        "max_dd": max_dd,
        "trades": trades,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
    }


def _passing_result() -> dict:
    """A raw walk-forward payload that clears all six thresholds.

    Worst fold drawdown is 18% (limit 20%), gross profit/loss 1600/1100 gives a
    profit factor of 1.4545 (limit 1.30) and 70 trades (minimum 50).
    """
    return {
        "strategy": "moving_average_cross",
        "walk_forward_efficiency": 0.80,
        "avg_oos_sharpe": 1.40,
        "deflated_sharpe": {"deflated_sharpe": 0.97, "p_value": 0.03, "n_trials": 32},
        "profit_factor": 1.4545,
        "n_windows": 2,
        "oos_results": [
            _fold(1, 12.0, 40, 900.0, 600.0),
            _fold(2, 18.0, 30, 700.0, 500.0),
        ],
    }


def _resolve_source(raw: dict, source: str) -> float:
    """Read the raw field a threshold row claims to have been judged against."""
    match = _AGGREGATE_SOURCE.match(source)
    if match:
        aggregation, rows_key, field = match.groups()
        values = [row[field] for row in raw[rows_key]]
        return max(values) if aggregation == "max" else sum(values)

    node: object = raw
    for part in source.split("."):
        node = node[part]  # type: ignore[index]
    return node  # type: ignore[return-value]


# ── Adapter: raw output -> gate metrics ─────────────────────────────────────


def test_walk_forward_metrics_reads_the_nested_dsr_scalar():
    metrics = walk_forward_metrics(_passing_result())

    # The raw DSR block is a dict; the gate needs its scalar.
    assert metrics["dsr"] == pytest.approx(0.97)


def test_walk_forward_metrics_aggregates_fold_rows():
    metrics = walk_forward_metrics(_passing_result())

    assert metrics["wfe"] == pytest.approx(0.80)
    assert metrics["oos_sharpe"] == pytest.approx(1.40)
    # Worst fold, kept on the 0-100 scale the optimizer emits.
    assert metrics["max_drawdown"] == pytest.approx(18.0)
    assert metrics["trade_count"] == 70


def test_walk_forward_metrics_winners_only_has_no_finite_profit_factor():
    raw = _passing_result()
    raw["profit_factor"] = None  # no losing round trip anywhere
    raw["oos_results"] = [_fold(1, 5.0, 60, 1200.0, 0.0)]

    metrics = walk_forward_metrics(raw)

    # The gate may pass this criterion, but nothing infinite is ever serialised.
    assert math.isinf(metrics["profit_factor"])


def test_walk_forward_metrics_absent_profit_factor_stays_absent():
    raw = _passing_result()
    raw["profit_factor"] = None
    raw["oos_results"] = [_fold(1, 5.0, 0, 0.0, 0.0)]

    assert walk_forward_metrics(raw)["profit_factor"] is None


def test_walk_forward_metrics_missing_fields_become_none():
    metrics = walk_forward_metrics({"strategy": "moving_average_cross", "oos_results": []})

    for metric in ("wfe", "dsr", "oos_sharpe", "max_drawdown", "profit_factor", "trade_count"):
        assert metrics[metric] is None


# ── Report: verdict plus per-threshold evidence ─────────────────────────────


def test_evaluate_walk_forward_result_passes_qualifying_strategy():
    report = evaluate_walk_forward_result(_passing_result())

    assert report["status"] == "PASS"
    assert report["reasons"] == []
    assert report["spec_version"] == "1.0"
    assert all(row["passed"] for row in report["thresholds"])


def test_evaluate_walk_forward_result_rejects_each_breached_threshold():
    raw = _passing_result()
    raw["walk_forward_efficiency"] = 0.30
    raw["deflated_sharpe"] = {"deflated_sharpe": 0.50}
    raw["avg_oos_sharpe"] = 0.20
    raw["profit_factor"] = 1.00
    raw["oos_results"] = [_fold(1, 45.0, 10, 100.0, 100.0)]

    report = evaluate_walk_forward_result(raw)

    assert report["status"] == "REJECT"
    assert len(report["reasons"]) == 6
    assert not any(row["passed"] for row in report["thresholds"])


def test_evaluate_walk_forward_result_verdict_matches_its_own_evidence():
    """The reported verdict is exactly the conjunction of the per-threshold rows."""
    breaching = _passing_result()
    breaching["avg_oos_sharpe"] = 0.90

    passing_report = evaluate_walk_forward_result(_passing_result())
    breaching_report = evaluate_walk_forward_result(breaching)

    assert (passing_report["status"] == "PASS") is all(
        row["passed"] for row in passing_report["thresholds"]
    )
    assert (breaching_report["status"] == "PASS") is all(
        row["passed"] for row in breaching_report["thresholds"]
    )
    assert breaching_report["status"] == "REJECT"
    assert any("sharpe" in reason.lower() for reason in breaching_report["reasons"])


def test_every_threshold_references_the_raw_field_it_judged():
    """item 8 — each threshold points at a specific part of the raw output."""
    raw = _passing_result()
    report = evaluate_walk_forward_result(raw)

    keys = {row["threshold"] for row in report["thresholds"]}
    assert keys == {
        "min_wfe",
        "min_dsr",
        "min_oos_sharpe",
        "max_drawdown",
        "min_profit_factor",
        "min_trade_count",
    }

    by_key = {row["threshold"]: row for row in report["thresholds"]}
    comparisons = {
        "min_wfe": (0.80, 0.50),
        "min_dsr": (0.97, 0.95),
        "min_oos_sharpe": (1.40, 1.00),
        "max_drawdown": (0.18, 0.20),  # normalised from the worst fold's 18%
        "min_profit_factor": (1.4545, 1.30),
        "min_trade_count": (70, 50),
    }

    for key, (value, limit) in comparisons.items():
        row = by_key[key]
        # The declared source really exists in the raw output and holds the value.
        resolved = _resolve_source(raw, row["source"])
        assert resolved is not None
        assert row["limit"] == pytest.approx(limit)
        assert row["value"] == pytest.approx(value)
        assert row["passed"] is True
        if key == "max_drawdown":
            # Percent-scaled raw value is reported alongside the compared fraction.
            assert row["observed"] == pytest.approx(resolved)
        else:
            assert row["value"] == pytest.approx(resolved)


def test_threshold_row_for_unmeasurable_metric_is_not_a_pass():
    """A criterion with no producer in the raw output can never pass."""
    raw = _passing_result()
    raw["profit_factor"] = None
    raw["oos_results"] = [_fold(1, 5.0, 60, 0.0, 0.0)]

    report = evaluate_walk_forward_result(raw)
    row = next(r for r in report["thresholds"] if r["threshold"] == "min_profit_factor")

    assert row["passed"] is False
    assert row["value"] is None
    assert report["status"] == "REJECT"
    assert any("profit_factor" in reason for reason in report["reasons"])


def test_report_never_serialises_non_finite_numbers():
    raw = _passing_result()
    raw["profit_factor"] = None
    raw["oos_results"] = [_fold(1, 5.0, 60, 1200.0, 0.0)]

    report = evaluate_walk_forward_result(raw)
    row = next(r for r in report["thresholds"] if r["threshold"] == "min_profit_factor")

    assert report["status"] == "PASS"  # winners-only clears the criterion
    assert row["value"] is None  # ... without emitting Infinity
    assert row["passed"] is True
    json.dumps(report, allow_nan=False)  # raises if any non-finite float leaked
