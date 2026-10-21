"""Audit F-04 — a future-return feature must not pass the pipeline silently.

The canary feature that leaked future information (IC 0.999) rode through the
whole feature pipeline because nothing inspected feature *names* for the
horizon. ``FeatureEngine._canary_check`` now fails such a sample and names the
offending keys.
"""

from __future__ import annotations

import pytest

from services.feature_engine import FeatureEngine, is_leakage_feature


@pytest.fixture
def engine() -> FeatureEngine:
    """A FeatureEngine without the DB/queue wiring the canary does not need."""
    return FeatureEngine.__new__(FeatureEngine)


def _features(**overrides) -> dict:
    base = {
        "ticker": "TEST",
        "eps_ttm": 1.0,
        "last_price": 100.0,
        "volume": 1000,
        "rsi_14": 50.0,
        "final_score": 50.0,
        "final_decision": "hold",
        "stop_loss": 95.0,
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    "name",
    [
        "future_return_5d",
        "fwd_return",
        "forward_return",
        "next_close",
        "lookahead_pe",
        "look_ahead_score",
        "label_up",
        "actual_return_pct",
        "trade_outcome",
        "leak_flag",
        "FUTURE_RETURN",
    ],
)
def test_future_looking_names_are_flagged(name):
    assert is_leakage_feature(name) is True


@pytest.mark.parametrize(
    "name",
    [
        "target_profit",       # take-profit level, computed from TODAY's price
        "target_1",
        "close",
        "ma_20",
        "returns_5d",          # trailing returns are legitimate
        "trailing_stop",
        "final_decision",
        "half_trend_signal",
    ],
)
def test_legitimate_names_are_not_flagged(name):
    assert is_leakage_feature(name) is False


def test_canary_fails_and_names_the_leaking_feature(engine):
    result = engine._canary_check(_features(future_return_5d=0.42), {"symbol": "TEST"})

    leakage = [c for c in result["checks"] if c["check"] == "leakage"]
    assert result["status"] == "FAIL"
    assert leakage and leakage[0]["status"] == "FAIL"
    assert "future_return_5d" in leakage[0]["message"]


def test_canary_reports_a_clean_leakage_check(engine):
    result = engine._canary_check(_features(target_profit=120.0), {"symbol": "TEST"})

    leakage = [c for c in result["checks"] if c["check"] == "leakage"]
    assert leakage and leakage[0]["status"] == "PASS"
