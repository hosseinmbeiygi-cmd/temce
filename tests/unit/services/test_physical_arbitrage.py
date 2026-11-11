"""Unit tests for the physical gold, assay and coin-bubble engine.

Formulas under test (Iranian retail gold market conventions):

  * 1 mesghal = 4.6083 g of 17-karat (705) gold
  * gram18 = mesghal_17k_price / 4.6083 * (750 / 705)
  * real 18k weight = weight * (assay / 750)
  * coin intrinsic = ounce_usd * usd_irr * (net_weight / 31.1034768) * (900 / 999.9)
  * bubble = (market - intrinsic) / intrinsic * 100
  * IME certificate vs Tehran melted: 995 assay adjustment and 0.0015 fee per leg

Single source of truth: services/gold/constants.py
Physical arbitrage and pricer share coin specs via services.gold.constants.

Pure functions only — no DB, no network.
"""

from __future__ import annotations

import pytest

from services.gold.constants import (
    MESGHAL_GRAMS,
    PURITY_17K,
    PURITY_18K,
    TROY_OUNCE_GRAMS,
)
from services.gold.constants import (
    PURITY_COIN as COIN_ASSAY,
)
from services.gold.constants import (
    PURITY_FINE as FINE_GOLD,
)
from services.gold.physical_arbitrage import (
    GERAMI_MINTING_FEE_IRR,
    IME_BULLION_ASSAY,
    IME_EXCHANGE_FEE,
    adjust_melted_by_assay,
    calculate_coin_bubbles,
    calculate_gram18_from_mesghal,
    calculate_ime_vs_melted_arbitrage,
)

OUNCE_USD = 2_000.0
USD_IRR = 1_000_000.0

# Reference intrinsic values for OUNCE_USD / USD_IRR (independent arithmetic).
# STEP 6-FIX-2 unified the IR_COIN_EMAMI mint fee at 80,000 IRR (the
# same physical full-coin cost as bahar) and calculate_coin_bubbles
# folds that fee into intrinsic_value_irr.  EMAMI_INTRINSIC stays the
# gold-only component; the fee-inclusive value adds EMAMI_MINTING_FEE_IRR.
# Gate: tests/unit/test_step6_fix2.py::test_emami_mint_fee_unified.
EMAMI_MINTING_FEE_IRR = 80_000.0
EMAMI_INTRINSIC = 470_714_710.7878512
EMAMI_INTRINSIC_WITH_FEE = EMAMI_INTRINSIC + EMAMI_MINTING_FEE_IRR
HALF_INTRINSIC = 235_328_416.82815728
QUARTER_INTRINSIC = 117_664_208.41407864
GERAMI_GOLD_VALUE = 58_455_902.85205087


def _intrinsic(weight_grams: float, purity: float = COIN_ASSAY) -> float:
    return (
        OUNCE_USD
        * USD_IRR
        * (weight_grams / TROY_OUNCE_GRAMS)
        * (purity / FINE_GOLD)
    )


class TestGram18FromMesghal:
    def test_one_mesghal_price_equals_weight_times_gram17(self):
        # 4.6083 g of 17k costs exactly one mesghal price, so the per-gram
        # 17k price is 1 and only the 705 -> 750 uplift remains.
        assert calculate_gram18_from_mesghal(MESGHAL_GRAMS) == pytest.approx(
            PURITY_18K / PURITY_17K
        )

    def test_known_value_for_one_million_rial(self):
        assert calculate_gram18_from_mesghal(1_000_000.0) == pytest.approx(
            230_850.80989389637, rel=1e-9
        )

    def test_matches_traditional_formula(self):
        price = 87_500_000.0
        expected = price / MESGHAL_GRAMS * (PURITY_18K / PURITY_17K)
        assert calculate_gram18_from_mesghal(price) == pytest.approx(expected, rel=1e-12)

    def test_is_linear_in_mesghal_price(self):
        base = calculate_gram18_from_mesghal(50_000_000.0)
        assert calculate_gram18_from_mesghal(100_000_000.0) == pytest.approx(2 * base)

    @pytest.mark.parametrize("bad", [0.0, -1.0])
    def test_non_positive_price_raises(self, bad):
        with pytest.raises(ValueError):
            calculate_gram18_from_mesghal(bad)


class TestAdjustMeltedByAssay:
    def test_assay_750_is_identity(self):
        result = adjust_melted_by_assay(10.0, 750, 5_000_000.0)
        assert result["real_weight_gram18"] == pytest.approx(10.0)
        assert result["value_irr"] == pytest.approx(50_000_000.0)

    def test_assay_705_downweights(self):
        result = adjust_melted_by_assay(10.0, 705, 5_000_000.0)
        assert result["real_weight_gram18"] == pytest.approx(10.0 * 705 / 750)
        assert result["real_weight_gram18"] == pytest.approx(9.4)

    def test_assay_900_upweights(self):
        result = adjust_melted_by_assay(10.0, 900, 5_000_000.0)
        assert result["real_weight_gram18"] == pytest.approx(12.0)

    def test_value_uses_real_weight(self):
        result = adjust_melted_by_assay(7.5, 900, 4_000_000.0)
        assert result["value_irr"] == pytest.approx(7.5 * (900 / 750) * 4_000_000.0)

    def test_zero_weight_is_allowed_and_zero_valued(self):
        result = adjust_melted_by_assay(0.0, 750, 5_000_000.0)
        assert result["real_weight_gram18"] == pytest.approx(0.0)
        assert result["value_irr"] == pytest.approx(0.0)

    def test_returns_input_metadata(self):
        result = adjust_melted_by_assay(3.0, 705, 1_000_000.0)
        assert result["weight_grams"] == pytest.approx(3.0)
        assert result["assay"] == 705
        assert result["base_gram18_price_irr"] == pytest.approx(1_000_000.0)

    def test_negative_weight_raises(self):
        with pytest.raises(ValueError):
            adjust_melted_by_assay(-1.0, 750, 5_000_000.0)

    @pytest.mark.parametrize("bad_assay", [0, -750])
    def test_non_positive_assay_raises(self, bad_assay):
        with pytest.raises(ValueError):
            adjust_melted_by_assay(10.0, bad_assay, 5_000_000.0)

    @pytest.mark.parametrize("bad_price", [0.0, -1.0])
    def test_non_positive_price_raises(self, bad_price):
        with pytest.raises(ValueError):
            adjust_melted_by_assay(10.0, 750, bad_price)


class TestCalculateCoinBubbles:
    def _bubbles(self, prices: dict[str, float], **kwargs) -> dict:
        return calculate_coin_bubbles(OUNCE_USD, USD_IRR, prices, **kwargs)

    def test_returns_all_four_traded_denominations(self):
        result = self._bubbles(
            {
                "emami": 500_000_000.0,
                "half": 250_000_000.0,
                "quarter": 125_000_000.0,
                "gerami": 60_000_000.0,
            }
        )
        assert set(result) == {"emami", "half", "quarter", "gerami"}

    def test_emami_intrinsic_matches_ounce_formula(self):
        result = self._bubbles({"emami": 500_000_000.0})
        # intrinsic includes the unified 80,000 IRR mint fee; the gold-only
        # component is unchanged (STEP 6-FIX-2).
        assert result["emami"]["intrinsic_value_irr"] == pytest.approx(
            EMAMI_INTRINSIC_WITH_FEE, rel=1e-9
        )
        assert result["emami"]["gold_value_irr"] == pytest.approx(
            EMAMI_INTRINSIC, rel=1e-9
        )

    def test_half_and_quarter_scale_from_emami(self):
        result = self._bubbles(
            {
                "emami": 500_000_000.0,
                "half": 250_000_000.0,
                "quarter": 125_000_000.0,
            }
        )
        assert result["half"]["intrinsic_value_irr"] == pytest.approx(
            HALF_INTRINSIC + 50_000.0, rel=1e-9
        )
        assert result["quarter"]["intrinsic_value_irr"] == pytest.approx(
            QUARTER_INTRINSIC + 35_000.0, rel=1e-9
        )
        assert result["half"]["intrinsic_value_irr"] == pytest.approx(
            result["emami"]["gold_value_irr"] * (4.066 / 8.133) + 50_000.0
        )
        assert result["quarter"]["intrinsic_value_irr"] == pytest.approx(
            result["emami"]["gold_value_irr"] * (2.033 / 8.133) + 35_000.0
        )

    def test_coin_metadata_matches_spec(self):
        result = self._bubbles(
            {"emami": 1.0, "half": 1.0, "quarter": 1.0, "gerami": 1.0}
        )
        # Updated to match standardized coin specs (single source of truth)
        assert result["emami"]["weight_grams"] == pytest.approx(8.133)
        assert result["half"]["weight_grams"] == pytest.approx(4.066)
        assert result["quarter"]["weight_grams"] == pytest.approx(2.033)
        assert result["gerami"]["weight_grams"] == pytest.approx(1.010)
        for coin in result.values():
            assert coin["purity"] == pytest.approx(0.900)

    def test_gerami_includes_minting_fee_in_intrinsic(self):
        result = self._bubbles({"gerami": 60_000_000.0})
        gerami = result["gerami"]
        assert gerami["minting_fee_irr"] == pytest.approx(GERAMI_MINTING_FEE_IRR)
        assert gerami["gold_value_irr"] == pytest.approx(GERAMI_GOLD_VALUE, rel=1e-9)
        assert gerami["intrinsic_value_irr"] == pytest.approx(
            GERAMI_GOLD_VALUE + GERAMI_MINTING_FEE_IRR, rel=1e-9
        )

    def test_gerami_minting_fee_can_be_overridden(self):
        result = self._bubbles({"gerami": 60_000_000.0}, gerami_minting_fee_irr=0.0)
        assert result["gerami"]["intrinsic_value_irr"] == pytest.approx(
            GERAMI_GOLD_VALUE, rel=1e-9
        )

    def test_emami_includes_unified_minting_fee(self):
        """STEP 6-FIX-2: emami carries the same 80,000 IRR fee as bahar.

        Emami and bahar are the same 8.133 g / 900-oz coin; previously
        emami was modelled fee-free while bahar carried 80,000 IRR.  Both
        now read services.gold.constants.COIN_MINTING_COSTS.
        """
        result = self._bubbles({"emami": 500_000_000.0})
        assert result["emami"]["minting_fee_irr"] == pytest.approx(
            EMAMI_MINTING_FEE_IRR
        )
        assert result["emami"]["intrinsic_value_irr"] == pytest.approx(
            result["emami"]["gold_value_irr"] + EMAMI_MINTING_FEE_IRR
        )

    def test_zero_bubble_when_market_equals_intrinsic(self):
        prices = {
            "emami": EMAMI_INTRINSIC_WITH_FEE,
            "half": HALF_INTRINSIC + 50_000.0,
            "quarter": QUARTER_INTRINSIC + 35_000.0,
            "gerami": GERAMI_GOLD_VALUE + GERAMI_MINTING_FEE_IRR,
        }
        result = self._bubbles(prices)
        for coin, row in result.items():
            assert row["bubble_pct"] == pytest.approx(0.0, abs=1e-9), coin
            assert row["is_discount"] is False

    def test_positive_bubble_is_percentage_over_intrinsic(self):
        result = self._bubbles({"emami": EMAMI_INTRINSIC_WITH_FEE * 1.5})
        assert result["emami"]["bubble_pct"] == pytest.approx(50.0)
        assert result["emami"]["is_discount"] is False

    def test_negative_bubble_marks_discount(self):
        result = self._bubbles({"emami": EMAMI_INTRINSIC_WITH_FEE * 0.8})
        assert result["emami"]["bubble_pct"] == pytest.approx(-20.0)
        assert result["emami"]["is_discount"] is True

    def test_market_price_is_echoed(self):
        result = self._bubbles({"emami": 123_456_789.0})
        assert result["emami"]["market_price_irr"] == pytest.approx(123_456_789.0)

    def test_missing_denominations_are_skipped(self):
        result = self._bubbles({"emami": 500_000_000.0})
        assert set(result) == {"emami"}

    def test_symbol_aliases_are_normalised(self):
        result = self._bubbles(
            {
                "IR_COIN_EMAMI": EMAMI_INTRINSIC_WITH_FEE,
                "coin_half": HALF_INTRINSIC + 50_000.0,
                "bahar": EMAMI_INTRINSIC_WITH_FEE,
                "IR_COIN_QUARTER": QUARTER_INTRINSIC + 35_000.0,
            }
        )
        assert set(result) == {"emami", "bahar", "half", "quarter"}
        assert result["emami"]["bubble_pct"] == pytest.approx(0.0, abs=1e-9)
        assert result["bahar"]["bubble_pct"] == pytest.approx(0.0, abs=1e-9)
        assert result["half"]["bubble_pct"] == pytest.approx(0.0, abs=1e-9)
        assert result["quarter"]["bubble_pct"] == pytest.approx(0.0, abs=1e-9)

    def test_unknown_symbols_are_ignored(self):
        result = self._bubbles({"silver_gram": 1_000_000.0})
        assert result == {}

    def test_empty_price_map_returns_empty_dict(self):
        assert self._bubbles({}) == {}

    @pytest.mark.parametrize("bad_price", [0.0, -1.0])
    def test_non_positive_market_price_raises(self, bad_price):
        with pytest.raises(ValueError):
            self._bubbles({"emami": bad_price})

    @pytest.mark.parametrize("bad_ounce,bad_usd", [(0.0, USD_IRR), (-1.0, USD_IRR),
                                                  (OUNCE_USD, 0.0), (OUNCE_USD, -1.0)])
    def test_non_positive_ounce_or_fx_raises(self, bad_ounce, bad_usd):
        with pytest.raises(ValueError):
            calculate_coin_bubbles(bad_ounce, bad_usd, {"emami": 500_000_000.0})


class TestCoinSpecConsistency:
    """Ensure pricer and physical_arbitrage agree on intrinsic for every coin.

    Both modules now import from the same services.gold.constants, so they
    must compute the same intrinsic for identical inputs.
    """

    OUNCE_USD = 2_000.0
    USD_IRR = 1_000_000.0

    def _pricer_intrinsic(self, symbol: str) -> float:
        from src.gold_desk.pricer import fair_coin
        return fair_coin(symbol, self.OUNCE_USD, self.USD_IRR)

    def _arbitrage_intrinsic(self, coin_key: str, price: float) -> float:
        from services.gold.physical_arbitrage import calculate_coin_bubbles
        bubble = calculate_coin_bubbles(
            self.OUNCE_USD, self.USD_IRR, {coin_key: price}
        )
        # Pick the first (and only) coin from the bubble result
        for coin_name in bubble:
            return bubble[coin_name]["intrinsic_value_irr"]
        return 0.0

    @pytest.mark.parametrize(
        "symbol, arb_input, expected",
        [
            ("IR_COIN_EMAMI", "emami", 470714710.7878512 + 80000.0),
            ("IR_COIN_BAHAR", "bahar", 470714710.7878512 + 80000.0),
            ("IR_COIN_HALF", "half", 235328416.82815728 + 50000.0),
            ("IR_COIN_QUARTER", "quarter", 117664208.41407864 + 35000.0),
            ("IR_COIN_1G", "1g", 58470902.85205087),
            ("IR_COIN_GERAMI", "gerami", 58470902.85205087),
        ],
    )
    def test_intrinsic_matches_between_pricer_and_arbitrage(self, symbol, arb_input, expected):
        # Both modules MUST import from services.gold.constants (single source of truth).
        from services.gold.physical_arbitrage import calculate_coin_bubbles
        arb_result = calculate_coin_bubbles(
            self.OUNCE_USD, self.USD_IRR, {arb_input: 1.0}
        )
        # arb_input aliases to a canonical key in the result
        # e.g. '1g' -> 'gerami'; 'bahar' is its own canonical key because its
        # mint fee differs from emami even though the coin weight is equal.
        canonical_key = arb_input
        if arb_input == '1g':
            canonical_key = 'gerami'
        arb_intrinsic = arb_result[canonical_key]["intrinsic_value_irr"]

        # Compute via pricer
        from src.gold_desk.pricer import fair_coin
        pricer_intrinsic = fair_coin(symbol, self.OUNCE_USD, self.USD_IRR)

        # Both must match their expected values
        assert arb_intrinsic == pytest.approx(expected, rel=1e-9)
        assert pricer_intrinsic == pytest.approx(expected, rel=1e-9)
        assert pricer_intrinsic == pytest.approx(arb_intrinsic, rel=1e-9)



class TestCalculateImeVsMeltedArbitrage:
    MELTED_18K = 5_000_000.0  # IRR per gram of 750 gold in Tehran
    MELTED_995 = MELTED_18K * (IME_BULLION_ASSAY / PURITY_18K)

    def test_assay_adjustment_uses_995_over_750(self):
        result = calculate_ime_vs_melted_arbitrage(self.MELTED_995, self.MELTED_18K)
        assert IME_BULLION_ASSAY == 995
        assert result["melted_equivalent_fine_irr"] == pytest.approx(
            6_633_333.333333333
        )
        assert result["assay_factor"] == pytest.approx(995 / 750)

    def test_flat_market_has_no_gross_spread(self):
        result = calculate_ime_vs_melted_arbitrage(self.MELTED_995, self.MELTED_18K)
        assert result["gross_spread_pct"] == pytest.approx(0.0, abs=1e-9)
        assert result["action"] == "NO_ARBITRAGE"
        assert result["is_profitable"] is False

    def test_fees_are_charged_on_both_legs(self):
        assert pytest.approx(0.0015) == IME_EXCHANGE_FEE
        result = calculate_ime_vs_melted_arbitrage(self.MELTED_995, self.MELTED_18K)
        assert result["fee_pct"] == pytest.approx(0.15)
        assert result["total_fee_pct"] == pytest.approx(0.30)
        # Selling the certificate and buying the melted leg costs ~0.30%.
        assert result["net_spread_pct"] == pytest.approx(-0.299550674013, rel=1e-6)
        assert result["net_spread_pct"] < result["gross_spread_pct"]

    def test_certificate_at_premium_buys_melted_and_sells_cert(self):
        cert = self.MELTED_995 * 1.10
        result = calculate_ime_vs_melted_arbitrage(cert, self.MELTED_18K)
        assert result["gross_spread_pct"] == pytest.approx(10.0, rel=1e-9)
        assert result["net_spread_pct"] < result["gross_spread_pct"]
        assert result["net_spread_pct"] > 0
        assert result["action"] == "BUY_MELTED_SELL_IME_CERT"
        assert result["is_profitable"] is True
        assert "شمش" in result["strategy"]

    def test_certificate_at_discount_reverses_the_trade(self):
        cert = self.MELTED_995 * 0.90
        result = calculate_ime_vs_melted_arbitrage(cert, self.MELTED_18K)
        assert result["gross_spread_pct"] == pytest.approx(-10.0, rel=1e-9)
        assert result["net_spread_pct"] < 0
        assert result["action"] == "BUY_IME_CERT_SELL_MELTED"
        assert result["is_profitable"] is True

    def test_small_premium_is_eaten_by_fees(self):
        # 0.5% premium < ~0.30% round-trip fee + 1% margin? It stays below the
        # execution threshold, so no trade is recommended even though gross > 0.
        cert = self.MELTED_995 * 1.005
        result = calculate_ime_vs_melted_arbitrage(cert, self.MELTED_18K)
        assert result["gross_spread_pct"] == pytest.approx(0.5, rel=1e-9)
        assert result["action"] == "NO_ARBITRAGE"
        assert result["is_profitable"] is False

    def test_net_spread_matches_fee_arithmetic(self):
        cert = 7_000_000.0
        result = calculate_ime_vs_melted_arbitrage(cert, self.MELTED_18K)
        sell_cert = cert * (1 - IME_EXCHANGE_FEE)
        buy_melted = self.MELTED_995 * (1 + IME_EXCHANGE_FEE)
        expected = (sell_cert - buy_melted) / buy_melted * 100
        assert result["net_spread_pct"] == pytest.approx(expected, rel=1e-12)

    def test_inputs_are_echoed(self):
        result = calculate_ime_vs_melted_arbitrage(7_000_000.0, self.MELTED_18K)
        assert result["ime_cert_price_irr"] == pytest.approx(7_000_000.0)
        assert result["melted_gram18_price_irr"] == pytest.approx(self.MELTED_18K)

    @pytest.mark.parametrize(
        "cert,melted",
        [
            (0.0, MELTED_18K),
            (-1.0, MELTED_18K),
            (MELTED_995, 0.0),
            (MELTED_995, -1.0),
            (0.0, 0.0),
        ],
    )
    def test_non_positive_inputs_raise(self, cert, melted):
        with pytest.raises(ValueError):
            calculate_ime_vs_melted_arbitrage(cert, melted)
