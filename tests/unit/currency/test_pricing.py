"""Pure pricing math — verifies the spec examples verbatim."""

from __future__ import annotations

import pytest

from apps.currency_service.domain.pricing import (
    arbitrage_status_for,
    bubble_index,
    classify_sentiment,
    daily_volatility_pct,
    position_pnl_toman,
    simple_return_pct,
    spread_pct,
    tether_arbitrage_pct,
)


class TestBubbleIndex:
    def test_spec_example(self) -> None:
        # ((615000 - 315000) / 315000) * 100 = 95.238095...
        assert bubble_index(615_000, 315_000) == pytest.approx(95.23809523809524)

    def test_zero_premium(self) -> None:
        assert bubble_index(315_000, 315_000) == 0.0

    def test_negative_when_below_official(self) -> None:
        assert bubble_index(300_000, 315_000) == pytest.approx(-4.7619047619)

    def test_zero_official_raises(self) -> None:
        with pytest.raises(ValueError, match="official_cbi_usd"):
            bubble_index(615_000, 0)


class TestTetherArbitrage:
    def test_spec_example(self) -> None:
        # ((620000 - 615000) / 615000) * 100 = +0.813008...
        assert tether_arbitrage_pct(620_000, 615_000) == pytest.approx(0.8130081300813008)

    def test_negative(self) -> None:
        assert tether_arbitrage_pct(610_000, 615_000) == pytest.approx(-0.8130081300813008)

    def test_zero_free_raises(self) -> None:
        with pytest.raises(ValueError, match="free_market_usd"):
            tether_arbitrage_pct(620_000, 0)


class TestSpread:
    def test_basic(self) -> None:
        assert spread_pct(617_000, 615_000) == pytest.approx(0.32414910859)

    def test_zero_spread(self) -> None:
        assert spread_pct(615_000, 615_000) == 0.0


class TestDailyVolatility:
    def test_positive(self) -> None:
        assert daily_volatility_pct(615_000, 600_000) == pytest.approx(2.5)

    def test_negative(self) -> None:
        assert daily_volatility_pct(585_000, 600_000) == pytest.approx(-2.5)

    def test_zero_change(self) -> None:
        assert daily_volatility_pct(600_000, 600_000) == 0.0


class TestSimpleReturn:
    def test_spec_example(self) -> None:
        # ((615 - 600) / 600) * 100 = +2.5
        assert simple_return_pct(615_000, 600_000) == 2.5

    def test_negative(self) -> None:
        assert simple_return_pct(580_000, 600_000) == pytest.approx(-3.333333333)


class TestPositionPnL:
    def test_long_profit(self) -> None:
        assert position_pnl_toman(615_000, 600_000, 100) == 1_500_000

    def test_long_loss(self) -> None:
        assert position_pnl_toman(580_000, 600_000, 50) == -1_000_000


class TestSentiment:
    def test_bearish_high_bubble(self) -> None:
        assert classify_sentiment(bubble=120.0, daily_vol=0.5) == "BEARISH"

    def test_bearish_negative_vol(self) -> None:
        assert classify_sentiment(bubble=50.0, daily_vol=-4.0) == "BEARISH"

    def test_bullish_stable_up(self) -> None:
        assert classify_sentiment(bubble=20.0, daily_vol=1.0) == "BULLISH"

    def test_neutral(self) -> None:
        assert classify_sentiment(bubble=50.0, daily_vol=0.5) == "NEUTRAL"


class TestArbitrageStatus:
    def test_opportunity(self) -> None:
        assert arbitrage_status_for(-1.0) == "OPPORTUNITY"

    def test_expensive(self) -> None:
        assert arbitrage_status_for(2.0) == "EXPENSIVE"

    def test_normal(self) -> None:
        assert arbitrage_status_for(0.3) == "NORMAL"
