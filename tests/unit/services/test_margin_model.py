"""Config-driven margin simulation tests.

The numbers below are test assumptions supplied by the caller.  No exchange
margin rate is hardcoded in the service or asserted as a market fact here.
"""

from __future__ import annotations

import pytest

from services.gold.margin_model import simulate_margin_path

CONFIG = {
    "initial_margin_ratio": 0.10,
    "maintenance_margin_ratio": 0.05,
    "margin_call_equity_ratio": 1.00,
    "stop_out_equity_ratio": 0.50,
    "contract_size": 10.0,
    "contract_multiplier": 1.0,
}


def test_not_configured_returns_missing_parameters():
    result = simulate_margin_path(100.0, [100.0, 90.0], config={})

    assert result["status"] == "not_configured"
    assert result["configured"] is False
    assert set(result["missing"]) == {
        "initial_margin_ratio",
        "maintenance_margin_ratio",
        "margin_call_equity_ratio",
        "stop_out_equity_ratio",
        "contract_size",
    }
    assert result["steps"] == []


def test_margin_call_and_stop_out_are_hand_computed():
    # starting equity defaults to initial margin = 100 * 10 * 0.10 = 100
    result = simulate_margin_path(
        100.0, [100.0, 95.0, 94.0, 90.0], config=CONFIG
    )

    assert result["status"] == "ok"
    assert result["starting_equity"] == pytest.approx(100.0)
    assert result["initial_margin_requirement"] == pytest.approx(100.0)

    steps = result["steps"]
    assert [step["price"] for step in steps] == [100.0, 95.0, 94.0, 90.0]
    assert steps[0]["equity"] == pytest.approx(100.0)
    assert steps[0]["maintenance_requirement"] == pytest.approx(50.0)
    assert steps[0]["equity_ratio"] == pytest.approx(2.0)
    assert steps[0]["event"] is None

    assert steps[1]["pnl"] == pytest.approx(-50.0)
    assert steps[1]["equity"] == pytest.approx(50.0)
    assert steps[1]["maintenance_requirement"] == pytest.approx(47.5)
    assert steps[1]["equity_ratio"] == pytest.approx(50.0 / 47.5)
    assert steps[1]["event"] is None

    assert steps[2]["equity"] == pytest.approx(40.0)
    assert steps[2]["maintenance_requirement"] == pytest.approx(47.0)
    assert steps[2]["equity_ratio"] == pytest.approx(40.0 / 47.0)
    assert steps[2]["event"] == "MARGIN_CALL"

    assert steps[3]["equity"] == pytest.approx(0.0)
    assert steps[3]["equity_ratio"] == pytest.approx(0.0)
    assert steps[3]["event"] == "STOP_OUT"

    assert result["margin_call"] is True
    assert result["margin_call_index"] == 2
    assert result["stop_out"] is True
    assert result["stop_out_index"] == 3


def test_no_events_when_equity_ratio_stays_above_thresholds():
    config = {**CONFIG, "margin_call_equity_ratio": 0.50, "stop_out_equity_ratio": 0.25}
    result = simulate_margin_path(
        100.0, [100.0, 105.0, 110.0], starting_equity=1_000.0, config=config
    )

    assert result["margin_call"] is False
    assert result["stop_out"] is False
    assert result["margin_call_index"] is None
    assert result["stop_out_index"] is None
    assert all(step["event"] is None for step in result["steps"])


def test_short_direction_pnl_and_stop_out():
    result = simulate_margin_path(
        100.0,
        [100.0, 105.0, 110.0],
        direction=-1,
        config=CONFIG,
    )

    assert result["steps"][1]["pnl"] == pytest.approx(-50.0)
    assert result["steps"][2]["pnl"] == pytest.approx(-100.0)
    assert result["steps"][2]["event"] == "STOP_OUT"


def test_quantity_and_contract_multiplier_scale_pnl():
    config = {**CONFIG, "contract_multiplier": 2.0}
    result = simulate_margin_path(
        100.0, [90.0], quantity=2.0, starting_equity=1_000.0, config=config
    )
    # (90 - 100) * 2 * 10 * 2 = -400
    assert result["steps"][0]["pnl"] == pytest.approx(-400.0)
    assert result["steps"][0]["equity"] == pytest.approx(600.0)


@pytest.mark.parametrize(
    ("config", "message"),
    [
        ({**CONFIG, "stop_out_equity_ratio": 1.5}, "stop_out_equity_ratio"),
        ({**CONFIG, "maintenance_margin_ratio": -0.1}, "maintenance_margin_ratio"),
        ({**CONFIG, "contract_size": 0.0}, "contract_size"),
    ],
)
def test_invalid_config_raises(config, message):
    with pytest.raises(ValueError, match=message):
        simulate_margin_path(100.0, [100.0], config=config)


def test_invalid_direction_raises():
    with pytest.raises(ValueError, match="direction"):
        simulate_margin_path(100.0, [100.0], direction=0, config=CONFIG)


def test_empty_price_path_raises():
    with pytest.raises(ValueError, match="prices"):
        simulate_margin_path(100.0, [], config=CONFIG)


def test_negative_starting_equity_raises():
    with pytest.raises(ValueError, match="starting_equity"):
        simulate_margin_path(
            100.0, [100.0], starting_equity=-1.0, config=CONFIG
        )
