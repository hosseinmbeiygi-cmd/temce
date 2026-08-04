"""Unit tests for MarketService.

Covers:
  - Technical indicator calculations (SMA, EMA, RSI, MACD, Bollinger, Stochastic, ATR, OBV, Williams %R, Ichimoku)
  - get_overview with mocked BrsApi
  - get_historical_quotes with mocked repos
  - get_ohlcv with mocked repos
  - get_sector_summary with mocked data
  - _to_ohlcv conversion
  - _build_sectors aggregation
  - Edge cases (empty data, short data, unknown indicator)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.result import Result
from services.market_service import MarketService

# ── Helpers ──────────────────────────────────────────────────────


def _make_service(**kwargs: Any) -> MarketService:
    """Create a MarketService with all dependencies mocked."""
    defaults = {
        "quote_repo": MagicMock(),
        "instrument_repo": MagicMock(),
        "brsapi_query_service": MagicMock(),
        "brsapi_client": MagicMock(),
    }
    defaults.update(kwargs)
    return MarketService(**defaults)


# ════════════════════════════════════════════════════════════════
# 1. Technical Indicators (static methods — pure functions)
# ════════════════════════════════════════════════════════════════


class TestSMA:
    def test_basic(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = MarketService._sma(data, 3)
        assert len(result) == 3
        assert result[0] == pytest.approx(2.0)  # (1+2+3)/3
        assert result[1] == pytest.approx(3.0)  # (2+3+4)/3
        assert result[2] == pytest.approx(4.0)  # (3+4+5)/3

    def test_period_equals_length(self):
        result = MarketService._sma([1.0, 2.0, 3.0], 3)
        assert len(result) == 1
        assert result[0] == pytest.approx(2.0)

    def test_insufficient_data(self):
        assert MarketService._sma([1.0, 2.0], 5) == []

    def test_empty_data(self):
        assert MarketService._sma([], 3) == []

    def test_single_element(self):
        assert MarketService._sma([5.0], 1) == [5.0]


class TestEMA:
    def test_basic(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = MarketService._ema(data, 3)
        assert len(result) > 0
        # First EMA value is SMA of first 3 elements
        assert result[0] == pytest.approx(2.0)

    def test_insufficient_data(self):
        assert MarketService._ema([1.0], 5) == []

    def test_convergence(self):
        """EMA of constant data should converge to that constant."""
        data = [100.0] * 30
        result = MarketService._ema(data, 10)
        assert all(v == pytest.approx(100.0) for v in result)


class TestRSI:
    def test_basic(self):
        # Rising prices → RSI > 50
        data = list(range(1, 21))
        result = MarketService._rsi(data, 14)
        assert len(result) > 0
        assert all(0 <= v <= 100 for v in result)
        assert result[-1] > 50  # strong uptrend

    def test_falling_prices(self):
        data = list(range(20, 0, -1))
        result = MarketService._rsi(data, 14)
        assert len(result) > 0
        assert result[-1] < 50  # strong downtrend

    def test_insufficient_data(self):
        assert MarketService._rsi([1.0, 2.0], 14) == []

    def test_range(self):
        """RSI should always be between 0 and 100."""
        data = [10, 12, 11, 13, 12, 14, 13, 15, 14, 16, 15, 17, 16, 18, 17, 19]
        result = MarketService._rsi(data, 14)
        assert all(0 <= v <= 100 for v in result)


class TestMACD:
    def test_basic(self):
        data = list(range(1, 50))
        macd, signal, hist = MarketService._macd(data, 12, 26, 9)
        assert len(macd) > 0
        assert len(signal) > 0
        assert len(hist) > 0
        # MACD line should be positive for uptrending data
        assert macd[-1] > 0

    def test_insufficient_data(self):
        macd, signal, hist = MarketService._macd([1.0], 12, 26, 9)
        assert len(macd) == 0


class TestBollinger:
    def test_basic(self):
        data = [100.0 + i * 0.5 for i in range(30)]
        upper, middle, lower = MarketService._bollinger(data, 20, 2.0)
        assert len(upper) == len(middle) == len(lower) > 0
        # Upper > Middle > Lower
        for u, m, lo in zip(upper, middle, lower, strict=True):
            assert u >= m >= lo

    def test_insufficient_data(self):
        u, m, lo = MarketService._bollinger([1.0], 20, 2.0)
        assert u == m == lo == []

    def test_constant_data(self):
        """Constant data → zero stddev → upper = middle = lower."""
        data = [100.0] * 25
        upper, middle, lower = MarketService._bollinger(data, 20, 2.0)
        assert len(upper) > 0
        for u, m, lo in zip(upper, middle, lower, strict=True):
            assert u == pytest.approx(m, abs=1e-10)
            assert lo == pytest.approx(m, abs=1e-10)


class TestStochastic:
    def test_basic(self):
        highs = [10 + i for i in range(20)]
        lows = [5 + i for i in range(20)]
        closes = [7 + i for i in range(20)]
        k, d = MarketService._stochastic(highs, lows, closes, 14)
        assert len(k) > 0
        assert len(d) > 0
        # All values in [0, 100]
        assert all(0 <= v <= 100 for v in k)

    def test_insufficient_data(self):
        assert MarketService._stochastic([1.0], [1.0], [1.0], 14) == ([], [])


class TestATR:
    def test_basic(self):
        highs = [10, 12, 11, 13, 12, 14, 13, 15, 14, 16]
        lows = [8, 10, 9, 11, 10, 12, 11, 13, 12, 14]
        closes = [9, 11, 10, 12, 11, 13, 12, 14, 13, 15]
        result = MarketService._atr(highs, lows, closes, 5)
        assert len(result) > 0
        assert all(v >= 0 for v in result)

    def test_insufficient_data(self):
        assert MarketService._atr([1.0], [1.0], [1.0], 5) == []


class TestOBV:
    def test_basic(self):
        closes = [10, 11, 10, 12, 11]
        volumes = [100, 200, 150, 300, 250]
        result = MarketService._obv(closes, volumes)
        assert len(result) == 5
        assert result[0] == 100  # first OBV = first volume
        assert result[1] == 300  # price up → +200
        assert result[2] == 150  # price down → -150
        assert result[3] == 450  # price up → +300

    def test_empty(self):
        assert MarketService._obv([], []) == []


class TestWilliamsR:
    def test_basic(self):
        highs = [10, 12, 11, 13, 12]
        lows = [8, 10, 9, 11, 10]
        closes = [9, 11, 10, 12, 11]
        result = MarketService._williams_r(highs, lows, closes, 3)
        assert len(result) > 0
        assert all(-100 <= v <= 0 for v in result)

    def test_insufficient_data(self):
        assert MarketService._williams_r([1.0], [1.0], [1.0], 3) == []


class TestIchimoku:
    def test_basic(self):
        highs = list(range(10, 70))
        lows = list(range(5, 65))
        closes = list(range(7, 67))
        tenkan, kijun, senkou_a, senkou_b, chikou = MarketService._ichimoku(highs, lows, closes)
        assert len(tenkan) > 0
        assert len(kijun) > 0
        assert len(senkou_a) > 0

    def test_insufficient_data(self):
        result = MarketService._ichimoku([1.0], [1.0], [1.0])
        assert all(len(v) == 0 for v in result)


# ════════════════════════════════════════════════════════════════
# 2. _compute_indicator dispatcher
# ════════════════════════════════════════════════════════════════


class TestComputeIndicator:
    def test_unknown_indicator_raises(self):
        with pytest.raises(ValueError, match="Unknown indicator"):
            MarketService._compute_indicator("unknown", [1, 2, 3], {})

    def test_sma_dispatch(self):
        result = MarketService._compute_indicator("sma", [1.0, 2.0, 3.0, 4.0, 5.0], {"period": 3})
        assert isinstance(result, list)
        assert len(result) == 3

    def test_macd_dispatch(self):
        result = MarketService._compute_indicator("macd", list(range(1, 40)), {})
        assert isinstance(result, dict)
        assert "macd" in result
        assert "signal" in result
        assert "histogram" in result

    def test_bollinger_dispatch(self):
        result = MarketService._compute_indicator("bollinger", [100.0] * 25, {"period": 20})
        assert isinstance(result, dict)
        assert "upper" in result


# ════════════════════════════════════════════════════════════════
# 3. _to_ohlcv conversion
# ════════════════════════════════════════════════════════════════


class TestToOhlcv:
    def test_basic(self):
        d = {"date": "2024-01-01", "price_first": 100, "price_max": 110, "price_min": 90, "price_last": 105, "trade_volume": 1000}
        result = MarketService._to_ohlcv(d)
        assert result["date"] == "2024-01-01"
        assert result["open"] == 100
        assert result["high"] == 110
        assert result["low"] == 90
        assert result["close"] == 105
        assert result["volume"] == 1000

    def test_missing_fields(self):
        result = MarketService._to_ohlcv({})
        assert result["open"] is None
        assert result["volume"] is None


# ════════════════════════════════════════════════════════════════
# 4. _build_sectors aggregation
# ════════════════════════════════════════════════════════════════


class TestBuildSectors:
    def test_basic(self):
        snapshots = [
            {"sector_name": "metal", "trade_value": 1000},
            {"sector_name": "metal", "trade_value": 2000},
            {"sector_name": "petro", "trade_value": 500},
        ]
        result = MarketService._build_sectors(snapshots)
        assert len(result) == 2
        metal = next(s for s in result if s["name"] == "metal")
        assert metal["count"] == 2
        assert metal["total_value"] == 3000

    def test_empty(self):
        assert MarketService._build_sectors([]) == []

    def test_missing_sector_name(self):
        snapshots = [{"trade_value": 100}]
        result = MarketService._build_sectors(snapshots)
        assert result[0]["name"] == "سایر"


# ════════════════════════════════════════════════════════════════
# 5. Async methods with mocked dependencies
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestGetOverview:
    async def test_with_brsapi(self):
        svc = _make_service()
        svc._brsapi.get_latest_snapshots = AsyncMock(return_value=[
            {"price_last_change_pct": 2.0, "trade_value": 1000, "trade_volume": 100},
            {"price_last_change_pct": -1.0, "trade_value": 2000, "trade_volume": 200},
        ])
        result = await svc.get_overview()
        assert result.success
        assert result.value["total_instruments"] == 2
        assert result.value["gainers"] == 1
        assert result.value["losers"] == 1

    async def test_brsapi_fails_fallback(self):
        svc = _make_service()
        svc._brsapi.get_latest_snapshots = AsyncMock(side_effect=Exception("DB down"))
        svc.quote_repo.get_market_summary = AsyncMock(return_value=Result.ok({"total": 0}))
        result = await svc.get_overview()
        assert result.success

    async def test_no_brsapi(self):
        svc = _make_service(brsapi_query_service=None)
        svc.quote_repo.get_market_summary = AsyncMock(return_value=Result.ok({"total": 0}))
        result = await svc.get_overview()
        assert result.success


@pytest.mark.asyncio
class TestGetIndexValues:
    async def test_with_brsapi(self):
        svc = _make_service()
        svc._brsapi.get_latest_indices = AsyncMock(return_value=[{"name": "TEPIX"}])
        result = await svc.get_index_values()
        assert result.success
        assert len(result.value) == 1

    async def test_brsapi_empty_fallback_to_client(self):
        svc = _make_service()
        svc._brsapi.get_latest_indices = AsyncMock(return_value=[])
        svc._client = MagicMock()
        result = await svc.get_index_values()
        assert result.success

    async def test_no_sources(self):
        svc = _make_service(brsapi_query_service=None, brsapi_client=None)
        result = await svc.get_index_values()
        assert result.success
        assert result.value == []


@pytest.mark.asyncio
class TestGetSectorSummary:
    async def test_with_brsapi(self):
        svc = _make_service()
        svc._brsapi.get_latest_snapshots = AsyncMock(return_value=[
            {"sector_name": "metal", "trade_value": 1000},
            {"sector_name": "petro", "trade_value": 2000},
        ])
        result = await svc.get_sector_summary()
        assert result.success
        assert len(result.value) == 2

    async def test_no_sources(self):
        svc = _make_service(brsapi_query_service=None, brsapi_client=None)
        result = await svc.get_sector_summary()
        assert result.success
        assert result.value == []


@pytest.mark.asyncio
class TestGetHistoricalQuotes:
    async def test_with_brsapi(self):
        svc = _make_service()
        data = [{"date": "2024-01-15", "price_close": 100}, {"date": "2024-01-10", "price_close": 90}]
        svc._brsapi.get_historical_daily = AsyncMock(return_value=data)
        result = await svc.get_historical_quotes("فولاد", "2024-01-10", "2024-01-20")
        assert result.success
        assert len(result.value) == 2

    async def test_no_sources(self):
        svc = _make_service(brsapi_query_service=None, brsapi_client=None)
        result = await svc.get_historical_quotes("فولاد", "2024-01-01", "2024-12-31")
        assert result.success
        assert result.value == []


@pytest.mark.asyncio
class TestCalculateIndicator:
    async def test_no_data_returns_fail(self):
        svc = _make_service(brsapi_query_service=None, brsapi_client=None)
        result = await svc.calculate_indicator("فولاد", "sma")
        assert not result.success

    async def test_with_brsapi_data(self):
        svc = _make_service()
        data = [{"date": f"2024-01-{i:02d}", "price_last": 100 + i, "price_max": 105 + i, "price_min": 95 + i, "trade_volume": 1000} for i in range(1, 30)]
        svc._brsapi.get_historical_daily = AsyncMock(return_value=data)
        result = await svc.calculate_indicator("فولاد", "sma", {"period": 14})
        assert result.success
        assert "dates" in result.value
        assert "values" in result.value
        assert len(result.value["values"]) > 0

    async def test_unknown_indicator(self):
        svc = _make_service()
        data = [{"date": f"2024-01-{i:02d}", "price_last": 100 + i} for i in range(1, 30)]
        svc._brsapi.get_historical_daily = AsyncMock(return_value=data)
        result = await svc.calculate_indicator("فولاد", "unknown_indicator")
        assert not result.success
