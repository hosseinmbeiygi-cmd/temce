"""تست ثابت‌های GoldDesk."""

from __future__ import annotations

from src.gold_desk.constants import (
    AED_PEG,
    BUBBLE_GREEN_MAX,
    COIN_WEIGHTS,
    GOLD_PURITY_18K,
    GOLD_PURITY_24K,
    GOLD_PURITY_COIN,
    MESGHAL_GRAMS,
    SCORE_GREEN_MIN,
    SCORE_WEIGHTS,
    SCORE_YELLOW_MIN,
    TROY_OUNCE_GRAMS,
    VEHICLE_FEES,
)


def test_troy_ounce_constant():
    assert abs(TROY_OUNCE_GRAMS - 31.1034768) < 1e-6


def test_aed_peg_constant():
    assert abs(AED_PEG - 3.6725) < 1e-6


def test_purity_values():
    assert GOLD_PURITY_24K == 999.9
    assert GOLD_PURITY_18K == 750.0
    assert GOLD_PURITY_COIN == 900.0


def test_mesghal_grams():
    assert abs(MESGHAL_GRAMS - 4.6083) < 1e-4


def test_coin_weights_complete():
    required = {"IR_COIN_EMAMI", "IR_COIN_BAHAR", "IR_COIN_HALF", "IR_COIN_QUARTER", "IR_COIN_1G"}
    assert required.issubset(COIN_WEIGHTS.keys())
    # وزن‌های منطقی
    assert COIN_WEIGHTS["IR_COIN_EMAMI"] == 8.133
    assert COIN_WEIGHTS["IR_COIN_HALF"] == 4.066  # تقریباً نصف
    assert COIN_WEIGHTS["IR_COIN_QUARTER"] == 2.033


def test_score_weights_sum_to_100():
    assert sum(SCORE_WEIGHTS.values()) == 100


def test_score_weights_components():
    expected = {"bubble", "nav", "tsetmc", "technical", "parity", "fund_flow"}
    assert set(SCORE_WEIGHTS.keys()) == expected


def test_score_bands_ordering():
    assert SCORE_YELLOW_MIN < SCORE_GREEN_MIN
    assert SCORE_YELLOW_MIN > 0


def test_bubble_thresholds_ordering():
    assert BUBBLE_GREEN_MAX < 20  # منطقی


def test_vehicle_fees_structure():
    for _vehicle, fees in VEHICLE_FEES.items():
        assert "buy_pct" in fees
        assert "sell_pct" in fees
        assert "vat_pct" in fees
        assert fees["buy_pct"] >= 0
        assert fees["vat_pct"] >= 0


def test_vehicle_fees_etf_cheapest():
    """ETF باید کمترین کارمزد را داشته باشد."""
    etf_buy = VEHICLE_FEES["etf"]["buy_pct"]
    for v in VEHICLE_FEES.values():
        assert v["buy_pct"] >= etf_buy
