"""Behavioral tests for the Gold Engine acceptance gate (spec v1.0, 2026-10-13).

Covers:
  * Step 1 — ``acceptance.yaml`` loads with all three gold instruments.
  * Step 3 — ``get_gold_market_rules`` returns the per-instrument currency,
    risk-free rate and annualisation factor (USD/0.045/252d vs IRR/0.300/240d).
  * Step 3 — ``evaluate_acceptance`` gates a strategy as PASS/REJECT.
  * Step 2 (TD-01) — ``deflated_sharpe_ratio`` survives ``n_trials == 1``.

All tests are behavioral: they call the public helpers and assert on returned
values — no source inspection or regex matching.
"""

from __future__ import annotations

import math

import pytest

from core.config.acceptance_loader import (
    evaluate_acceptance,
    get_acceptance_config,
    get_gold_market_rules,
)

# ── Step 1: acceptance.yaml loads ────────────────────────────────────────────

GOLD_INSTRUMENTS = ("global_xau", "domestic_ime", "domestic_etf")


def test_acceptance_yaml_loads_all_gold_instruments():
    config = get_acceptance_config()

    assert config["version"] == "1.0"
    assert config["asset_class"] == "gold"

    gold = config["market_rules"]["gold"]
    assert set(gold.keys()) == set(GOLD_INSTRUMENTS)
    for instrument in GOLD_INSTRUMENTS:
        rules = gold[instrument]
        assert set(rules.keys()) == {
            "currency",
            "risk_free_rate",
            "trading_days_per_year",
            "spread_model",
        }


def test_acceptance_yaml_thresholds_present():
    thresholds = get_acceptance_config()["thresholds"]

    assert thresholds["walk_forward"]["min_wfe"] == pytest.approx(0.50)
    assert thresholds["walk_forward"]["min_dsr"] == pytest.approx(0.95)
    assert thresholds["walk_forward"]["min_oos_sharpe"] == pytest.approx(1.00)
    assert thresholds["risk_management"]["max_drawdown"] == pytest.approx(0.20)
    assert thresholds["risk_management"]["min_profit_factor"] == pytest.approx(1.30)
    assert thresholds["risk_management"]["min_trade_count"] == 50


# ── Step 3: per-instrument market rules ─────────────────────────────────────


def test_get_gold_market_rules_global_xau():
    rules = get_gold_market_rules("global_xau")

    assert rules["currency"] == "USD"
    assert rules["risk_free_rate"] == pytest.approx(0.045)
    assert rules["trading_days_per_year"] == 252
    assert rules["annualization_factor"] == pytest.approx(math.sqrt(252))
    assert rules["spread_model"] == "floating_points"


@pytest.mark.parametrize("instrument", ["domestic_ime", "domestic_etf"])
def test_get_gold_market_rules_domestic(instrument):
    rules = get_gold_market_rules(instrument)

    assert rules["currency"] == "IRR"
    assert rules["risk_free_rate"] == pytest.approx(0.300)
    assert rules["trading_days_per_year"] == 240
    assert rules["annualization_factor"] == pytest.approx(math.sqrt(240))


def test_get_gold_market_rules_unknown_instrument_raises():
    with pytest.raises(KeyError):
        get_gold_market_rules("not_an_instrument")


# ── Step 3: the acceptance gate ─────────────────────────────────────────────


def _passing_metrics() -> dict:
    return {
        "walk_forward_efficiency": 0.80,
        "deflated_sharpe": 0.97,
        "avg_oos_sharpe": 1.50,
        "max_drawdown": 0.10,
        "profit_factor": 1.80,
        "trade_count": 120,
    }


def test_evaluate_acceptance_passes_qualifying_strategy():
    verdict = evaluate_acceptance(_passing_metrics())

    assert verdict["status"] == "PASS"
    assert verdict["reasons"] == []


def test_evaluate_acceptance_rejects_each_breached_criterion():
    metrics = {
        "walk_forward_efficiency": 0.30,  # < min_wfe 0.50
        "deflated_sharpe": 0.90,          # < min_dsr 0.95
        "avg_oos_sharpe": 0.40,           # < min_oos_sharpe 1.00
        "max_drawdown": 0.45,             # > max_drawdown 0.20
        "profit_factor": 1.10,            # < min_profit_factor 1.30
        "trade_count": 10,                # < min_trade_count 50
    }
    verdict = evaluate_acceptance(metrics)

    assert verdict["status"] == "REJECT"
    assert len(verdict["reasons"]) == 6
    joined = " ".join(verdict["reasons"]).lower()
    for token in ("wfe", "dsr", "sharpe", "drawdown", "profit", "trade"):
        assert token in joined


def test_evaluate_acceptance_boundary_values_pass():
    """Exactly-at-threshold must PASS (>= / <= semantics)."""
    metrics = {
        "walk_forward_efficiency": 0.50,
        "deflated_sharpe": 0.95,
        "avg_oos_sharpe": 1.00,
        "max_drawdown": 0.20,
        "profit_factor": 1.30,
        "trade_count": 50,
    }
    assert evaluate_acceptance(metrics)["status"] == "PASS"


def test_evaluate_acceptance_missing_metric_is_rejected():
    metrics = _passing_metrics()
    del metrics["profit_factor"]

    verdict = evaluate_acceptance(metrics)

    assert verdict["status"] == "REJECT"
    assert any("profit_factor" in r and "missing" in r.lower() for r in verdict["reasons"])


def test_evaluate_acceptance_normalizes_percent_drawdown():
    """Risk metrics reported as 0-100 percentages are normalized to fractions."""
    metrics = _passing_metrics()
    metrics["max_drawdown"] = 10.0  # 10% expressed on the 0-100 scale

    assert evaluate_acceptance(metrics)["status"] == "PASS"

    metrics["max_drawdown"] = 45.0  # 45% → above the 20% limit
    assert evaluate_acceptance(metrics)["status"] == "REJECT"


# ── Step 2 (TD-01): degenerate DSR guard ────────────────────────────────────


def test_deflated_sharpe_single_trial_does_not_raise():
    from backtesting.metrics.deflated_sharpe import deflated_sharpe_ratio

    result = deflated_sharpe_ratio(
        sharpe_observed=1.5,
        n_trials=1,
        n_observations=250,
    )

    assert result["n_trials"] == 1
    assert 0.0 <= result["deflated_sharpe"] <= 1.0
    assert 0.0 <= result["p_value"] <= 1.0
    assert math.isfinite(result["deflated_sharpe"])
