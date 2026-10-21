"""Unit tests for the derivatives options-chain analytics.

The analyzer is pure: contracts are plain dicts and historical IV is supplied
through the provider seam.  No database or network is used here.
"""

from __future__ import annotations

import math

import pytest

from services.gold.black76_engine import black76_price
from services.gold.options_chain import (
    OptionsChainProvider,
    analyze_options_chain,
    build_options_chain_report,
)

F = 100.0
R = 0.03


def _contract(
    strike: float,
    option_type: str,
    *,
    iv: float = 0.30,
    days: int = 30,
    expiry: str = "2026-11-20",
    volume: float = 100,
    oi: float = 100,
    previous_oi: float | None = None,
    bid: float | None = None,
    ask: float | None = None,
    contract_key: str | None = None,
    **extra,
) -> dict:
    T = days / 365.0
    price = black76_price(F, strike, T, R, iv, option_type)
    row = {
        "contract_key": contract_key or f"{expiry}-{strike:g}-{option_type}",
        "symbol": contract_key or f"{expiry}-{strike:g}-{option_type}",
        "strike": strike,
        "option_type": option_type,
        "market_price": price,
        "days_to_expiry": days,
        "expiry": expiry,
        "volume": volume,
        "open_interest": oi,
    }
    if previous_oi is not None:
        row["previous_open_interest"] = previous_oi
    if bid is not None:
        row["bid"] = bid
    if ask is not None:
        row["ask"] = ask
    row.update(extra)
    return row


def _by_key(report: dict) -> dict[str, dict]:
    return {row["contract_key"]: row for row in report["contracts"]}


class TestOptionChainContractAnalytics:
    def test_iv_is_recovered_per_contract(self):
        chain = [
            _contract(90.0, "call", iv=0.22),
            _contract(100.0, "call", iv=0.30),
            _contract(110.0, "put", iv=0.38),
        ]
        report = analyze_options_chain(
            chain, forward_price=F, risk_free_rate=R, days_to_expiry=30
        )

        assert report["available"] is True
        rows = _by_key(report)
        assert rows["2026-11-20-90-call"]["iv"] == pytest.approx(0.22, rel=1e-6)
        assert rows["2026-11-20-100-call"]["iv"] == pytest.approx(0.30, rel=1e-6)
        assert rows["2026-11-20-110-put"]["iv"] == pytest.approx(0.38, rel=1e-6)

    def test_iv_rank_and_percentile_use_supplied_history(self):
        chain = [_contract(100.0, "call", iv=0.30)]
        report = analyze_options_chain(
            chain,
            forward_price=F,
            risk_free_rate=R,
            days_to_expiry=30,
            iv_history_by_contract={
                "2026-11-20-100-call": [0.20, 0.25, 0.30, 0.40]
            },
        )
        row = report["contracts"][0]

        # rank = (0.30 - 0.20) / (0.40 - 0.20) * 100 = 50
        assert row["iv_rank"] == pytest.approx(50.0)
        # percentile = 3 values <= 0.30 out of 4 = 75
        assert row["iv_percentile"] == pytest.approx(75.0)
        assert row["iv_history_points"] == 4

    def test_iv_rank_is_none_without_enough_history(self):
        report = analyze_options_chain(
            [_contract(100.0, "call", iv=0.30)],
            forward_price=F,
            risk_free_rate=R,
            days_to_expiry=30,
            iv_history_by_contract={"2026-11-20-100-call": [0.30]},
        )
        row = report["contracts"][0]
        assert row["iv_rank"] is None
        assert row["iv_percentile"] == pytest.approx(100.0)
        assert row["iv_history_points"] == 1

    def test_iv_rank_is_none_when_history_has_zero_range(self):
        report = analyze_options_chain(
            [_contract(100.0, "call", iv=0.30)],
            forward_price=F,
            risk_free_rate=R,
            days_to_expiry=30,
            iv_history_by_contract={"2026-11-20-100-call": [0.30, 0.30]},
        )
        assert report["contracts"][0]["iv_rank"] is None
        assert report["contracts"][0]["iv_percentile"] == pytest.approx(100.0)

    def test_skew_uses_nearest_otm_put_minus_nearest_otm_call(self):
        chain = [
            _contract(90.0, "put", iv=0.40),
            _contract(95.0, "put", iv=0.35),
            _contract(100.0, "call", iv=0.25),
            _contract(105.0, "call", iv=0.20),
            _contract(110.0, "call", iv=0.18),
        ]
        report = analyze_options_chain(
            chain, forward_price=F, risk_free_rate=R, days_to_expiry=30
        )
        skew = report["skew_by_expiry"][0]

        assert skew["put_strike"] == pytest.approx(95.0)
        assert skew["call_strike"] == pytest.approx(105.0)
        assert skew["put_iv"] == pytest.approx(0.35, rel=1e-6)
        assert skew["call_iv"] == pytest.approx(0.20, rel=1e-6)
        assert skew["skew"] == pytest.approx(0.15, rel=1e-5)

    def test_iv_term_structure_uses_atm_contract_per_expiry(self):
        chain = [
            _contract(100.0, "call", iv=0.25, days=30, expiry="2026-11-20"),
            _contract(100.0, "call", iv=0.30, days=60, expiry="2026-12-20"),
            _contract(110.0, "call", iv=0.50, days=30, expiry="2026-11-20"),
        ]
        report = analyze_options_chain(
            chain, forward_price=F, risk_free_rate=R, days_to_expiry=30
        )
        term = report["iv_term_structure"]

        assert [point["days_to_expiry"] for point in term] == [30.0, 60.0]
        assert term[0]["atm_strike"] == pytest.approx(100.0)
        assert term[0]["atm_iv"] == pytest.approx(0.25, rel=1e-6)
        assert term[1]["atm_iv"] == pytest.approx(0.30, rel=1e-6)

    def test_oi_change_is_computed_against_previous_snapshot(self):
        report = analyze_options_chain(
            [_contract(100.0, "call", oi=120, previous_oi=100)],
            forward_price=F,
            risk_free_rate=R,
            days_to_expiry=30,
        )
        row = report["contracts"][0]
        assert row["oi_change"] == pytest.approx(20.0)
        assert row["oi_change_pct"] == pytest.approx(20.0)

    def test_oi_change_is_none_when_previous_snapshot_is_missing(self):
        report = analyze_options_chain(
            [_contract(100.0, "call", oi=120)],
            forward_price=F,
            risk_free_rate=R,
            days_to_expiry=30,
        )
        row = report["contracts"][0]
        assert row["oi_change"] is None
        assert row["oi_change_pct"] is None

    def test_liquidity_filter_reports_reasons_without_dropping_rows(self):
        chain = [
            _contract(100.0, "call", volume=5, oi=10, bid=99.0, ask=101.0),
            _contract(105.0, "call", volume=50, oi=100, bid=2.0, ask=2.02),
        ]
        report = analyze_options_chain(
            chain,
            forward_price=F,
            risk_free_rate=R,
            days_to_expiry=30,
            liquidity_thresholds={
                "min_volume": 10,
                "min_open_interest": 20,
                "max_bid_ask_spread_pct": 1.5,
            },
        )
        assert len(report["contracts"]) == 2
        first, second = report["contracts"]
        assert first["is_liquid"] is False
        assert "volume_below_minimum" in first["liquidity_reasons"]
        assert "open_interest_below_minimum" in first["liquidity_reasons"]
        assert "bid_ask_spread_above_maximum" in first["liquidity_reasons"]
        assert second["is_liquid"] is True
        assert second["liquidity_reasons"] == []

    def test_missing_bid_ask_fails_configured_spread_filter(self):
        report = analyze_options_chain(
            [_contract(100.0, "call", volume=50, oi=100)],
            forward_price=F,
            risk_free_rate=R,
            days_to_expiry=30,
            liquidity_thresholds={"max_bid_ask_spread_pct": 2.0},
        )
        row = report["contracts"][0]
        assert row["is_liquid"] is False
        assert "missing_bid_ask" in row["liquidity_reasons"]

    def test_missing_forward_marks_iv_unavailable(self):
        chain = [
            {
                "contract_key": "NO-FORWARD",
                "strike": 100.0,
                "option_type": "call",
                "market_price": 5.0,
                "days_to_expiry": 30,
                "expiry": "2026-11-20",
                "volume": 10,
                "open_interest": 10,
            }
        ]
        report = analyze_options_chain(
            chain, forward_price=None, risk_free_rate=R, days_to_expiry=30
        )
        row = report["contracts"][0]
        assert row["iv"] is None
        assert "forward_price" in row["iv_error"]

    def test_invalid_contract_does_not_abort_the_chain(self):
        chain = [
            {
                "contract_key": "BAD",
                "strike": 0.0,
                "option_type": "call",
                "market_price": 5.0,
                "days_to_expiry": 30,
                "expiry": "2026-11-20",
            },
            _contract(100.0, "call", iv=0.30),
        ]
        report = analyze_options_chain(
            chain, forward_price=F, risk_free_rate=R, days_to_expiry=30
        )
        rows = _by_key(report)
        assert rows["BAD"]["iv"] is None
        assert rows["BAD"]["iv_error"]
        assert rows["2026-11-20-100-call"]["iv"] == pytest.approx(0.30, rel=1e-6)

    def test_empty_chain_is_unavailable(self):
        report = analyze_options_chain(
            [], forward_price=F, risk_free_rate=R, days_to_expiry=30
        )
        assert report["available"] is False
        assert report["contracts"] == []
        assert "no option contracts" in report["reason"]

    def test_put_call_parity_on_live_shaped_chain(self):
        sigma = 0.28
        days = 45
        T = days / 365.0
        chain = []
        for strike in (90.0, 95.0, 100.0, 105.0, 110.0):
            for option_type in ("call", "put"):
                chain.append(
                    _contract(
                        strike,
                        option_type,
                        iv=sigma,
                        days=days,
                        expiry="2026-12-04",
                        volume=25,
                        oi=80,
                        bid=black76_price(F, strike, T, R, sigma, option_type) * 0.99,
                        ask=black76_price(F, strike, T, R, sigma, option_type) * 1.01,
                    )
                )

        report = analyze_options_chain(
            chain, forward_price=F, risk_free_rate=R, days_to_expiry=days
        )
        rows = _by_key(report)
        for strike in (90.0, 95.0, 100.0, 105.0, 110.0):
            call = rows[f"2026-12-04-{strike:g}-call"]
            put = rows[f"2026-12-04-{strike:g}-put"]
            assert call["iv"] == pytest.approx(sigma, rel=1e-6)
            assert put["iv"] == pytest.approx(sigma, rel=1e-6)
            assert call["market_price"] - put["market_price"] == pytest.approx(
                math.exp(-R * T) * (F - strike), abs=1e-9
            )


class FakeProvider(OptionsChainProvider):
    def __init__(self, contracts, *, forward=100.0, histories=None):
        self._contracts = contracts
        self._forward = forward
        self._histories = histories or {}

    async def load_contracts(self, *, commodity=None, limit=500):
        return list(self._contracts)

    async def load_forward_price(self, *, commodity, expiry):
        return self._forward

    async def load_iv_history(self, contract_key, *, limit=60):
        return list(self._histories.get(contract_key, []))

    async def load_previous_open_interest(self, contract_key):
        return None


class TestProviderSeam:
    async def test_build_report_attaches_provider_forward_and_history(self):
        provider = FakeProvider(
            [_contract(100.0, "call", iv=0.30)],
            forward=100.0,
            histories={"2026-11-20-100-call": [0.20, 0.30]},
        )
        report = await build_options_chain_report(
            provider,
            commodity="GOLD",
            risk_free_rate=R,
            liquidity_thresholds=None,
        )

        row = report["contracts"][0]
        assert row["forward_price"] == pytest.approx(100.0)
        assert row["iv"] == pytest.approx(0.30, rel=1e-6)
        assert row["iv_rank"] == pytest.approx(100.0)
        assert report["source"] == "provider"

    async def test_build_report_marks_missing_forward(self):
        provider = FakeProvider([_contract(100.0, "call")], forward=None)
        report = await build_options_chain_report(
            provider, commodity="GOLD", risk_free_rate=R
        )
        row = report["contracts"][0]
        assert row["forward_price"] is None
        assert row["iv"] is None
        assert "forward_price" in row["iv_error"]
