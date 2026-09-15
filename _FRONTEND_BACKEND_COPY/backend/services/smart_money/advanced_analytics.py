"""Advanced Analytics Module — Technical indicators, pattern recognition, and trend analysis.

Provides:
- Technical indicators (RSI, MACD, Bollinger Bands, ATR, OBV, VWAP)
- Candlestick pattern detection
- Support/Resistance levels
- Trend strength and direction
- Volatility analysis
- Volume profile
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class TechnicalIndicators:
    """Computed technical indicators for a symbol."""

    rsi_14: float = 0.0
    rsi_7: float = 0.0
    macd_line: float = 0.0
    macd_signal: float = 0.0
    macd_histogram: float = 0.0
    bb_upper: float = 0.0
    bb_middle: float = 0.0
    bb_lower: float = 0.0
    bb_width: float = 0.0
    bb_pct: float = 0.0
    atr_14: float = 0.0
    obv: float = 0.0
    obv_slope: float = 0.0
    vwap: float = 0.0
    ema_9: float = 0.0
    ema_21: float = 0.0
    ema_50: float = 0.0
    sma_20: float = 0.0
    sma_50: float = 0.0
    sma_200: float = 0.0
    stochastic_k: float = 0.0
    stochastic_d: float = 0.0
    adx: float = 0.0
    cci: float = 0.0
    mfi: float = 0.0
    williams_r: float = 0.0


@dataclass
class PatternSignal:
    """Detected candlestick or chart pattern."""

    pattern: str
    direction: str  # bullish, bearish, neutral
    confidence: float
    description: str
    bar_index: int = 0


@dataclass
class SupportResistance:
    """Support and resistance level."""

    level: float
    type: str  # support, resistance
    strength: float  # 0-1, how many times tested
    last_test_index: int = 0


@dataclass
class TrendAnalysis:
    """Trend analysis results."""

    direction: str  # up, down, sideways
    strength: float  # 0-1
    duration_bars: int = 0
    slope: float = 0.0
    acceleration: float = 0.0


@dataclass
class VolatilityAnalysis:
    """Volatility analysis results."""

    current: float = 0.0
    historical_avg: float = 0.0
    percentile: float = 0.0  # where current vol ranks historically
    regime: str = "normal"  # low, normal, high, extreme
    atr_pct: float = 0.0  # ATR as % of price


@dataclass
class VolumeProfile:
    """Volume profile analysis."""

    poc_price: float = 0.0  # Point of Control
    poc_volume: float = 0.0
    value_area_high: float = 0.0
    value_area_low: float = 0.0
    volume_trend: str = "neutral"  # increasing, decreasing, neutral
    accumulation_distribution: float = 0.0


@dataclass
class AdvancedAnalysis:
    """Complete advanced analysis output."""

    indicators: TechnicalIndicators
    patterns: list[PatternSignal]
    support_resistance: list[SupportResistance]
    trend: TrendAnalysis
    volatility: VolatilityAnalysis
    volume_profile: VolumeProfile
    composite_signal: str  # strong_buy, buy, neutral, sell, strong_sell
    composite_score: float  # -1 to 1


class AdvancedAnalyticsEngine:
    """Compute advanced technical analytics from OHLCV history."""

    def analyze(self, history: list[dict[str, Any]], current_quote: dict[str, Any] | None = None) -> AdvancedAnalysis:
        if not history or len(history) < 5:
            return self._empty_analysis()

        closes = [float(h.get("price_close", 0) or 0) for h in history]
        highs = [float(h.get("price_high", 0) or 0) for h in history]
        lows = [float(h.get("price_low", 0) or 0) for h in history]
        volumes = [float(h.get("volume", 0) or 0) for h in history]

        indicators = self._compute_indicators(closes, highs, lows, volumes)
        patterns = self._detect_patterns(closes, highs, lows, volumes)
        sr_levels = self._find_support_resistance(closes, highs, lows)
        trend = self._analyze_trend(closes)
        volatility = self._analyze_volatility(closes, highs, lows)
        vol_profile = self._analyze_volume(closes, highs, lows, volumes)

        composite_score = self._compute_composite(indicators, trend, volatility, patterns)
        composite_signal = self._score_to_signal(composite_score)

        return AdvancedAnalysis(
            indicators=indicators,
            patterns=patterns,
            support_resistance=sr_levels,
            trend=trend,
            volatility=volatility,
            volume_profile=vol_profile,
            composite_signal=composite_signal,
            composite_score=round(composite_score, 4),
        )

    # ── Technical Indicators ──────────────────────────────────────────

    def _compute_indicators(
        self, closes: list[float], highs: list[float], lows: list[float], volumes: list[float]
    ) -> TechnicalIndicators:
        ind = TechnicalIndicators()
        if len(closes) < 14:
            return ind

        ind.rsi_14 = self._rsi(closes, 14)
        ind.rsi_7 = self._rsi(closes, 7)
        ind.ema_9 = self._ema(closes, 9)
        ind.ema_21 = self._ema(closes, 21)
        ind.ema_50 = self._ema(closes, min(50, len(closes)))
        ind.sma_20 = self._sma(closes, min(20, len(closes)))
        ind.sma_50 = self._sma(closes, min(50, len(closes)))
        ind.sma_200 = self._sma(closes, min(200, len(closes)))

        macd_l, macd_s, macd_h = self._macd(closes)
        ind.macd_line = macd_l
        ind.macd_signal = macd_s
        ind.macd_histogram = macd_h

        bb_u, bb_m, bb_l = self._bollinger(closes, min(20, len(closes)))
        ind.bb_upper = bb_u
        ind.bb_middle = bb_m
        ind.bb_lower = bb_l
        ind.bb_width = (bb_u - bb_l) / bb_m if bb_m else 0
        ind.bb_pct = (closes[-1] - bb_l) / (bb_u - bb_l) if (bb_u - bb_l) else 0.5

        ind.atr_14 = self._atr(closes, highs, lows, min(14, len(closes) - 1))
        ind.obv = self._obv(closes, volumes)
        ind.obv_slope = self._slope(list(self._obv_series(closes, volumes)[-10:]))

        ind.vwap = self._vwap(highs, lows, closes, volumes)
        ind.stochastic_k, ind.stochastic_d = self._stochastic(closes, highs, lows)
        ind.adx = self._adx(closes, highs, lows)
        ind.cci = self._cci(closes, highs, lows)
        ind.mfi = self._mfi(closes, highs, lows, volumes)
        ind.williams_r = self._williams_r(closes, highs, lows)

        return ind

    def _rsi(self, data: list[float], period: int) -> float:
        if len(data) < period + 1:
            return 50.0
        gains, losses = [], []
        for i in range(1, len(data)):
            change = data[i] - data[i - 1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _ema(self, data: list[float], period: int) -> float:
        if not data:
            return 0.0
        if len(data) < period:
            return data[-1]
        k = 2 / (period + 1)
        ema = sum(data[:period]) / period
        for val in data[period:]:
            ema = val * k + ema * (1 - k)
        return ema

    def _sma(self, data: list[float], period: int) -> float:
        if len(data) < period:
            return sum(data) / len(data) if data else 0.0
        return sum(data[-period:]) / period

    def _macd(self, data: list[float]) -> tuple[float, float, float]:
        ema12 = self._ema(data, 12)
        ema26 = self._ema(data, min(26, len(data)))
        macd_line = ema12 - ema26
        # Simplified signal
        if len(data) > 35:
            macd_vals = []
            for i in range(26, len(data) + 1):
                e12 = self._ema(data[:i], 12)
                e26 = self._ema(data[:i], min(26, i))
                macd_vals.append(e12 - e26)
            signal = self._ema(macd_vals, 9) if len(macd_vals) >= 9 else macd_line
        else:
            signal = macd_line * 0.8
        return macd_line, signal, macd_line - signal

    def _bollinger(self, data: list[float], period: int) -> tuple[float, float, float]:
        sma = self._sma(data, period)
        if len(data) < period:
            return sma * 1.02, sma, sma * 0.98
        variance = sum((x - sma) ** 2 for x in data[-period:]) / period
        std = math.sqrt(variance)
        return sma + 2 * std, sma, sma - 2 * std

    def _atr(self, closes: list[float], highs: list[float], lows: list[float], period: int) -> float:
        if len(closes) < 2:
            return 0.0
        trs = []
        for i in range(1, len(closes)):
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
            trs.append(tr)
        return sum(trs[-period:]) / min(period, len(trs)) if trs else 0.0

    def _obv(self, closes: list[float], volumes: list[float]) -> float:
        obv = 0.0
        for i in range(1, len(closes)):
            if closes[i] > closes[i - 1]:
                obv += volumes[i]
            elif closes[i] < closes[i - 1]:
                obv -= volumes[i]
        return obv

    def _obv_series(self, closes: list[float], volumes: list[float]) -> list[float]:
        series = [0.0]
        for i in range(1, len(closes)):
            prev = series[-1]
            if closes[i] > closes[i - 1]:
                series.append(prev + volumes[i])
            elif closes[i] < closes[i - 1]:
                series.append(prev - volumes[i])
            else:
                series.append(prev)
        return series

    def _vwap(self, highs: list[float], lows: list[float], closes: list[float], volumes: list[float]) -> float:
        total_pv = sum((h + lo + c) / 3 * v for h, lo, c, v in zip(highs, lows, closes, volumes, strict=True))
        total_vol = sum(volumes)
        return total_pv / total_vol if total_vol else closes[-1]

    def _stochastic(
        self, closes: list[float], highs: list[float], lows: list[float], period: int = 14
    ) -> tuple[float, float]:
        if len(closes) < period:
            return 50.0, 50.0
        k_vals = []
        for i in range(period - 1, len(closes)):
            h = max(highs[i - period + 1 : i + 1])
            lo = min(lows[i - period + 1 : i + 1])
            k = ((closes[i] - lo) / (h - lo) * 100) if (h - lo) else 50.0
            k_vals.append(k)
        k = k_vals[-1]
        d = sum(k_vals[-3:]) / 3 if len(k_vals) >= 3 else k
        return k, d

    def _adx(self, closes: list[float], highs: list[float], lows: list[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 25.0
        plus_dm, minus_dm, tr_list = [], [], []
        for i in range(1, len(closes)):
            up = highs[i] - highs[i - 1]
            down = lows[i - 1] - lows[i]
            plus_dm.append(up if up > down and up > 0 else 0)
            minus_dm.append(down if down > up and down > 0 else 0)
            tr_list.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
        atr = sum(tr_list[-period:]) / period
        if atr == 0:
            return 25.0
        plus_di = (sum(plus_dm[-period:]) / period / atr) * 100
        minus_di = (sum(minus_dm[-period:]) / period / atr) * 100
        dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) else 0
        return dx

    def _cci(self, closes: list[float], highs: list[float], lows: list[float], period: int = 20) -> float:
        if len(closes) < period:
            return 0.0
        tp = [(h + lo + c) / 3 for h, lo, c in zip(highs[-period:], lows[-period:], closes[-period:], strict=True)]
        sma = sum(tp) / period
        mean_dev = sum(abs(x - sma) for x in tp) / period
        return (tp[-1] - sma) / (0.015 * mean_dev) if mean_dev else 0.0

    def _mfi(
        self, closes: list[float], highs: list[float], lows: list[float], volumes: list[float], period: int = 14
    ) -> float:
        if len(closes) < period + 1:
            return 50.0
        tp = [(h + lo + c) / 3 for h, lo, c in zip(highs, lows, closes, strict=True)]
        mf = [tp[i] * volumes[i] for i in range(len(tp))]
        pos_mf, neg_mf = 0.0, 0.0
        for i in range(-period, 0):
            if tp[i] > tp[i - 1]:
                pos_mf += mf[i]
            else:
                neg_mf += mf[i]
        ratio = pos_mf / neg_mf if neg_mf else 100
        return 100 - (100 / (1 + ratio))

    def _williams_r(self, closes: list[float], highs: list[float], lows: list[float], period: int = 14) -> float:
        if len(closes) < period:
            return -50.0
        h = max(highs[-period:])
        lo = min(lows[-period:])
        return ((h - closes[-1]) / (h - lo) * -100) if (h - lo) else -50.0

    def _slope(self, values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        den = sum((i - x_mean) ** 2 for i in range(n))
        return num / den if den else 0.0

    # ── Pattern Detection ─────────────────────────────────────────────

    def _detect_patterns(
        self, closes: list[float], highs: list[float], lows: list[float], volumes: list[float]
    ) -> list[PatternSignal]:
        patterns = []
        n = len(closes)
        if n < 3:
            return patterns

        for i in range(2, n):
            o = closes[i - 1]  # simplified: use close as open
            h = highs[i]
            lo = lows[i]
            c = closes[i]
            body = abs(c - o)
            upper = h - max(o, c)
            lower = min(o, c) - lo
            total_range = h - lo if h - lo else 0.001

            # Doji
            if body / total_range < 0.1 and total_range > 0:
                patterns.append(PatternSignal("doji", "neutral", 0.6, "Doji — عدم تصمیم", i))

            # Hammer
            if lower > 2 * body and upper < body * 0.3 and c > o:
                patterns.append(PatternSignal("hammer", "bullish", 0.7, "چکش — بازگشت صعودی", i))

            # Shooting Star
            if upper > 2 * body and lower < body * 0.3 and c < o:
                patterns.append(PatternSignal("shooting_star", "bearish", 0.7, "ستاره دنباله‌دار — بازگشت نزولی", i))

            # Engulfing
            if i >= 2:
                prev_o, prev_c = closes[i - 2], closes[i - 1]
                if prev_c < prev_o and c > o and c > prev_o and o < prev_c:
                    patterns.append(PatternSignal("bullish_engulfing", "bullish", 0.75, "الگوی احاطه صعودی", i))
                elif prev_c > prev_o and c < o and c < prev_o and o > prev_c:
                    patterns.append(PatternSignal("bearish_engulfing", "bearish", 0.75, "الگوی احاطه نزولی", i))

            # Morning Star (3-candle)
            if i >= 3:
                c1_o, c1_c = closes[i - 3], closes[i - 2]
                c2_o, c2_c = closes[i - 2], closes[i - 1]
                c3_o, c3_c = closes[i - 1], closes[i]
                body2 = abs(c2_c - c2_o)
                body1 = abs(c1_c - c1_o)
                if c1_c < c1_o and body2 < body1 * 0.3 and c3_c > c3_o and c3_c > (c1_o + c1_c) / 2:
                    patterns.append(PatternSignal("morning_star", "bullish", 0.8, "ستاره صبحگاهی", i))

            # Evening Star
            if i >= 3:
                c1_o, c1_c = closes[i - 3], closes[i - 2]
                c2_o, c2_c = closes[i - 2], closes[i - 1]
                c3_o, c3_c = closes[i - 1], closes[i]
                body2 = abs(c2_c - c2_o)
                body1 = abs(c1_c - c1_o)
                if c1_c > c1_o and body2 < body1 * 0.3 and c3_c < c3_o and c3_c < (c1_o + c1_c) / 2:
                    patterns.append(PatternSignal("evening_star", "bearish", 0.8, "ستاره شامگاهی", i))

        return patterns[-10:]  # return last 10 patterns

    # ── Support/Resistance ────────────────────────────────────────────

    def _find_support_resistance(
        self, closes: list[float], highs: list[float], lows: list[float]
    ) -> list[SupportResistance]:
        levels: list[SupportResistance] = []
        if len(closes) < 10:
            return levels

        # Find local highs and lows
        for i in range(2, len(closes) - 2):
            if (
                highs[i] > highs[i - 1]
                and highs[i] > highs[i - 2]
                and highs[i] > highs[i + 1]
                and highs[i] > highs[i + 2]
            ):
                levels.append(SupportResistance(highs[i], "resistance", 0.5, i))
            if lows[i] < lows[i - 1] and lows[i] < lows[i - 2] and lows[i] < lows[i + 1] and lows[i] < lows[i + 2]:
                levels.append(SupportResistance(lows[i], "support", 0.5, i))

        # Merge nearby levels (within 1%)
        merged = []
        for lv in sorted(levels, key=lambda x: x.level):
            if merged and abs(lv.level - merged[-1].level) / merged[-1].level < 0.01:
                merged[-1].strength = min(1.0, merged[-1].strength + 0.2)
                merged[-1].last_test_index = max(merged[-1].last_test_index, lv.last_test_index)
            else:
                merged.append(lv)

        return merged[-8:]

    # ── Trend Analysis ────────────────────────────────────────────────

    def _analyze_trend(self, closes: list[float]) -> TrendAnalysis:
        if len(closes) < 10:
            return TrendAnalysis("sideways", 0.0)

        recent = closes[-20:] if len(closes) >= 20 else closes
        slope = self._slope(recent)
        price = closes[-1]
        slope_pct = slope / price * 100 if price else 0

        if abs(slope_pct) < 0.05:
            direction = "sideways"
            strength = 1 - min(abs(slope_pct) / 0.05, 1)
        elif slope_pct > 0:
            direction = "up"
            strength = min(abs(slope_pct) / 0.5, 1)
        else:
            direction = "down"
            strength = min(abs(slope_pct) / 0.5, 1)

        # Count duration
        duration = 0
        for i in range(len(closes) - 1, 0, -1):
            if direction == "up" and closes[i] >= closes[i - 1] or direction == "down" and closes[i] <= closes[i - 1]:
                duration += 1
            else:
                break

        return TrendAnalysis(
            direction=direction,
            strength=round(strength, 4),
            duration_bars=duration,
            slope=round(slope, 6),
        )

    # ── Volatility Analysis ───────────────────────────────────────────

    def _analyze_volatility(self, closes: list[float], highs: list[float], lows: list[float]) -> VolatilityAnalysis:
        if len(closes) < 14:
            return VolatilityAnalysis()

        returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes)) if closes[i - 1]]
        current_vol = (sum(r**2 for r in returns[-14:]) / 14) ** 0.5 if len(returns) >= 14 else 0
        hist_vol = (sum(r**2 for r in returns) / len(returns)) ** 0.5 if returns else 0

        # Percentile
        if len(returns) >= 20:
            window_vols = []
            for i in range(20, len(returns) + 1):
                w = returns[i - 20 : i]
                v = (sum(r**2 for r in w) / 20) ** 0.5
                window_vols.append(v)
            rank = sum(1 for v in window_vols if v <= current_vol)
            percentile = rank / len(window_vols) * 100
        else:
            percentile = 50.0

        if percentile > 90:
            regime = "extreme"
        elif percentile > 70:
            regime = "high"
        elif percentile < 30:
            regime = "low"
        else:
            regime = "normal"

        atr = self._atr(closes, highs, lows, 14)
        atr_pct = atr / closes[-1] * 100 if closes[-1] else 0

        return VolatilityAnalysis(
            current=round(current_vol, 6),
            historical_avg=round(hist_vol, 6),
            percentile=round(percentile, 1),
            regime=regime,
            atr_pct=round(atr_pct, 2),
        )

    # ── Volume Profile ────────────────────────────────────────────────

    def _analyze_volume(
        self, closes: list[float], highs: list[float], lows: list[float], volumes: list[float]
    ) -> VolumeProfile:
        if not closes:
            return VolumeProfile()

        # POC (Point of Control) — price with highest volume
        price_vol: dict[float, float] = {}
        for p, v in zip(closes, volumes, strict=True):
            bucket = round(p, 0)
            price_vol[bucket] = price_vol.get(bucket, 0) + v

        poc_price = max(price_vol, key=price_vol.get) if price_vol else closes[-1]
        poc_vol = price_vol.get(poc_price, 0)

        # Value Area (70% of volume)
        total_vol = sum(volumes)
        sorted_by_vol = sorted(price_vol.items(), key=lambda x: x[1], reverse=True)
        cumulative = 0
        va_prices = []
        for price, vol in sorted_by_vol:
            cumulative += vol
            va_prices.append(price)
            if cumulative >= total_vol * 0.7:
                break

        va_high = max(va_prices) if va_prices else closes[-1]
        va_low = min(va_prices) if va_prices else closes[-1]

        # Volume trend
        if len(volumes) >= 10:
            recent_avg = sum(volumes[-5:]) / 5
            older_avg = sum(volumes[-10:-5]) / 5
            if older_avg > 0:
                vol_change = (recent_avg - older_avg) / older_avg
                if vol_change > 0.1:
                    vol_trend = "increasing"
                elif vol_change < -0.1:
                    vol_trend = "decreasing"
                else:
                    vol_trend = "neutral"
            else:
                vol_trend = "neutral"
        else:
            vol_trend = "neutral"

        # Accumulation/Distribution
        ad = 0.0
        for i in range(len(closes)):
            clv = ((closes[i] - lows[i]) - (highs[i] - closes[i])) / (highs[i] - lows[i]) if highs[i] - lows[i] else 0
            ad += clv * volumes[i]

        return VolumeProfile(
            poc_price=poc_price,
            poc_volume=poc_vol,
            value_area_high=va_high,
            value_area_low=va_low,
            volume_trend=vol_trend,
            accumulation_distribution=round(ad, 0),
        )

    # ── Composite Score ───────────────────────────────────────────────

    def _compute_composite(
        self, ind: TechnicalIndicators, trend: TrendAnalysis, vol: VolatilityAnalysis, patterns: list[PatternSignal]
    ) -> float:
        score = 0.0

        # RSI contribution (-0.2 to +0.2)
        if ind.rsi_14 < 30:
            score += 0.2
        elif ind.rsi_14 < 40:
            score += 0.1
        elif ind.rsi_14 > 70:
            score -= 0.2
        elif ind.rsi_14 > 60:
            score -= 0.1

        # MACD contribution (-0.15 to +0.15)
        if ind.macd_histogram > 0:
            score += min(0.15, ind.macd_histogram / 10)
        else:
            score -= min(0.15, abs(ind.macd_histogram) / 10)

        # Trend contribution (-0.25 to +0.25)
        if trend.direction == "up":
            score += 0.15 + 0.10 * trend.strength
        elif trend.direction == "down":
            score -= 0.15 + 0.10 * trend.strength

        # Bollinger contribution (-0.1 to +0.1)
        if ind.bb_pct < 0.2:
            score += 0.1  # near lower band — potential buy
        elif ind.bb_pct > 0.8:
            score -= 0.1  # near upper band — potential sell

        # Pattern contribution (-0.15 to +0.15)
        for p in patterns[-3:]:
            if p.direction == "bullish":
                score += 0.05 * p.confidence
            elif p.direction == "bearish":
                score -= 0.05 * p.confidence

        # Volatility penalty
        if vol.regime == "extreme":
            score *= 0.7

        return max(-1.0, min(1.0, score))

    def _score_to_signal(self, score: float) -> str:
        if score > 0.4:
            return "strong_buy"
        elif score > 0.15:
            return "buy"
        elif score < -0.4:
            return "strong_sell"
        elif score < -0.15:
            return "sell"
        return "neutral"

    def _empty_analysis(self) -> AdvancedAnalysis:
        return AdvancedAnalysis(
            indicators=TechnicalIndicators(),
            patterns=[],
            support_resistance=[],
            trend=TrendAnalysis("sideways", 0.0),
            volatility=VolatilityAnalysis(),
            volume_profile=VolumeProfile(),
            composite_signal="neutral",
            composite_score=0.0,
        )
