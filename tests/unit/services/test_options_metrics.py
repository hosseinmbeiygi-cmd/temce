"""Unit tests for the options chain matrix: PCR, Max Pain and enrichment.

Contracts are plain dicts:
    {"strike": float, "option_type": "call"|"put", "market_price": float,
     "open_interest": int, "volume": int, "days_to_expiry": int}

Pure functions only — no DB, no network.
"""

from __future__ import annotations

import copy
import math

import pytest

from services.gold.black76_engine import black76_price, calculate_greeks
from services.gold.options_matrix import (
    calculate_max_pain,
    calculate_pcr,
    enrich_options_chain,
)

F = 100.0
R = 0.03


def _contract(
    strike: float,
    option_type: str,
    *,
    market_price: float | None = None,
    oi: float = 0,
    volume: float = 0,
    **extra,
) -> dict:
    contract = {
        "strike": strike,
        "option_type": option_type,
        "open_interest": oi,
        "volume": volume,
    }
    if market_price is not None:
        contract["market_price"] = market_price
    contract.update(extra)
    return contract


class TestPCR:
    def test_basic_ratios(self):
        chain = [
            _contract(100.0, "call", oi=1_000, volume=100),
            _contract(105.0, "call", oi=500, volume=50),
            _contract(100.0, "put", oi=800, volume=150),
            _contract(95.0, "put", oi=200, volume=50),
        ]
        result = calculate_pcr(chain)
        assert result["total_call_volume"] == pytest.approx(150)
        assert result["total_put_volume"] == pytest.approx(200)
        assert result["total_call_oi"] == pytest.approx(1_500)
        assert result["total_put_oi"] == pytest.approx(1_000)
        assert result["pcr_volume"] == pytest.approx(200 / 150)
        assert result["pcr_oi"] == pytest.approx(1_000 / 1_500)
        assert result["contracts"] == 4
        assert result["call_volume_zero"] is False
        assert result["call_oi_zero"] is False

    def test_zero_call_volume_does_not_divide(self):
        result = calculate_pcr(
            [_contract(100.0, "put", oi=10, volume=25), _contract(100.0, "call")]
        )
        assert result["pcr_volume"] is None
        assert result["call_volume_zero"] is True
        assert result["pcr_oi"] is None

    def test_zero_call_oi_does_not_divide(self):
        result = calculate_pcr(
            [
                _contract(100.0, "call", oi=0, volume=10),
                _contract(100.0, "put", oi=50, volume=5),
            ]
        )
        assert result["pcr_oi"] is None
        assert result["call_oi_zero"] is True
        assert result["pcr_volume"] == pytest.approx(0.5)

    def test_all_zero_chain(self):
        result = calculate_pcr([_contract(100.0, "call"), _contract(100.0, "put")])
        assert result["pcr_volume"] is None
        assert result["pcr_oi"] is None
        assert result["total_call_volume"] == pytest.approx(0.0)
        assert result["total_put_volume"] == pytest.approx(0.0)

    def test_missing_volume_and_oi_default_to_zero(self):
        result = calculate_pcr(
            [
                {"strike": 100.0, "option_type": "call"},
                {"strike": 100.0, "option_type": "put"},
            ]
        )
        assert result["total_call_volume"] == pytest.approx(0.0)
        assert result["total_put_oi"] == pytest.approx(0.0)
        assert result["pcr_volume"] is None

    def test_option_type_is_case_insensitive(self):
        result = calculate_pcr(
            [
                _contract(100.0, "CALL", volume=10, oi=10),
                _contract(100.0, "Put", volume=20, oi=5),
            ]
        )
        assert result["pcr_volume"] == pytest.approx(2.0)
        assert result["pcr_oi"] == pytest.approx(0.5)

    def test_empty_chain(self):
        result = calculate_pcr([])
        assert result["contracts"] == 0
        assert result["pcr_volume"] is None
        assert result["pcr_oi"] is None

    def test_unknown_option_type_raises(self):
        with pytest.raises(ValueError, match="option_type"):
            calculate_pcr([_contract(100.0, "straddle", volume=1, oi=1)])

    def test_negative_volume_raises(self):
        with pytest.raises(ValueError):
            calculate_pcr([_contract(100.0, "call", volume=-5)])


class TestMaxPain:
    def test_deterministic_vector_returns_middle_strike(self):
        chain = [
            _contract(90.0, "call", oi=100),
            _contract(100.0, "call", oi=100),
            _contract(110.0, "call", oi=10),
            _contract(90.0, "put", oi=10),
            _contract(100.0, "put", oi=100),
            _contract(110.0, "put", oi=100),
        ]
        assert calculate_max_pain(chain) == pytest.approx(100.0)

    def test_put_open_interest_pulls_max_pain_up(self):
        chain = [
            _contract(90.0, "call", oi=10),
            _contract(100.0, "call", oi=10),
            _contract(110.0, "call", oi=10),
            _contract(110.0, "put", oi=1_000),
        ]
        assert calculate_max_pain(chain) == pytest.approx(110.0)

    def test_call_open_interest_pulls_max_pain_down(self):
        chain = [
            _contract(90.0, "call", oi=1_000),
            _contract(100.0, "call", oi=10),
            _contract(110.0, "put", oi=10),
        ]
        assert calculate_max_pain(chain) == pytest.approx(90.0)

    def test_single_strike_chain_returns_that_strike(self):
        chain = [
            _contract(100.0, "call", oi=10),
            _contract(100.0, "put", oi=10),
        ]
        assert calculate_max_pain(chain) == pytest.approx(100.0)

    def test_ties_break_toward_lowest_strike(self):
        chain = [
            _contract(90.0, "call"),
            _contract(100.0, "call"),
            _contract(110.0, "call"),
        ]
        assert calculate_max_pain(chain) == pytest.approx(90.0)

    def test_uses_only_existing_strike_continuum(self):
        chain = [
            _contract(90.0, "call", oi=5),
            _contract(100.0, "call", oi=5),
            _contract(110.0, "call", oi=5),
            _contract(90.0, "put", oi=5),
            _contract(110.0, "put", oi=5),
        ]
        assert calculate_max_pain(chain) in (90.0, 100.0, 110.0)

    def test_missing_open_interest_is_zero(self):
        chain = [
            {"strike": 100.0, "option_type": "call"},
            {"strike": 100.0, "option_type": "put"},
        ]
        assert calculate_max_pain(chain) == pytest.approx(100.0)

    def test_empty_chain_raises(self):
        with pytest.raises(ValueError, match="empty"):
            calculate_max_pain([])

    @pytest.mark.parametrize("bad_strike", [0.0, -100.0])
    def test_non_positive_strike_raises(self, bad_strike):
        with pytest.raises(ValueError):
            calculate_max_pain([_contract(bad_strike, "call", oi=1)])

    def test_unknown_option_type_raises(self):
        with pytest.raises(ValueError, match="option_type"):
            calculate_max_pain([_contract(100.0, "future", oi=1)])


def _priced_chain(sigma: float, days: int = 30) -> list[dict]:
    T = days / 365.0
    chain = []
    for strike in (90.0, 95.0, 100.0, 105.0, 110.0):
        for option_type in ("call", "put"):
            price = black76_price(F, strike, T, R, sigma, option_type)
            chain.append(
                _contract(
                    strike,
                    option_type,
                    market_price=price,
                    oi=100,
                    volume=10,
                    symbol=f"GOLD-{int(strike)}-{option_type.upper()}",
                )
            )
    return chain


class TestEnrichOptionsChain:
    def test_round_trips_iv_for_every_contract(self):
        sigma = 0.32
        enriched = enrich_options_chain(_priced_chain(sigma), F, R, 30)
        assert len(enriched) == 10
        for row in enriched:
            assert row["iv"] == pytest.approx(sigma, rel=1e-6), row["symbol"]

    def test_adds_required_analytics(self):
        row = enrich_options_chain(_priced_chain(0.3), F, R, 30)[0]
        for key in (
            "iv",
            "delta",
            "gamma",
            "theta",
            "theta_daily",
            "vega",
            "vega_pct",
            "rho",
            "moneyness",
            "time_to_expiry_years",
        ):
            assert key in row
        assert row["time_to_expiry_years"] == pytest.approx(30 / 365.0)
        assert row["moneyness"] == pytest.approx(F / row["strike"])

    def test_greeks_match_black76_engine(self):
        enriched = enrich_options_chain(_priced_chain(0.3), F, R, 90)
        for row in enriched:
            expected = calculate_greeks(
                F, row["strike"], 90 / 365.0, R, row["iv"], row["option_type"]
            )
            for key in ("delta", "gamma", "theta", "vega", "rho"):
                assert row[key] == pytest.approx(expected[key], rel=1e-12)

    def test_does_not_mutate_input(self):
        chain = _priced_chain(0.25)
        snapshot = copy.deepcopy(chain)
        enrich_options_chain(chain, F, R, 30)
        assert chain == snapshot

    def test_preserves_original_fields(self):
        row = enrich_options_chain(_priced_chain(0.25), F, R, 30)[0]
        assert row["symbol"].startswith("GOLD-")
        assert row["open_interest"] == pytest.approx(100)
        assert row["volume"] == pytest.approx(10)

    def test_contract_days_override_parameter(self):
        chain = [_contract(100.0, "call", market_price=5.0, days_to_expiry=60)]
        row = enrich_options_chain(chain, F, R, 30)[0]
        assert row["time_to_expiry_years"] == pytest.approx(60 / 365.0)

    def test_intrinsic_and_itm_flags(self):
        chain = [
            _contract(90.0, "call", market_price=12.0),
            _contract(110.0, "call", market_price=1.0),
            _contract(110.0, "put", market_price=12.0),
            _contract(90.0, "put", market_price=1.0),
        ]
        rows = enrich_options_chain(chain, F, R, 30)
        assert rows[0]["is_itm"] is True  # 100 > 90 call
        assert rows[1]["is_itm"] is False
        assert rows[2]["is_itm"] is True  # 100 < 110 put
        assert rows[3]["is_itm"] is False
        assert rows[0]["intrinsic_value"] == pytest.approx(
            10.0 * math.exp(-R * 30 / 365), rel=1e-9
        )

    def test_price_below_arbitrage_bound_raises(self):
        chain = [_contract(90.0, "call", market_price=1.0)]
        with pytest.raises(ValueError, match="lower arbitrage bound"):
            enrich_options_chain(chain, F, R, 30)

    def test_zero_days_to_expiry_raises(self):
        with pytest.raises(ValueError):
            enrich_options_chain(_priced_chain(0.3), F, R, 0)

    @pytest.mark.parametrize("bad_forward", [0.0, -100.0])
    def test_non_positive_forward_raises(self, bad_forward):
        with pytest.raises(ValueError):
            enrich_options_chain(_priced_chain(0.3), bad_forward, R, 30)

    def test_negative_rate_raises(self):
        with pytest.raises(ValueError):
            enrich_options_chain(_priced_chain(0.3), F, -0.01, 30)

    def test_negative_days_raises(self):
        with pytest.raises(ValueError):
            enrich_options_chain(_priced_chain(0.3), F, R, -1)

    def test_missing_market_price_raises(self):
        with pytest.raises(ValueError, match="market_price"):
            enrich_options_chain([_contract(100.0, "call")], F, R, 30)

    def test_empty_chain_returns_empty_list(self):
        assert enrich_options_chain([], F, R, 30) == []
