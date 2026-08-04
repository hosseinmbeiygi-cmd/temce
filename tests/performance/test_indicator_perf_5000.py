"""Performance benchmarks for MarketService indicator calculations.

Generates 5 000 OHLCV data points and times every indicator.
Results are printed so they can be reviewed manually; hard assertions
enforce upper-bound latency thresholds.
"""

from __future__ import annotations

import random
import time

import pytest

from services.market_service import MarketService

# ── 5 000 realistic OHLCV bars (random-walk price) ─────────

_SEED = 42
_N = 5_000

random.seed(_SEED)

_PRICES: list[float] = []
_HIGHS: list[float] = []
_LOWS: list[float] = []
_VOLUMES: list[float] = []

price = 1000.0
for _ in range(_N):
    change_pct = random.gauss(0, 2.0)  # daily return ~ N(0, 2%)
    bar_range = abs(random.gauss(0, 1.0))  # intraday range
    close = price * (1 + change_pct / 100)
    high = close + bar_range
    low = close - bar_range
    vol = random.randint(1_000_000, 50_000_000)

    _PRICES.append(close)
    _HIGHS.append(high)
    _LOWS.append(low)
    _VOLUMES.append(float(vol))
    price = close


# ── Thresholds (seconds) ──────────────────────────────────

SIMPLE_THRESHOLD = 0.5  # sma / ema / obv / williams_r
MEDIUM_THRESHOLD = 1.5  # rsi / atr
COMPLEX_THRESHOLD = 3.0  # macd / bollinger / stochastic / ichimoku


# ═══════════════════════════════════════════════════════════
#  Single-indicator benchmarks (static methods)
# ═══════════════════════════════════════════════════════════


@pytest.mark.performance
def test_sma_5000() -> None:
    t0 = time.perf_counter()
    result = MarketService._sma(_PRICES, 14)
    elapsed = time.perf_counter() - t0
    assert len(result) == _N - 14 + 1
    assert elapsed < SIMPLE_THRESHOLD, f"SMA 5000: {elapsed:.4f}s > {SIMPLE_THRESHOLD}s"
    print(f"  SMA(14)  x5000: {elapsed:.4f}s  ({len(result)} values)")


@pytest.mark.performance
def test_ema_5000() -> None:
    t0 = time.perf_counter()
    result = MarketService._ema(_PRICES, 14)
    elapsed = time.perf_counter() - t0
    assert len(result) == _N - 14 + 1
    assert elapsed < SIMPLE_THRESHOLD, f"EMA 5000: {elapsed:.4f}s > {SIMPLE_THRESHOLD}s"
    print(f"  EMA(14)  x5000: {elapsed:.4f}s  ({len(result)} values)")


@pytest.mark.performance
def test_rsi_5000() -> None:
    t0 = time.perf_counter()
    result = MarketService._rsi(_PRICES, 14)
    elapsed = time.perf_counter() - t0
    assert len(result) == _N - 14
    assert elapsed < MEDIUM_THRESHOLD, f"RSI 5000: {elapsed:.4f}s > {MEDIUM_THRESHOLD}s"
    print(f"  RSI(14)  x5000: {elapsed:.4f}s  ({len(result)} values)")


@pytest.mark.performance
def test_macd_5000() -> None:
    t0 = time.perf_counter()
    macd_line, signal_line, hist = MarketService._macd(_PRICES, 12, 26, 9)
    elapsed = time.perf_counter() - t0
    assert len(macd_line) == _N - 26 + 1
    assert elapsed < COMPLEX_THRESHOLD, f"MACD 5000: {elapsed:.4f}s > {COMPLEX_THRESHOLD}s"
    print(f"  MACD(12,26,9) x5000: {elapsed:.4f}s  (macd={len(macd_line)} signal={len(signal_line)} hist={len(hist)})")


@pytest.mark.performance
def test_bollinger_5000() -> None:
    t0 = time.perf_counter()
    upper, middle, lower = MarketService._bollinger(_PRICES, 20, 2)
    elapsed = time.perf_counter() - t0
    assert len(middle) == _N - 20 + 1
    assert elapsed < COMPLEX_THRESHOLD, f"Bollinger 5000: {elapsed:.4f}s > {COMPLEX_THRESHOLD}s"
    print(f"  Bollinger(20,2) x5000: {elapsed:.4f}s  ({len(middle)} values)")


@pytest.mark.performance
def test_stochastic_5000() -> None:
    t0 = time.perf_counter()
    k_line, d_line = MarketService._stochastic(_HIGHS, _LOWS, _PRICES, 14, 3, 3)
    elapsed = time.perf_counter() - t0
    assert elapsed < COMPLEX_THRESHOLD, f"Stochastic 5000: {elapsed:.4f}s > {COMPLEX_THRESHOLD}s"
    print(f"  Stochastic(14,3,3) x5000: {elapsed:.4f}s  (k={len(k_line)} d={len(d_line)})")


@pytest.mark.performance
def test_atr_5000() -> None:
    t0 = time.perf_counter()
    result = MarketService._atr(_HIGHS, _LOWS, _PRICES, 14)
    elapsed = time.perf_counter() - t0
    assert len(result) == _N - 14  # 5000-1-14+1=4986
    assert elapsed < MEDIUM_THRESHOLD, f"ATR 5000: {elapsed:.4f}s > {MEDIUM_THRESHOLD}s"
    print(f"  ATR(14)  x5000: {elapsed:.4f}s  ({len(result)} values)")


@pytest.mark.performance
def test_obv_5000() -> None:
    t0 = time.perf_counter()
    result = MarketService._obv(_PRICES, _VOLUMES)
    elapsed = time.perf_counter() - t0
    assert len(result) == _N
    assert elapsed < SIMPLE_THRESHOLD, f"OBV 5000: {elapsed:.4f}s > {SIMPLE_THRESHOLD}s"
    print(f"  OBV      x5000: {elapsed:.4f}s  ({len(result)} values)")


@pytest.mark.performance
def test_williams_r_5000() -> None:
    t0 = time.perf_counter()
    result = MarketService._williams_r(_HIGHS, _LOWS, _PRICES, 14)
    elapsed = time.perf_counter() - t0
    assert len(result) == _N - 14 + 1
    assert elapsed < SIMPLE_THRESHOLD, f"Williams %R 5000: {elapsed:.4f}s > {SIMPLE_THRESHOLD}s"
    print(f"  Williams %R(14) x5000: {elapsed:.4f}s  ({len(result)} values)")


@pytest.mark.performance
def test_ichimoku_5000() -> None:
    t0 = time.perf_counter()
    tenkan, kijun, senkou_a, senkou_b, chikou = MarketService._ichimoku(
        _HIGHS,
        _LOWS,
        _PRICES,
        9,
        26,
        52,
    )
    elapsed = time.perf_counter() - t0
    assert len(tenkan) == _N - 9 + 1
    assert elapsed < COMPLEX_THRESHOLD, f"Ichimoku 5000: {elapsed:.4f}s > {COMPLEX_THRESHOLD}s"
    print(
        f"  Ichimoku(9,26,52) x5000: {elapsed:.4f}s  (t={len(tenkan)} k={len(kijun)} sa={len(senkou_a)} sb={len(senkou_b)} c={len(chikou)})"
    )


# ── _compute_indicator routing ─────────────────────────────


@pytest.mark.performance
def test_compute_indicator_routing_overhead() -> None:
    """Measure the routing layer overhead (negligible vs computation)."""
    t0 = time.perf_counter()
    _ = MarketService._compute_indicator("sma", _PRICES, {"period": 14})
    routing_time = time.perf_counter() - t0
    assert routing_time < 0.05, f"Routing overhead: {routing_time:.4f}s > 0.05s"
    print(f"  _compute_indicator routing: {routing_time:.4f}s")


# ═══════════════════════════════════════════════════════════
#  Full pipeline (with mock DB) benchmark
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.performance
async def test_calculate_indicator_pipeline_5000() -> None:
    """Full calculate_indicator pipeline with 5000 mock DB rows."""
    from unittest.mock import AsyncMock

    mock_data = [
        {
            "date": f"2020-01-{i % 28 + 1:02d}",
            "price_last": _PRICES[i],
            "price_max": _HIGHS[i],
            "price_min": _LOWS[i],
            "trade_volume": _VOLUMES[i],
        }
        for i in range(_N)
    ]
    mock_query = AsyncMock()
    mock_query.get_historical_daily.return_value = mock_data

    service = MarketService(brsapi_query_service=mock_query)

    t0 = time.perf_counter()
    result = await service.calculate_indicator("TEST", "sma", {"period": 14})
    elapsed = time.perf_counter() - t0

    assert result.success
    assert len(result.value["values"]) == _N - 14 + 1
    assert elapsed < SIMPLE_THRESHOLD * 1.5, f"Pipeline SMA 5000: {elapsed:.4f}s"
    print(f"  Pipeline SMA(14) x5000: {elapsed:.4f}s  (mock DB + full pipeline)")


@pytest.mark.asyncio
@pytest.mark.performance
async def test_calculate_indicator_pipeline_ichimoku_5000() -> None:
    """Full calculate_indicator pipeline for a complex multi-line indicator."""
    from unittest.mock import AsyncMock

    mock_data = [
        {
            "date": f"2020-01-{i % 28 + 1:02d}",
            "price_last": _PRICES[i],
            "price_max": _HIGHS[i],
            "price_min": _LOWS[i],
            "trade_volume": _VOLUMES[i],
        }
        for i in range(_N)
    ]
    mock_query = AsyncMock()
    mock_query.get_historical_daily.return_value = mock_data

    service = MarketService(brsapi_query_service=mock_query)

    t0 = time.perf_counter()
    result = await service.calculate_indicator("TEST", "ichimoku")
    elapsed = time.perf_counter() - t0

    assert result.success
    assert isinstance(result.value["values"], dict)
    assert "tenkan" in result.value["values"]
    assert elapsed < COMPLEX_THRESHOLD * 1.5, f"Pipeline Ichimoku 5000: {elapsed:.4f}s"
    print(f"  Pipeline Ichimoku x5000: {elapsed:.4f}s  (mock DB + full pipeline)")
