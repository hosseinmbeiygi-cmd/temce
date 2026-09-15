"""Unified technical indicator calculations.

All technical indicators used across the codebase are defined here to ensure
consistency, avoid duplication, and enable single-point testing.

Indicators:
    - RSI (Relative Strength Index) with Wilder's smoothing
    - ATR (Average True Range) with Wilder's smoothing
    - MACD (Moving Average Convergence Divergence) with proper EMA
    - Trend Strength (ADX-like directional movement)
    - Volatility (annualized standard deviation of returns)
    - EMA (Exponential Moving Average)
    - SMA (Simple Moving Average)
"""

from __future__ import annotations

import numpy as np

# ── Core Moving Averages ──────────────────────────────────────────────────────


def compute_sma(values: list[float], period: int) -> float:
    """Simple Moving Average of the last *period* values."""
    if not values or period <= 0:
        return 0.0
    window = values[-period:]
    return sum(window) / len(window)


def compute_ema(values: list[float], period: int) -> float:
    """Exponential Moving Average with standard smoothing factor alpha = 2 / (period + 1).

    The first EMA value is seeded with the SMA of the first *period* values.
    """
    if not values or period <= 0:
        return 0.0
    if len(values) < period:
        return sum(values) / len(values)

    alpha = 2.0 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = alpha * v + (1 - alpha) * ema
    return ema


def compute_ema_series(values: list[float], period: int) -> list[float]:
    """Full EMA series (one value per input point, starting from index *period-1*)."""
    if not values or period <= 0 or len(values) < period:
        return []

    alpha = 2.0 / (period + 1)
    ema_values: list[float] = []
    ema = sum(values[:period]) / period
    ema_values.append(ema)
    for v in values[period:]:
        ema = alpha * v + (1 - alpha) * ema
        ema_values.append(ema)
    return ema_values


# ── RSI (Wilder's Smoothing) ──────────────────────────────────────────────────


def compute_rsi(closes: list[float], period: int = 14) -> float:
    """Relative Strength Index using Wilder's smoothing (industry standard).

    Wilder's smoothing is an EMA with alpha = 1 / period, which gives
    more weight to the most recent observation while still smoothing
    over the full lookback window.

    Returns 50.0 (neutral) when insufficient data is available.
    Returns 100.0 when there are no losses (all gains).
    """
    if len(closes) < period + 1:
        return 50.0

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]

    # Seed: simple average of first *period* values
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Wilder's smoothing: alpha = 1 / period (strict zip — gains/losses same length by construction)
    for g, loss in zip(gains[period:], losses[period:], strict=True):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss < 1e-10:
        return 100.0

    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


# ── ATR (Wilder's Smoothing) ─────────────────────────────────────────────────


def compute_atr(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
) -> float | None:
    """Average True Range using Wilder's smoothing.

    True Range = max(high - low, |high - prev_close|, |low - prev_close|).
    ATR uses the same Wilder's smoothing as RSI for consistency.

    Returns None when insufficient data is available.
    """
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

    # Seed with simple average
    atr = sum(trs[:period]) / period

    # Wilder's smoothing
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period

    return atr


# ── MACD (Proper EMA) ───────────────────────────────────────────────────────


def compute_macd(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> dict[str, float]:
    """MACD with proper Exponential Moving Averages.

    Returns a dict with:
        - macd_line: the MACD line (EMA_fast - EMA_slow)
        - signal_line: the signal line (EMA of MACD line)
        - histogram: MACD - signal
        - direction: 1.0 (bullish), -1.0 (bearish), 0.0 (neutral)
    """
    if len(closes) < slow + signal_period:
        return {
            "macd_line": 0.0,
            "signal_line": 0.0,
            "histogram": 0.0,
            "direction": 0.0,
        }

    # Compute EMA series for fast and slow
    fast_ema_series = compute_ema_series(closes, fast)
    slow_ema_series = compute_ema_series(closes, slow)

    # Align: slow series starts at index slow-1, fast at fast-1
    # MACD line starts where both EMAs exist
    offset = slow - fast  # how many more points slow needs
    macd_values = [fast_ema_series[offset + i] - slow_ema_series[i] for i in range(len(slow_ema_series))]

    if not macd_values:
        return {
            "macd_line": 0.0,
            "signal_line": 0.0,
            "histogram": 0.0,
            "direction": 0.0,
        }

    macd_line = macd_values[-1]

    # Signal line = EMA of MACD values
    if len(macd_values) >= signal_period:
        signal_ema = compute_ema(macd_values, signal_period)
    else:
        signal_ema = sum(macd_values) / len(macd_values)

    histogram = macd_line - signal_ema

    if macd_line > signal_ema:
        direction = 1.0
    elif macd_line < signal_ema:
        direction = -1.0
    else:
        direction = 0.0

    return {
        "macd_line": macd_line,
        "signal_line": signal_ema,
        "histogram": histogram,
        "direction": direction,
    }


def compute_macd_signal(closes: list[float]) -> float:
    """Simplified MACD direction signal: 1 = bullish, -1 = bearish, 0 = neutral."""
    return compute_macd(closes)["direction"]


# ── Trend Strength (ADX-like) ────────────────────────────────────────────────


def compute_trend_strength(closes: list[float], period: int = 14) -> float:
    """ADX-like trend strength: how directional vs. choppy the price action is.

    Returns 0.0 to 1.0:
        - 0.0 = perfectly choppy (equal up and down days)
        - 1.0 = perfectly directional (all days moving the same direction)

    Uses directional movement counting (percentage of days moving in the
    dominant direction), scaled by 1.5 for a reasonable spread.
    """
    if len(closes) < period + 1:
        return 0.5

    up_days = 0
    down_days = 0
    for i in range(1, period + 1):
        if closes[-i] > closes[-i - 1]:
            up_days += 1
        elif closes[-i] < closes[-i - 1]:
            down_days += 1

    total = up_days + down_days
    if total == 0:
        return 0.5

    strength = abs(up_days - down_days) / total
    return min(1.0, strength * 1.5)


# ── Volatility ──────────────────────────────────────────────────────────────


def compute_volatility_regime(
    closes: list[float],
    period: int = 20,
    scale: float = 20.0,
) -> float:
    """Annualized volatility regime score (0-1).

    Uses the standard deviation of log returns over the lookback window,
    scaled to a 0-1 range. The scale parameter controls the sensitivity:
    a scale of 20.0 maps 5% std to the maximum (1.0).

    Lower values indicate calmer markets; higher values indicate turbulence.
    """
    if len(closes) < period + 1:
        return 0.5

    returns = [(closes[i] - closes[i - 1]) / max(closes[i - 1], 0.001) for i in range(-period, 0) if closes[i - 1] > 0]
    if not returns:
        return 0.5

    vol = float(np.std(returns))
    return float(min(1.0, vol * scale))


# ── Data Quality ─────────────────────────────────────────────────────────────


def compute_data_quality_score(
    total_fields: int = 0,
    missing_fields: int = 0,
    total_price_points: int = 0,
    min_price_points: int = 20,
) -> float:
    """Compute a 0-1 data quality score based on field completeness and price history.

    The score is the product of two sub-scores:
        - Field completeness: 1 - (missing / total)
        - Price history sufficiency: min(1.0, actual_points / min_points)

    When no field metadata is provided, returns a conservative 0.5.
    """
    if total_fields <= 0 and total_price_points <= 0:
        return 0.5

    field_score = 1.0
    if total_fields > 0:
        field_score = max(0.0, 1.0 - (missing_fields / max(total_fields, 1)))

    history_score = 1.0
    if min_price_points > 0:
        history_score = min(1.0, total_price_points / min_price_points)

    return round(field_score * history_score, 3)
