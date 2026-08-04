from __future__ import annotations

from backtesting.microstructure.auction_engine import (
    AuctionEngine,
    AuctionSession,
)


class TestAuctionEngine:
    def test_calculate_clearing_price_basic(self):
        engine = AuctionEngine()
        bids = {100: 1000, 101: 500, 102: 200}
        asks = {99: 800, 100: 400, 101: 300}
        result = engine.calculate_clearing_price(bids, asks)
        assert result.is_valid
        assert result.clearing_price > 0
        assert result.matched_volume > 0

    def test_calculate_clearing_price_no_bids(self):
        engine = AuctionEngine()
        result = engine.calculate_clearing_price({}, {100: 1000})
        assert not result.is_valid

    def test_calculate_clearing_price_no_asks(self):
        engine = AuctionEngine()
        result = engine.calculate_clearing_price({100: 1000}, {})
        assert not result.is_valid

    def test_opening_auction_with_reference_price(self):
        engine = AuctionEngine()
        bids = {105: 1000, 106: 500}
        asks = {100: 800, 101: 400}
        result = engine.calculate_opening_auction(
            bids, asks, reference_price=100, price_limit_pct=5
        )
        assert result.is_valid
        assert 95 <= result.clearing_price <= 105

    def test_closing_auction(self):
        engine = AuctionEngine()
        bids = {100: 1000, 102: 500}
        asks = {98: 800, 99: 600}
        result = engine.calculate_closing_auction([100.0, 101.0], bids, asks)
        assert result.is_valid

    def test_volatility_auction(self):
        engine = AuctionEngine()
        bids = {110: 1000, 115: 500}
        asks = {90: 800, 95: 600}
        result = engine.calculate_volatility_auction(
            bids, asks, reference_price=100, band_pct=10
        )
        assert result.is_valid
        assert 90 <= result.clearing_price <= 110

    def test_periodic_auction(self):
        engine = AuctionEngine()
        bids = {100: 1000, 102: 500}
        asks = {98: 800, 99: 600}
        result = engine.calculate_periodic_auction(
            bids, asks, reference_price=100, price_limit_pct=3
        )
        assert result.is_valid

    def test_base_market_auction(self):
        engine = AuctionEngine()
        bids = {100: 1000, 102: 500}
        asks = {98: 800, 99: 600}
        result = engine.calculate_base_market_auction(bids, asks, reference_price=100)
        assert result.is_valid

    def test_base_market_tiered_bands(self):
        engine = AuctionEngine()
        bids = {115: 1000}
        asks = {85: 800}
        result = engine.calculate_base_market_auction(
            bids,
            asks,
            reference_price=100,
            yellow_band_pct=3,
            orange_band_pct=2,
            red_band_pct=1,
        )
        assert result.price_limit_lower >= 97

    def test_ime_auction(self):
        engine = AuctionEngine()
        bids = {100: 1000, 105: 500}
        asks = {95: 800, 98: 600}
        result = engine.calculate_ime_auction(
            bids, asks, reference_price=100, contract_spec={"delivery": "spot"}
        )
        assert result.is_valid
        assert result.extra.get("delivery") == "spot"

    def test_apply_session_auction_preopen(self):
        engine = AuctionEngine()
        bids = {100: 1000}
        asks = {99: 800}
        result = engine.apply_session_auction(
            bids, asks, AuctionSession.PREOPEN, reference_price=100
        )
        assert result.is_valid

    def test_apply_session_auction_pre_close(self):
        engine = AuctionEngine()
        bids = {100: 1000}
        asks = {99: 800}
        result = engine.apply_session_auction(
            bids, asks, AuctionSession.PRE_CLOSE, reference_price=100
        )
        assert result.is_valid

    def test_imbalance_calculation(self):
        engine = AuctionEngine()
        bids = {100: 5000}
        asks = {99: 1000}
        result = engine.calculate_clearing_price(bids, asks)
        assert result.imbalance > 0
        assert result.imbalance_pct > 0

    def test_uncrossed_orders(self):
        engine = AuctionEngine()
        bids = {100: 1000, 105: 500}
        asks = {90: 800, 95: 600}
        result = engine.calculate_clearing_price(bids, asks)
        assert isinstance(result.uncrossed_bids, dict)
        assert isinstance(result.uncrossed_asks, dict)
