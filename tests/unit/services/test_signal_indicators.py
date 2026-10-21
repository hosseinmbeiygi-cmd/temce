"""RSI/ATR keep their exact values after only scanning the bars they use.

``_compute_rsi``/``_compute_atr`` used to walk the whole price history (thousands
of bars per symbol per timeframe) and then keep just the last ``period`` values.
They now slice the tail first. These tests pin the numbers to a reference copy of
the original loop so the speed-up cannot drift the indicator values.
"""

from __future__ import annotations

import random

import pytest

from services.multi_market_signal_engine import _compute_atr, _compute_rsi

PERIOD = 14


def _reference_rsi(closes: list[float], period: int = PERIOD) -> float | None:
    """Verbatim copy of the pre-optimisation implementation."""
    if len(closes) < period + 1:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss < 1e-10:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _reference_atr(
    highs: list[float], lows: list[float], closes: list[float], period: int = PERIOD
) -> float | None:
    if len(closes) < period + 1:
        return None
    trs: list[float] = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    return sum(trs[-period:]) / period


def _series(n: int, seed: int = 7) -> tuple[list[float], list[float], list[float]]:
    rng = random.Random(seed)
    closes = [1000.0]
    for _ in range(n - 1):
        closes.append(max(1.0, closes[-1] + rng.uniform(-15, 15)))
    highs = [c + rng.uniform(0, 10) for c in closes]
    lows = [c - rng.uniform(0, 10) for c in closes]
    return highs, lows, closes


@pytest.mark.parametrize("n", [15, 16, 60, 500, 5_000, 20_000])
def test_rsi_matches_reference(n: int) -> None:
    _, _, closes = _series(n)
    assert _compute_rsi(closes) == _reference_rsi(closes)


@pytest.mark.parametrize("n", [15, 16, 60, 500, 5_000, 20_000])
def test_atr_matches_reference(n: int) -> None:
    highs, lows, closes = _series(n)
    assert _compute_atr(highs, lows, closes) == _reference_atr(highs, lows, closes)


def test_flat_series_returns_100_rsi() -> None:
    closes = [4200.0] * 40
    assert _compute_rsi(closes) == 100.0
    assert _compute_rsi(closes) == _reference_rsi(closes)


def test_short_series_returns_none() -> None:
    closes = [100.0] * 14  # exactly period, one bar short of the minimum
    assert _compute_rsi(closes) is None
    assert _compute_atr(closes, closes, closes) is None


def test_monotonic_rise_and_fall() -> None:
    rising = [float(i) for i in range(1, 200)]
    falling = list(reversed(rising))
    assert _compute_rsi(rising) == _reference_rsi(rising)
    assert _compute_rsi(falling) == _reference_rsi(falling)
    assert _compute_rsi(falling) == pytest.approx(0.0, abs=1e-9)
