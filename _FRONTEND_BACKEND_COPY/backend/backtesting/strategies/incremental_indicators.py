"""Incremental Indicators — streaming computation to prevent Look-Ahead Bias.

All indicators are computed only from data available at time t (not future data).
Each call to update() uses only the current bar and the history window.

Critical: In backtesting, indicators must be computed incrementally.
Pre-computed indicators on the full dataset introduce look-ahead bias.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BarFeatures:
    """Features computed from a single bar + its lookback window."""

    timestamp: Any = None

    # Price
    close: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    last: float = 0.0

    # Moving Averages
    sma_5: float = 0.0
    sma_10: float = 0.0
    sma_20: float = 0.0
    ema_12: float = 0.0
    ema_26: float = 0.0

    # Momentum
    rsi_14: float = 50.0
    macd: float = 0.0
    macd_signal: float = 0.0
    macd_histogram: float = 0.0

    # Volatility
    atr_14: float = 0.0
    bollinger_upper: float = 0.0
    bollinger_lower: float = 0.0
    bollinger_mid: float = 0.0
    volatility_20: float = 0.0

    # Volume
    volume_sma_20: float = 0.0
    volume_ratio: float = 1.0  # volume / volume_sma_20
    obv: float = 0.0

    # Returns
    return_1d: float = 0.0
    return_5d: float = 0.0
    return_10d: float = 0.0
    return_20d: float = 0.0

    # CLV (Close Location Value)
    clv: float = 0.0
    clv_n: float = 0.5

    # Recovery
    recovery: float = 0.5

    def to_dict(self) -> dict[str, float]:
        """Convert to dict for strategy consumption."""
        result = {}
        for k, v in self.__dict__.items():
            if k.startswith("_"):
                continue
            if isinstance(v, (int, float)):
                result[k] = v
        return result


class IncrementalIndicators:
    """Computes indicators incrementally from a sliding window.

    Usage:
        indicators = IncrementalIndicators(max_window=60)
        for bar in data:
            features = indicators.update(bar)
            orders = strategy.on_bar(bar, features)
    """

    def __init__(self, max_window: int = 60) -> None:
        self._max_window = max_window
        self._closes: deque[float] = deque(maxlen=max_window)
        self._highs: deque[float] = deque(maxlen=max_window)
        self._lows: deque[float] = deque(maxlen=max_window)
        self._opens: deque[float] = deque(maxlen=max_window)
        self._volumes: deque[float] = deque(maxlen=max_window)
        self._lasts: deque[float] = deque(maxlen=max_window)

        # EMA state
        self._ema12: float | None = None
        self._ema26: float | None = None
        self._macd_signal: float | None = None

        # OBV state
        self._obv: float = 0.0
        self._prev_close: float = 0.0

        # RSI state
        self._avg_gain: float = 0.0
        self._avg_loss: float = 0.0
        self._rsi_initialized: bool = False

        self._count: int = 0

    def update(self, bar: dict[str, Any]) -> BarFeatures:
        """Update with a new bar and return features computed ONLY from past data."""
        c = bar.get("price_close", bar.get("close", 0.0))
        o = bar.get("price_open", bar.get("open", 0.0))
        h = bar.get("price_high", bar.get("high", 0.0))
        low = bar.get("price_low", bar.get("low", 0.0))
        v = bar.get("volume", 0.0)
        last = bar.get("price_last", c)

        self._closes.append(c)
        self._highs.append(h)
        self._lows.append(low)
        self._opens.append(o)
        self._volumes.append(v)
        self._lasts.append(last)
        self._count += 1

        feat = BarFeatures(
            timestamp=bar.get("timestamp"),
            close=c,
            open=o,
            high=h,
            low=low,
            last=last,
        )

        closes = np.array(self._closes)
        highs = np.array(self._highs)
        lows = np.array(self._lows)
        volumes = np.array(self._volumes)

        # --- Moving Averages ---
        feat.sma_5 = self._sma(closes, 5)
        feat.sma_10 = self._sma(closes, 10)
        feat.sma_20 = self._sma(closes, 20)

        self._ema12 = self._update_ema(closes, 12, self._ema12)
        self._ema26 = self._update_ema(closes, 26, self._ema26)
        feat.ema_12 = self._ema12 or c
        feat.ema_26 = self._ema26 or c

        # --- MACD ---
        feat.macd = feat.ema_12 - feat.ema_26
        self._macd_signal = self._update_ema_from_val(feat.macd, 9, self._macd_signal)
        feat.macd_signal = self._macd_signal or 0.0
        feat.macd_histogram = feat.macd - feat.macd_signal

        # --- RSI ---
        feat.rsi_14 = self._update_rsi(closes, 14)

        # --- ATR ---
        feat.atr_14 = self._atr(highs, lows, closes, 14)

        # --- Bollinger ---
        if len(closes) >= 20:
            sma20 = float(np.mean(closes[-20:]))
            std20 = float(np.std(closes[-20:], ddof=1))
            feat.bollinger_mid = sma20
            feat.bollinger_upper = sma20 + 2 * std20
            feat.bollinger_lower = sma20 - 2 * std20
        elif len(closes) > 0:
            feat.bollinger_mid = float(np.mean(closes))
            feat.bollinger_upper = feat.bollinger_mid
            feat.bollinger_lower = feat.bollinger_mid

        # --- Volatility ---
        if len(closes) >= 2:
            returns = np.diff(closes) / closes[:-1]
            feat.volatility_20 = float(np.std(returns[-20:], ddof=1) * np.sqrt(252)) if len(returns) >= 2 else 0.0

        # --- Volume ---
        feat.volume_sma_20 = float(np.mean(volumes[-20:])) if len(volumes) > 0 else 0.0
        feat.volume_ratio = v / feat.volume_sma_20 if feat.volume_sma_20 > 0 else 1.0

        # --- OBV ---
        if self._prev_close > 0:
            if c > self._prev_close:
                self._obv += v
            elif c < self._prev_close:
                self._obv -= v
        feat.obv = self._obv
        self._prev_close = c

        # --- Returns ---
        feat.return_1d = self._return(closes, 1)
        feat.return_5d = self._return(closes, 5)
        feat.return_10d = self._return(closes, 10)
        feat.return_20d = self._return(closes, 20)

        # --- CLV ---
        r = h - low
        feat.clv = ((c - low) - (h - c)) / r if r > 0 else 0.0
        feat.clv_n = (feat.clv + 1) / 2

        # --- Recovery ---
        feat.recovery = (c - low) / r if r > 0 else 0.5

        return feat

    def reset(self) -> None:
        """Reset all state for a new backtest."""
        self._closes.clear()
        self._highs.clear()
        self._lows.clear()
        self._opens.clear()
        self._volumes.clear()
        self._lasts.clear()
        self._ema12 = None
        self._ema26 = None
        self._macd_signal = None
        self._obv = 0.0
        self._prev_close = 0.0
        self._avg_gain = 0.0
        self._avg_loss = 0.0
        self._rsi_initialized = False
        self._count = 0

    @staticmethod
    def _sma(arr: np.ndarray, period: int) -> float:
        if len(arr) < period:
            return float(arr[-1]) if len(arr) > 0 else 0.0
        return float(np.mean(arr[-period:]))

    @staticmethod
    def _update_ema(arr: np.ndarray, period: int, prev_ema: float | None) -> float:
        if len(arr) == 0:
            return 0.0
        if prev_ema is None:
            return float(np.mean(arr[-period:])) if len(arr) >= period else float(arr[-1])
        alpha = 2.0 / (period + 1)
        return alpha * float(arr[-1]) + (1 - alpha) * prev_ema

    @staticmethod
    def _update_ema_from_val(value: float, period: int, prev_ema: float | None) -> float:
        if prev_ema is None:
            return value
        alpha = 2.0 / (period + 1)
        return alpha * value + (1 - alpha) * prev_ema

    def _update_rsi(self, closes: np.ndarray, period: int = 14) -> float:
        if len(closes) < 2:
            return 50.0

        change = float(closes[-1] - closes[-2])
        gain = max(change, 0.0)
        loss = max(-change, 0.0)

        if not self._rsi_initialized and len(closes) >= period + 1:
            changes = np.diff(closes[-(period + 1) :])
            gains = np.maximum(changes, 0)
            losses = np.maximum(-changes, 0)
            self._avg_gain = float(np.mean(gains))
            self._avg_loss = float(np.mean(losses))
            self._rsi_initialized = True
        elif self._rsi_initialized:
            self._avg_gain = (self._avg_gain * (period - 1) + gain) / period
            self._avg_loss = (self._avg_loss * (period - 1) + loss) / period

        if self._avg_loss == 0:
            return 100.0 if self._avg_gain > 0 else 50.0
        rs = self._avg_gain / self._avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
        if len(closes) < 2:
            return 0.0
        trs = []
        for i in range(1, len(highs)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            trs.append(tr)
        if not trs:
            return 0.0
        recent = trs[-period:]
        return float(np.mean(recent))

    @staticmethod
    def _return(closes: np.ndarray, period: int) -> float:
        if len(closes) <= period:
            return 0.0
        prev = closes[-period - 1]
        return float((closes[-1] - prev) / prev) if prev > 0 else 0.0
