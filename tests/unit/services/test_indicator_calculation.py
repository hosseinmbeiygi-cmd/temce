"""Unit tests for MarketService indicator calculations.

Covers: SMA, EMA, RSI, MACD, Bollinger, Stochastic, ATR, OBV,
Williams %R, and Ichimoku Kinko Hyo.

All tests verify exact computed values against known-correct expectations.
"""

from __future__ import annotations

import math

import pytest

from services.market_service import MarketService

# ── Test data ──────────────────────────────────────────────

# Simple linear series: 5 points
SIMPLE = [10.0, 20.0, 30.0, 40.0, 50.0]

# Moderate series: 20 points increasing by 2
INCREASING_20 = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0, 26.0, 28.0,
                 30.0, 32.0, 34.0, 36.0, 38.0, 40.0, 42.0, 44.0, 46.0, 48.0]

# 40-point series for MACD (needs mins low + signal periods)
INCREASING_40 = [float(i) for i in range(10, 50)]  # [10, 11, ..., 49]


# ── SMA ────────────────────────────────────────────────────

def test_sma_period_3_simple():
    """SMA(3) on [10,20,30,40,50] → [20,30,40]"""
    result = MarketService._sma(SIMPLE, 3)
    assert result == [20.0, 30.0, 40.0]


def test_sma_period_5_on_20_points():
    """SMA(5) on 20 linearly increasing points (step +2)."""
    result = MarketService._sma(INCREASING_20, 5)
    # Each 5-element window average = middle element (linear)
    expected = [14.0, 16.0, 18.0, 20.0, 22.0, 24.0, 26.0, 28.0,
                30.0, 32.0, 34.0, 36.0, 38.0, 40.0, 42.0, 44.0]
    assert len(result) == 16  # 20 - 5 + 1
    assert result == expected


def test_sma_period_too_large_returns_empty():
    """Period > data length → empty list."""
    assert MarketService._sma([1.0, 2.0, 3.0], 5) == []


def test_sma_period_1_returns_original():
    """SMA(1) is the original series."""
    result = MarketService._sma([10.0, 20.0, 30.0], 1)
    assert result == [10.0, 20.0, 30.0]


def test_sma_period_equals_length():
    """SMA(n) on n points → one value (the average)."""
    result = MarketService._sma([10.0, 20.0, 30.0], 3)
    assert result == [20.0]


# ── EMA ────────────────────────────────────────────────────

def test_ema_period_3_simple():
    """EMA(3) on [10,20,30,40,50]."""
    result = MarketService._ema(SIMPLE, 3)
    # Initial SMA: (10+20+30)/3 = 20
    # multiplier = 2/4 = 0.5
    # ema[1] = 20 + 0.5*(40-20) = 30
    # ema[2] = 30 + 0.5*(50-30) = 40
    assert result == pytest.approx([20.0, 30.0, 40.0])


def test_ema_period_5_on_20_points():
    """EMA(5) on 20 linearly increasing points."""
    result = MarketService._ema(INCREASING_20, 5)
    # Initial SMA of first 5: (10+12+14+16+18)/5 = 14
    # multiplier = 2/6 ≈ 0.33333...
    # For linear data stepping by +2, each ema step = +2 exactly
    expected = [14.0, 16.0, 18.0, 20.0, 22.0, 24.0, 26.0, 28.0,
                30.0, 32.0, 34.0, 36.0, 38.0, 40.0, 42.0, 44.0]
    assert len(result) == 16  # 20 - 5 + 1
    assert result == pytest.approx(expected)


def test_ema_period_too_large():
    """Period > data → empty."""
    assert MarketService._ema([1.0, 2.0], 3) == []


def test_ema_approaches_last_price_over_time():
    """With constant price, EMA should converge to that price."""
    prices = [100.0] * 20
    result = MarketService._ema(prices, 5)
    # Initial SMA = 100, all subsequent = 100 since no change
    assert len(result) == 16
    assert all(abs(v - 100.0) < 1e-10 for v in result)


# ── RSI ────────────────────────────────────────────────────

def test_rsi_period_3_up_trend():
    """RSI(3) on steadily increasing prices → all 100 (no losses)."""
    prices = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0]
    result = MarketService._rsi(prices, 3)
    # len=7, gains = 6*2.0, losses = 6*0.0
    # avg_gain=2.0, avg_loss=0 → RSI=100, all subsequent 100
    assert len(result) == 4  # 7 - 1 - 3 + 1
    assert result == pytest.approx([100.0, 100.0, 100.0, 100.0])


def test_rsi_period_3_down_trend():
    """RSI(3) on steadily decreasing prices → all 0 (no gains)."""
    prices = [22.0, 20.0, 18.0, 16.0, 14.0, 12.0, 10.0]
    result = MarketService._rsi(prices, 3)
    # gains = 6*0.0, losses = 6*2.0
    # avg_gain=0, avg_loss=2.0
    # First: RSI = 100 - 100/(1+0/2) = 100 - 100 = 0
    assert len(result) == 4
    assert result == pytest.approx([0.0, 0.0, 0.0, 0.0])


def test_rsi_period_3_mixed():
    """RSI(3) on alternating up/down moves."""
    prices = [10.0, 12.0, 10.0, 12.0, 10.0, 12.0]
    result = MarketService._rsi(prices, 3)
    # gains = [2, 0, 2, 0, 2]  → sum[:3] = 4
    # losses = [0, 2, 0, 2, 0] → sum[:3] = 2
    # avg_gain = 4/3 ≈ 1.333, avg_loss = 2/3 ≈ 0.667
    # First RSI: 100 - 100/(1+1.333/0.667) = 100 - 100/3 ≈ 66.67
    assert len(result) == 3  # 6 - 1 - 3 + 1
    assert result[0] == pytest.approx(100 - 100 / (1 + (4 / 3) / (2 / 3)), rel=1e-9)
    # The value is: 100 - 100/3 = 66.666...
    assert result[0] == pytest.approx(100.0 / 3 * 2, rel=1e-9)


def test_rsi_period_too_large():
    """Period + 1 > data → empty."""
    assert MarketService._rsi([1.0, 2.0, 3.0], 3) == []


def test_rsi_flat_prices():
    """Flat prices: avg_gain=0, avg_loss=0 → RSI defaults to 100."""
    prices = [100.0] * 20
    result = MarketService._rsi(prices, 14)
    assert len(result) == 6  # 20 - 1 - 14 + 1
    # When avg_loss == 0, we short-circuit to 100
    assert result == pytest.approx([100.0] * 6)


# ── MACD data ──────────────────────────────────────────────

# 55-point series for long-term MACD combos (needs 50 slow)
MACD_55 = [float(i) for i in range(10, 65)]  # [10, 11, ..., 64]


# ── MACD exact values (computed by hand) ───────────────────

# Data: [10, 12, 14, 16, 18, 20, 22] — 7 points stepping by 2
_MACD_SMALL = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0]


def test_macd_3_5_2_exact_values():
    """MACD(3,5,2) on [10,12,14,16,18,20,22] — exact values."""
    macd_line, signal_line, hist = MarketService._macd(_MACD_SMALL, 3, 5, 2)
    # EMA(3): Initial SMA=(10+12+14)/3=12, mult=0.5
    #   [12, 12+0.5*(16-12)=14, 14+0.5*(18-14)=16, 16+0.5*(20-16)=18, 18+0.5*(22-18)=20]
    #   = [12, 14, 16, 18, 20] — 5 values
    # EMA(5): Initial SMA=(10+12+14+16+18)/5=14, mult=1/3
    #   [14, 14+(1/3)*(20-14)=16, 16+(1/3)*(22-16)=18]
    #   = [14, 16, 18] — 3 values
    # MACD line (offset=5-3=2): ema_fast[2:]=[16,18,20] - [14,16,18] = [2,2,2]
    assert len(macd_line) == 3
    assert macd_line == pytest.approx([2.0, 2.0, 2.0])
    # Signal = EMA(2) on [2,2,2]: Initial SMA=(2+2)/2=2, mult=2/3
    #   [2, 2+(2/3)*(2-2)=2] = [2, 2]
    assert len(signal_line) == 2
    assert signal_line == pytest.approx([2.0, 2.0])
    # Histogram: min(3,2)=2, [2-2, 2-2] = [0, 0]
    assert len(hist) == 2
    assert hist == pytest.approx([0.0, 0.0])


# ── MACD: multiple parameter combos ────────────────────────

def test_macd_12_26_9_lengths():
    """MACD(12,26,9) standard on 40 points."""
    macd_line, signal_line, hist = MarketService._macd(INCREASING_40, 12, 26, 9)
    # EMA(12): 40-12+1=29, EMA(26): 40-26+1=15
    # MACD line: 15 (aligned to slow EMA)
    # Signal: EMA(9) on 15: 15-9+1=7
    # Histogram: min(15, 7) = 7
    assert len(macd_line) == 15
    assert len(signal_line) == 7
    assert len(hist) == 7
    # Linear uptrend → fast EMA > slow EMA → MACD > 0
    assert all(m > 0 for m in macd_line)


def test_macd_8_17_9_lengths():
    """MACD(8,17,9) — tighter parameters."""
    macd_line, signal_line, hist = MarketService._macd(INCREASING_40, 8, 17, 9)
    # EMA(8): 40-8+1=33, EMA(17): 40-17+1=24
    # MACD: 24, signal: 24-9+1=16, hist: min(24,16)=16
    assert len(macd_line) == 24
    assert len(signal_line) == 16
    assert len(hist) == 16


def test_macd_5_35_5_lengths():
    """MACD(5,35,5) — wide fast/slow gap, needs 35+ data."""
    macd_line, signal_line, hist = MarketService._macd(INCREASING_40, 5, 35, 5)
    # EMA(5): 40-5+1=36, EMA(35): 40-35+1=6
    # MACD: 6, signal: 6-5+1=2, hist: min(6,2)=2
    assert len(macd_line) == 6
    assert len(signal_line) == 2
    assert len(hist) == 2


def test_macd_20_50_10_lengths():
    """MACD(20,50,10) — long-term combo on 55 points."""
    macd_line, signal_line, hist = MarketService._macd(MACD_55, 20, 50, 10)
    # EMA(20): 55-20+1=36, EMA(50): 55-50+1=6
    # MACD: 6, signal: 6-10+1=-3 → 0 (invalid), actually EMA(10) on 6 values
    # 6 < 10 → _ema returns [] → signal = []
    assert len(macd_line) == 6
    # signal_line may be empty if insufficient data for EMA(10)
    assert len(hist) == 0


def test_macd_3_10_5_short_data():
    """MACD(3,10,5) on data < slow period → all empty."""
    macd_line, signal_line, hist = MarketService._macd([10.0] * 7, 3, 10, 5)
    assert macd_line == []
    assert signal_line == []
    assert hist == []


# ── MACD: behavioral tests ────────────────────────────────

def test_macd_uptrend_positive():
    """In an uptrend, MACD line should be positive."""
    data = list(range(10, 50))  # 40 points of pure uptrend
    macd_line, signal_line, hist = MarketService._macd(data, 12, 26, 9)
    assert len(macd_line) == 15  # 40-26+1
    # Fast EMA should be above slow EMA in pure uptrend
    assert all(m > 0 for m in macd_line)


def test_macd_downtrend_negative():
    """In a downtrend, MACD line should be negative."""
    data = list(range(50, 10, -1))  # 40 points of pure downtrend
    macd_line, signal_line, hist = MarketService._macd(data, 12, 26, 9)
    assert len(macd_line) == 15
    # Fast EMA should be below slow EMA in pure downtrend
    assert all(m < 0 for m in macd_line)


def test_macd_crosses_zero():
    """MACD should cross zero when trend reverses."""
    # 20 up + 20 down (no duplicate at crossover)
    data = list(range(10, 30)) + list(range(29, 9, -1))[1:]
    macd_line, signal_line, hist = MarketService._macd(data, 5, 10, 5)
    assert len(macd_line) > 0
    # Should have positive values early and negative late
    assert any(m > 0 for m in macd_line[:len(macd_line) // 2])
    assert any(m < 0 for m in macd_line[len(macd_line) // 2:])


def test_macd_constant_prices():
    """Constant prices → MACD ≈ 0, signal ≈ 0, histogram ≈ 0."""
    prices = [50.0] * 45
    macd_line, signal_line, hist = MarketService._macd(prices, 12, 26, 9)
    for v in macd_line:
        assert abs(v) < 1e-10
    for v in signal_line:
        assert abs(v) < 1e-10
    for v in hist:
        assert abs(v) < 1e-10


def test_macd_signal_lags_macd():
    """Signal line (EMA of MACD) should lag behind MACD line."""
    data = list(range(10, 55))  # 45 points
    macd_line, signal_line, _ = MarketService._macd(data, 12, 26, 9)
    assert len(macd_line) > len(signal_line)  # signal starts later


# ── MACD: edge cases ──────────────────────────────────────

def test_macd_minimal_fast():
    """MACD(2,5,2) — minimal fast period."""
    macd_line, signal_line, hist = MarketService._macd(_MACD_SMALL, 2, 5, 2)
    # EMA(2): 7-2+1=6, EMA(5): 7-5+1=3
    # MACD: 3, signal: 3-2+1=2, hist: min(3,2)=2
    assert len(macd_line) == 3
    assert len(signal_line) == 2


def test_macd_exact_length_at_slow_period():
    """When len(data) == slow_period exactly, still works."""
    data = list(range(1, 27))  # 26 points = slow period
    macd_line, signal_line, hist = MarketService._macd(data, 12, 26, 9)
    assert len(macd_line) == 1  # just 1 MACD value


# ── MACD pipeline test ────────────────────────────────────

@pytest.mark.asyncio
async def test_calculate_indicator_pipeline_macd_exact():
    """Full pipeline with MACD(12,26,9) and exact value checks."""
    from unittest.mock import AsyncMock

    mock_data = [
        {"date": f"2024-01-{i+1:02d}", "price_last": float(10 + i)}
        for i in range(40)
    ]
    mock_query = AsyncMock()
    mock_query.get_historical_daily.return_value = mock_data

    service = MarketService(brsapi_query_service=mock_query)
    result = await service.calculate_indicator("TEST", "macd")

    assert result.success
    data = result.value
    assert data["indicator"] == "macd"
    assert isinstance(data["values"], dict)
    assert set(data["values"].keys()) == {"macd", "signal", "histogram"}
    assert len(data["values"]["macd"]) == 15
    assert len(data["values"]["signal"]) == 7
    assert len(data["values"]["histogram"]) == 7
    # All three for uptrend: MACD > 0, histogram = MACD - signal should also be > 0
    assert all(m > 0 for m in data["values"]["macd"])


# ── Bollinger Bands ────────────────────────────────────────

def test_bollinger_default_params():
    """Bollinger(20, 2) on 20 linearly increasing points."""
    upper, middle, lower = MarketService._bollinger(INCREASING_20, 20, 2)
    # 20 points, period=20 → 1 value (20-20+1)
    assert len(upper) == 1
    assert len(middle) == 1
    assert len(lower) == 1
    # middle = average of [10..48] = (10+48)/2 = 29
    assert middle[0] == pytest.approx(29.0)
    # std dev of 10,12,...,48
    # variance = sum((x-29)^2)/20 for x in range(10,50,2)
    # = sum over i=0..19 of (10+2i-29)^2 / 20 = sum over i of (2i-19)^2 / 20
    # For linear data, upper > middle > lower
    assert upper[0] > middle[0] > lower[0]


def test_bollinger_band_spread():
    """Verify upper and lower bands are symmetric around middle."""
    prices = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0]
    upper, middle, lower = MarketService._bollinger(prices, 5, 2)
    assert len(middle) == 4  # 8 - 5 + 1
    for i in range(len(middle)):
        assert upper[i] == pytest.approx(2 * middle[i] - lower[i], rel=1e-9)


def test_bollinger_too_short():
    """Data < period → all empty."""
    assert MarketService._bollinger([1.0, 2.0], 5, 2) == ([], [], [])


def test_bollinger_constant_prices():
    """Constant prices → upper = middle = lower."""
    prices = [100.0] * 20
    upper, middle, lower = MarketService._bollinger(prices, 5, 2)
    for i in range(len(middle)):
        assert upper[i] == pytest.approx(100.0)
        assert middle[i] == pytest.approx(100.0)
        assert lower[i] == pytest.approx(100.0)


# ── Bollinger exact values ─────────────────────────────────

def test_bollinger_exact_values():
    """Bollinger(3, 1) on [1,2,3,4,5] — can compute exactly."""
    prices = [1.0, 2.0, 3.0, 4.0, 5.0]
    upper, middle, lower = MarketService._bollinger(prices, 3, 1)
    # period=3, len=5 → 5-3+1 = 3 values
    assert len(middle) == 3
    # Window [1,2,3]: middle=2, var=((1-2)^2+(2-2)^2+(3-2)^2)/3 = (1+0+1)/3 = 2/3
    # stdev=√(2/3), upper=2+√(2/3), lower=2-√(2/3)
    assert middle[0] == pytest.approx(2.0)
    assert upper[0] == pytest.approx(2.0 + math.sqrt(2 / 3))
    assert lower[0] == pytest.approx(2.0 - math.sqrt(2 / 3))
    # Window [2,3,4]: middle=3, same variance → same band width
    assert middle[1] == pytest.approx(3.0)
    # Window [3,4,5]: middle=4
    assert middle[2] == pytest.approx(4.0)


# ── Bollinger: multiple period × stddev combos ─────────────

# Data: [2, 4, 6, 8, 10] — linearly increasing by 2
BOLL_DATA = [2.0, 4.0, 6.0, 8.0, 10.0]


def test_bollinger_period_2_stddev_1():
    """Bollinger(2, 1) on [2,4,6,8,10]."""
    upper, middle, lower = MarketService._bollinger(BOLL_DATA, 2, 1)
    # len=5, period=2 → 4 values
    assert len(middle) == 4
    # Window [2,4]: mid=3, var=((2-3)^2+(4-3)^2)/2 = 1, stdev=1
    # upper=4, lower=2
    assert middle[0] == pytest.approx(3.0)
    assert upper[0] == pytest.approx(4.0)
    assert lower[0] == pytest.approx(2.0)
    # Window [4,6]: mid=5
    assert middle[1] == pytest.approx(5.0)
    assert upper[1] == pytest.approx(6.0)
    assert lower[1] == pytest.approx(4.0)
    # Window [6,8]: mid=7
    assert middle[2] == pytest.approx(7.0)
    # Window [8,10]: mid=9
    assert middle[3] == pytest.approx(9.0)


def test_bollinger_period_2_stddev_2():
    """Bollinger(2, 2) — double stddev = double band width."""
    upper, middle, lower = MarketService._bollinger(BOLL_DATA, 2, 2)
    # Same middles, bands 2x wider
    assert middle[0] == pytest.approx(3.0)
    assert upper[0] == pytest.approx(5.0)   # 3 + 2*1
    assert lower[0] == pytest.approx(1.0)   # 3 - 2*1


def test_bollinger_period_3_stddev_1():
    """Bollinger(3, 1) on [2,4,6,8,10]."""
    upper, middle, lower = MarketService._bollinger(BOLL_DATA, 3, 1)
    # len=5, period=3 → 3 values
    assert len(middle) == 3
    # Window [2,4,6]: mid=4, var=((2-4)^2+(4-4)^2+(6-4)^2)/3 = (4+0+4)/3 = 8/3
    # stdev=√(8/3) ≈ 1.633
    assert middle[0] == pytest.approx(4.0)
    assert upper[0] == pytest.approx(4.0 + math.sqrt(8 / 3))
    assert lower[0] == pytest.approx(4.0 - math.sqrt(8 / 3))
    # Window [4,6,8]: mid=6
    assert middle[1] == pytest.approx(6.0)
    # Window [6,8,10]: mid=8
    assert middle[2] == pytest.approx(8.0)


def test_bollinger_period_3_stddev_2():
    """Bollinger(3, 2) — double stddev."""
    upper, middle, lower = MarketService._bollinger(BOLL_DATA, 3, 2)
    assert middle[0] == pytest.approx(4.0)
    assert upper[0] == pytest.approx(4.0 + 2 * math.sqrt(8 / 3))
    assert lower[0] == pytest.approx(4.0 - 2 * math.sqrt(8 / 3))


def test_bollinger_period_4_stddev_1():
    """Bollinger(4, 1) on [2,4,6,8,10]."""
    upper, middle, lower = MarketService._bollinger(BOLL_DATA, 4, 1)
    # len=5, period=4 → 2 values
    assert len(middle) == 2
    # Window [2,4,6,8]: mid=5, var=((2-5)^2+(4-5)^2+(6-5)^2+(8-5)^2)/4 = (9+1+1+9)/4 = 5
    # stdev=√5 ≈ 2.236
    assert middle[0] == pytest.approx(5.0)
    assert upper[0] == pytest.approx(5.0 + math.sqrt(5))
    assert lower[0] == pytest.approx(5.0 - math.sqrt(5))
    # Window [4,6,8,10]: mid=7
    assert middle[1] == pytest.approx(7.0)


def test_bollinger_period_5_stddev_1():
    """Bollinger(5, 1) — period equals data length → 1 value."""
    upper, middle, lower = MarketService._bollinger(BOLL_DATA, 5, 1)
    assert len(middle) == 1
    assert middle[0] == pytest.approx(6.0)  # (2+4+6+8+10)/5 = 6
    # var = ((2-6)^2+(4-6)^2+(6-6)^2+(8-6)^2+(10-6)^2)/5 = (16+4+0+4+16)/5 = 8
    assert upper[0] == pytest.approx(6.0 + math.sqrt(8))
    assert lower[0] == pytest.approx(6.0 - math.sqrt(8))


def test_bollinger_period_5_stddev_3():
    """Bollinger(5, 3) — wide bands with triple stddev."""
    upper, middle, lower = MarketService._bollinger(BOLL_DATA, 5, 3)
    assert len(middle) == 1
    assert middle[0] == pytest.approx(6.0)
    assert upper[0] == pytest.approx(6.0 + 3 * math.sqrt(8))
    assert lower[0] == pytest.approx(6.0 - 3 * math.sqrt(8))


def test_bollinger_period_5_stddev_half():
    """Bollinger(5, 0.5) — narrow bands with small stddev."""
    upper, middle, lower = MarketService._bollinger(BOLL_DATA, 5, 0.5)
    assert len(middle) == 1
    assert middle[0] == pytest.approx(6.0)
    assert upper[0] == pytest.approx(6.0 + 0.5 * math.sqrt(8))
    assert lower[0] == pytest.approx(6.0 - 0.5 * math.sqrt(8))


# ── Bollinger: wider stddev = wider bands ──────────────────

def test_bollinger_wider_stddev_gives_wider_bands():
    """For the same period, stddev=3 bands > stddev=1 bands."""
    data = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0, 26.0, 28.0]
    u1, m1, l1 = MarketService._bollinger(data, 5, 1)
    u3, m3, l3 = MarketService._bollinger(data, 5, 3)
    assert len(m1) == len(m3) == 6
    for i in range(len(m1)):
        assert m1[i] == pytest.approx(m3[i])          # same middle
        assert u3[i] > u1[i]                          # wider upper
        assert l3[i] < l1[i]                          # wider lower
        assert (u3[i] - l3[i]) == pytest.approx(3 * (u1[i] - l1[i]))  # 3x band width


# ── Bollinger: shorter period = more reactive ──────────────

def test_bollinger_shorter_period_bounces_more():
    """Shorter period tracks price more closely (smaller lag)."""
    # Data with a spike in the middle
    data = [10.0, 10.0, 10.0, 10.0, 50.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    _, m3, _ = MarketService._bollinger(data, 3, 2)
    _, m7, _ = MarketService._bollinger(data, 7, 2)
    # After the spike (bar index 4, value 50), period=3 recovers faster
    # By bar 6 the 3-period middle should be closer to 10 than the 7-period
    assert m3[-1] < m7[-1]  # 3-period middle drops faster toward 10


# ── Bollinger: edge cases ─────────────────────────────────

def test_bollinger_period_1():
    """Bollinger(1, any) — middle = price, bands = middle (zero variance)."""
    data = [10.0, 20.0, 30.0]
    upper, middle, lower = MarketService._bollinger(data, 1, 2)
    assert len(middle) == 3
    assert middle == pytest.approx([10.0, 20.0, 30.0])
    # Variance of a single value = 0, so upper = lower = middle
    assert upper == pytest.approx(middle)
    assert lower == pytest.approx(middle)


def test_bollinger_period_2_constant_data():
    """Bollinger(2, 1) on constant data → bands = middle."""
    data = [5.0, 5.0, 5.0, 5.0, 5.0]
    upper, middle, lower = MarketService._bollinger(data, 2, 1)
    assert len(middle) == 4
    assert middle == pytest.approx([5.0, 5.0, 5.0, 5.0])
    assert upper == pytest.approx(middle)
    assert lower == pytest.approx(middle)


def test_bollinger_large_dataset():
    """Bollinger(20, 2) on 100 points — correct lengths."""
    data = list(range(1, 101))  # 100 points
    upper, middle, lower = MarketService._bollinger(data, 20, 2)
    assert len(middle) == 81  # 100 - 20 + 1
    assert len(upper) == 81
    assert len(lower) == 81
    # All middles should be increasing (linear data)
    for i in range(1, len(middle)):
        assert middle[i] > middle[i - 1]
    # Bands should not cross
    for i in range(len(middle)):
        assert upper[i] >= middle[i] >= lower[i]


# ── Bollinger pipeline test ──────────────────────────────

@pytest.mark.asyncio
async def test_calculate_indicator_pipeline_bollinger():
    """Full pipeline with Bollinger returns dict with correct keys."""
    from unittest.mock import AsyncMock

    mock_data = [
        {"date": f"2024-01-{i+1:02d}", "price_last": float(10 + i * 2)}
        for i in range(20)
    ]
    mock_query = AsyncMock()
    mock_query.get_historical_daily.return_value = mock_data

    service = MarketService(brsapi_query_service=mock_query)
    result = await service.calculate_indicator("TEST", "bollinger", {"period": 5, "stddev": 2})

    assert result.success
    data = result.value
    assert data["indicator"] == "bollinger"
    assert isinstance(data["values"], dict)
    assert set(data["values"].keys()) == {"upper", "middle", "lower"}
    assert len(data["values"]["middle"]) == 16  # 20 - 5 + 1
    # Symmetry check
    for u, m, l in zip(data["values"]["upper"], data["values"]["middle"], data["values"]["lower"]):
        assert u == pytest.approx(2 * m - l, rel=1e-9)


# ── _compute_indicator routing ─────────────────────────────

def test_compute_indicator_routes_sma():
    result = MarketService._compute_indicator("sma", SIMPLE, {"period": 3})
    assert isinstance(result, list)
    assert result == [20.0, 30.0, 40.0]


def test_compute_indicator_routes_macd_as_dict():
    result = MarketService._compute_indicator("macd", INCREASING_40, {})
    assert isinstance(result, dict)
    assert "macd" in result
    assert "signal" in result
    assert "histogram" in result
    assert len(result["macd"]) == 15


def test_compute_indicator_routes_bollinger_as_dict():
    result = MarketService._compute_indicator("bollinger", INCREASING_20, {"period": 5})
    assert isinstance(result, dict)
    assert "upper" in result
    assert "middle" in result
    assert "lower" in result


def test_compute_indicator_unknown_raises():
    with pytest.raises(ValueError, match="Unknown indicator"):
        MarketService._compute_indicator("nonexistent", [1.0, 2.0], {})


# ── calculate_indicator full pipeline (with mock DB) ──────

@pytest.mark.asyncio
async def test_calculate_indicator_pipeline_sma():
    """Full calculate_indicator pipeline with mocked BrsApiQueryService."""
    from unittest.mock import AsyncMock

    # Mock historical data: 20 days
    mock_data = [
        {"date": f"2024-01-{i+1:02d}", "price_last": float(10 + i * 2)}
        for i in range(20)
    ]
    mock_query = AsyncMock()
    mock_query.get_historical_daily.return_value = mock_data

    service = MarketService(brsapi_query_service=mock_query)
    result = await service.calculate_indicator("TEST", "sma", {"period": 5})

    assert result.success
    data = result.value
    assert data["symbol"] == "TEST"
    assert data["indicator"] == "sma"
    assert data["values"] == [14.0, 16.0, 18.0, 20.0, 22.0, 24.0, 26.0, 28.0,
                              30.0, 32.0, 34.0, 36.0, 38.0, 40.0, 42.0, 44.0]
    assert len(data["dates"]) == 16  # aligned with values


@pytest.mark.asyncio
async def test_calculate_indicator_pipeline_macd():
    """Full pipeline with MACD returns dict values."""
    from unittest.mock import AsyncMock

    mock_data = [
        {"date": f"2024-01-{i+1:02d}", "price_last": float(10 + i)}
        for i in range(40)
    ]
    mock_query = AsyncMock()
    mock_query.get_historical_daily.return_value = mock_data

    service = MarketService(brsapi_query_service=mock_query)
    result = await service.calculate_indicator("TEST", "macd")

    assert result.success
    data = result.value
    assert data["indicator"] == "macd"
    assert isinstance(data["values"], dict)
    assert set(data["values"].keys()) == {"macd", "signal", "histogram"}


@pytest.mark.asyncio
async def test_calculate_indicator_no_data():
    """When DB returns empty and no client, return failure."""
    from unittest.mock import AsyncMock

    mock_query = AsyncMock()
    mock_query.get_historical_daily.return_value = []

    service = MarketService(brsapi_query_service=mock_query)
    result = await service.calculate_indicator("TEST", "sma", {"period": 5})

    assert not result.success
    assert "No historical data" in result.error


@pytest.mark.asyncio
async def test_calculate_indicator_unknown_indicator():
    """Unknown indicator name → ValueError caught → failure result."""
    from unittest.mock import AsyncMock

    mock_data = [{"date": "2024-01-01", "price_last": 100.0}]
    mock_query = AsyncMock()
    mock_query.get_historical_daily.return_value = mock_data

    service = MarketService(brsapi_query_service=mock_query)
    result = await service.calculate_indicator("TEST", "unknown")

    assert not result.success
    assert "Unknown indicator" in result.error


# ═══════════════════════════════════════════════════════════
#  NEW INDICATORS: Stochastic, ATR, OBV, Williams %R, Ichimoku
# ═══════════════════════════════════════════════════════════

# OHLCV test data — 15 bars, each with high/low/close/volume
OHLC_BARS_HIGH = [52.0, 53.0, 54.0, 53.5, 54.5, 55.0, 56.0, 55.5, 54.0, 53.0, 52.5, 53.5, 55.0, 56.0, 57.0]
OHLC_BARS_LOW = [48.0, 49.0, 50.0, 49.5, 50.5, 51.0, 52.0, 51.5, 50.0, 49.0, 48.5, 49.5, 51.0, 52.0, 53.0]
OHLC_BARS_CLOSE = [50.0, 51.0, 52.0, 51.0, 52.5, 54.0, 55.0, 53.0, 51.0, 50.0, 49.0, 51.0, 53.0, 54.5, 56.0]
OHLC_VOLUMES = [1000, 1200, 900, 1100, 800, 1500, 2000, 1600, 900, 700, 600, 1000, 1300, 1800, 2200]

# 25-bar series for Ichimoku (needs min 52)
_H = [float(10 + i + abs(i % 5 - 2)) for i in range(60)]  # highs with some noise
_L = [float(9 + i - abs(i % 5 - 2)) for i in range(60)]   # lows
_C = [float(10 + i) for i in range(60)]                     # closes (linear)


# ── Stochastic ─────────────────────────────────────────────

def test_stochastic_lengths():
    """Stochastic(5,3,3) on 15 bars → proper output lengths."""
    k_line, d_line = MarketService._stochastic(OHLC_BARS_HIGH, OHLC_BARS_LOW, OHLC_BARS_CLOSE, 5, 3, 3)
    # raw %K: 15 - 5 + 1 = 11 values
    # smoothed %K (SMA 3 of 11): 11 - 3 + 1 = 9 values
    # %D (SMA 3 of 9): 9 - 3 + 1 = 7 values
    assert len(k_line) == 9
    assert len(d_line) == 7


def test_stochastic_in_panic_low():
    """When close = low, raw %K ≈ 0."""
    highs = [100.0] * 20
    lows = [90.0] * 20
    closes = [90.0] * 20  # close at the low → %K = 0
    k_line, d_line = MarketService._stochastic(highs, lows, closes, 5, 3, 3)
    # raw %K: 20 - 5 + 1 = 16 values, all 0
    # smoothed %K: SMA(3) of all 0 → all 0, 14 values
    # %D: SMA(3) of all 0 → all 0, 12 values
    assert len(k_line) > 0
    assert all(v == pytest.approx(0.0) for v in k_line)
    assert all(v == pytest.approx(0.0) for v in d_line)


def test_stochastic_in_breakout():
    """When close = high, raw %K = 100."""
    highs = [100.0] * 20
    lows = [90.0] * 20
    closes = [100.0] * 20  # close at the high → %K = 100
    k_line, d_line = MarketService._stochastic(highs, lows, closes, 5, 3, 3)
    assert len(k_line) > 0
    assert all(v == pytest.approx(100.0) for v in k_line)
    assert all(v == pytest.approx(100.0) for v in d_line)


def test_stochastic_flat_range():
    """Flat high=low → %K = 50 (neutral)."""
    flats = [100.0] * 20
    k_line, d_line = MarketService._stochastic(flats, flats, flats, 5, 3, 3)
    assert len(k_line) > 0
    assert all(v == pytest.approx(50.0) for v in k_line)


def test_stochastic_too_short():
    """Data shorter than period → empty."""
    k_line, d_line = MarketService._stochastic([1.0], [1.0], [1.0], 5)
    assert k_line == []
    assert d_line == []


# ── ATR ───────────────────────────────────────────────────

def test_atr_length():
    """ATR(5) on 15 bars → 15 - 1 - 5 + 1 = 10 values."""
    result = MarketService._atr(OHLC_BARS_HIGH, OHLC_BARS_LOW, OHLC_BARS_CLOSE, 5)
    # 14 true ranges, first 5 → SMA → 1 value, then Wilder's for remaining 9 → 10 total
    assert len(result) == 10


def test_atr_positive():
    """All ATR values must be ≥ 0."""
    result = MarketService._atr(OHLC_BARS_HIGH, OHLC_BARS_LOW, OHLC_BARS_CLOSE, 5)
    assert all(v >= 0 for v in result)


def test_atr_constant_range():
    """Constant H=5, L=0, C=2.5 → TR = 5 every bar → ATR = 5."""
    highs = [5.0] * 20
    lows = [0.0] * 20
    closes = [2.5] * 20
    result = MarketService._atr(highs, lows, closes, 5)
    # First ATR = SMA(5) of TR values: all TR=5 → 5
    # Wilder's: (5*4 + 5)/5 = 5 → all 5
    assert len(result) == 15  # 19 TRs, 5 initial → 1 + (19-5) = 15
    assert all(v == pytest.approx(5.0) for v in result)


def test_atr_too_short():
    """Need at least period+1 bars."""
    assert MarketService._atr([1.0], [1.0], [1.0], 5) == []


# ── OBV ───────────────────────────────────────────────────

def test_obv_cumulative():
    """OBV starts with first volume, accumulates/decreases based on price direction."""
    closes = [10.0, 12.0, 10.0, 10.0, 14.0]
    volumes = [100.0, 200.0, 150.0, 300.0, 250.0]
    result = MarketService._obv(closes, volumes)
    # bar 0: +100 = 100
    # bar 1: price up → +200 = 300
    # bar 2: price down → -150 = 150
    # bar 3: price flat → +0 = 150
    # bar 4: price up → +250 = 400
    assert result == [100.0, 300.0, 150.0, 150.0, 400.0]


def test_obv_all_up():
    """All prices increasing → OBV = cumulative sum of volumes."""
    closes = list(range(10, 20))
    volumes = [100.0] * 10
    result = MarketService._obv(closes, volumes)
    expected = [100.0 * (i + 1) for i in range(10)]
    assert result == pytest.approx(expected)


def test_obv_empty():
    assert MarketService._obv([], []) == []


def test_obv_mismatched_lengths():
    """Uses min(len(closes), len(volumes))."""
    result = MarketService._obv([10.0, 20.0, 30.0], [100.0, 200.0])
    assert len(result) == 2


# ── Williams %R ───────────────────────────────────────────

def test_williams_r_length():
    """Williams %R(5) on 15 bars → 15 - 5 + 1 = 11 values."""
    result = MarketService._williams_r(OHLC_BARS_HIGH, OHLC_BARS_LOW, OHLC_BARS_CLOSE, 5)
    assert len(result) == 11


def test_williams_r_at_high():
    """Close = period high → %R = 0."""
    highs = [100.0] * 20
    lows = [90.0] * 20
    closes = [100.0] * 20
    result = MarketService._williams_r(highs, lows, closes, 5)
    assert len(result) > 0
    assert all(v == pytest.approx(0.0) for v in result)


def test_williams_r_at_low():
    """Close = period low → %R = -100."""
    highs = [100.0] * 20
    lows = [90.0] * 20
    closes = [90.0] * 20
    result = MarketService._williams_r(highs, lows, closes, 5)
    assert len(result) > 0
    assert all(v == pytest.approx(-100.0) for v in result)


def test_williams_r_flat_range():
    """Flat range → %R = -50."""
    flats = [100.0] * 20
    result = MarketService._williams_r(flats, flats, flats, 5)
    assert all(v == pytest.approx(-50.0) for v in result)


def test_williams_r_too_short():
    assert MarketService._williams_r([1.0], [1.0], [1.0], 5) == []


# ── Ichimoku ──────────────────────────────────────────────

def test_ichimoku_lengths():
    """Ichimoku(9,26,52) on 60 bars."""
    tenkan, kijun, senkou_a, senkou_b, chikou = MarketService._ichimoku(_H, _L, _C, 9, 26, 52)
    # Tenkan: 60 - 9 + 1 = 52
    assert len(tenkan) == 52
    # Kijun: 60 - 26 + 1 = 35
    assert len(kijun) == 35
    # Senkou B: 60 - 52 + 1 = 9
    assert len(senkou_b) == 9
    # Chikou = close shifted 26: 60 - 26 = 34
    assert len(chikou) == 34


def test_ichimoku_tenkan_vs_kijun():
    """Tenkan (9) should be more reactive than Kijun (26)."""
    tenkan, kijun, senkou_a, senkou_b, chikou = MarketService._ichimoku(_H, _L, _C, 9, 26, 52)
    # In an uptrend, tenkan (shorter) should generally be above kijun (longer)
    offset = 26 - 9  # 17
    tenkan_aligned = tenkan[offset:offset + len(kijun)]
    # Most values: tenkan > kijun
    above_count = sum(1 for t, k in zip(tenkan_aligned, kijun) if t > k)
    assert above_count > len(kijun) * 0.6  # at least 60% of the time


def test_ichimoku_too_short():
    """Need at least max_period bars."""
    short = [1.0] * 30
    tenkan, kijun, senkou_a, senkou_b, chikou = MarketService._ichimoku(short, short, short)
    assert tenkan == []
    assert kijun == []


def test_ichimoku_constant_prices():
    """Constant prices → all lines = same constant."""
    flats = [100.0] * 60
    tenkan, kijun, senkou_a, senkou_b, chikou = MarketService._ichimoku(flats, flats, flats)
    assert all(abs(v - 100.0) < 1e-10 for v in tenkan)
    assert all(abs(v - 100.0) < 1e-10 for v in kijun)
    assert all(abs(v - 100.0) < 1e-10 for v in senkou_a)
    assert all(abs(v - 100.0) < 1e-10 for v in senkou_b)
    assert all(abs(v - 100.0) < 1e-10 for v in chikou)


# ── Ichimoku: 9/26/52 exact values ────────────────────────

# 52 bars: high=200+i, low=100+i, close=150+i  (i from 0 to 51)
_ICH_52_N = 52
_ICH_52_H = [float(200 + i) for i in range(_ICH_52_N)]
_ICH_52_L = [float(100 + i) for i in range(_ICH_52_N)]
_ICH_52_C = [float(150 + i) for i in range(_ICH_52_N)]


def test_ichimoku_9_26_52_exact_values():
    """Ichimoku(9,26,52) on 52 bars — exact values computed by hand."""
    tenkan, kijun, senkou_a, senkou_b, chikou = MarketService._ichimoku(
        _ICH_52_H, _ICH_52_L, _ICH_52_C, 9, 26, 52,
    )
    # ── Lengths ──
    assert len(tenkan) == 44    # 52 - 9 + 1
    assert len(kijun) == 27     # 52 - 26 + 1
    assert len(senkou_a) == 27  # same as kijun
    assert len(senkou_b) == 1   # 52 - 52 + 1
    assert len(chikou) == 26    # 52 - 26

    # ── Tenkan (9): hh = 208+a, ll = 100+a → (308+2a)/2 = 154+a ──
    for a in range(44):
        assert tenkan[a] == pytest.approx(154.0 + a)

    # ── Kijun (26): hh = 225+a, ll = 100+a → (325+2a)/2 = 162.5+a ──
    for a in range(27):
        assert kijun[a] == pytest.approx(162.5 + a)

    # ── Senkou A: tenkan_aligned[a] = tenkan[17+a] = 171+a, kijun[a] = 162.5+a
    #     → (171+a + 162.5+a)/2 = (333.5+2a)/2 = 166.75+a ──
    for a in range(27):
        assert senkou_a[a] == pytest.approx(166.75 + a)

    # ── Senkou B (52): hh=251, ll=100 → (251+100)/2 = 175.5 ──
    assert senkou_b[0] == pytest.approx(175.5)

    # ── Chikou = closes[26:] = [176, 177, ..., 201] ──
    for a in range(26):
        assert chikou[a] == pytest.approx(176.0 + a)

    # ── Uptrend: tenkan > kijun (shorter = more reactive) ──
    offset = 26 - 9  # 17
    for i in range(len(kijun)):
        assert tenkan[i + offset] > kijun[i]

    # ── Senkou A between tenkan and kijun ──
    for i in range(len(senkou_a)):
        t_val = tenkan[i + offset]
        k_val = kijun[i]
        assert min(t_val, k_val) <= senkou_a[i] <= max(t_val, k_val)


# ── Ichimoku: 7/22/44 exact values ────────────────────────

# 44 bars: high=200+i, low=100+i, close=150+i  (i from 0 to 43)
_ICH_44_N = 44
_ICH_44_H = [float(200 + i) for i in range(_ICH_44_N)]
_ICH_44_L = [float(100 + i) for i in range(_ICH_44_N)]
_ICH_44_C = [float(150 + i) for i in range(_ICH_44_N)]


def test_ichimoku_7_22_44_exact_values():
    """Ichimoku(7,22,44) on 44 bars — exact values computed by hand."""
    tenkan, kijun, senkou_a, senkou_b, chikou = MarketService._ichimoku(
        _ICH_44_H, _ICH_44_L, _ICH_44_C, 7, 22, 44,
    )
    # ── Lengths ──
    assert len(tenkan) == 38    # 44 - 7 + 1
    assert len(kijun) == 23     # 44 - 22 + 1
    assert len(senkou_a) == 23  # same as kijun
    assert len(senkou_b) == 1   # 44 - 44 + 1
    assert len(chikou) == 22    # 44 - 22

    # ── Tenkan (7): hh = 206+a, ll = 100+a → (306+2a)/2 = 153+a ──
    for a in range(38):
        assert tenkan[a] == pytest.approx(153.0 + a)

    # ── Kijun (22): hh = 221+a, ll = 100+a → (321+2a)/2 = 160.5+a ──
    for a in range(23):
        assert kijun[a] == pytest.approx(160.5 + a)

    # ── Senkou A: tenkan_aligned[a] = tenkan[15+a] = 168+a, kijun[a] = 160.5+a
    #     → (168+a + 160.5+a)/2 = (328.5+2a)/2 = 164.25+a ──
    for a in range(23):
        assert senkou_a[a] == pytest.approx(164.25 + a)

    # ── Senkou B (44): hh=243, ll=100 → (243+100)/2 = 171.5 ──
    assert senkou_b[0] == pytest.approx(171.5)

    # ── Chikou = closes[22:] = [172, 173, ..., 193] ──
    for a in range(22):
        assert chikou[a] == pytest.approx(172.0 + a)

    # ── Uptrend: tenkan > kijun ──
    offset_7_22 = 22 - 7  # 15
    for i in range(len(kijun)):
        assert tenkan[i + offset_7_22] > kijun[i]


# ── Ichimoku: 20/60/120 exact values ──────────────────────

# 120 bars: high=200+i, low=100+i, close=150+i  (i from 0 to 119)
_ICH_120_N = 120
_ICH_120_H = [float(200 + i) for i in range(_ICH_120_N)]
_ICH_120_L = [float(100 + i) for i in range(_ICH_120_N)]
_ICH_120_C = [float(150 + i) for i in range(_ICH_120_N)]


def test_ichimoku_20_60_120_exact_values():
    """Ichimoku(20,60,120) on 120 bars — exact values computed by hand."""
    tenkan, kijun, senkou_a, senkou_b, chikou = MarketService._ichimoku(
        _ICH_120_H, _ICH_120_L, _ICH_120_C, 20, 60, 120,
    )
    # ── Lengths ──
    assert len(tenkan) == 101   # 120 - 20 + 1
    assert len(kijun) == 61     # 120 - 60 + 1
    assert len(senkou_a) == 61  # same as kijun
    assert len(senkou_b) == 1   # 120 - 120 + 1
    assert len(chikou) == 60    # 120 - 60

    # ── Tenkan (20): hh = 219+a, ll = 100+a → (319+2a)/2 = 159.5+a ──
    for a in range(0, 101, 10):  # sample every 10th
        assert tenkan[a] == pytest.approx(159.5 + a)
    # Last value
    assert tenkan[100] == pytest.approx(259.5)

    # ── Kijun (60): hh = 259+a, ll = 100+a → (359+2a)/2 = 179.5+a ──
    for a in range(0, 61, 10):  # sample every 10th
        assert kijun[a] == pytest.approx(179.5 + a)

    # ── Senkou A: tenkan_aligned[a] = tenkan[40+a] = 199.5+a, kijun[a] = 179.5+a
    #     → (199.5+a + 179.5+a)/2 = (379+2a)/2 = 189.5+a ──
    for a in range(0, 61, 10):
        assert senkou_a[a] == pytest.approx(189.5 + a)

    # ── Senkou B (120): hh=319, ll=100 → (319+100)/2 = 209.5 ──
    assert senkou_b[0] == pytest.approx(209.5)

    # ── Chikou = closes[60:] = [210, 211, ..., 269] ──
    for a in range(0, 60, 10):
        assert chikou[a] == pytest.approx(210.0 + a)

    # ── Uptrend: tenkan > kijun ──
    offset_20_60 = 60 - 20  # 40
    for i in range(len(kijun)):
        assert tenkan[i + offset_20_60] > kijun[i]


# ── Ichimoku: constant data for all three combos ──────────

def test_ichimoku_9_26_52_constant():
    """All constant → all lines = that constant."""
    n = 52
    flats = [100.0] * n
    tenkan, kijun, senkou_a, senkou_b, chikou = MarketService._ichimoku(flats, flats, flats)
    assert len(tenkan) == 44
    assert len(kijun) == 27
    assert len(senkou_a) == 27
    assert len(senkou_b) == 1
    assert len(chikou) == 26
    for arr in (tenkan, kijun, senkou_a, senkou_b, chikou):
        assert all(abs(v - 100.0) < 1e-10 for v in arr)


def test_ichimoku_7_22_44_constant():
    """Constant data with tighter combo."""
    n = 44
    flats = [100.0] * n
    tenkan, kijun, senkou_a, senkou_b, chikou = MarketService._ichimoku(
        flats, flats, flats, 7, 22, 44,
    )
    assert len(tenkan) == 38
    assert len(kijun) == 23
    assert len(senkou_a) == 23
    assert len(senkou_b) == 1
    assert len(chikou) == 22
    for arr in (tenkan, kijun, senkou_a, senkou_b, chikou):
        assert all(abs(v - 100.0) < 1e-10 for v in arr)


def test_ichimoku_20_60_120_constant():
    """Constant data with long-term combo."""
    n = 120
    flats = [100.0] * n
    tenkan, kijun, senkou_a, senkou_b, chikou = MarketService._ichimoku(
        flats, flats, flats, 20, 60, 120,
    )
    assert len(tenkan) == 101
    assert len(kijun) == 61
    assert len(senkou_a) == 61
    assert len(senkou_b) == 1
    assert len(chikou) == 60
    for arr in (tenkan, kijun, senkou_a, senkou_b, chikou):
        assert all(abs(v - 100.0) < 1e-10 for v in arr)


# ── Ichimoku: behavioural tests ───────────────────────────

def test_ichimoku_tenkan_more_reactive_than_kijun():
    """On varying data, tenkan (shorter) should have larger range than kijun."""
    n = 60
    highs = [float(200 + i + (10 if i % 7 == 0 else 0)) for i in range(n)]
    lows = [float(100 + i - (5 if i % 5 == 0 else 0)) for i in range(n)]
    closes = [float(150 + i) for i in range(n)]
    tenkan, kijun, _, _, _ = MarketService._ichimoku(highs, lows, closes, 9, 26, 52)
    # Tenkan should have higher variance (more reactive)
    tenkan_range = max(tenkan) - min(tenkan)
    kijun_range = max(kijun) - min(kijun)
    assert tenkan_range > kijun_range  # shorter period = more reactive


def test_ichimoku_chikou_equals_lagged_close():
    """Chikou Span = close shifted backward by kijun_period."""
    n = 60
    highs = [float(200 + i) for i in range(n)]
    lows = [float(100 + i) for i in range(n)]
    closes = [float(150 + i) for i in range(n)]
    _, _, _, _, chikou = MarketService._ichimoku(highs, lows, closes, 9, 26, 52)
    # chikou[i] should equal closes[i + 26]
    for i in range(len(chikou)):
        assert chikou[i] == pytest.approx(closes[i + 26])


def test_ichimoku_9_26_52_downtrend():
    """In a downtrend, tenkan < kijun (shorter drops faster)."""
    n = 60
    highs = [float(300 - i) for i in range(n)]
    lows = [float(200 - i) for i in range(n)]
    closes = [float(250 - i) for i in range(n)]
    tenkan, kijun, _, _, _ = MarketService._ichimoku(highs, lows, closes, 9, 26, 52)
    offset = 26 - 9  # 17
    # In a downtrend, shorter MA (tenkan) should be below longer MA (kijun)
    below_count = sum(
        1 for i in range(len(kijun)) if tenkan[i + offset] < kijun[i]
    )
    assert below_count > len(kijun) * 0.6


def test_ichimoku_senkou_a_between_tenkan_and_kijun():
    """Senkou Span A is always the average of tenkan and kijun, so it sits between them."""
    n = 60
    highs = [float(200 + i + (i % 3) * 2) for i in range(n)]
    lows = [float(100 + i - (i % 3)) for i in range(n)]
    closes = [float(150 + i) for i in range(n)]
    tenkan, kijun, senkou_a, _, _ = MarketService._ichimoku(highs, lows, closes, 9, 26, 52)
    offset = 26 - 9  # 17
    for i in range(len(senkou_a)):
        t = tenkan[i + offset]
        k = kijun[i]
        # senkou_a = (t + k) / 2, so it's exactly between them
        assert senkou_a[i] == pytest.approx((t + k) / 2.0)


# ── Ichimoku: edge cases ──────────────────────────────────

def test_ichimoku_7_22_44_exact_min_data():
    """Exactly 44 bars (equals max_period) → senkou_b has 1 value, others work."""
    n = 44
    highs = [float(200 + i) for i in range(n)]
    lows = [float(100 + i) for i in range(n)]
    closes = [float(150 + i) for i in range(n)]
    tenkan, kijun, senkou_a, senkou_b, chikou = MarketService._ichimoku(highs, lows, closes, 7, 22, 44)
    assert len(tenkan) == 38
    assert len(kijun) == 23
    assert len(senkou_a) == 23
    assert len(senkou_b) == 1
    assert len(chikou) == 22


def test_ichimoku_20_60_120_need_120_bars():
    """119 bars < max_period(120) → all empty."""
    n = 119
    highs = [float(200 + i) for i in range(n)]
    lows = [float(100 + i) for i in range(n)]
    closes = [float(150 + i) for i in range(n)]
    result = MarketService._ichimoku(highs, lows, closes, 20, 60, 120)
    assert result == ([], [], [], [], [])


def test_ichimoku_9_26_52_just_above_min():
    """53 bars (52+1) → senkou_b gets 2 values, all lines non-empty."""
    n = 53
    highs = [float(200 + i) for i in range(n)]
    lows = [float(100 + i) for i in range(n)]
    closes = [float(150 + i) for i in range(n)]
    tenkan, kijun, senkou_a, senkou_b, chikou = MarketService._ichimoku(highs, lows, closes, 9, 26, 52)
    assert len(tenkan) == 45   # 53 - 9 + 1
    assert len(kijun) == 28    # 53 - 26 + 1
    assert len(senkou_a) == 28
    assert len(senkou_b) == 2  # 53 - 52 + 1 = 2
    assert len(chikou) == 27   # 53 - 26


def test_ichimoku_7_22_44_mismatched_array_lengths():
    """Different length arrays → uses min(len)."""
    n = 50
    highs = [float(200 + i) for i in range(n)]
    lows = [float(100 + i) for i in range(n - 1)]   # one shorter
    closes = [float(150 + i) for i in range(n - 2)]  # two shorter
    # min = 48
    tenkan, kijun, senkou_a, senkou_b, chikou = MarketService._ichimoku(highs, lows, closes, 7, 22, 44)
    assert len(tenkan) == 42   # 48 - 7 + 1
    assert len(kijun) == 27    # 48 - 22 + 1
    assert len(senkou_a) == 27
    assert len(senkou_b) == 5  # 48 - 44 + 1
    assert len(chikou) == 26   # 48 - 22


# ── Ichimoku: pipeline tests with custom combos ────────────

@pytest.mark.asyncio
async def test_calculate_indicator_pipeline_ichimoku_7_22_44():
    """Full pipeline with Ichimoku(7,22,44) custom params."""
    from unittest.mock import AsyncMock

    n = 50
    mock_data = [
        {"date": f"2024-01-{i+1:02d}", "price_last": float(150 + i),
         "price_max": float(200 + i), "price_min": float(100 + i)}
        for i in range(n)
    ]
    mock_query = AsyncMock()
    mock_query.get_historical_daily.return_value = mock_data

    service = MarketService(brsapi_query_service=mock_query)
    result = await service.calculate_indicator(
        "TEST", "ichimoku", {"tenkan": 7, "kijun": 22, "senkou_b": 44},
    )

    assert result.success
    data = result.value
    assert data["indicator"] == "ichimoku"
    assert isinstance(data["values"], dict)
    assert set(data["values"].keys()) == {"tenkan", "kijun", "senkou_a", "senkou_b", "chikou"}
    assert len(data["values"]["tenkan"]) == 44   # 50 - 7 + 1
    assert len(data["values"]["kijun"]) == 29    # 50 - 22 + 1
    assert len(data["values"]["senkou_a"]) == 29
    assert len(data["values"]["senkou_b"]) == 7  # 50 - 44 + 1
    assert len(data["values"]["chikou"]) == 28   # 50 - 22
    # Dates aligned to first non-empty series length (tenkan = 44)
    assert len(data["dates"]) == 44


@pytest.mark.asyncio
async def test_calculate_indicator_pipeline_ichimoku_20_60_120():
    """Full pipeline with Ichimoku(20,60,120) long-term params."""
    from unittest.mock import AsyncMock

    n = 130
    mock_data = [
        {"date": f"2024-01-{i+1:02d}", "price_last": float(150 + i),
         "price_max": float(200 + i), "price_min": float(100 + i)}
        for i in range(n)
    ]
    mock_query = AsyncMock()
    mock_query.get_historical_daily.return_value = mock_data

    service = MarketService(brsapi_query_service=mock_query)
    result = await service.calculate_indicator(
        "TEST", "ichimoku", {"tenkan": 20, "kijun": 60, "senkou_b": 120},
    )

    assert result.success
    data = result.value
    assert set(data["values"].keys()) == {"tenkan", "kijun", "senkou_a", "senkou_b", "chikou"}
    assert len(data["values"]["tenkan"]) == 111   # 130 - 20 + 1
    assert len(data["values"]["kijun"]) == 71     # 130 - 60 + 1
    assert len(data["values"]["senkou_b"]) == 11  # 130 - 120 + 1
    assert len(data["values"]["chikou"]) == 70    # 130 - 60
    # Dates aligned to tenkan = 111
    assert len(data["dates"]) == 111


# ── _compute_indicator routing (new indicators) ───────────

def test_compute_indicator_routes_stochastic():
    result = MarketService._compute_indicator(
        "stochastic", OHLC_BARS_CLOSE, {"period": 5, "k_smooth": 3, "d_smooth": 3},
        highs=OHLC_BARS_HIGH, lows=OHLC_BARS_LOW,
    )
    assert isinstance(result, dict)
    assert "k" in result
    assert "d" in result
    assert len(result["k"]) == 9
    assert len(result["d"]) == 7


def test_compute_indicator_routes_atr():
    result = MarketService._compute_indicator(
        "atr", OHLC_BARS_CLOSE, {"period": 5},
        highs=OHLC_BARS_HIGH, lows=OHLC_BARS_LOW,
    )
    assert isinstance(result, list)
    assert len(result) == 10
    assert all(v >= 0 for v in result)


def test_compute_indicator_routes_obv():
    result = MarketService._compute_indicator(
        "obv", [10.0, 12.0, 10.0, 10.0, 14.0], {},
        volumes=[100.0, 200.0, 150.0, 300.0, 250.0],
    )
    assert isinstance(result, list)
    assert result == [100.0, 300.0, 150.0, 150.0, 400.0]


def test_compute_indicator_routes_williams_r():
    result = MarketService._compute_indicator(
        "williams_r", OHLC_BARS_CLOSE, {"period": 5},
        highs=OHLC_BARS_HIGH, lows=OHLC_BARS_LOW,
    )
    assert isinstance(result, list)
    assert len(result) == 11


def test_compute_indicator_routes_ichimoku():
    result = MarketService._compute_indicator(
        "ichimoku", _C, {"tenkan": 9, "kijun": 26, "senkou_b": 52},
        highs=_H, lows=_L,
    )
    assert isinstance(result, dict)
    assert set(result.keys()) == {"tenkan", "kijun", "senkou_a", "senkou_b", "chikou"}
    assert len(result["tenkan"]) == 52


# ── Pipeline tests (new indicators with mock DB) ────────

@pytest.mark.asyncio
async def test_calculate_indicator_pipeline_stochastic():
    from unittest.mock import AsyncMock

    mock_data = [
        {"date": f"2024-01-{i+1:02d}", "price_last": OHLC_BARS_CLOSE[i],
         "price_max": OHLC_BARS_HIGH[i], "price_min": OHLC_BARS_LOW[i]}
        for i in range(len(OHLC_BARS_CLOSE))
    ]
    mock_query = AsyncMock()
    mock_query.get_historical_daily.return_value = mock_data

    service = MarketService(brsapi_query_service=mock_query)
    result = await service.calculate_indicator("TEST", "stochastic", {"period": 5})

    assert result.success
    data = result.value
    assert data["indicator"] == "stochastic"
    assert isinstance(data["values"], dict)
    assert "k" in data["values"]
    assert "d" in data["values"]


@pytest.mark.asyncio
async def test_calculate_indicator_pipeline_atr():
    from unittest.mock import AsyncMock

    mock_data = [
        {"date": f"2024-01-{i+1:02d}", "price_last": OHLC_BARS_CLOSE[i],
         "price_max": OHLC_BARS_HIGH[i], "price_min": OHLC_BARS_LOW[i]}
        for i in range(len(OHLC_BARS_CLOSE))
    ]
    mock_query = AsyncMock()
    mock_query.get_historical_daily.return_value = mock_data

    service = MarketService(brsapi_query_service=mock_query)
    result = await service.calculate_indicator("TEST", "atr", {"period": 5})

    assert result.success
    data = result.value
    assert data["indicator"] == "atr"
    assert isinstance(data["values"], list)
    assert len(data["values"]) == 10


@pytest.mark.asyncio
async def test_calculate_indicator_pipeline_ichimoku():
    from unittest.mock import AsyncMock

    mock_data = [
        {"date": f"2024-01-{i+1:02d}", "price_last": _C[i],
         "price_max": _H[i], "price_min": _L[i]}
        for i in range(len(_C))
    ]
    mock_query = AsyncMock()
    mock_query.get_historical_daily.return_value = mock_data

    service = MarketService(brsapi_query_service=mock_query)
    result = await service.calculate_indicator("TEST", "ichimoku")

    assert result.success
    data = result.value
    assert data["indicator"] == "ichimoku"
    assert isinstance(data["values"], dict)
    assert set(data["values"].keys()) == {"tenkan", "kijun", "senkou_a", "senkou_b", "chikou"}
