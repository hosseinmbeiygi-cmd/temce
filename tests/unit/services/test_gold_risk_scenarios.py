"""Unit tests for the pure Iranian gold portfolio stress engine."""

from __future__ import annotations

import pytest

from services.gold.risk_scenarios import (
    GOLD_RISK_SCENARIOS,
    list_risk_scenarios,
    stress_test_gold_portfolio,
)


def _coin(exposure_irr: float = 500_000_000, **overrides) -> dict:
    position = {
        "symbol": "IR_COIN_EMAMI",
        "asset_type": "coin",
        "direction": "long",
        "exposure_irr": exposure_irr,
    }
    position.update(overrides)
    return position


def test_scenario_catalogue_has_eight_named_scenarios() -> None:
    scenarios = list_risk_scenarios()
    ids = [row["scenario_id"] for row in scenarios]

    assert len(scenarios) == 8
    assert ids == [scenario.scenario_id for scenario in GOLD_RISK_SCENARIOS]
    assert "black_swan" in ids
    assert all(len(row["shocks"]) == 6 for row in scenarios)
    assert all(row["name_fa"] and row["name_en"] for row in scenarios)


def test_black_swan_coin_position_is_hand_computed() -> None:
    result = stress_test_gold_portfolio(
        equity_irr=1_000_000_000,
        positions=[_coin()],
        scenarios=[scenario for scenario in GOLD_RISK_SCENARIOS if scenario.scenario_id == "black_swan"],
    )

    black_swan = result["scenarios"][0]
    # (1 - 0.18) * (1 + 0.25) - 1 = 0.025; coin premium -0.12 -> -0.095.
    # 500m * -0.095 = -47.5m, minus 15% liquidity haircut (75m).
    assert black_swan["pnl_irr"] == pytest.approx(-122_500_000)
    assert black_swan["pnl_pct_of_equity"] == pytest.approx(-12.25)
    assert black_swan["post_equity_irr"] == pytest.approx(877_500_000)
    assert black_swan["margin_call"] is False
    assert black_swan["forced_liquidation"] is False
    assert result["risk_level"] == "HIGH"
    assert result["worst_case"]["scenario_id"] == "black_swan"


def test_margin_call_and_forced_liquidation_are_flagged() -> None:
    result = stress_test_gold_portfolio(
        equity_irr=100_000_000,
        positions=[_coin(maintenance_margin_irr=50_000_000, margin_irr=100_000_000)],
        scenarios=[scenario for scenario in GOLD_RISK_SCENARIOS if scenario.scenario_id == "black_swan"],
    )

    row = result["scenarios"][0]
    assert row["post_equity_irr"] == pytest.approx(-22_500_000)
    assert row["margin_call"] is True
    assert row["forced_liquidation"] is True
    assert row["maintenance_coverage_ratio"] == pytest.approx(-0.45)
    assert result["risk_level"] == "CRITICAL"


def test_option_delta_and_vega_are_applied() -> None:
    result = stress_test_gold_portfolio(
        equity_irr=1_000_000_000,
        positions=[
            {
                "symbol": "GOLD_CALL",
                "asset_type": "option",
                "direction": "long",
                "exposure_irr": 100_000_000,
                "delta": 0.5,
                "vega_irr_per_vol_point": 10_000_000,
            }
        ],
        scenarios=[
            {
                "scenario_id": "vol_up",
                "name_fa": "افزایش نوسان",
                "name_en": "Vol up",
                "shocks": {
                    "xau_usd_pct": 0.10,
                    "volatility_points": 0.05,
                },
            }
        ],
    )

    row = result["scenarios"][0]
    # 100m * 10% * delta 0.5 = 5m; vega 10m * 0.05 = 0.5m.
    assert row["pnl_irr"] == pytest.approx(5_500_000)
    assert row["positions"][0]["market_pnl_irr"] == pytest.approx(5_000_000)
    assert row["positions"][0]["vega_pnl_irr"] == pytest.approx(500_000)


def test_short_position_profits_from_local_premium_drop() -> None:
    result = stress_test_gold_portfolio(
        equity_irr=1_000_000_000,
        positions=[_coin(direction="short")],
        scenarios=[
            {
                "scenario_id": "premium_drop",
                "shocks": {"local_premium_pct": -0.10},
            }
        ],
    )

    row = result["scenarios"][0]
    assert row["pnl_irr"] == pytest.approx(50_000_000)
    assert row["positions"][0]["market_return_pct"] == pytest.approx(10.0)


def test_exposure_concentration_and_leverage_metrics() -> None:
    result = stress_test_gold_portfolio(
        equity_irr=1_000_000_000,
        positions=[
            _coin(exposure_irr=600_000_000),
            {
                "symbol": "ZARFSHANG",
                "asset_type": "etf",
                "direction": "short",
                "exposure_irr": 400_000_000,
            },
        ],
    )

    assert result["gross_exposure_irr"] == pytest.approx(1_000_000_000)
    assert result["net_exposure_irr"] == pytest.approx(200_000_000)
    assert result["net_exposure_pct_of_equity"] == pytest.approx(20.0)
    assert result["gross_leverage_ratio"] == pytest.approx(1.0)
    assert result["concentration_hhi"] == pytest.approx(0.52)
    assert result["largest_position_pct"] == pytest.approx(60.0)
    assert result["exposure_by_asset_type_irr"]["coin"] == pytest.approx(600_000_000)
    assert result["exposure_by_asset_type_irr"]["etf"] == pytest.approx(400_000_000)


def test_empty_positions_returns_unavailable_without_raising() -> None:
    result = stress_test_gold_portfolio(equity_irr=1_000_000_000, positions=[])

    assert result["available"] is False
    assert result["reason"] == "no positions supplied"
    assert result["gross_exposure_irr"] == 0
    assert result["worst_case"]["pnl_irr"] == 0
    assert len(result["scenarios"]) == len(GOLD_RISK_SCENARIOS)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"equity_irr": 0, "positions": [_coin()]}, "equity_irr"),
        ({"equity_irr": 1_000, "positions": [_coin(asset_type="bond")]}, "asset_type"),
        ({"equity_irr": 1_000, "positions": [_coin(direction="flat")]}, "direction"),
        ({"equity_irr": 1_000, "positions": [_coin(exposure_irr=-1)]}, "exposure_irr"),
        (
            {
                "equity_irr": 1_000,
                "positions": [_coin()],
                "scenarios": [{"scenario_id": "bad", "shocks": {"xau_usd_pct": -1.0}}],
            },
            "xau_usd_pct",
        ),
        (
            {"equity_irr": 1_000, "positions": [_coin()], "scenarios": []},
            "at least one scenario",
        ),
    ],
)
def test_invalid_inputs_raise_value_error(kwargs: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        stress_test_gold_portfolio(**kwargs)
