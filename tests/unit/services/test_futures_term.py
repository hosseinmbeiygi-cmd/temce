"""Unit tests for futures term structure, basis and implied repo rate.

Formulas under test:

    Basis            = F - S
    Annualized_Basis = (Basis / S) * (365 / Days) * 100
    r_implied        = ln(F / S) / (Days / 365)
    Market state     = CONTANGO if F > S, BACKWARDATION if F < S

Cash-and-carry flag: ``r_implied > benchmark_yield + transaction_frictions_pct``.

Pure math only — no DB, no network.
"""

from __future__ import annotations

import copy
import math
from datetime import date

import pytest

from services.gold.futures_term import (
    DEFAULT_BENCHMARK_YIELD,
    DEFAULT_TRANSACTION_FRICTIONS,
    DEFAULT_TRANSACTION_FRICTIONS_PCT,
    analyze_futures_curve,
)

SPOT = 100.0
BENCHMARK = 0.30


def _contract(days: float, price: float, **extra) -> dict:
    return {"days_to_expiry": days, "price": price, **extra}


def _gold_contract(symbol: str, futures_price: float, days: float) -> dict:
    return {
        "contract_symbol": symbol,
        "futures_price": futures_price,
        "days_to_expiry": days,
    }


def _by_symbol(result: dict) -> dict[str, dict]:
    return {row["contract_symbol"]: row for row in result["contracts"]}


class TestContango:
    def test_multiple_maturities_are_sorted_and_annualized(self):
        contracts = [
            _contract(180, 112.0, symbol="FAR"),
            _contract(30, 102.0, symbol="NEAR"),
            _contract(90, 106.0, symbol="MID"),
        ]
        result = analyze_futures_curve(SPOT, contracts, BENCHMARK)

        assert result["curve_state"] == "contango"
        assert result["state"] == "contango"
        assert result["curve_structure"] == "CONTANGO"
        assert result["is_contango"] is True
        assert result["is_backwardation"] is False
        assert [c["days_to_expiry"] for c in result["contracts"]] == [30, 90, 180]
        assert [c["symbol"] for c in result["contracts"]] == ["NEAR", "MID", "FAR"]
        assert result["front_contract"]["symbol"] == "NEAR"

        assert result["basis"] == pytest.approx(2.0)
        assert result["annualized_basis_pct"] == pytest.approx(
            (2.0 / SPOT) * (365.0 / 30.0) * 100.0
        )
        assert result["implied_repo_rate"] == pytest.approx(
            math.log(102.0 / SPOT) / (30.0 / 365.0)
        )

        for contract, expected_basis in zip(
            result["contracts"], [2.0, 6.0, 12.0], strict=True
        ):
            days = contract["days_to_expiry"]
            assert contract["basis"] == pytest.approx(expected_basis)
            assert contract["basis_pct"] == pytest.approx(expected_basis)
            assert contract["basis_pct_of_spot"] == pytest.approx(expected_basis)
            assert contract["state"] == "contango"
            assert contract["market_state"] == "CONTANGO"
            assert contract["contango"] is True
            assert contract["backwardation"] is False
            assert contract["annualized_basis_pct"] == pytest.approx(
                (expected_basis / SPOT) * (365.0 / days) * 100.0
            )
            assert contract["implied_repo_rate"] == pytest.approx(
                math.log(1.0 + expected_basis / SPOT) / (days / 365.0)
            )

        assert result["max_implied_repo_rate"] >= result["min_implied_repo_rate"]

    def test_term_structure_is_sorted_by_maturity(self):
        result = analyze_futures_curve(
            SPOT,
            [_contract(120, 108.0), _contract(30, 102.0), _contract(60, 104.0)],
            BENCHMARK,
        )
        assert [c["days_to_expiry"] for c in result["term_structure"]] == [30, 60, 120]
        assert result["curve"] == result["term_structure"]

    def test_known_annualized_basis(self):
        # 10% basis over 73 days = (0.10 * 365/73) * 100 = 50%
        result = analyze_futures_curve(100.0, [_contract(73, 110.0)])
        row = result["contracts"][0]
        assert row["annualized_basis_pct"] == pytest.approx(50.0)

    def test_multi_contract_spec_shape(self):
        contracts = [
            _gold_contract("GOLD-30", 105.0, 30),
            _gold_contract("GOLD-90", 110.0, 90),
            _gold_contract("GOLD-180", 120.0, 180),
        ]
        result = analyze_futures_curve(SPOT, contracts)

        assert result["n_contracts"] == 3
        assert result["curve_structure"] == "CONTANGO"
        rows = _by_symbol(result)
        assert set(rows) == {"GOLD-30", "GOLD-90", "GOLD-180"}

        for symbol, multiple, days in (
            ("GOLD-30", 1.05, 30),
            ("GOLD-90", 1.10, 90),
            ("GOLD-180", 1.20, 180),
        ):
            row = rows[symbol]
            assert row["futures_price"] == pytest.approx(SPOT * multiple)
            assert row["days_to_expiry"] == days
            assert row["basis"] == pytest.approx(SPOT * (multiple - 1))
            assert row["annualized_basis_pct"] == pytest.approx(
                (multiple - 1) * (365 / days) * 100, rel=1e-12
            )
            assert row["implied_repo_rate"] == pytest.approx(
                math.log(multiple) / (days / 365), rel=1e-12
            )
            assert row["implied_repo_rate_pct"] == pytest.approx(
                row["implied_repo_rate"] * 100
            )
            assert row["market_state"] == "CONTANGO"

    def test_output_is_sorted_by_maturity(self):
        result = analyze_futures_curve(
            SPOT,
            [
                _gold_contract("F3", 120.0, 180),
                _gold_contract("F1", 105.0, 30),
                _gold_contract("F2", 110.0, 90),
            ],
        )
        assert [row["contract_symbol"] for row in result["contracts"]] == [
            "F1",
            "F2",
            "F3",
        ]


class TestBackwardation:
    def test_backwardation_flags_and_negative_implied_rate(self):
        result = analyze_futures_curve(
            SPOT,
            [_contract(60, 96.0), _contract(120, 92.0)],
            BENCHMARK,
        )
        assert result["curve_state"] == "backwardation"
        assert result["curve_structure"] == "BACKWARDATION"
        assert result["is_backwardation"] is True
        assert result["is_contango"] is False
        for contract in result["contracts"]:
            assert contract["state"] == "backwardation"
            assert contract["market_state"] == "BACKWARDATION"
            assert contract["basis"] < 0
            assert contract["annualized_basis_pct"] < 0
            assert contract["implied_repo_rate"] < 0
            assert contract["arbitrage"] is False
        assert result["arbitrage"] is False
        assert result["arbitrage_opportunities"] == []
        assert result["opportunities"] == []

    def test_inverted_curve_implied_rate_is_negative(self):
        result = analyze_futures_curve(SPOT, [_contract(365, 90.0)], BENCHMARK)
        contract = result["contracts"][0]
        assert contract["implied_repo_rate"] == pytest.approx(math.log(0.9))
        assert contract["implied_repo_rate"] < 0
        assert contract["annualized_basis_pct"] == pytest.approx(-10.0)
        assert result["curve_state"] == "backwardation"
        assert result["arbitrage"] is False

    def test_mixed_curve_reports_mixed_state(self):
        result = analyze_futures_curve(
            SPOT,
            [_contract(30, 102.0), _contract(90, 98.0)],
            BENCHMARK,
        )
        assert result["curve_state"] == "mixed"
        assert result["curve_structure"] == "MIXED"
        assert result["contracts"][0]["state"] == "contango"
        assert result["contracts"][1]["state"] == "backwardation"

    def test_flat_curve_has_zero_basis_and_zero_implied_rate(self):
        result = analyze_futures_curve(SPOT, [_contract(30, SPOT)], BENCHMARK)
        contract = result["contracts"][0]
        assert result["curve_state"] == "flat"
        assert result["curve_structure"] == "FLAT"
        assert contract["market_state"] == "FLAT"
        assert contract["basis"] == 0.0
        assert contract["annualized_basis_pct"] == 0.0
        assert contract["implied_repo_rate"] == 0.0
        assert result["arbitrage"] is False


class TestDefaults:
    def test_default_benchmark_and_frictions(self):
        assert pytest.approx(0.30) == DEFAULT_BENCHMARK_YIELD
        assert pytest.approx(0.01) == DEFAULT_TRANSACTION_FRICTIONS_PCT
        assert pytest.approx(0.01) == DEFAULT_TRANSACTION_FRICTIONS

    def test_threshold_is_benchmark_plus_frictions(self):
        result = analyze_futures_curve(SPOT, [_contract(30, 102.0)])
        assert result["benchmark_yield"] == pytest.approx(0.30)
        assert result["transaction_frictions"] == pytest.approx(0.01)
        assert result["threshold_yield"] == pytest.approx(0.31)
        assert result["threshold_yield_pct"] == pytest.approx(31.0)


class TestArbitrage:
    def test_carry_arbitrage_flagged_above_benchmark_plus_frictions(self):
        result = analyze_futures_curve(
            SPOT,
            [_contract(365, 140.0, symbol="FAR")],
            benchmark_yield=0.30,
            transaction_frictions=0.02,
        )
        contract = result["contracts"][0]
        assert contract["implied_repo_rate"] == pytest.approx(math.log(1.40))
        assert contract["arbitrage"] is True
        assert contract["arbitrage_signal"] == "CARRY_ARBITRAGE_OPPORTUNITY"
        assert contract["arbitrage_excess"] == pytest.approx(math.log(1.40) - 0.32)
        assert result["arbitrage"] is True
        assert result["arbitrage_opportunity"] is True
        assert result["carry_arbitrage"] is True
        assert result["is_carry_arbitrage"] is True
        assert result["best_arbitrage"]["symbol"] == "FAR"
        assert len(result["arbitrage_opportunities"]) == 1
        assert result["opportunities"] == ["FAR"]

    def test_no_arbitrage_below_threshold(self):
        result = analyze_futures_curve(
            SPOT,
            [_contract(365, 130.0)],
            benchmark_yield=0.30,
            transaction_frictions=0.02,
        )
        assert result["contracts"][0]["arbitrage"] is False
        assert result["contracts"][0]["arbitrage_signal"] is None
        assert result["arbitrage"] is False
        assert result["best_arbitrage"] is None
        assert result["opportunities"] == []

    def test_custom_benchmark_changes_the_flag(self):
        contract = [_contract(365, 110.0)]
        strict = analyze_futures_curve(SPOT, contract)
        loose = analyze_futures_curve(SPOT, contract, benchmark_yield=0.05)
        assert strict["contracts"][0]["arbitrage"] is False
        assert loose["threshold_yield"] == pytest.approx(0.06)
        assert loose["contracts"][0]["arbitrage"] is True

    def test_custom_frictions_change_the_flag(self):
        contract = [_contract(365, 110.0)]
        wide = analyze_futures_curve(
            SPOT,
            contract,
            benchmark_yield=0.05,
            transaction_frictions_pct=0.06,
        )
        assert wide["threshold_yield"] == pytest.approx(0.11)
        assert wide["contracts"][0]["arbitrage"] is False

    def test_benchmark_accepts_percentage_input(self):
        decimal = analyze_futures_curve(SPOT, [_contract(365, 140.0)], 0.30, 0.02)
        percent = analyze_futures_curve(SPOT, [_contract(365, 140.0)], 30.0, 2.0)
        assert percent["benchmark_yield"] == pytest.approx(decimal["benchmark_yield"])
        assert percent["transaction_frictions"] == pytest.approx(
            decimal["transaction_frictions"]
        )
        assert percent["arbitrage"] is True
        assert decimal["arbitrage"] is True

    def test_contract_friction_override(self):
        result = analyze_futures_curve(
            SPOT,
            [_contract(365, 135.0, transaction_frictions=0.0)],
            benchmark_yield=0.30,
            transaction_frictions=0.02,
        )
        contract = result["contracts"][0]
        assert contract["transaction_frictions"] == 0.0
        assert contract["arbitrage"] is True

    def test_default_frictions_are_applied(self):
        result = analyze_futures_curve(SPOT, [_contract(365, 135.0)], 0.30)
        assert result["transaction_frictions"] == pytest.approx(
            DEFAULT_TRANSACTION_FRICTIONS
        )
        assert result["contracts"][0]["arbitrage"] is False

    def test_multiple_opportunities_are_all_listed(self):
        result = analyze_futures_curve(
            SPOT,
            [
                _gold_contract("F1", 140.0, 365),
                _gold_contract("F2", 110.0, 365),
                _gold_contract("F3", 160.0, 365),
            ],
        )
        assert result["opportunities"] == ["F1", "F3"]
        assert [row["carry_arbitrage"] for row in result["contracts"]] == [
            True,
            False,
            True,
        ]


class TestEdgeCases:
    @pytest.mark.parametrize("days", [0, -5])
    def test_expiry_non_positive_returns_no_annualized_metrics(self, days):
        result = analyze_futures_curve(SPOT, [_contract(days, 102.0)], BENCHMARK)
        contract = result["contracts"][0]
        assert contract["is_expired"] is True
        assert contract["term_metrics_available"] is False
        assert contract["annualized_basis"] is None
        assert contract["annualized_basis_pct"] is None
        assert contract["implied_repo_rate"] is None
        assert contract["implied_repo_rate_pct"] is None
        assert contract["arbitrage"] is False
        assert contract["basis"] == pytest.approx(2.0)
        assert result["arbitrage"] is False
        assert result["implied_repo_rate"] is None
        assert result["annualized_basis_pct"] is None

    def test_non_integer_days_are_annualized(self):
        result = analyze_futures_curve(SPOT, [_gold_contract("F1", 105.0, 30.5)])
        row = result["contracts"][0]
        assert row["days_to_expiry"] == pytest.approx(30.5)
        assert row["annualized_basis_pct"] == pytest.approx(
            (5.0 / SPOT) * (365 / 30.5) * 100
        )

    def test_empty_contracts_returns_unavailable_curve(self):
        result = analyze_futures_curve(SPOT, [], BENCHMARK)
        assert result["curve_state"] == "unavailable"
        assert result["curve_structure"] == "NO_DATA"
        assert result["contracts"] == []
        assert result["n_contracts"] == 0
        assert result["front_contract"] is None
        assert result["implied_repo_rate"] is None
        assert result["arbitrage"] is False
        assert result["is_carry_arbitrage"] is False
        assert result["opportunities"] == []

    def test_invalid_contract_is_reported_without_breaking_curve(self):
        result = analyze_futures_curve(
            SPOT,
            [_contract(30, 102.0), {"symbol": "BAD", "days_to_expiry": 30}],
            BENCHMARK,
        )
        assert result["curve_state"] == "contango"
        bad = next(c for c in result["contracts"] if c["symbol"] == "BAD")
        assert bad["valid"] is False
        assert bad["futures_price"] is None
        assert bad["error"]

    @pytest.mark.parametrize("bad_price", [0.0, -100.0])
    def test_non_positive_futures_price_is_reported(self, bad_price):
        result = analyze_futures_curve(SPOT, [_gold_contract("BAD", bad_price, 30)])
        row = result["contracts"][0]
        assert row["valid"] is False
        assert "positive" in row["error"]
        assert result["curve_structure"] == "UNAVAILABLE"
        assert result["is_carry_arbitrage"] is False
        assert result["opportunities"] == []

    def test_missing_symbol_falls_back_to_positional_name(self):
        result = analyze_futures_curve(
            SPOT, [{"futures_price": 105.0, "days_to_expiry": 30}]
        )
        row = result["contracts"][0]
        assert row["contract_symbol"] == "contract_1"
        assert row["symbol"] == "contract_1"

    def test_blank_symbol_falls_back_to_positional_name(self):
        result = analyze_futures_curve(SPOT, [_gold_contract("   ", 105.0, 30)])
        assert result["contracts"][0]["contract_symbol"] == "contract_1"

    @pytest.mark.parametrize("spot", [0.0, -1.0, float("nan"), float("inf")])
    def test_invalid_spot_raises(self, spot):
        with pytest.raises(ValueError):
            analyze_futures_curve(spot, [], BENCHMARK)

    @pytest.mark.parametrize("bad_benchmark", [float("nan"), float("inf")])
    def test_non_finite_benchmark_raises(self, bad_benchmark):
        with pytest.raises(ValueError):
            analyze_futures_curve(SPOT, [], bad_benchmark)

    def test_negative_frictions_raise(self):
        with pytest.raises(ValueError):
            analyze_futures_curve(
                SPOT, [_contract(30, 102.0)], transaction_frictions_pct=-0.01
            )

    def test_inputs_are_not_mutated(self):
        contracts = [_contract(30, 102.0, symbol="NEAR")]
        snapshot = copy.deepcopy(contracts)
        analyze_futures_curve(SPOT, contracts, BENCHMARK)
        assert contracts == snapshot


class TestContractAliases:
    def test_expiry_date_is_converted_using_as_of(self):
        result = analyze_futures_curve(
            SPOT,
            [{"expiry": "2026-01-31", "futures_price": 102.0, "symbol": "JAN"}],
            BENCHMARK,
            as_of=date(2026, 1, 1),
        )
        contract = result["contracts"][0]
        assert contract["days_to_expiry"] == 30
        assert contract["expiry"] == "2026-01-31"
        assert result["as_of"] == "2026-01-01"

    def test_common_field_aliases(self):
        result = analyze_futures_curve(
            SPOT,
            [
                {
                    "maturity_date": date(2026, 1, 31),
                    "settlement_price": 102.0,
                    "contract_symbol": "JAN",
                }
            ],
            "30%",
            as_of=date(2026, 1, 1),
        )
        contract = result["contracts"][0]
        assert contract["symbol"] == "JAN"
        assert contract["futures_price"] == 102.0
        assert contract["days_to_expiry"] == 30
        assert result["benchmark_yield"] == pytest.approx(0.30)
