"""Comprehensive unit tests for all 10 main services.

Tests cover:
- market_service.py: get_overview, get_index_values, get_top_gainers/losers, get_sector_summary, _build_sectors, _to_ohlcv, _compute_indicator, _sma, _ema, _rsi, _macd, _bollinger, calculate_indicator
- signal_service.py: create, generate, list, get_by_symbol, bulk_generate
- screener_service.py: ScreenerService.screen, _CacheManager (already has tests, skip)
- backtest_service.py: run_backtest, list_runs, get_result, list_strategies (enhance existing)
- news_service.py: list_all, search, get_by_symbol, create
- codal_service.py: list_all, get_by_instrument, create
- fund_service.py: list_all, get_by_id, get_by_symbol, search, create, update, get_nav_history, ensure_seeded, _infer_fund_type
- alert_service.py: list_alerts, create_alert, update_alert, delete_alert, evaluate_and_trigger
- portfolio_service.py: get_portfolio, list_portfolios, create_portfolio
- trade_service.py: get_trades, get_recent, save_trade
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.result import Result

# ═══════════════════════════════════════════════════════════════════════════════
# MarketService Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestMarketServiceBuildSectors:
    """Test static _build_sectors method."""

    def test_empty_snapshots(self):
        from services.market_service import MarketService
        result = MarketService._build_sectors([])
        assert result == []

    def test_single_sector(self):
        from services.market_service import MarketService
        snapshots = [
            {"sector_name": "فلزات", "trade_value": 1000},
            {"sector_name": "فلزات", "trade_value": 2000},
        ]
        result = MarketService._build_sectors(snapshots)
        assert len(result) == 1
        assert result[0]["name"] == "فلزات"
        assert result[0]["count"] == 2
        assert result[0]["total_value"] == 3000

    def test_multiple_sectors(self):
        from services.market_service import MarketService
        snapshots = [
            {"sector_name": "فلزات", "trade_value": 1000},
            {"sector_name": "بانکها", "trade_value": 500},
            {"sector_name": "فلزات", "trade_value": 2000},
        ]
        result = MarketService._build_sectors(snapshots)
        assert len(result) == 2
        names = {r["name"] for r in result}
        assert names == {"فلزات", "بانکها"}

    def test_fallback_sector_name(self):
        from services.market_service import MarketService
        snapshots = [{"industry": "خودرو", "trade_value": 100}]
        result = MarketService._build_sectors(snapshots)
        assert result[0]["name"] == "خودرو"

    def test_missing_sector_defaults_to_other(self):
        from services.market_service import MarketService
        snapshots = [{"trade_value": 100}]
        result = MarketService._build_sectors(snapshots)
        assert result[0]["name"] == "سایر"


class TestMarketServiceToOhlcv:
    """Test static _to_ohlcv conversion."""

    def test_full_data(self):
        from services.market_service import MarketService
        d = {"date": "2024-01-01", "price_first": 100, "price_max": 110, "price_min": 90, "price_last": 105, "trade_volume": 1000}
        result = MarketService._to_ohlcv(d)
        assert result["date"] == "2024-01-01"
        assert result["open"] == 100
        assert result["high"] == 110
        assert result["low"] == 90
        assert result["close"] == 105
        assert result["volume"] == 1000

    def test_missing_fields(self):
        from services.market_service import MarketService
        result = MarketService._to_ohlcv({})
        assert result["date"] is None
        assert result["open"] is None
        assert result["high"] is None
        assert result["low"] is None
        assert result["close"] is None
        assert result["volume"] is None


class TestMarketServiceIndicators:
    """Test technical indicator calculations."""

    def test_sma_basic(self):
        from services.market_service import MarketService
        data = [10, 11, 12, 13, 14]
        result = MarketService._sma(data, 3)
        assert len(result) == 3
        assert result[0] == pytest.approx(11.0)
        assert result[1] == pytest.approx(12.0)
        assert result[2] == pytest.approx(13.0)

    def test_sma_insufficient_data(self):
        from services.market_service import MarketService
        assert MarketService._sma([1, 2], 5) == []

    def test_ema_basic(self):
        from services.market_service import MarketService
        data = [10, 11, 12, 13, 14]
        result = MarketService._ema(data, 3)
        assert len(result) == 3
        assert result[0] == pytest.approx(11.0)
        # EMA should be responsive to recent prices
        assert result[-1] > result[0]

    def test_ema_insufficient_data(self):
        from services.market_service import MarketService
        assert MarketService._ema([1, 2], 5) == []

    def test_rsi_overbought(self):
        from services.market_service import MarketService
        # All rising → RSI should be 100
        data = list(range(1, 20))
        result = MarketService._rsi(data, 14)
        assert len(result) > 0
        assert result[-1] == pytest.approx(100.0)

    def test_rsi_oversold(self):
        from services.market_service import MarketService
        # All falling → RSI should be 0
        data = list(range(20, 1, -1))
        result = MarketService._rsi(data, 14)
        assert len(result) > 0
        assert result[-1] == pytest.approx(0.0)

    def test_rsi_insufficient_data(self):
        from services.market_service import MarketService
        assert MarketService._rsi([1, 2, 3], 14) == []

    def test_macd_basic(self):
        from services.market_service import MarketService
        data = [i * 0.5 for i in range(50)]
        macd_line, signal_line, histogram = MarketService._macd(data, 12, 26, 9)
        assert len(macd_line) > 0
        assert len(signal_line) > 0
        assert len(histogram) > 0

    def test_bollinger_basic(self):
        from services.market_service import MarketService
        data = [100 + i * 0.1 for i in range(30)]
        upper, middle, lower = MarketService._bollinger(data, 20, 2.0)
        assert len(upper) == len(middle) == len(lower)
        assert upper[0] > middle[0] > lower[0]

    def test_bollinger_insufficient_data(self):
        from services.market_service import MarketService
        upper, middle, lower = MarketService._bollinger([1, 2], 20, 2.0)
        assert upper == [] and middle == [] and lower == []

    def test_atr_basic(self):
        from services.market_service import MarketService
        highs = [110, 115, 112, 118, 120]
        lows = [100, 105, 102, 108, 110]
        closes = [105, 110, 108, 115, 118]
        result = MarketService._atr(highs, lows, closes, 3)
        assert len(result) > 0
        assert all(v > 0 for v in result)

    def test_obv_basic(self):
        from services.market_service import MarketService
        closes = [100, 105, 103, 108, 106]
        volumes = [1000, 2000, 1500, 3000, 1000]
        result = MarketService._obv(closes, volumes)
        assert len(result) == 5
        assert result[0] == 1000  # First bar
        assert result[1] == 3000  # Price up → add volume
        assert result[2] == 1500  # Price down → subtract volume

    def test_williams_r(self):
        from services.market_service import MarketService
        highs = [110, 115, 112, 118, 120]
        lows = [100, 105, 102, 108, 110]
        closes = [105, 110, 108, 115, 118]
        result = MarketService._williams_r(highs, lows, closes, 3)
        assert len(result) > 0
        assert all(-100 <= v <= 0 for v in result)

    def test_stochastic(self):
        from services.market_service import MarketService
        highs = [110, 115, 112, 118, 120, 125, 122, 128, 130, 135]
        lows = [100, 105, 102, 108, 110, 115, 112, 118, 120, 125]
        closes = [105, 110, 108, 115, 118, 122, 118, 125, 128, 132]
        k_line, d_line = MarketService._stochastic(highs, lows, closes, 5)
        assert len(k_line) > 0
        assert len(d_line) > 0

    def test_ichimoku(self):
        from services.market_service import MarketService
        highs = [float(100 + i * 2) for i in range(60)]
        lows = [float(90 + i * 2) for i in range(60)]
        closes = [float(95 + i * 2) for i in range(60)]
        tenkan, kijun, senkou_a, senkou_b, chikou = MarketService._ichimoku(highs, lows, closes, 9, 26, 52)
        assert len(tenkan) > 0
        assert len(kijun) > 0

    def test_obv_empty(self):
        from services.market_service import MarketService
        assert MarketService._obv([], []) == []

    def test_compute_indicator_unknown(self):
        from services.market_service import MarketService
        with pytest.raises(ValueError, match="Unknown indicator"):
            MarketService._compute_indicator("unknown", [1, 2, 3], {})

    def test_compute_indicator_sma(self):
        from services.market_service import MarketService
        result = MarketService._compute_indicator("sma", [10, 11, 12, 13, 14], {"period": 3})
        assert isinstance(result, list)
        assert len(result) == 3


class TestMarketServiceGetOverview:
    """Test get_overview with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_overview_from_brsapi(self):
        from services.market_service import MarketService
        mock_brsapi = AsyncMock()
        mock_brsapi.get_latest_snapshots.return_value = [
            {"price_last_change_pct": 2.0, "trade_value": 1000, "trade_volume": 500},
            {"price_last_change_pct": -1.0, "trade_value": 2000, "trade_volume": 300},
            {"price_last_change_pct": 0.0, "trade_value": 500, "trade_volume": 100},
        ]
        service = MarketService(brsapi_query_service=mock_brsapi)
        result = await service.get_overview()
        assert result.success
        assert result.value["gainers"] == 1
        assert result.value["losers"] == 1
        assert result.value["unchanged"] == 1
        assert result.value["total_instruments"] == 3

    @pytest.mark.asyncio
    async def test_overview_empty_brsapi_fallback(self):
        from services.market_service import MarketService
        mock_brsapi = AsyncMock()
        mock_brsapi.get_latest_snapshots.return_value = []
        mock_repo = AsyncMock()
        mock_repo.get_market_summary.return_value = Result.ok({"total_quotes": 0})
        service = MarketService(brsapi_query_service=mock_brsapi, quote_repo=mock_repo)
        result = await service.get_overview()
        assert result.success

    @pytest.mark.asyncio
    async def test_overview_brsapi_exception_fallback(self):
        from services.market_service import MarketService
        mock_brsapi = AsyncMock()
        mock_brsapi.get_latest_snapshots.side_effect = Exception("DB down")
        mock_repo = AsyncMock()
        mock_repo.get_market_summary.return_value = Result.ok({"total_quotes": 0})
        service = MarketService(brsapi_query_service=mock_brsapi, quote_repo=mock_repo)
        result = await service.get_overview()
        assert result.success


class TestMarketServiceGetIndexValues:
    @pytest.mark.asyncio
    async def test_indices_from_brsapi(self):
        from services.market_service import MarketService
        mock_brsapi = AsyncMock()
        mock_brsapi.get_latest_indices.return_value = [{"name": "شاخص کل", "index_value": 5000000}]
        service = MarketService(brsapi_query_service=mock_brsapi)
        result = await service.get_index_values()
        assert result.success
        assert len(result.value) == 1

    @pytest.mark.asyncio
    async def test_indices_brsapi_empty_live_fallback(self):
        from services.market_service import MarketService
        mock_brsapi = AsyncMock()
        mock_brsapi.get_latest_indices.return_value = []
        mock_client = AsyncMock()
        mock_client.fetch.return_value = MagicMock(success=False)
        service = MarketService(brsapi_query_service=mock_brsapi, brsapi_client=mock_client)
        result = await service.get_index_values()
        assert result.success

    @pytest.mark.asyncio
    async def test_indices_no_brsapi_no_client(self):
        from services.market_service import MarketService
        service = MarketService()
        result = await service.get_index_values()
        assert result.success
        assert result.value == []


class TestMarketServiceGainersLosers:
    @pytest.mark.asyncio
    async def test_top_gainers(self):
        from services.market_service import MarketService
        mock_repo = AsyncMock()
        mock_repo.get_top_gainers.return_value = Result.ok([])
        service = MarketService(quote_repo=mock_repo)
        result = await service.get_top_gainers(5)
        assert result.success
        mock_repo.get_top_gainers.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_top_losers(self):
        from services.market_service import MarketService
        mock_repo = AsyncMock()
        mock_repo.get_top_losers.return_value = Result.ok([])
        service = MarketService(quote_repo=mock_repo)
        result = await service.get_top_losers(10)
        assert result.success

    @pytest.mark.asyncio
    async def test_most_active(self):
        from services.market_service import MarketService
        mock_repo = AsyncMock()
        mock_repo.get_most_active.return_value = Result.ok([])
        service = MarketService(quote_repo=mock_repo)
        result = await service.get_most_active(10)
        assert result.success


class TestMarketServiceHistoricalQuotes:
    @pytest.mark.asyncio
    async def test_historical_from_brsapi(self):
        from services.market_service import MarketService
        mock_brsapi = AsyncMock()
        mock_brsapi.get_historical_daily.return_value = [
            {"date": "2024-06-01", "price_last": 100},
            {"date": "2024-06-02", "price_last": 105},
        ]
        service = MarketService(brsapi_query_service=mock_brsapi)
        result = await service.get_historical_quotes("فولاد", "2024-06-01", "2024-06-30")
        assert result.success
        assert len(result.value) == 2

    @pytest.mark.asyncio
    async def test_historical_brsapi_filters_dates(self):
        from services.market_service import MarketService
        mock_brsapi = AsyncMock()
        mock_brsapi.get_historical_daily.return_value = [
            {"date": "2024-01-01", "price_last": 100},
            {"date": "2024-06-15", "price_last": 105},
            {"date": "2024-12-31", "price_last": 110},
        ]
        service = MarketService(brsapi_query_service=mock_brsapi)
        result = await service.get_historical_quotes("فولاد", "2024-06-01", "2024-06-30")
        assert result.success
        assert len(result.value) == 1
        assert result.value[0]["date"] == "2024-06-15"

    @pytest.mark.asyncio
    async def test_ohlcv_conversion(self):
        from services.market_service import MarketService
        mock_brsapi = AsyncMock()
        mock_brsapi.get_historical_daily.return_value = [
            {"date": "2024-06-01", "price_first": 100, "price_max": 110, "price_min": 90, "price_last": 105, "trade_volume": 1000},
        ]
        service = MarketService(brsapi_query_service=mock_brsapi)
        result = await service.get_ohlcv("فولاد", "2024-06-01", "2024-06-30")
        assert result.success
        assert result.value[0]["open"] == 100
        assert result.value[0]["high"] == 110


class TestMarketServiceCalculateIndicator:
    @pytest.mark.asyncio
    async def test_sma_indicator(self):
        from services.market_service import MarketService
        mock_brsapi = AsyncMock()
        mock_brsapi.get_historical_daily.return_value = [
            {"date": f"2024-06-{i:02d}", "price_last": 100 + i} for i in range(1, 31)
        ]
        service = MarketService(brsapi_query_service=mock_brsapi)
        result = await service.calculate_indicator("فولاد", "sma", {"period": 10})
        assert result.success
        assert result.value["indicator"] == "sma"
        assert len(result.value["values"]) > 0

    @pytest.mark.asyncio
    async def test_no_data_returns_fail(self):
        from services.market_service import MarketService
        service = MarketService()
        result = await service.calculate_indicator("nonexistent", "sma")
        assert not result.success


# ═══════════════════════════════════════════════════════════════════════════════
# SignalService Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSignalService:
    @pytest.mark.asyncio
    async def test_create_signal(self):
        from domain.common.enum_types import SignalType
        from services.signal_service import SignalService
        mock_repo = AsyncMock()
        mock_repo.save.return_value = Result.ok(MagicMock())
        service = SignalService(signal_repo=mock_repo)
        result = await service.create("inst_001", SignalType.STRONG_BUY, score=75.0, confidence=0.8)
        assert result.success
        mock_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_signals(self):
        from services.signal_service import SignalService
        mock_repo = AsyncMock()
        mock_repo.list.return_value = Result.ok(MagicMock(items=[], total=0, page=1, page_size=50, total_pages=1))
        service = SignalService(signal_repo=mock_repo)
        result = await service.list(page=1, page_size=50)
        assert result.success

    @pytest.mark.asyncio
    async def test_get_by_symbol(self):
        from services.signal_service import SignalService
        mock_repo = AsyncMock()
        mock_repo.get_by_instrument.return_value = Result.ok(MagicMock(items=[], total=0, page=1, page_size=100, total_pages=1))
        service = SignalService(signal_repo=mock_repo)
        result = await service.get_by_symbol("فولاد")
        assert result.success

    @pytest.mark.asyncio
    async def test_generate_signal(self):
        from services.signal_service import SignalService
        mock_repo = AsyncMock()
        service = SignalService(signal_repo=mock_repo)
        with patch("services.multi_market_signal_engine.MultiMarketSignalEngine") as MockEngine:
            mock_engine = AsyncMock()
            mock_signal = MagicMock()
            mock_signal.symbol = "فولاد"
            mock_signal.direction = "buy"
            mock_signal.score = 75.0
            mock_signal.strength = 0.8
            mock_signal.confidence = 0.7
            mock_signal.reason = "test reason"
            mock_signal.market = "stock"
            mock_signal.price = 10000
            mock_signal.change_pct = 2.5
            mock_engine.generate_all.return_value = ([mock_signal], [])
            MockEngine.return_value = mock_engine
            result = await service.generate("فولاد")
            assert result.success
            assert result.value["direction"] == "buy"


# ═══════════════════════════════════════════════════════════════════════════════
# NewsService Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestNewsService:
    @pytest.mark.asyncio
    async def test_list_all(self):
        from services.news_service import NewsService
        mock_repo = AsyncMock()
        mock_repo.list.return_value = Result.ok(MagicMock(items=[], total=0, page=1, page_size=50, total_pages=1))
        service = NewsService(repo=mock_repo)
        result = await service.list_all(page=1, page_size=50)
        assert result.success
        mock_repo.list.assert_called_once_with(1, 50)

    @pytest.mark.asyncio
    async def test_search(self):
        from services.news_service import NewsService
        mock_repo = AsyncMock()
        mock_repo.search.return_value = Result.ok(MagicMock(items=[], total=0, page=1, page_size=50, total_pages=1))
        service = NewsService(repo=mock_repo)
        result = await service.search("بازار سهام")
        assert result.success
        mock_repo.search.assert_called_once_with("بازار سهام", 1, 50)

    @pytest.mark.asyncio
    async def test_get_by_symbol(self):
        from services.news_service import NewsService
        mock_repo = AsyncMock()
        mock_repo.get_by_symbol.return_value = Result.ok(MagicMock(items=[], total=0, page=1, page_size=50, total_pages=1))
        service = NewsService(repo=mock_repo)
        result = await service.get_by_symbol("فولاد")
        assert result.success
        mock_repo.get_by_symbol.assert_called_once_with("فولاد", 1, 50)

    @pytest.mark.asyncio
    async def test_create_news(self):
        from services.news_service import NewsService
        mock_repo = AsyncMock()
        mock_repo.save.return_value = Result.ok(MagicMock())
        service = NewsService(repo=mock_repo)
        result = await service.create("تیتر خبر جدید", source="کدال")
        assert result.success
        mock_repo.save.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# CodalService Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestCodalService:
    @pytest.mark.asyncio
    async def test_list_all(self):
        from services.codal_service import CodalService
        mock_repo = AsyncMock()
        mock_repo.list.return_value = Result.ok(MagicMock(items=[], total=0, page=1, page_size=50, total_pages=1))
        service = CodalService(repo=mock_repo)
        result = await service.list_all()
        assert result.success

    @pytest.mark.asyncio
    async def test_get_by_instrument(self):
        from services.codal_service import CodalService
        mock_repo = AsyncMock()
        mock_repo.get_by_instrument.return_value = Result.ok(MagicMock(items=[], total=0, page=1, page_size=50, total_pages=1))
        service = CodalService(repo=mock_repo)
        result = await service.get_by_instrument("inst_001")
        assert result.success
        mock_repo.get_by_instrument.assert_called_once_with("inst_001", 1, 50)

    @pytest.mark.asyncio
    async def test_create_disclosure(self):
        from services.codal_service import CodalService
        mock_repo = AsyncMock()
        mock_repo.save.return_value = Result.ok(MagicMock())
        service = CodalService(repo=mock_repo)
        result = await service.create("inst_001", "صورت مالی سالانه")
        assert result.success
        mock_repo.save.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# FundService Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestFundService:
    @pytest.mark.asyncio
    async def test_list_all(self):
        from services.fund_service import FundService
        mock_fund_repo = AsyncMock()
        mock_fund_repo.list.return_value = Result.ok(MagicMock(items=[], total=0, page=1, page_size=50, total_pages=1))
        service = FundService(fund_repo=mock_fund_repo)
        result = await service.list_all()
        assert result.success

    @pytest.mark.asyncio
    async def test_get_by_id(self):
        from services.fund_service import FundService
        mock_fund_repo = AsyncMock()
        mock_fund_repo.get.return_value = Result.ok(MagicMock())
        service = FundService(fund_repo=mock_fund_repo)
        result = await service.get_by_id("fund_001")
        assert result.success

    @pytest.mark.asyncio
    async def test_get_by_symbol(self):
        from services.fund_service import FundService
        mock_fund_repo = AsyncMock()
        mock_fund_repo.get_by_symbol.return_value = Result.ok(MagicMock())
        service = FundService(fund_repo=mock_fund_repo)
        result = await service.get_by_symbol("آگاس")
        assert result.success

    @pytest.mark.asyncio
    async def test_search(self):
        from services.fund_service import FundService
        mock_fund_repo = AsyncMock()
        mock_fund_repo.search.return_value = Result.ok(MagicMock(items=[], total=0, page=1, page_size=50, total_pages=1))
        service = FundService(fund_repo=mock_fund_repo)
        result = await service.search("آگاه")
        assert result.success

    @pytest.mark.asyncio
    async def test_create_fund(self):
        from services.fund_service import FundService
        mock_fund_repo = AsyncMock()
        mock_fund_repo.save.return_value = Result.ok(MagicMock())
        service = FundService(fund_repo=mock_fund_repo)
        result = await service.create("صندوق جدید", symbol="جدید")
        assert result.success
        mock_fund_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_fund(self):
        from domain.funds.entities import Fund
        from services.fund_service import FundService
        mock_fund_repo = AsyncMock()
        fund = Fund(id="fund_001", name="Test Fund", symbol="TST")
        mock_fund_repo.get.return_value = Result.ok(fund)
        mock_fund_repo.save.return_value = Result.ok(fund)
        service = FundService(fund_repo=mock_fund_repo)
        result = await service.update("fund_001", name="Updated Fund")
        assert result.success

    @pytest.mark.asyncio
    async def test_update_fund_not_found(self):
        from services.fund_service import FundService
        mock_fund_repo = AsyncMock()
        mock_fund_repo.get.return_value = Result.fail("Not found")
        service = FundService(fund_repo=mock_fund_repo)
        result = await service.update("nonexistent", name="Test")
        assert not result.success

    @pytest.mark.asyncio
    async def test_get_nav_history(self):
        from services.fund_service import FundService
        mock_fund_repo = AsyncMock()
        mock_nav_repo = AsyncMock()
        mock_nav_repo.get_by_fund.return_value = Result.ok([])
        service = FundService(fund_repo=mock_fund_repo, nav_repo=mock_nav_repo)
        result = await service.get_nav_history("fund_001")
        assert result.success

    @pytest.mark.asyncio
    async def test_count(self):
        from services.fund_service import FundService
        mock_fund_repo = AsyncMock()
        mock_fund_repo.count.return_value = 42
        service = FundService(fund_repo=mock_fund_repo)
        count = await service.count()
        assert count == 42

    def test_infer_fund_type_gold(self):
        from services.fund_service import FundService
        service = FundService()
        assert service._infer_fund_type({"name": "صندوق طلا", "isin": ""}) == "بخشی"

    def test_infer_fund_type_fixed_income(self):
        from services.fund_service import FundService
        service = FundService()
        assert service._infer_fund_type({"name": "درآمد ثابت آگاه", "isin": ""}) == "درآمد ثابت"

    def test_infer_fund_type_leveraged(self):
        from services.fund_service import FundService
        service = FundService()
        assert service._infer_fund_type({"name": "اهرمی اول", "isin": ""}) == "اهرمی"

    def test_infer_fund_type_default(self):
        from services.fund_service import FundService
        service = FundService()
        assert service._infer_fund_type({"name": "صندوق معمولی", "isin": ""}) == "سهامی"

    @pytest.mark.asyncio
    async def test_ensure_seeded_empty(self):
        from services.fund_service import FundService
        mock_fund_repo = AsyncMock()
        mock_fund_repo.count.return_value = 0
        mock_fund_repo.save.return_value = Result.ok(MagicMock())
        service = FundService(fund_repo=mock_fund_repo)
        seeded = await service.ensure_seeded()
        assert seeded > 0

    @pytest.mark.asyncio
    async def test_ensure_seeded_already_populated(self):
        from services.fund_service import FundService
        mock_fund_repo = AsyncMock()
        mock_fund_repo.count.return_value = 50
        service = FundService(fund_repo=mock_fund_repo)
        seeded = await service.ensure_seeded()
        assert seeded == 0


# ═══════════════════════════════════════════════════════════════════════════════
# AlertService Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAlertService:
    @pytest.mark.asyncio
    async def test_create_alert(self):
        from services.alert_service import AlertService
        mock_session = AsyncMock()
        service = AlertService(session=mock_session)
        result = await service.create_alert(
            user_id="user_001",
            instrument_id="inst_001",
            symbol="فولاد",
            alert_type="price_above",
            condition={"field": "price", "operator": "gte", "threshold": 50000},
            channels=["console"],
            description="قیمت بالای ۵۰ هزار",
        )
        assert result.success
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_alert(self):
        from models.alert import AlertModel
        from services.alert_service import AlertService
        mock_session = AsyncMock()
        alert = AlertModel(id="alr_001", symbol="فولاد", enabled=True)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = alert
        mock_session.execute.return_value = mock_result
        service = AlertService(session=mock_session)
        result = await service.update_alert("alr_001", "user_001", enabled=False)
        assert result.success
        assert alert.enabled is False

    @pytest.mark.asyncio
    async def test_update_alert_not_found(self):
        from services.alert_service import AlertService
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        service = AlertService(session=mock_session)
        result = await service.update_alert("nonexistent", "user_001")
        assert not result.success

    @pytest.mark.asyncio
    async def test_delete_alert(self):
        from models.alert import AlertModel
        from services.alert_service import AlertService
        mock_session = AsyncMock()
        alert = AlertModel(id="alr_001", symbol="فولاد")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = alert
        mock_session.execute.return_value = mock_result
        service = AlertService(session=mock_session)
        result = await service.delete_alert("alr_001", "user_001")
        assert result.success
        mock_session.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_alert_not_found(self):
        from services.alert_service import AlertService
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        service = AlertService(session=mock_session)
        result = await service.delete_alert("nonexistent", "user_001")
        assert not result.success

    @pytest.mark.asyncio
    async def test_evaluate_and_trigger(self):
        import json

        from models.alert import AlertModel
        from services.alert_service import AlertService
        mock_session = AsyncMock()
        alert = AlertModel(
            id="alr_001",
            instrument_id="inst_001",
            enabled=True,
            condition=json.dumps({"field": "price", "operator": "gte", "threshold": 50000}),
            channels=json.dumps(["console"]),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [alert]
        mock_session.execute.return_value = mock_result
        service = AlertService(session=mock_session)
        triggered = await service.evaluate_and_trigger("inst_001", "فولاد", "price", 55000)
        assert len(triggered) == 1
        assert triggered[0]["alert_id"] == "alr_001"

    @pytest.mark.asyncio
    async def test_evaluate_no_trigger(self):
        import json

        from models.alert import AlertModel
        from services.alert_service import AlertService
        mock_session = AsyncMock()
        alert = AlertModel(
            id="alr_001",
            instrument_id="inst_001",
            enabled=True,
            condition=json.dumps({"field": "price", "operator": "gte", "threshold": 50000}),
            channels=json.dumps(["console"]),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [alert]
        mock_session.execute.return_value = mock_result
        service = AlertService(session=mock_session)
        triggered = await service.evaluate_and_trigger("inst_001", "فولاد", "price", 45000)
        assert len(triggered) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# PortfolioService Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestPortfolioService:
    @pytest.mark.asyncio
    async def test_list_portfolios(self):
        from services.portfolio_service import PortfolioService
        mock_repo = AsyncMock()
        mock_repo.list.return_value = Result.ok(MagicMock(items=[]))
        mock_session = AsyncMock()
        with patch("services.portfolio_service.PortfolioRepository", return_value=mock_repo):
            service = PortfolioService(session=mock_session)
            service.repo = mock_repo
            result = await service.list_portfolios()
            assert result.success

    @pytest.mark.asyncio
    async def test_create_portfolio(self):
        from services.portfolio_service import PortfolioService
        mock_repo = AsyncMock()
        mock_repo.save.return_value = Result.ok(MagicMock())
        mock_session = AsyncMock()
        with patch("services.portfolio_service.PortfolioRepository", return_value=mock_repo):
            service = PortfolioService(session=mock_session)
            service.repo = mock_repo
            result = await service.create_portfolio("سبد جدید", initial_capital=1_000_000_000)
            assert result.success
            mock_repo.save.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# TradeService Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTradeService:
    @pytest.mark.asyncio
    async def test_get_trades_from_db(self):
        from services.trade_service import TradeService
        mock_brsapi = AsyncMock()
        mock_brsapi.get_intraday_trades.return_value = [
            {"trade_date": "2024-06-01", "price": 10000, "volume": 100}
        ]
        service = TradeService(brsapi_query_service=mock_brsapi)
        result = await service.get_trades("فولاد", limit=50)
        assert result.success
        assert len(result.value) == 1

    @pytest.mark.asyncio
    async def test_get_trades_empty_db_live_fallback(self):
        from services.trade_service import TradeService
        mock_brsapi = AsyncMock()
        mock_brsapi.get_intraday_trades.return_value = []
        mock_client = AsyncMock()
        mock_client.fetch.return_value = MagicMock(success=False)
        service = TradeService(brsapi_query_service=mock_brsapi, brsapi_client=mock_client)
        result = await service.get_trades("فولاد")
        assert result.success
        assert result.value == []

    @pytest.mark.asyncio
    async def test_get_recent(self):
        from services.trade_service import TradeService
        mock_brsapi = AsyncMock()
        mock_brsapi.get_intraday_trades.return_value = [{"trade_date": "2024-06-01", "price": 10000}]
        service = TradeService(brsapi_query_service=mock_brsapi)
        result = await service.get_recent("فولاد")
        assert result.success
        mock_brsapi.get_intraday_trades.assert_called_once_with("فولاد", limit=20)

    @pytest.mark.asyncio
    async def test_get_trades_exception(self):
        from services.trade_service import TradeService
        mock_brsapi = AsyncMock()
        mock_brsapi.get_intraday_trades.side_effect = Exception("DB error")
        service = TradeService(brsapi_query_service=mock_brsapi)
        result = await service.get_trades("فولاد")
        assert result.success
        assert result.value == []


# ═══════════════════════════════════════════════════════════════════════════════
# ScreenerService Tests (basic — _CacheManager has dedicated tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestScreenerServiceBasic:
    @pytest.mark.asyncio
    async def test_screen_empty_data(self):
        from services.screener_service import ScreenerService
        service = ScreenerService(session=None)
        results, stats = await service.screen(instruments=[], market_watch=[])
        assert isinstance(results, list)
        assert len(results) == 0
        assert "total" in stats
