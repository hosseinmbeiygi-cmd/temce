"""Signal generator — heuristic coverage."""

from __future__ import annotations

from apps.currency_service.domain.entities import MarketSummary
from apps.currency_service.domain.signals import generate_signals


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


class TestSignals:
    def test_no_signals_in_neutral(self) -> None:
        assert generate_signals(_mkt()) == []

    def test_buy_signal_when_stable(self) -> None:
        sigs = generate_signals(_mkt(bubble_index=20.0, daily_volatility=1.0))
        assert len(sigs) == 1
        s = sigs[0]
        assert s.asset_type == "CASH_USD"
        assert s.signal_type == "BUY"
        assert s.confidence == "MEDIUM"
        assert s.entry_range is not None
        lo, hi = s.entry_range
        assert lo < hi
        assert s.target_price is not None and s.target_price > hi
        assert s.stop_loss is not None and s.stop_loss < lo

    def test_no_buy_when_bubble_too_high(self) -> None:
        sigs = generate_signals(_mkt(bubble_index=40.0, daily_volatility=1.0))
        assert sigs == []

    def test_no_buy_when_vol_too_high(self) -> None:
        sigs = generate_signals(_mkt(bubble_index=20.0, daily_volatility=3.0))
        assert sigs == []

    def test_sell_usdt_when_premium_high(self) -> None:
        sigs = generate_signals(_mkt(tether_arbitrage=3.0))
        assert any(s.asset_type == "USDT" and s.signal_type == "SELL" for s in sigs)

    def test_both_can_coexist(self) -> None:
        # Stable market AND tether stretched -> two signals.
        sigs = generate_signals(_mkt(bubble_index=10.0, daily_volatility=0.5, tether_arbitrage=2.5))
        assert len(sigs) == 2
