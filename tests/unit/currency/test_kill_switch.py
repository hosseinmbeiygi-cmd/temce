"""Kill-switch rule coverage. Five independent rules."""

from __future__ import annotations

from apps.currency_service.domain.entities import MarketSummary
from apps.currency_service.domain.kill_switch import check_kill_switch


def _mkt(**overrides) -> MarketSummary:
    base = dict(
        free_market_usd=615_000,
        official_cbi_usd=315_000,
        nima_usd=345_000,
        usdt_irt=620_000,
        bubble_index=95.24,
        daily_volatility=1.2,
        bid_ask_spread=0.65,
        tether_arbitrage=0.81,
        sentiment="NEUTRAL",
    )
    base.update(overrides)
    return MarketSummary(**base)


class TestKillSwitchInactive:
    def test_stable_market(self) -> None:
        ks = check_kill_switch(_mkt())
        assert ks.active is False
        assert ks.reasons == []
        assert ks.action is None


class TestKillSwitchRules:
    def test_rule_volatility(self) -> None:
        ks = check_kill_switch(_mkt(daily_volatility=-6.0))
        assert ks.active is True
        assert any("Daily volatility" in r for r in ks.reasons)
        assert ks.action == "AVOID_NEW_POSITIONS"

    def test_rule_bubble(self) -> None:
        ks = check_kill_switch(_mkt(bubble_index=160.0))
        assert ks.active is True
        assert any("bubble exceeds 150" in r for r in ks.reasons)

    def test_rule_spread(self) -> None:
        ks = check_kill_switch(_mkt(bid_ask_spread=3.5))
        assert ks.active is True
        assert any("Liquidity crisis" in r for r in ks.reasons)

    def test_rule_tether_positive(self) -> None:
        ks = check_kill_switch(_mkt(tether_arbitrage=6.0))
        assert ks.active is True
        assert any("USDT deviation" in r for r in ks.reasons)

    def test_rule_tether_negative(self) -> None:
        ks = check_kill_switch(_mkt(tether_arbitrage=-5.5))
        assert ks.active is True
        assert any("USDT deviation" in r for r in ks.reasons)

    def test_rule_hourly(self) -> None:
        ks = check_kill_switch(_mkt(), hourly_change_pct=-2.5)
        assert ks.active is True
        assert any("Hourly shock" in r for r in ks.reasons)

    def test_multiple_reasons(self) -> None:
        ks = check_kill_switch(
            _mkt(daily_volatility=-7.0, bubble_index=200.0),
            hourly_change_pct=3.0,
        )
        assert ks.active is True
        assert len(ks.reasons) == 3

    def test_boundary_exactly_at_limit_does_not_fire(self) -> None:
        # spec uses strict >, so exactly 5.0 must NOT trigger.
        ks = check_kill_switch(_mkt(daily_volatility=5.0))
        assert ks.active is False
