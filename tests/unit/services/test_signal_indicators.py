"""RSI/ATR keep their exact values across all history lengths.

``_compute_rsi``/``_compute_atr`` delegate to ``core.indicators`` which uses
Wilder's exponential smoothing (alpha = 1/period): seed the first *period*
values with a simple average, then smooth every subsequent bar.  These
reference functions mirror that algorithm exactly so a future refactor of
either site cannot silently drift the numbers.
"""

from __future__ import annotations

import random

import pytest

from services.multi_market_signal_engine import _compute_atr, _compute_rsi

PERIOD = 14


def _reference_rsi(closes: list[float], period: int = PERIOD) -> float | None:
    """Wilder's-smoothed RSI — mirrors core.indicators.compute_rsi."""
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for g, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss < 1e-10:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _reference_atr(
    highs: list[float], lows: list[float], closes: list[float], period: int = PERIOD
) -> float | None:
    """Wilder's-smoothed ATR — mirrors core.indicators.compute_atr."""
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
    if len(trs) < period:
        return None
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr


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
