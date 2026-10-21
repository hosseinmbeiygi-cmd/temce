"""Unit tests for Step 3 Iran physical-market completeness calculators.

Every expected value below is either an explicit arithmetic expression or a
hand-computed constant derived from the published formulas.  The functions are
pure: no database, no network and no cache.
"""

from __future__ import annotations

import math
from decimal import Decimal, localcontext

import pytest

from services.gold.constants import (
    AED_PEG,
    GERAMI_MINTING_FEE_IRR,
    IME_BULLION_ASSAY,
    PURITY_18K,
)
from services.gold.physical_market import (
    aed_hawala_spread,
    calculate_assay_variance_scenarios,
    calculate_coin_bubbles_with_history,
    calculate_gram18_from_mesghal_decimal,
    calculate_ime_certificate_spread,
    evaluate_aed_hawala_alert,
    rolling_zscore_percentile,
    validate_ime_position_limit,
)

OUNCE_USD = 2_000.0
USD_IRR = 1_000_000.0


class TestDecimalMazanehConversion:
    def test_returns_decimal_and_known_one_million_value(self) -> None:
        result = calculate_gram18_from_mesghal_decimal(1_000_000.0)

        assert isinstance(result, Decimal)
        assert result == pytest.approx(Decimal("230850.8098938963507565673593"))

    def test_matches_exact_rational_without_intermediate_rounding(self) -> None:
        price = Decimal("123456789")
        with localcontext() as ctx:
            ctx.prec = 50
            exact = price / Decimal("4.6083") * (Decimal("750") / Decimal("705"))

        result = calculate_gram18_from_mesghal_decimal(price)

        assert abs(result - exact) / exact < Decimal("1e-25")

        # A 2-decimal intermediate rounding is measurably different, so this
        # assertion proves the implementation did not round mid-calculation.
        naive = Decimal(str(round(float(price) / 4.6083, 2))) * (
            Decimal("750") / Decimal("705")
        )
        assert abs(result - naive) > Decimal("0.001")

    def test_accepts_string_input(self) -> None:
        assert calculate_gram18_from_mesghal_decimal("1000000") == pytest.approx(
            Decimal("230850.8098938963507565673593")
        )

    @pytest.mark.parametrize("bad", [0, -1, "-5", Decimal("NaN")])
    def test_rejects_non_positive_or_non_finite(self, bad) -> None:
        with pytest.raises(ValueError):
            calculate_gram18_from_mesghal_decimal(bad)


class TestAssayVarianceScenarios:
    def test_covers_745_through_755_with_hand_computed_values(self) -> None:
        result = calculate_assay_variance_scenarios(10.0, 5_000_000.0)

        assert result["assays"] == list(range(745, 756))
        assert result["scenarios"][745]["real_weight_gram18"] == pytest.approx(
            10.0 * 745 / 750
        )
        assert result["scenarios"][745]["value_irr"] == pytest.approx(
            10.0 * 745 / 750 * 5_000_000.0
        )
        assert result["scenarios"][750]["value_irr"] == pytest.approx(50_000_000.0)
        assert result["scenarios"][755]["value_irr"] == pytest.approx(
            10.0 * 755 / 750 * 5_000_000.0
        )
        assert result["scenarios"][745]["delta_vs_750_irr"] == pytest.approx(
            -333_333.3333333333
        )
        assert result["scenarios"][755]["delta_vs_750_irr"] == pytest.approx(
            333_333.3333333333
        )
        assert result["range_value_irr"] == pytest.approx(666_666.6666666666)
        assert result["min_value_irr"] == pytest.approx(49_666_666.666666664)
        assert result["max_value_irr"] == pytest.approx(50_333_333.333333336)

    def test_supports_custom_assay_list(self) -> None:
        result = calculate_assay_variance_scenarios(
            4.0, 1_000_000.0, assays=[745, 750, 755]
        )

        assert result["assays"] == [745, 750, 755]
        assert result["scenarios"][750]["value_irr"] == pytest.approx(4_000_000.0)

    def test_zero_weight_is_allowed_and_zero_valued(self) -> None:
        result = calculate_assay_variance_scenarios(0.0, 5_000_000.0)

        assert result["range_value_irr"] == pytest.approx(0.0)
        assert result["scenarios"][750]["value_irr"] == pytest.approx(0.0)

    @pytest.mark.parametrize("bad_weight", [-1.0, float("inf")])
    def test_invalid_weight_raises(self, bad_weight) -> None:
        with pytest.raises(ValueError):
            calculate_assay_variance_scenarios(bad_weight, 5_000_000.0)

    @pytest.mark.parametrize("bad_price", [0.0, -1.0])
    def test_invalid_base_price_raises(self, bad_price) -> None:
        with pytest.raises(ValueError):
            calculate_assay_variance_scenarios(10.0, bad_price)


class TestCoinBubbleCompleteness:
    PRICES = {
        "IR_COIN_EMAMI": 500_000_000.0,
        "IR_COIN_HALF": 250_000_000.0,
        "IR_COIN_QUARTER": 125_000_000.0,
        "IR_COIN_1G": 60_000_000.0,
    }

    def test_all_canonical_coins_have_nominal_percent_and_fee_breakdown(self) -> None:
        result = calculate_coin_bubbles_with_history(
            OUNCE_USD, USD_IRR, self.PRICES
        )

        assert set(result) == {"emami", "half", "quarter", "gerami"}

        emami = result["emami"]
        assert emami["gold_value_irr"] == pytest.approx(470_714_710.7878512)
        assert emami["minting_fee_irr"] == pytest.approx(0.0)
        assert emami["intrinsic_value_irr"] == pytest.approx(
            emami["gold_value_irr"] + emami["minting_fee_irr"]
        )
        assert emami["bubble_abs_irr"] == pytest.approx(
            500_000_000.0 - 470_714_710.7878512
        )
        assert emami["bubble_pct"] == pytest.approx(
            (500_000_000.0 - 470_714_710.7878512)
            / 470_714_710.7878512
            * 100.0
        )

        gerami = result["gerami"]
        assert gerami["minting_fee_irr"] == pytest.approx(GERAMI_MINTING_FEE_IRR)
        assert gerami["intrinsic_value_irr"] == pytest.approx(
            58_455_902.85205087 + GERAMI_MINTING_FEE_IRR
        )
        assert gerami["bubble_abs_irr"] == pytest.approx(
            60_000_000.0 - (58_455_902.85205087 + GERAMI_MINTING_FEE_IRR)
        )
        assert gerami["is_discount"] is False

    def test_history_adds_zscore_and_percentile(self) -> None:
        result = calculate_coin_bubbles_with_history(
            OUNCE_USD,
            USD_IRR,
            {"IR_COIN_EMAMI": 611_929_124.0242066},
            history_by_coin={"IR_COIN_EMAMI": [10.0, 20.0, 30.0]},
        )

        emami = result["emami"]
        assert emami["history_sample_size"] == 3
        assert emami["bubble_zscore"] == pytest.approx(1.224744871391589)
        assert emami["bubble_percentile"] == pytest.approx(100.0)

    def test_missing_history_leaves_stats_empty(self) -> None:
        result = calculate_coin_bubbles_with_history(
            OUNCE_USD, USD_IRR, {"IR_COIN_EMAMI": 500_000_000.0}
        )

        emami = result["emami"]
        assert emami["history_sample_size"] == 0
        assert emami["bubble_zscore"] is None
        assert emami["bubble_percentile"] is None

    def test_missing_prices_are_not_fabricated(self) -> None:
        result = calculate_coin_bubbles_with_history(
            OUNCE_USD, USD_IRR, {"IR_COIN_EMAMI": 500_000_000.0}
        )

        assert set(result) == {"emami"}


class TestRollingStats:
    def test_empty_history_has_no_stats(self) -> None:
        result = rolling_zscore_percentile([], 10.0)

        assert result == {
            "sample_size": 0,
            "mean": None,
            "std": None,
            "z_score": None,
            "percentile": None,
        }

    def test_single_point_has_percentile_but_no_zscore(self) -> None:
        result = rolling_zscore_percentile([10.0], 10.0)

        assert result["sample_size"] == 1
        assert result["z_score"] is None
        assert result["percentile"] == pytest.approx(100.0)

    def test_percentile_is_share_at_or_below_current(self) -> None:
        result = rolling_zscore_percentile([10.0, 20.0, 30.0], 20.0)

        assert result["mean"] == pytest.approx(20.0)
        assert result["std"] == pytest.approx(8.16496580927726)
        assert result["z_score"] == pytest.approx(0.0)
        assert result["percentile"] == pytest.approx(66.66666666666666)

    def test_below_history_is_zero_percentile(self) -> None:
        result = rolling_zscore_percentile([10.0, 20.0, 30.0], 0.0)

        assert result["percentile"] == pytest.approx(0.0)

    def test_zero_std_has_no_zscore(self) -> None:
        result = rolling_zscore_percentile([5.0, 5.0, 5.0], 6.0)

        assert result["std"] == pytest.approx(0.0)
        assert result["z_score"] is None
        assert result["percentile"] == pytest.approx(100.0)

    def test_non_finite_values_are_ignored(self) -> None:
        result = rolling_zscore_percentile(
            [10.0, math.nan, 20.0, math.inf], 20.0
        )

        assert result["sample_size"] == 2
        assert result["mean"] == pytest.approx(15.0)


class TestImeCertificateSpread:
    def test_premium_certificate_buys_melted_and_sells_certificate(self) -> None:
        result = calculate_ime_certificate_spread(7_000_000.0, 5_000_000.0)

        assert result["assay_uplift"] == pytest.approx(IME_BULLION_ASSAY / PURITY_18K)
        assert result["melted_equivalent_grams"] == pytest.approx(995 / 750)
        assert result["cert_notional_irr"] == pytest.approx(7_000_000.0)
        assert result["melted_notional_irr"] == pytest.approx(6_633_333.333333333)
        assert result["cert_fee_irr"] == pytest.approx(10_500.0)
        assert result["melted_fee_irr"] == pytest.approx(9_950.0)

        buy_melted = result["buy_melted_sell_cert"]
        assert buy_melted["cert_proceeds_irr"] == pytest.approx(6_989_500.0)
        assert buy_melted["melted_cost_irr"] == pytest.approx(6_643_283.333333333)
        assert buy_melted["net_spread_irr"] == pytest.approx(346_216.666666667)
        assert buy_melted["net_spread_pct"] == pytest.approx(5.211529439509083)
        assert result["action"] == "BUY_MELTED_SELL_IME_CERT"
        assert result["is_profitable"] is True

    def test_discount_certificate_reverses_the_trade(self) -> None:
        result = calculate_ime_certificate_spread(5_000_000.0, 5_000_000.0)

        buy_cert = result["buy_cert_sell_melted"]
        assert buy_cert["cert_cost_irr"] == pytest.approx(5_007_500.0)
        assert buy_cert["melted_proceeds_irr"] == pytest.approx(6_623_383.333333333)
        assert buy_cert["net_spread_irr"] == pytest.approx(1_615_883.333333333)
        assert buy_cert["net_spread_pct"] == pytest.approx(32.2692627725079)
        assert result["action"] == "BUY_IME_CERT_SELL_MELTED"
        assert result["is_profitable"] is True

    def test_storage_and_delivery_are_charged_on_the_physical_leg(self) -> None:
        base = calculate_ime_certificate_spread(7_000_000.0, 5_000_000.0, quantity_grams=2.0)
        with_costs = calculate_ime_certificate_spread(
            7_000_000.0,
            5_000_000.0,
            quantity_grams=2.0,
            storage_irr_per_gram_per_day=1_000.0,
            holding_days=10,
            delivery_irr_per_gram=5_000.0,
        )

        assert with_costs["storage_cost_irr"] == pytest.approx(26_533.333333333336)
        assert with_costs["delivery_cost_irr"] == pytest.approx(13_266.666666666666)
        assert with_costs["total_friction_irr"] == pytest.approx(
            base["total_friction_irr"] + 39_800.0
        )
        assert with_costs["buy_melted_sell_cert"]["net_spread_irr"] == pytest.approx(
            base["buy_melted_sell_cert"]["net_spread_irr"] - 39_800.0
        )
        assert with_costs["buy_cert_sell_melted"]["net_spread_irr"] == pytest.approx(
            base["buy_cert_sell_melted"]["net_spread_irr"] - 39_800.0
        )

    def test_flat_market_has_no_arbitrage_after_both_fees(self) -> None:
        flat_cert = 5_000_000.0 * (IME_BULLION_ASSAY / PURITY_18K)
        result = calculate_ime_certificate_spread(flat_cert, 5_000_000.0)

        assert result["buy_melted_sell_cert"]["net_spread_pct"] < 0
        assert result["buy_cert_sell_melted"]["net_spread_pct"] < 0
        assert result["action"] == "NO_ARBITRAGE"
        assert result["is_profitable"] is False

    def test_minimum_spread_threshold_can_suppress_a_profitable_trade(self) -> None:
        suppressed = calculate_ime_certificate_spread(
            7_000_000.0, 5_000_000.0, min_net_spread_pct=6.0
        )
        allowed = calculate_ime_certificate_spread(
            7_000_000.0, 5_000_000.0, min_net_spread_pct=5.0
        )

        assert suppressed["action"] == "NO_ARBITRAGE"
        assert allowed["action"] == "BUY_MELTED_SELL_IME_CERT"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"cert_price_irr": 0.0},
            {"melted_gram18_price_irr": 0.0},
            {"quantity_grams": 0.0},
            {"cert_fee_rate": -0.01},
            {"melted_fee_rate": -0.01},
            {"storage_irr_per_gram_per_day": -1.0},
            {"delivery_irr_per_gram": -1.0},
            {"holding_days": -1},
            {"cert_assay": 0.0},
            {"melted_assay": 0.0},
        ],
    )
    def test_invalid_inputs_raise(self, kwargs) -> None:
        params = {"cert_price_irr": 7_000_000.0, "melted_gram18_price_irr": 5_000_000.0}
        params.update(kwargs)

        with pytest.raises(ValueError):
            calculate_ime_certificate_spread(**params)


class TestImePositionLimitValidator:
    def test_no_configured_limits_is_reported_as_not_configured(self) -> None:
        result = validate_ime_position_limit(
            100.0, position_limit_grams=None, ownership_limit_grams=None
        )

        assert result["ok"] is None
        assert result["status"] == "not_configured"
        assert result["violations"] == []

    def test_within_position_limit(self) -> None:
        result = validate_ime_position_limit(
            400.0,
            current_position_grams=500.0,
            position_limit_grams=1_000.0,
        )

        assert result["ok"] is True
        assert result["status"] == "ok"
        assert result["projected_grams"] == pytest.approx(900.0)
        assert result["position"]["utilization_pct"] == pytest.approx(90.0)

    def test_exact_position_limit_is_allowed(self) -> None:
        result = validate_ime_position_limit(
            500.0,
            current_position_grams=500.0,
            position_limit_grams=1_000.0,
        )

        assert result["ok"] is True
        assert result["position"]["utilization_pct"] == pytest.approx(100.0)

    def test_position_limit_breach(self) -> None:
        result = validate_ime_position_limit(
            501.0,
            current_position_grams=500.0,
            position_limit_grams=1_000.0,
        )

        assert result["ok"] is False
        assert result["status"] == "breach"
        assert result["violations"] == ["position"]

    def test_ownership_limit_boundary_and_breach(self) -> None:
        at_limit = validate_ime_position_limit(
            200.0, ownership_limit_grams=200.0
        )
        over_limit = validate_ime_position_limit(
            201.0, ownership_limit_grams=200.0
        )

        assert at_limit["ok"] is True
        assert over_limit["ok"] is False
        assert over_limit["violations"] == ["ownership"]

    def test_both_limits_report_every_violation(self) -> None:
        result = validate_ime_position_limit(
            500.0,
            position_limit_grams=100.0,
            ownership_limit_grams=200.0,
        )

        assert result["ok"] is False
        assert result["violations"] == ["position", "ownership"]

    @pytest.mark.parametrize("bad_quantity", [0.0, -1.0])
    def test_invalid_quantity_raises(self, bad_quantity) -> None:
        with pytest.raises(ValueError):
            validate_ime_position_limit(bad_quantity, position_limit_grams=100.0)

    def test_negative_current_position_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_ime_position_limit(
                -1.0, current_position_grams=-1.0, position_limit_grams=100.0
            )

    @pytest.mark.parametrize("bad_limit", [0.0, -100.0])
    def test_non_positive_limit_raises(self, bad_limit) -> None:
        with pytest.raises(ValueError):
            validate_ime_position_limit(10.0, position_limit_grams=bad_limit)


class TestAedHawalaSpread:
    def test_hand_computed_spread(self) -> None:
        result = aed_hawala_spread(3_800_000.0, 1_000_000.0)

        assert result["parity_usd_irr"] == pytest.approx(1_000_000.0 * AED_PEG)
        assert result["spread_irr"] == pytest.approx(127_500.0)
        assert result["spread_pct"] == pytest.approx(3.4717494894486043)

    def test_negative_spread_is_preserved(self) -> None:
        result = aed_hawala_spread(3_500_000.0, 1_000_000.0)

        assert result["spread_irr"] == pytest.approx(-172_500.0)
        assert result["spread_pct"] < 0

    @pytest.mark.parametrize(
        "usd_irt,aed_irt", [(0.0, 1_000_000.0), (1_000_000.0, 0.0), (-1.0, 1.0)]
    )
    def test_invalid_inputs_raise(self, usd_irt, aed_irt) -> None:
        with pytest.raises(ValueError):
            aed_hawala_spread(usd_irt, aed_irt)

    def test_alert_fires_above_threshold(self) -> None:
        result = evaluate_aed_hawala_alert([1.0, 2.0, 3.0], 4.0, alert_zscore=2.0)

        assert result["z_score"] == pytest.approx(2.449489742783178)
        assert result["alert"] is True

    def test_alert_does_not_fire_at_mean(self) -> None:
        result = evaluate_aed_hawala_alert([1.0, 2.0, 3.0], 2.0, alert_zscore=2.0)

        assert result["z_score"] == pytest.approx(0.0)
        assert result["alert"] is False

    def test_alert_is_false_without_enough_history_or_variance(self) -> None:
        one_point = evaluate_aed_hawala_alert([1.0], 4.0, alert_zscore=2.0)
        no_variance = evaluate_aed_hawala_alert([2.0, 2.0, 2.0], 4.0, alert_zscore=2.0)

        assert one_point["z_score"] is None
        assert one_point["alert"] is False
        assert no_variance["z_score"] is None
        assert no_variance["alert"] is False

    def test_alert_is_false_when_threshold_is_not_configured(self) -> None:
        result = evaluate_aed_hawala_alert([1.0, 2.0, 3.0], 4.0, alert_zscore=None)

        assert result["alert"] is False
