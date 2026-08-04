"""pytest-benchmark suite for all 10 MarketService indicators on 5 000 OHLCV bars."""

from __future__ import annotations

import random

from services.market_service import MarketService

# ── 5 000 OHLCV bars (seeded for reproducibility) ────────

random.seed(42)
_N = 5_000

prices: list[float] = []
highs: list[float] = []
lows: list[float] = []
volumes: list[float] = []

pr = 1000.0
for _ in range(_N):
    chg = random.gauss(0, 2.0)
    rng = abs(random.gauss(0, 1.0))
    c = pr * (1 + chg / 100)
    h = c + rng
    low = c - rng
    v = random.randint(1_000_000, 50_000_000)
    prices.append(c)
    highs.append(h)
    lows.append(low)
    volumes.append(float(v))
    pr = c


# ═══════════════════════════════════════════════════════════
# SMA
# ═══════════════════════════════════════════════════════════


def test_bench_sma(benchmark) -> None:
    benchmark(MarketService._sma, prices, 14)


def test_bench_sma_50(benchmark) -> None:
    benchmark(MarketService._sma, prices, 50)


def test_bench_sma_200(benchmark) -> None:
    benchmark(MarketService._sma, prices, 200)


# ═══════════════════════════════════════════════════════════
# EMA
# ═══════════════════════════════════════════════════════════


def test_bench_ema(benchmark) -> None:
    benchmark(MarketService._ema, prices, 14)


def test_bench_ema_50(benchmark) -> None:
    benchmark(MarketService._ema, prices, 50)


# ═══════════════════════════════════════════════════════════
# RSI
# ═══════════════════════════════════════════════════════════


def test_bench_rsi(benchmark) -> None:
    benchmark(MarketService._rsi, prices, 14)


def test_bench_rsi_9(benchmark) -> None:
    benchmark(MarketService._rsi, prices, 9)


# ═══════════════════════════════════════════════════════════
# MACD
# ═══════════════════════════════════════════════════════════


def test_bench_macd(benchmark) -> None:
    benchmark(MarketService._macd, prices, 12, 26, 9)


def test_bench_macd_tight(benchmark) -> None:
    benchmark(MarketService._macd, prices, 5, 13, 5)


def test_bench_macd_long(benchmark) -> None:
    benchmark(MarketService._macd, prices, 20, 50, 10)


# ═══════════════════════════════════════════════════════════
# Bollinger
# ═══════════════════════════════════════════════════════════


def test_bench_bollinger(benchmark) -> None:
    benchmark(MarketService._bollinger, prices, 20, 2)


def test_bench_bollinger_50(benchmark) -> None:
    benchmark(MarketService._bollinger, prices, 50, 2)


# ═══════════════════════════════════════════════════════════
# Stochastic
# ═══════════════════════════════════════════════════════════


def test_bench_stochastic(benchmark) -> None:
    benchmark(MarketService._stochastic, highs, lows, prices, 14, 3, 3)


# ═══════════════════════════════════════════════════════════
# ATR
# ═══════════════════════════════════════════════════════════


def test_bench_atr(benchmark) -> None:
    benchmark(MarketService._atr, highs, lows, prices, 14)


# ═══════════════════════════════════════════════════════════
# OBV
# ═══════════════════════════════════════════════════════════


def test_bench_obv(benchmark) -> None:
    benchmark(MarketService._obv, prices, volumes)


# ═══════════════════════════════════════════════════════════
# Williams %R
# ═══════════════════════════════════════════════════════════


def test_bench_williams_r(benchmark) -> None:
    benchmark(MarketService._williams_r, highs, lows, prices, 14)


# ═══════════════════════════════════════════════════════════
# Ichimoku
# ═══════════════════════════════════════════════════════════


def test_bench_ichimoku(benchmark) -> None:
    benchmark(MarketService._ichimoku, highs, lows, prices, 9, 26, 52)


# ═══════════════════════════════════════════════════════════
# _compute_indicator routing
# ═══════════════════════════════════════════════════════════


def test_bench_compute_routing(benchmark) -> None:
    benchmark(MarketService._compute_indicator, "sma", prices, {"period": 14})
