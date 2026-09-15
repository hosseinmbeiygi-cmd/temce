"""Stock Assistant Service — Conversational Q&A with scoring, filtering, and analysis.

Adapted from standalone CLI assistant into async FastAPI service.
Uses BrsApiQueryService for data, project cache for caching.
Adds Persian colloquial/conversational keyword support.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core.db_utils import safe_float, safe_int
from core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Technical indicators (pure functions, no I/O)
# ---------------------------------------------------------------------------


class TechnicalIndicators:
    @staticmethod
    def sma(prices: list[float], period: int) -> list[float]:
        if len(prices) < period:
            return []
        return [sum(prices[i : i + period]) / period for i in range(len(prices) - period + 1)]

    @staticmethod
    def ema(prices: list[float], period: int) -> list[float]:
        if len(prices) < period:
            return []
        multiplier = 2 / (period + 1)
        ema_values = [sum(prices[:period]) / period]
        for price in prices[period:]:
            ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])
        return ema_values

    @staticmethod
    def rsi(prices: list[float], period: int = 14) -> list[float]:
        if len(prices) < period + 1:
            return []
        gains = []
        losses = []
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i - 1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        rsi_values = []
        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - (100 / (1 + rs)))
        for i in range(period, len(gains)):
            avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
            avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period
            if avg_loss == 0:
                rsi_values.append(100.0)
            else:
                rs = avg_gain / avg_loss
                rsi_values.append(100 - (100 / (1 + rs)))
        return rsi_values

    @staticmethod
    def macd(prices: list[float]) -> dict[str, list[float]]:
        if len(prices) < 26:
            return {"macd": [], "signal": [], "histogram": []}
        ema12 = TechnicalIndicators.ema(prices, 12)
        ema26 = TechnicalIndicators.ema(prices, 26)
        if not ema12 or not ema26:
            return {"macd": [], "signal": [], "histogram": []}
        offset = len(ema12) - len(ema26)
        if offset > 0:
            ema12 = ema12[offset:]
        macd_line = [a - b for a, b in zip(ema12, ema26, strict=False)]
        signal_line = TechnicalIndicators.ema(macd_line, 9)
        if not signal_line:
            return {"macd": macd_line, "signal": [], "histogram": []}
        offset2 = len(macd_line) - len(signal_line)
        aligned_macd = macd_line[offset2:]
        histogram = [m - s for m, s in zip(aligned_macd, signal_line, strict=False)]
        return {"macd": aligned_macd, "signal": signal_line, "histogram": histogram}

    @staticmethod
    def bollinger_bands(prices: list[float], period: int = 20, std_dev: float = 2.0) -> dict[str, list[float]]:
        if len(prices) < period:
            return {"upper": [], "middle": [], "lower": []}
        middle = TechnicalIndicators.sma(prices, period)
        upper = []
        lower = []
        for i in range(len(middle)):
            window = prices[i : i + period]
            std = (sum((x - middle[i]) ** 2 for x in window) / period) ** 0.5
            upper.append(middle[i] + std_dev * std)
            lower.append(middle[i] - std_dev * std)
        return {"upper": upper, "middle": middle, "lower": lower}

    @staticmethod
    def stochastic(
        highs: list[float], lows: list[float], closes: list[float], k_period: int = 14, d_period: int = 3
    ) -> dict[str, list[float]]:
        if len(closes) < k_period:
            return {"k": [], "d": []}
        k_values = []
        for i in range(len(closes) - k_period + 1):
            window_high = max(highs[i : i + k_period])
            window_low = min(lows[i : i + k_period])
            if window_high == window_low:
                k_values.append(50.0)
            else:
                k_values.append(((closes[i + k_period - 1] - window_low) / (window_high - window_low)) * 100)
        d_values = TechnicalIndicators.sma(k_values, d_period) if len(k_values) >= d_period else []
        return {"k": k_values, "d": d_values}

    @staticmethod
    def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[float]:
        if len(closes) < 2:
            return []
        tr_values = []
        for i in range(1, len(closes)):
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
            tr_values.append(tr)
        return TechnicalIndicators.sma(tr_values, period) if len(tr_values) >= period else []

    @staticmethod
    def vwap(highs: list[float], lows: list[float], closes: list[float], volumes: list[float]) -> list[float]:
        if not closes:
            return []
        vwap_values = []
        cumulative_volume = 0
        cumulative_tp_volume = 0
        for i in range(len(closes)):
            typical_price = (highs[i] + lows[i] + closes[i]) / 3
            cumulative_volume += volumes[i]
            cumulative_tp_volume += typical_price * volumes[i]
            vwap_values.append(cumulative_tp_volume / cumulative_volume if cumulative_volume > 0 else typical_price)
        return vwap_values

    @staticmethod
    def ichimoku(highs: list[float], lows: list[float], closes: list[float]) -> dict[str, list[float]]:
        def period_high(data: list[float], period: int, end: int) -> float:
            start = max(0, end - period + 1)
            return max(data[start : end + 1])

        def period_low(data: list[float], period: int, end: int) -> float:
            start = max(0, end - period + 1)
            return min(data[start : end + 1])

        tenkan = []
        kijun = []
        for i in range(len(closes)):
            tenkan.append((period_high(highs, 9, i) + period_low(lows, 9, i)) / 2)
            kijun.append((period_high(highs, 26, i) + period_low(lows, 26, i)) / 2)

        senkou_a = [(tenkan[i] + kijun[i]) / 2 for i in range(len(closes))]
        senkou_b = []
        for i in range(len(closes)):
            senkou_b.append((period_high(highs, 52, i) + period_low(lows, 52, i)) / 2)

        chikou = closes[26:] + [None] * 26 if len(closes) >= 26 else [None] * len(closes)

        return {
            "tenkan": tenkan,
            "kijun": kijun,
            "senkou_a": senkou_a,
            "senkou_b": senkou_b,
            "chikou": chikou[: len(closes)],
        }

    @staticmethod
    def fibonacci_retracement(high: float, low: float) -> dict[str, float]:
        diff = high - low
        return {
            "0.0": high,
            "0.236": high - 0.236 * diff,
            "0.382": high - 0.382 * diff,
            "0.5": high - 0.5 * diff,
            "0.618": high - 0.618 * diff,
            "0.786": high - 0.786 * diff,
            "1.0": low,
        }

    @staticmethod
    def mfi(
        highs: list[float], lows: list[float], closes: list[float], volumes: list[float], period: int = 14
    ) -> list[float]:
        if len(closes) < period + 1:
            return []
        typical_prices = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(len(closes))]
        raw_money_flow = [typical_prices[i] * volumes[i] for i in range(len(closes))]

        mfi_values = []
        for i in range(period, len(closes)):
            positive_flow = 0
            negative_flow = 0
            for j in range(i - period + 1, i + 1):
                if typical_prices[j] > typical_prices[j - 1]:
                    positive_flow += raw_money_flow[j]
                elif typical_prices[j] < typical_prices[j - 1]:
                    negative_flow += raw_money_flow[j]

            if negative_flow == 0:
                mfi_values.append(100.0)
            else:
                money_ratio = positive_flow / negative_flow
                mfi_values.append(100 - (100 / (1 + money_ratio)))

        return mfi_values

    @staticmethod
    def advanced_analysis(
        closes: list[float],
        highs: list[float] | None = None,
        lows: list[float] | None = None,
        volumes: list[float] | None = None,
    ) -> dict[str, Any]:
        if not closes:
            return {}

        if not highs:
            highs = closes
        if not lows:
            lows = closes
        if not volumes:
            volumes = [1.0] * len(closes)

        sma20 = TechnicalIndicators.sma(closes, 20)
        sma50 = TechnicalIndicators.sma(closes, 50)
        sma200 = TechnicalIndicators.sma(closes, 200)
        rsi14 = TechnicalIndicators.rsi(closes, 14)
        macd_data = TechnicalIndicators.macd(closes)
        bb = TechnicalIndicators.bollinger_bands(closes)
        stoch = TechnicalIndicators.stochastic(highs, lows, closes)
        atr14 = TechnicalIndicators.atr(highs, lows, closes)
        vwap = TechnicalIndicators.vwap(highs, lows, closes, volumes)
        ichimoku = TechnicalIndicators.ichimoku(highs, lows, closes)
        fib = TechnicalIndicators.fibonacci_retracement(max(highs), min(lows))
        mfi14 = TechnicalIndicators.mfi(highs, lows, closes, volumes)

        return {
            "sma_20": sma20[-1] if sma20 else None,
            "sma_50": sma50[-1] if sma50 else None,
            "sma_200": sma200[-1] if sma200 else None,
            "rsi_14": rsi14[-1] if rsi14 else None,
            "macd": macd_data,
            "bollinger": {
                "upper": bb["upper"][-1] if bb["upper"] else None,
                "middle": bb["middle"][-1] if bb["middle"] else None,
                "lower": bb["lower"][-1] if bb["lower"] else None,
            },
            "stochastic": {
                "k": stoch["k"][-1] if stoch["k"] else None,
                "d": stoch["d"][-1] if stoch["d"] else None,
            },
            "atr": atr14[-1] if atr14 else None,
            "vwap": vwap[-1] if vwap else None,
            "ichimoku": {
                "tenkan": ichimoku["tenkan"][-1] if ichimoku["tenkan"] else None,
                "kijun": ichimoku["kijun"][-1] if ichimoku["kijun"] else None,
                "senkou_a": ichimoku["senkou_a"][-1] if ichimoku["senkou_a"] else None,
                "senkou_b": ichimoku["senkou_b"][-1] if ichimoku["senkou_b"] else None,
            },
            "fibonacci": fib,
            "mfi": mfi14[-1] if mfi14 else None,
            "last_price": closes[-1],
        }


# ---------------------------------------------------------------------------
# Candlestick patterns
# ---------------------------------------------------------------------------


class CandlestickPatterns:
    @staticmethod
    def detect_all(
        opens: list[float], highs: list[float], lows: list[float], closes: list[float]
    ) -> list[dict[str, Any]]:
        if len(opens) < 3:
            return []
        patterns = []
        i = len(opens) - 1
        o, h, low, c = opens[i], highs[i], lows[i], closes[i]
        body = abs(c - o)
        upper_shadow = h - max(o, c)
        lower_shadow = min(o, c) - low
        total_range = h - low if h != low else 0.001

        if body < total_range * 0.1 and upper_shadow < total_range * 0.1 and lower_shadow < total_range * 0.1:
            patterns.append({"name": "دوجی", "type": "neutral", "description": "بی‌تصمیمی بازار"})
        elif lower_shadow > body * 2 and upper_shadow < body * 0.5 and c > o:
            patterns.append({"name": "چکش", "type": "bullish", "description": "احتمال بازگشت صعودی"})
        elif lower_shadow > body * 2 and upper_shadow < body * 0.5 and c < o:
            patterns.append({"name": "چکش وارونه", "type": "bearish", "description": "احتمال بازگشت نزولی"})
        elif upper_shadow > body * 2 and lower_shadow < body * 0.5 and c < o:
            patterns.append({"name": "ستاره دنباله‌دار", "type": "bearish", "description": "فشار فروش در بالا"})
        elif upper_shadow > body * 2 and lower_shadow < body * 0.5 and c > o:
            patterns.append({"name": "چکش برعکس", "type": "bullish", "description": "فشار خرید در بالا"})
        elif body > total_range * 0.7:
            if c > o:
                patterns.append({"name": "شمع بزرگ صعودی", "type": "bullish", "description": "قدرتنمایی خریداران"})
            else:
                patterns.append({"name": "شمع بزرگ نزولی", "type": "bearish", "description": "قدرتنمایی فروشندگان"})

        if i >= 1:
            o2, _h2, _l2, c2 = opens[i - 1], highs[i - 1], lows[i - 1], closes[i - 1]
            body2 = abs(c2 - o2)
            if c2 < o2 and c > o and o <= c2 and c >= o2 and body > body2 * 1.5:
                patterns.append(
                    {"name": "الگوی اینگالفینگ صعودی", "type": "bullish", "description": "شکست نزولی با قدرت"}
                )
            elif c2 > o2 and c < o and o >= c2 and c <= o2 and body > body2 * 1.5:
                patterns.append(
                    {"name": "الگوی اینگالفینگ نزولی", "type": "bearish", "description": "شکست صعودی با قدرت"}
                )

            if c2 < o2 and abs(c2 - o2) < total_range * 0.1 and c > o and c > (o2 + c2) / 2:
                patterns.append({"name": "ستاره صبحگاهی", "type": "bullish", "description": "الگوی بازگشت صعودی قوی"})
            elif c2 > o2 and abs(c2 - o2) < total_range * 0.1 and c < o and c < (o2 + c2) / 2:
                patterns.append({"name": "ستاره شامگاهی", "type": "bearish", "description": "الگوی بازگشت نزولی قوی"})

        if i >= 2:
            o3, c3 = opens[i - 2], closes[i - 2]
            o2, c2 = opens[i - 1], closes[i - 1]
            if c3 < o3 and abs(c2 - o2) < abs(c3 - o3) * 0.3 and c > o and c > o3:
                patterns.append({"name": "سه سرباز سفید", "type": "bullish", "description": "روند صعودی قوی"})
            elif c3 > o3 and abs(c2 - o2) < abs(c3 - o3) * 0.3 and c < o and c < o3:
                patterns.append({"name": "سه کلاغ سیاه", "type": "bearish", "description": "روند نزولی قوی"})

        if i >= 1:
            o2, c2 = opens[i - 1], closes[i - 1]
            if c2 > o2 and c < o and c > o2 and o < c2:
                patterns.append({"name": "الگوی هارامی صعودی", "type": "bullish", "description": "تضعیف روند نزولی"})
            elif c2 < o2 and c > o and c < o2 and o > c2:
                patterns.append({"name": "الگوی هارامی نزولی", "type": "bearish", "description": "تضعیف روند صعودی"})

        return patterns


# ---------------------------------------------------------------------------
# Scoring engine
# ---------------------------------------------------------------------------


def _calculate_score(info: dict[str, Any], tech: dict[str, Any] | None = None) -> int:
    score = 50
    pe = safe_float(info.get("pe"), 10)
    roe = safe_float(info.get("roe"), 15)
    rsi_val = safe_float(info.get("rsi"), 50)
    ret = safe_float(info.get("return_1d"), 0)
    debt = safe_float(info.get("debt"), 40)
    beta = safe_float(info.get("beta"), 1.0)

    if pe > 0:
        if pe < 5:
            score += 15
        elif pe < 8:
            score += 10
        elif pe > 12:
            score -= 10

    if roe > 30:
        score += 15
    elif roe > 20:
        score += 10
    elif roe < 15:
        score -= 5

    if 30 <= rsi_val <= 70:
        score += 5
    elif rsi_val < 30:
        score += 10
    elif rsi_val > 70:
        score -= 10

    if ret > 0:
        score += 5
    if ret > 2:
        score += 5
    elif ret < -2:
        score -= 5

    if debt < 30:
        score += 5
    elif debt > 55:
        score -= 5

    if beta < 0.8:
        score += 5
    elif beta > 1.3:
        score -= 5

    if tech:
        sma20 = tech.get("sma_20")
        sma50 = tech.get("sma_50")
        last_price = tech.get("last_price")
        rsi14 = tech.get("rsi_14")

        if sma20 and sma50:
            if sma20 > sma50:
                score += 5
            elif sma20 < sma50:
                score -= 5
        if last_price and sma20:
            if last_price > sma20:
                score += 3
            else:
                score -= 3
        if rsi14 is not None:
            if 40 <= rsi14 <= 65:
                score += 3
            elif rsi14 > 75:
                score -= 4

    return max(0, min(100, score))


def _recommendation_text(score: int) -> str:
    if score >= 80:
        return "خرید قوی"
    if score >= 65:
        return "خرید"
    if score >= 50:
        return "نگهداری"
    if score >= 35:
        return "احتیاط"
    return "فروش"


# ---------------------------------------------------------------------------
# Colloquial Persian intent detection
# ---------------------------------------------------------------------------

# Maps colloquial / informal Persian to canonical intent keywords
_COLLOQUIAL_MAP: dict[str, list[str]] = {
    # Greetings
    "سلام": ["سلام"],
    "درود": ["سلام"],
    "هلو": ["سلام"],
    "اسلام": ["سلام"],
    "های": ["سلام"],
    "هی": ["سلام"],
    "خوبی": ["سلام"],
    "خوشی": ["سلام"],
    "چطوری": ["سلام"],
    "چخبر": ["سلام"],
    "چ خبر": ["سلام"],
    "چه خبر": ["سلام"],
    "احوال": ["سلام"],
    "احوالپرسی": ["سلام"],
    # Farewell
    "خداحافظ": ["خداحافظ"],
    "خدانگهدار": ["خداحافظ"],
    "فعلا": ["خداحافظ"],
    "بای": ["خداحافظ"],
    "تا بعد": ["خداحافظ"],
    "برم": ["خداحافظ"],
    "من رفتم": ["خداحافظ"],
    # Analysis
    "تحلیل": ["تحلیل"],
    "تحلیلش کن": ["تحلیل"],
    "تحلیلش کنی": ["تحلیل"],
    "بررسی": ["تحلیل"],
    "بررسیش کن": ["تحلیل"],
    "بررسی کن": ["تحلیل"],
    "چطوره": ["تحلیل"],
    "وضعیتش": ["تحلیل"],
    "وضعیتش چطوره": ["تحلیل"],
    "حالش چطوره": ["تحلیل"],
    "چه حالی داره": ["تحلیل"],
    "آیا خوبه": ["تحلیل"],
    "ارزش خرید داره": ["تحلیل"],
    "می‌ارزه": ["تحلیل"],
    "می‌ارزه بخرمش": ["تحلیل"],
    "بخرم": ["تحلیل"],
    "بفروشم": ["تحلیل"],
    "نگهش دارم": ["تحلیل"],
    # Market
    "بازار": ["بازار"],
    "بازار امروز": ["بازار"],
    "بازار چطوره": ["بازار"],
    "بازار چته": ["بازار"],
    "چه خبر از بازار": ["بازار"],
    "شاخص": ["بازار"],
    "شاخص کل": ["بازار"],
    "تکلیف بازار": ["بازار"],
    "بازار سبزه": ["بازار"],
    "بازار قرمزه": ["بازار"],
    "بازار صعودی": ["بازار"],
    "بازار نزولی": ["بازار"],
    # Screener / best stocks
    "ارزنده": ["ارزنده"],
    "ارزان": ["ارزنده"],
    "ارزون": ["ارزنده"],
    "ارزون‌ترین": ["ارزنده"],
    "بهترین": ["بهترین"],
    "بهترین سهم": ["بهترین"],
    "بهترین سهام": ["بهترین"],
    "برترین": ["بهترین"],
    "سهم خوب": ["بهترین"],
    "سهام خوب": ["بهترین"],
    "چه سهمی بخرم": ["بهترین"],
    "پیشنهاد سهم": ["بهترین"],
    "سهم پیشنهادی": ["بهترین"],
    "گلچین": ["بهترین"],
    # Compare
    "مقایسه": ["مقایسه"],
    "مقایسه کن": ["مقایسه"],
    "با هم مقایسه": ["مقایسه"],
    "کدوم بهتره": ["مقایسه"],
    "کدوم سود بیشتری": ["مقایسه"],
    "تفاوت": ["مقایسه"],
    # Filter
    "فیلتر": ["فیلتر"],
    "فیلتر کن": ["فیلتر"],
    "غربال": ["فیلتر"],
    "غربالگری": ["فیلتر"],
    "غربال کن": ["فیلتر"],
    "جستجو": ["فیلتر"],
    "پیدا کن": ["فیلتر"],
    "لیست": ["فیلتر"],
    # Refresh
    "بروزرسانی": ["بروزرسانی"],
    "به‌روزرسانی": ["بروزرسانی"],
    "آپدیت": ["بروزرسانی"],
    "تازه کن": ["بروزرسانی"],
    # History
    "تاریخچه": ["تاریخچه"],
    "گفتگوهای قبلی": ["تاریخچه"],
    "چی گفتیم": ["تاریخچه"],
    "سابقه": ["تاریخچه"],
    # Help
    "کمک": ["کمک"],
    "راهنما": ["کمک"],
    "help": ["کمک"],
    "چیکار می‌تونی": ["کمک"],
    "چیکار بلدي": ["کمک"],
    "دستورات": ["کمک"],
    "چه فرمان‌هایی": ["کمک"],
    # Backtest
    "بک‌تست": ["بک‌تست"],
    "بک تست": ["بک‌تست"],
    "بکتست": ["بک‌تست"],
    "backtest": ["بک‌تست"],
    # Strategy
    "استراتژی": ["استراتژی"],
    "strategy": ["استراتژی"],
    # Optimization
    "بهینه‌سازی": ["بهینه‌سازی"],
    "بهینه سازی": ["بهینه‌سازی"],
    "walk forward": ["بهینه‌سازی"],
    "مونت کارلو": ["بهینه‌سازی"],
    "مونته کارلو": ["بهینه‌سازی"],
    "monte carlo": ["بهینه‌سازی"],
    # Compare strategies
    "مقایسه استراتژی": ["مقایسه_استراتژی"],
    "مقایسه همه استراتژی": ["مقایسه_استراتژی"],
    "مقایسه استراتژی‌ها": ["مقایسه_استراتژی"],
    "مقایسه همه": ["مقایسه_استراتژی"],
    # Strategy generation
    "تولید استراتژی": ["تولید_استراتژی"],
    "ساخت استراتژی": ["تولید_استراتژی"],
    # Quick recommendation
    "پیشنهاد": ["پیشنهاد"],
    "پیشنهاد میدی": ["پیشنهاد"],
    "پیشنهاد می‌کنی": ["پیشنهاد"],
    "چی پیشنهاد میدی": ["پیشنهاد"],
    # Strong buy/sell signals
    "سیگنال": ["سیگنال"],
    "سیگنال خرید": ["سیگنال"],
    "سیگنال فروش": ["سیگنال"],
    # Alerts (separate from signals to avoid mis-routing)
    "هشدار": ["هشدار"],
    "هشدار جدید": ["هشدار"],
    "هشدارها": ["هشدار"],
    "لیست هشدارها": ["هشدار"],
    "alarm": ["هشدار"],
    "alert": ["هشدار"],
    # Pattern recognition
    "الگو": ["الگو"],
    "الگوهای": ["الگو"],
    "کندل": ["الگو"],
    "شمعی": ["الگو"],
    "pattern": ["الگو"],
    # Report
    "گزارش": ["گزارش"],
    "گزارش بازار": ["گزارش"],
    "report": ["گزارش"],
}


def _detect_intent(text: str) -> str | None:
    """Detect intent from conversational Persian text. Returns canonical intent or None."""
    text_lower = text.strip().lower()

    # Check colloquial map first
    for colloquial, intents in _COLLOQUIAL_MAP.items():
        if colloquial in text_lower:
            return intents[0]

    # Regex-based detection for structured queries
    if re.search(r"سلام|درود|هلو|اسلام", text_lower):
        return "سلام"
    if re.search(r"خداحافظ|خدانگهدار|فعلا|بای", text_lower):
        return "خداحافظ"
    if re.search(r"تحلیل\s*کن|بررسی\s*کن|وضعیت|چطوره|حالش", text_lower):
        return "تحلیل"
    if re.search(r"بازار|شاخص", text_lower):
        return "بازار"
    if re.search(r"ارزنده|ارزان|ارزون", text_lower):
        return "ارزنده"
    if re.search(r"بهترین|برترین|گلچین", text_lower):
        return "بهترین"
    if re.search(r"مقایسه|با هم|کدوم بهتر", text_lower):
        return "مقایسه"
    if re.search(r"فیلتر|غربال|جستجو|پیدا کن", text_lower):
        return "فیلتر"
    if re.search(r"بروزرسانی|آپدیت|تازه", text_lower):
        return "بروزرسانی"
    if re.search(r"تاریخچه|سابقه|چی گفتیم", text_lower):
        return "تاریخچه"
    if re.search(r"کمک|راهنما|دستورات", text_lower):
        return "کمک"
    if re.search(r"پیشنهاد|پیشنهاد میدی|چی پیشنهاد", text_lower):
        return "پیشنهاد"
    if re.search(r"سیگنال", text_lower):
        return "سیگنال"

    # Alert detection (separate from signals)
    if re.search(r"هشدار|alarm|alert", text_lower):
        return "هشدار"

    # Pattern detection
    if re.search(r"الگو|pattern|کندل|شمعی", text_lower):
        return "الگو"

    # Report detection
    if re.search(r"گزارش|report", text_lower):
        return "گزارش"

    # Backtest-related regex fallbacks
    if re.search(r"بک‌تست|بکتست|backtest", text_lower):
        return "بک‌تست"
    if re.search(r"استراتژی|strategy", text_lower):
        return "استراتژی"
    if re.search(r"بهینه‌سازی|walk.?forward|مونت.?کارلو|مونته.?کارلو|monte.?carlo", text_lower):
        return "بهینه‌سازی"
    if re.search(r"مقایسه\s*استراتژی|تولید\s*استراتژی|ساخت\s*استراتژی", text_lower):
        if "مقایسه" in text_lower:
            return "مقایسه_استراتژی"
        return "تولید_استراتژی"

    return None


# ---------------------------------------------------------------------------
# Portfolio management
# ---------------------------------------------------------------------------


@dataclass
class PortfolioHolding:
    symbol: str
    quantity: int
    avg_price: float
    current_price: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    weight: float = 0.0


class PortfolioManager:
    def __init__(self):
        self.holdings: dict[str, PortfolioHolding] = {}
        self.total_investment: float = 0.0

    def add_holding(self, symbol: str, quantity: int, price: float):
        if symbol in self.holdings:
            h = self.holdings[symbol]
            total_qty = h.quantity + quantity
            h.avg_price = (h.avg_price * h.quantity + price * quantity) / total_qty
            h.quantity = total_qty
        else:
            self.holdings[symbol] = PortfolioHolding(symbol=symbol, quantity=quantity, avg_price=price)
        self.total_investment += quantity * price

    def remove_holding(self, symbol: str):
        if symbol in self.holdings:
            h = self.holdings.pop(symbol)
            self.total_investment -= h.avg_price * h.quantity

    def update_prices(self, prices: dict[str, float]):
        for symbol, h in self.holdings.items():
            if symbol in prices:
                h.current_price = prices[symbol]
                h.pnl = (h.current_price - h.avg_price) * h.quantity
                h.pnl_pct = ((h.current_price / h.avg_price) - 1) * 100 if h.avg_price > 0 else 0

        total_value = sum(h.current_price * h.quantity for h in self.holdings.values())
        for h in self.holdings.values():
            h.weight = (h.current_price * h.quantity / total_value * 100) if total_value > 0 else 0

    def get_summary(self) -> dict[str, Any]:
        total_value = sum(h.current_price * h.quantity for h in self.holdings.values())
        total_pnl = sum(h.pnl for h in self.holdings.values())
        total_pnl_pct = ((total_value / self.total_investment) - 1) * 100 if self.total_investment > 0 else 0

        return {
            "total_investment": self.total_investment,
            "total_value": total_value,
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "holdings_count": len(self.holdings),
            "holdings": [
                {
                    "symbol": h.symbol,
                    "quantity": h.quantity,
                    "avg_price": h.avg_price,
                    "current_price": h.current_price,
                    "pnl": h.pnl,
                    "pnl_pct": h.pnl_pct,
                    "weight": h.weight,
                }
                for h in self.holdings.values()
            ],
        }


# ---------------------------------------------------------------------------
# Alerts system
# ---------------------------------------------------------------------------


@dataclass
class Alert:
    symbol: str
    alert_type: str
    condition: str
    threshold: float
    current_value: float = 0.0
    triggered: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class AlertManager:
    def __init__(self):
        self.alerts: list[Alert] = []

    def add_alert(self, symbol: str, alert_type: str, condition: str, threshold: float):
        self.alerts.append(
            Alert(
                symbol=symbol,
                alert_type=alert_type,
                condition=condition,
                threshold=threshold,
            )
        )

    def remove_alert(self, symbol: str, alert_type: str | None = None):
        if alert_type:
            self.alerts = [a for a in self.alerts if not (a.symbol == symbol and a.alert_type == alert_type)]
        else:
            self.alerts = [a for a in self.alerts if a.symbol != symbol]

    def check_alerts(self, symbol: str, values: dict[str, float]) -> list[Alert]:
        triggered = []
        for alert in self.alerts:
            if alert.symbol != symbol or alert.triggered:
                continue
            if alert.alert_type not in values:
                continue
            current = values[alert.alert_type]
            alert.current_value = current

            if (
                alert.condition == "above"
                and current > alert.threshold
                or alert.condition == "below"
                and current < alert.threshold
            ):
                alert.triggered = True
                triggered.append(alert)

        return triggered

    def get_active_alerts(self) -> list[dict[str, Any]]:
        return [
            {
                "symbol": a.symbol,
                "type": a.alert_type,
                "condition": a.condition,
                "threshold": a.threshold,
                "current": a.current_value,
                "triggered": a.triggered,
            }
            for a in self.alerts
        ]


# ---------------------------------------------------------------------------
# Multi-timeframe analysis
# ---------------------------------------------------------------------------


class MultiTimeframeAnalysis:
    @staticmethod
    def resample_to_weekly(daily_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not daily_data:
            return []
        weekly = []
        week_data = []
        for day in daily_data:
            week_data.append(day)
            if len(week_data) == 5 or day == daily_data[-1]:
                opens = [d.get("open", d.get("close", 0)) for d in week_data]
                highs = [d.get("high", d.get("close", 0)) for d in week_data]
                lows = [d.get("low", d.get("close", 0)) for d in week_data]
                closes = [d.get("close", 0) for d in week_data]
                volumes = [d.get("volume", 0) for d in week_data]
                weekly.append(
                    {
                        "date": week_data[-1].get("date", ""),
                        "open": opens[0],
                        "high": max(highs),
                        "low": min(lows),
                        "close": closes[-1],
                        "volume": sum(volumes),
                    }
                )
                week_data = []
        return weekly

    @staticmethod
    def resample_to_monthly(daily_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not daily_data:
            return []
        monthly = []
        month_data = []
        current_month = ""
        for day in daily_data:
            date = day.get("date", "")
            month = date[:7] if len(date) >= 7 else date
            if month != current_month and month_data:
                opens = [d.get("open", d.get("close", 0)) for d in month_data]
                highs = [d.get("high", d.get("close", 0)) for d in month_data]
                lows = [d.get("low", d.get("close", 0)) for d in month_data]
                closes = [d.get("close", 0) for d in month_data]
                volumes = [d.get("volume", 0) for d in month_data]
                monthly.append(
                    {
                        "date": month_data[-1].get("date", ""),
                        "open": opens[0],
                        "high": max(highs),
                        "low": min(lows),
                        "close": closes[-1],
                        "volume": sum(volumes),
                    }
                )
                month_data = []
            current_month = month
            month_data.append(day)

        if month_data:
            opens = [d.get("open", d.get("close", 0)) for d in month_data]
            highs = [d.get("high", d.get("close", 0)) for d in month_data]
            lows = [d.get("low", d.get("close", 0)) for d in month_data]
            closes = [d.get("close", 0) for d in month_data]
            volumes = [d.get("volume", 0) for d in month_data]
            monthly.append(
                {
                    "date": month_data[-1].get("date", ""),
                    "open": opens[0],
                    "high": max(highs),
                    "low": min(lows),
                    "close": closes[-1],
                    "volume": sum(volumes),
                }
            )
        return monthly

    @staticmethod
    def analyze_multi_timeframe(daily_data: list[dict[str, Any]]) -> dict[str, Any]:
        weekly = MultiTimeframeAnalysis.resample_to_weekly(daily_data)
        monthly = MultiTimeframeAnalysis.resample_to_monthly(daily_data)

        def get_trend(data: list[dict[str, Any]]) -> str:
            if len(data) < 2:
                return "نامشخص"
            closes = [d.get("close", 0) for d in data[-5:]]
            if all(closes[i] <= closes[i + 1] for i in range(len(closes) - 1)):
                return "صعودی"
            elif all(closes[i] >= closes[i + 1] for i in range(len(closes) - 1)):
                return "نزولی"
            return "خنثی"

        daily_closes = [d.get("close", 0) for d in daily_data[-20:]] if daily_data else []
        weekly_closes = [d.get("close", 0) for d in weekly[-10:]] if weekly else []
        monthly_closes = [d.get("close", 0) for d in monthly[-5:]] if monthly else []

        return {
            "daily_trend": get_trend(daily_data[-5:] if len(daily_data) >= 5 else daily_data),
            "weekly_trend": get_trend(weekly[-5:] if len(weekly) >= 5 else weekly),
            "monthly_trend": get_trend(monthly[-5:] if len(monthly) >= 5 else monthly),
            "daily_sma5": TechnicalIndicators.sma(daily_closes, 5)[-1] if len(daily_closes) >= 5 else None,
            "daily_sma20": TechnicalIndicators.sma(daily_closes, 20)[-1] if len(daily_closes) >= 20 else None,
            "weekly_sma5": TechnicalIndicators.sma(weekly_closes, 5)[-1] if len(weekly_closes) >= 5 else None,
            "monthly_sma3": TechnicalIndicators.sma(monthly_closes, 3)[-1] if len(monthly_closes) >= 3 else None,
        }


# ---------------------------------------------------------------------------
# Volume Profile
# ---------------------------------------------------------------------------


class VolumeProfile:
    @staticmethod
    def calculate(closes: list[float], volumes: list[float], num_levels: int = 20) -> dict[str, Any]:
        if not closes or not volumes:
            return {}
        min_price = min(closes)
        max_price = max(closes)
        if min_price == max_price:
            return {"poc": min_price, "value_area_high": max_price, "value_area_low": min_price, "levels": []}

        step = (max_price - min_price) / num_levels
        levels = []
        for i in range(num_levels):
            level_low = min_price + i * step
            level_high = level_low + step
            level_volume = 0
            for j in range(len(closes)):
                if level_low <= closes[j] < level_high:
                    level_volume += volumes[j]
            levels.append(
                {
                    "price": round((level_low + level_high) / 2, 2),
                    "volume": level_volume,
                    "range": f"{level_low:.2f}-{level_high:.2f}",
                }
            )

        poc_level = max(levels, key=lambda x: x["volume"]) if levels else None
        poc = poc_level["price"] if poc_level else (min_price + max_price) / 2

        total_volume = sum(level["volume"] for level in levels)
        target_volume = total_volume * 0.7
        sorted_levels = sorted(levels, key=lambda x: x["volume"], reverse=True)
        cumulative = 0
        value_area_levels = []
        for level in sorted_levels:
            cumulative += level["volume"]
            value_area_levels.append(level)
            if cumulative >= target_volume:
                break

        va_prices = [level["price"] for level in value_area_levels]
        value_area_high = max(va_prices) if va_prices else max_price
        value_area_low = min(va_prices) if va_prices else min_price

        return {
            "poc": poc,
            "value_area_high": value_area_high,
            "value_area_low": value_area_low,
            "total_volume": total_volume,
            "levels": sorted(levels, key=lambda x: x["volume"], reverse=True)[:5],
        }


# ---------------------------------------------------------------------------
# Correlation analysis
# ---------------------------------------------------------------------------


class CorrelationAnalysis:
    @staticmethod
    def pearson_correlation(x: list[float], y: list[float]) -> float:
        n = min(len(x), len(y))
        if n < 2:
            return 0.0
        x, y = x[:n], y[:n]
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        denom_x = sum((x[i] - mean_x) ** 2 for i in range(n)) ** 0.5
        denom_y = sum((y[i] - mean_y) ** 2 for i in range(n)) ** 0.5
        if denom_x == 0 or denom_y == 0:
            return 0.0
        return numerator / (denom_x * denom_y)

    @staticmethod
    def calculate_returns(prices: list[float]) -> list[float]:
        if len(prices) < 2:
            return []
        return [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices)) if prices[i - 1] != 0]

    @staticmethod
    def sector_correlation(sector_stocks: dict[str, list[float]]) -> dict[str, Any]:
        symbols = list(sector_stocks.keys())
        returns = {sym: CorrelationAnalysis.calculate_returns(prices) for sym, prices in sector_stocks.items()}
        correlations = {}
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                corr = CorrelationAnalysis.pearson_correlation(returns[symbols[i]], returns[symbols[j]])
                correlations[f"{symbols[i]}-{symbols[j]}"] = round(corr, 4)
        return correlations


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


class ReportGenerator:
    @staticmethod
    def daily_market_report(stocks: list[dict[str, Any]], alerts: list[dict[str, Any]] | None = None) -> str:
        if not stocks:
            return "داده‌ای برای گزارش موجود نیست."

        count = len(stocks)
        avg_pe = round(sum(safe_float(s.get("pe"), 0) for s in stocks) / count, 2)
        avg_roe = round(sum(safe_float(s.get("roe"), 0) for s in stocks) / count, 2)
        positive = sum(1 for s in stocks if safe_float(s.get("return_1d"), 0) > 0)
        negative = sum(1 for s in stocks if safe_float(s.get("return_1d"), 0) < 0)
        unchanged = count - positive - negative
        total_value = sum(safe_float(s.get("value"), 0) for s in stocks)
        avg_change = round(sum(safe_float(s.get("return_1d"), 0) for s in stocks) / count, 2)

        sorted_by_return = sorted(stocks, key=lambda s: safe_float(s.get("return_1d"), 0), reverse=True)
        top5 = sorted_by_return[:5]
        bottom5 = sorted_by_return[-5:]

        sorted_by_volume = sorted(stocks, key=lambda s: safe_float(s.get("volume"), 0), reverse=True)
        top_volume = sorted_by_volume[:5]

        lines = [
            "📊 گزارش روزانه بازار",
            "═" * 50,
            f"تاریخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "📈 آمار کلی:",
            f"  تعداد نمادها: {count}",
            f"  مثبت: {positive} | منفی: {negative} | بدون تغییر: {unchanged}",
            f"  میانگین تغییر: {avg_change:+.2f}%",
            f"  میانگین P/E: {avg_pe} | میانگین ROE: {avg_roe}%",
            f"  ارزش کل معاملات: {total_value:,.0f} ریال",
            "",
            "🏆 برترین‌ها:",
        ]
        for s in top5:
            lines.append(f"  🟢 {s.get('symbol', '')}: {safe_float(s.get('return_1d'), 0):+.2f}%")

        lines.append("")
        lines.append("⚠️ ضعیف‌ترین‌ها:")
        for s in bottom5:
            lines.append(f"  🔴 {s.get('symbol', '')}: {safe_float(s.get('return_1d'), 0):+.2f}%")

        lines.append("")
        lines.append("📊 بیشترین حجم:")
        for s in top_volume:
            lines.append(f"  📈 {s.get('symbol', '')}: {safe_int(s.get('volume'), 0):,}")

        if alerts:
            lines.append("")
            lines.append("🔔 هشدارهای فعال:")
            for a in alerts[:5]:
                lines.append(
                    f"  • {a.get('symbol', '')}: {a.get('type', '')} {a.get('condition', '')} {a.get('threshold', '')}"
                )

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------


class StockAssistantService:
    """Async conversational stock assistant for FastAPI.

    Fetches data via BrsApiQueryService, computes scores and indicators,
    and returns formatted Persian responses.
    """

    def __init__(self, brsapi_service: Any):
        self._brsapi = brsapi_service
        self._cache: dict[str, tuple[Any, float]] = {}
        self._cache_ttl = 300  # 5 minutes
        self.portfolio = PortfolioManager()
        self.alert_manager = AlertManager()
        self.volume_profile = VolumeProfile()
        self.correlation = CorrelationAnalysis()
        self.report_generator = ReportGenerator()

    def _cache_get(self, key: str) -> Any | None:
        item = self._cache.get(key)
        if not item:
            return None
        value, expires_at = item
        import time

        if time.time() > expires_at:
            self._cache.pop(key, None)
            return None
        return value

    def _cache_set(self, key: str, value: Any, ttl: int | None = None):
        import time

        self._cache[key] = (value, time.time() + (ttl or self._cache_ttl))

    async def _get_all_stocks(self) -> list[dict[str, Any]]:
        cached = self._cache_get("all_stocks")
        if cached is not None:
            return cached

        try:
            snapshots = await self._brsapi.get_enriched_snapshots(limit=500)
            if not snapshots:
                logger.warning("No stock data from BrsApi — DB may be empty (sync hasn't run yet)")
                return []
            stocks = [self._normalize(s) for s in snapshots if s.get("symbol")]
            if not stocks:
                logger.warning("BrsApi returned %d snapshots but none had a symbol field", len(snapshots))
                return []
            logger.info("Loaded %d stocks from BrsApi", len(stocks))
            self._cache_set("all_stocks", stocks)
            return stocks
        except Exception as exc:
            logger.warning("Failed to fetch stocks from BrsApi: %s", exc)
            return []

    async def _get_stock_history(self, symbol: str) -> list[dict[str, Any]]:
        cache_key = f"history:{symbol}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            history = await self._brsapi.get_historical_daily(symbol, limit=200)
            if not history:
                return []
            normalized = [
                {
                    "date": h.get("date", ""),
                    "close": safe_float(h.get("price_close") or h.get("price_last"), 0),
                    "volume": safe_int(h.get("trade_volume"), 0),
                }
                for h in history
            ]
            normalized = [r for r in normalized if r.get("close") and r["close"] > 0]
            normalized.sort(key=lambda x: x["date"])
            self._cache_set(cache_key, normalized)
            return normalized
        except Exception as exc:
            logger.warning("Failed to fetch history for %s: %s", symbol, exc)
            return []

    @staticmethod
    def _normalize(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "symbol": item.get("symbol", ""),
            "name": item.get("name", ""),
            "sector": item.get("sector", item.get("industry", "")),
            "price": safe_float(item.get("price_last") or item.get("price"), 0),
            "pe": safe_float(item.get("pe_ratio") or item.get("pe"), 0),
            "roe": safe_float(item.get("roe"), 0),
            "rsi": safe_float(item.get("rsi"), 50),
            "return_1d": safe_float(item.get("price_last_change_pct") or item.get("change_percent"), 0),
            "volume": safe_int(item.get("trade_volume") or item.get("volume"), 0),
            "debt": safe_float(item.get("debt"), 0),
            "beta": safe_float(item.get("beta"), 1.0),
            "eps": safe_float(item.get("eps"), 0),
            "market": item.get("market", ""),
            "value": safe_float(item.get("trade_value"), 0),
        }

    # ── Public API ──

    async def process_message(self, text: str) -> dict[str, Any]:
        """Process a conversational message and return structured response."""
        text = text.strip()
        if not text:
            return {"text": "پیامی وارد نکردید. لطفاً سوال خود را بنویسید.", "type": "error"}

        intent = _detect_intent(text)

        if intent == "سلام":
            return await self._greeting()
        if intent == "خداحافظ":
            return self._farewell()
        if intent == "کمک":
            return self._help()
        if intent == "بازار":
            return await self._market_summary()
        if intent == "بروزرسانی":
            return self._refresh()
        if intent == "تاریخچه":
            return self._history_note()
        if intent in ("تحلیل", "پیشنهاد", "سیگنال"):
            return await self._analyze_from_text(text)
        if intent == "ارزنده":
            return await self._find_cheap()
        if intent == "بهترین":
            return await self._find_best()
        if intent == "مقایسه":
            return await self._compare_from_text(text)
        if intent == "فیلتر":
            return await self._filter_from_text(text)

        if intent == "الگو":
            return await self._pattern_handler(text)
        if intent == "هشدار":
            return await self._alert_handler(text)
        if intent == "گزارش":
            return await self._report_handler(text)

        if intent == "بک‌تست":
            return await self._backtest_handler(text)
        if intent == "بهینه‌سازی":
            return await self._optimization_handler(text)
        if intent == "استراتژی":
            return await self._strategy_handler(text)
        if intent == "مقایسه_استراتژی":
            return await self._compare_strategies_handler(text)
        if intent == "تولید_استراتژی":
            return await self._strategy_generation_handler(text)

        if re.search(r"پرتفوی|سبد|portfolio", text, re.IGNORECASE):
            return await self._portfolio_handler(text)
        if re.search(r"هشدار|alarm|alert", text, re.IGNORECASE):
            return await self._alert_handler(text)
        if re.search(r"گزارش|report", text, re.IGNORECASE):
            return await self._report_handler(text)
        if re.search(r"الگو|pattern|کندل", text, re.IGNORECASE):
            return await self._pattern_handler(text)
        if re.search(r"چند بازه|multi.?time|هفتگی|ماهانه", text, re.IGNORECASE):
            return await self._multi_timeframe_handler(text)
        if re.search(r"حجم|volume.?profile|poc", text, re.IGNORECASE):
            return await self._volume_profile_handler(text)
        if re.search(r"همبستگی|correlation", text, re.IGNORECASE):
            return await self._correlation_handler(text)

        symbol = await self._extract_symbol(text)
        if symbol:
            return await self._get_recommendation(symbol)

        return {
            "text": (
                "متوجه درخواست نشدم.\n\n"
                "دستورات موجود:\n"
                "• تحلیل فلان سهم\n"
                "• بهترین سهام\n"
                "• مقایسه فولاد و خودرو\n"
                "• فیلتر RSI<30 ROE>20 P/E<8\n"
                "• بازار چطوره؟\n"
                "• ارزنده\n"
                "• پرتفوی من\n"
                "• هشدار قیمت\n"
                "• گزارش بازار\n"
                "• الگوهای شمعی\n"
                "• تحلیل چند بازه زمانی\n"
                "• حجم در قیمت\n"
                "• همبستگی سهام\n"
                "• بک‌تست استراتژی‌ها\n"
                "• کمک"
            ),
            "type": "unknown",
        }

    async def _greeting(self) -> dict[str, Any]:
        return {
            "text": (
                "سلام! 👋\n\n"
                "من دستیار هوشمند بورس هستم. می‌توانم:\n"
                "• تحلیل سهام با ۱۰+ اندیکاتور تکنیکال\n"
                "• تشخیص الگوهای شمعی\n"
                "• مدیریت پرتفوی و محاسبه سود/زیان\n"
                "• ثبت و مدیریت هشدارها\n"
                "• تحلیل چند بازه زمانی (روزانه/هفتگی/ماهانه)\n"
                "• تحلیل حجم در قیمت و نقاط کنترل\n"
                "• محاسبه همبستگی بین سهام\n"
                "• بک‌تست استراتژی‌ها و بهینه‌سازی پارامترها\n"
                "• گزارش‌های خودکار بازار\n"
                "• مقایسه و فیلتر پیشرفته\n\n"
                "یک سوال بپرسید!"
            ),
            "type": "greeting",
        }

    def _farewell(self) -> dict[str, Any]:
        return {
            "text": "خداحافظ! موفق باشید. 🙏",
            "type": "farewell",
        }

    def _help(self) -> dict[str, Any]:
        return {
            "text": (
                "راهنمای دستیار هوشمند بورس\n"
                "═══════════════════════════════\n\n"
                "🔹 تحلیل: «تحلیل فولاد»، «وضعیت خودرو چطوره؟»\n"
                "🔹 بهترین: «بهترین سهام»، «سهام خوب»، «چه سهمی بخرم»\n"
                "🔹 مقایسه: «مقایسه فولاد و خودرو»، «کدوم بهتره»\n"
                "🔹 فیلتر: «فیلتر RSI<30 ROE>20»\n"
                "🔹 بازار: «بازار چطوره؟»، «شاخص کل»\n"
                "🔹 ارزنده: «سهام ارزنده»، «ارزون‌ترین»\n"
                "🔹 پرتفوی: «اضافه فولاد 100 50000»، «خلاصه پرتفوی»\n"
                "🔹 هشدار: «هشدار فولاد rsi above 70»، «لیست هشدارها»\n"
                "🔹 الگوها: «الگوهای فولاد»، «کندل خودرو»\n"
                "🔹 چند بازه: «تحلیل چند بازه فولاد»\n"
                "🔹 حجم در قیمت: «حجم در قیمت فولاد»\n"
                "🔹 همبستگی: «همبستگی فولاد خودرو»\n"
                "🔹 گزارش: «گزارش بازار»\n"
                "🔹 بروزرسانی: «آپدیت»، «تازه کن»\n"
                "🔹 خداحافظ: «خداحافظ»، «فعلا»\n"
                "🔹 بک‌تست: «بک‌تست moving_average_cross روی فولاد»\n"
                "🔹 استراتژی: «استراتژی‌ها»، «بهترین استراتژی برای خودرو»\n"
                "🔹 بهینه‌سازی: «بهینه‌سازی پارامترها»، «walk forward فولاد»\n"
                "🔹 مقایسه استراتژی: «مقایسه همه استراتژی‌ها روی فولاد»\n"
                "🔹 تولید استراتژی: «تولید استراتژی برای فولاد»"
            ),
            "type": "help",
        }

    def _refresh(self) -> dict[str, Any]:
        self._cache.clear()
        return {
            "text": "داده‌ها بروزرسانی شدند. ✅",
            "type": "refresh",
        }

    def _history_note(self) -> dict[str, Any]:
        return {
            "text": "تاریخچه مکالمات در حال حاضر در سمت سرور ذخیره نمی‌شود.",
            "type": "info",
        }

    async def _market_summary(self) -> dict[str, Any]:
        stocks = await self._get_all_stocks()
        if not stocks:
            return {"text": "داده‌ای برای بازار در دسترس نیست.", "type": "error"}

        count = len(stocks)
        avg_pe = round(sum(safe_float(s.get("pe"), 0) for s in stocks) / count, 2) if count else 0
        avg_roe = round(sum(safe_float(s.get("roe"), 0) for s in stocks) / count, 2) if count else 0
        avg_rsi = round(sum(safe_float(s.get("rsi"), 0) for s in stocks) / count, 2) if count else 0
        positive = sum(1 for s in stocks if safe_float(s.get("return_1d"), 0) > 0)
        negative = sum(1 for s in stocks if safe_float(s.get("return_1d"), 0) < 0)
        total_value = sum(safe_float(s.get("value"), 0) for s in stocks)

        lines = [
            "📊 خلاصه بازار",
            "═" * 40,
            f"تعداد نمادها: {count}",
            f"میانگین P/E: {avg_pe}",
            f"میانگین ROE: {avg_roe}%",
            f"میانگین RSI: {avg_rsi}",
            f"نمادهای مثبت: {positive} 🟢",
            f"نمادهای منفی: {negative} 🔴",
            f"ارزش کل معاملات: {total_value:,.0f} ریال",
        ]

        # Top gainers
        sorted_stocks = sorted(stocks, key=lambda s: safe_float(s.get("return_1d"), 0), reverse=True)
        top3 = sorted_stocks[:3]
        if top3:
            lines.append("")
            lines.append("🏆 برترین‌ها:")
            for s in top3:
                lines.append(f"  🟢 {s['symbol']}: {safe_float(s.get('return_1d'), 0):+.2f}%")

        # Top losers
        bottom3 = sorted_stocks[-3:]
        if bottom3:
            lines.append("")
            lines.append("⚠️ ضعیف‌ترین‌ها:")
            for s in bottom3:
                lines.append(f"  🔴 {s['symbol']}: {safe_float(s.get('return_1d'), 0):+.2f}%")

        return {
            "text": "\n".join(lines),
            "type": "market",
            "data": {"count": count, "positive": positive, "negative": negative},
        }

    async def _extract_symbol(self, text: str) -> str | None:
        """Try to find a stock symbol mentioned in text."""
        stocks = await self._get_all_stocks()
        if not stocks:
            return None

        # Sort by length descending so longer symbols match first
        symbols = sorted([s["symbol"] for s in stocks if s.get("symbol")], key=len, reverse=True)
        for sym in symbols:
            if sym in text:
                return sym
        return None

    async def _analyze_from_text(self, text: str) -> dict[str, Any]:
        """Extract symbol from text and analyze it."""
        symbol = await self._extract_symbol(text)
        if symbol:
            return await self._get_recommendation(symbol)

        # Try analyze all
        if re.search(r"همه|تمام|تحلیل\s*کن|بررسی\s*همه", text):
            return await self._analyze_all()

        # If no symbol found, try to list available symbols as suggestions
        all_stocks = await self._get_all_stocks()
        if all_stocks:
            top_symbols = [s["symbol"] for s in all_stocks[:20] if s.get("symbol")]
            hint = "، ".join(top_symbols[:10])
            return {
                "text": "نماد مورد نظر در پایگاه داده یافت نشد.\n\n"
                "نمادهای موجود (نمونه):\n"
                f"{hint}\n\n"
                "لطفاً نام سهم را از لیست بالا انتخاب کنید.",
                "type": "info",
            }
        return {
            "text": "داده‌ای برای تحلیل موجود نیست. لطفاً بعداً تلاش کنید.",
            "type": "info",
        }

    async def _find_cheap(self) -> dict[str, Any]:
        stocks = await self._get_all_stocks()
        cheap = [s for s in stocks if 0 < safe_float(s.get("pe"), 999) < 8]
        if not cheap:
            return {"text": "سهم ارزنده‌ای با P/E کمتر از ۸ پیدا نشد.", "type": "info"}

        analyzed = []
        for s in cheap[:10]:
            tech = await self._get_tech_analysis(s["symbol"])
            score = _calculate_score(s, tech)
            analyzed.append({"symbol": s["symbol"], "score": score, "info": s})

        analyzed.sort(key=lambda x: x["score"], reverse=True)

        lines = [f"📊 سهام ارزنده ({len(analyzed)} سهم)", "═" * 50]
        for i, item in enumerate(analyzed[:5], 1):
            info = item["info"]
            lines.append(
                f"{i}. {item['symbol']} | امتیاز: {item['score']}\n"
                f"   P/E: {info.get('pe', 'N/A')} | ROE: {info.get('roe', 'N/A')}% | "
                f"قیمت: {safe_float(info.get('price'), 0):,.0f}"
            )

        return {"text": "\n".join(lines), "type": "screener", "data": {"count": len(analyzed)}}

    async def _find_best(self) -> dict[str, Any]:
        stocks = await self._get_all_stocks()
        if not stocks:
            return {"text": "داده‌ای موجود نیست.", "type": "error"}

        analyzed = []
        for s in stocks[:30]:
            tech = await self._get_tech_analysis(s["symbol"])
            score = _calculate_score(s, tech)
            analyzed.append({"symbol": s["symbol"], "score": score, "info": s, "tech": tech})

        analyzed.sort(key=lambda x: x["score"], reverse=True)

        lines = ["📊 بهترین سهام (بر اساس ترکیب فاکتورها)", "═" * 60]
        for i, item in enumerate(analyzed[:5], 1):
            info = item["info"]
            lines.append(
                f"{i}. {item['symbol']} | امتیاز: {item['score']} | {_recommendation_text(item['score'])}\n"
                f"   P/E: {info.get('pe', 'N/A')} | ROE: {info.get('roe', 'N/A')}% | "
                f"RSI: {info.get('rsi', 'N/A')} | بازده: {safe_float(info.get('return_1d'), 0):+.1f}%"
            )

        best = analyzed[0]
        lines.append("")
        lines.append(f"⭐ بهترین: {best['symbol']} (امتیاز {best['score']})")

        return {"text": "\n".join(lines), "type": "screener", "data": {"count": len(analyzed), "best": best["symbol"]}}

    async def _compare_from_text(self, text: str) -> dict[str, Any]:
        match = re.search(r"مقایسه\s*(\S+)\s*و\s*(\S+)|(\S+)\s*با\s*(\S+)", text)
        if not match:
            return {
                "text": "لطفاً دو نماد را مشخص کنید.\nمثال: مقایسه فولاد و خودرو",
                "type": "error",
            }

        sym1 = (match.group(1) or match.group(3) or "").strip()
        sym2 = (match.group(2) or match.group(4) or "").strip()

        if not sym1 or not sym2:
            return {"text": "لطفاً دو نماد معتبر وارد کنید.", "type": "error"}

        return await self._compare_stocks(sym1, sym2)

    async def _compare_stocks(self, sym1: str, sym2: str) -> dict[str, Any]:
        stocks = await self._get_all_stocks()
        stock_map = {s["symbol"]: s for s in stocks}

        s1 = stock_map.get(sym1)
        s2 = stock_map.get(sym2)

        if not s1 or not s2:
            missing = sym1 if not s1 else sym2
            return {"text": f"سهم '{missing}' پیدا نشد.", "type": "error"}

        tech1 = await self._get_tech_analysis(sym1)
        tech2 = await self._get_tech_analysis(sym2)
        score1 = _calculate_score(s1, tech1)
        score2 = _calculate_score(s2, tech2)

        comparisons = [
            ("قیمت", safe_float(s1.get("price")), safe_float(s2.get("price")), False),
            ("P/E", safe_float(s1.get("pe")), safe_float(s2.get("pe")), False),
            ("ROE", safe_float(s1.get("roe")), safe_float(s2.get("roe")), True),
            ("RSI", safe_float(s1.get("rsi")), safe_float(s2.get("rsi")), False),
            ("بازده", safe_float(s1.get("return_1d")), safe_float(s2.get("return_1d")), True),
        ]

        lines = [f"⚖️ مقایسه {sym1} و {sym2}", "═" * 60]
        for label, v1, v2, higher_better in comparisons:
            if v1 == v2:
                better = "مساوی"
            elif higher_better:
                better = sym1 if v1 > v2 else sym2
            else:
                better = sym1 if v1 < v2 else sym2
            lines.append(f"{label}: {v1:.2f} vs {v2:.2f} → {better}")

        lines.append("")
        lines.append(f"امتیاز: {sym1} = {score1} | {sym2} = {score2}")
        if score1 > score2 + 10:
            lines.append(f"🏆 برنده: {sym1}")
        elif score2 > score1 + 10:
            lines.append(f"🏆 برنده: {sym2}")
        else:
            lines.append("🤝 نتیجه نزدیک است.")

        return {
            "text": "\n".join(lines),
            "type": "comparison",
            "data": {"sym1": sym1, "sym2": sym2, "score1": score1, "score2": score2},
        }

    async def _filter_from_text(self, text: str) -> dict[str, Any]:
        conditions = self._extract_filter_conditions(text)
        if not conditions:
            return {
                "text": "شرطی شناسایی نشد.\nمثال: فیلتر RSI<30 ROE>20 P/E<8",
                "type": "error",
            }

        stocks = await self._get_all_stocks()
        results = []

        for s in stocks:
            rsi_val = safe_float(s.get("rsi"), 0)
            roe_val = safe_float(s.get("roe"), 0)
            pe_val = safe_float(s.get("pe"), 0)
            ret_val = safe_float(s.get("return_1d"), 0)

            if "rsi_min" in conditions and rsi_val < conditions["rsi_min"]:
                continue
            if "rsi_max" in conditions and rsi_val > conditions["rsi_max"]:
                continue
            if "roe_min" in conditions and roe_val < conditions["roe_min"]:
                continue
            if "roe_max" in conditions and roe_val > conditions["roe_max"]:
                continue
            if "pe_max" in conditions and pe_val > conditions["pe_max"]:
                continue
            if "pe_min" in conditions and pe_val < conditions["pe_min"]:
                continue
            if "return_min" in conditions and ret_val < conditions["return_min"]:
                continue
            if "return_max" in conditions and ret_val > conditions["return_max"]:
                continue

            score = _calculate_score(s)
            results.append((s["symbol"], s, score))

        if not results:
            return {"text": "هیچ سهمی با این شرایط پیدا نشد.", "type": "info"}

        results.sort(key=lambda x: x[2], reverse=True)

        lines = [f"🔍 نتایج فیلتر ({len(results)} سهم)", "═" * 50]
        for sym, info, score in results[:10]:
            lines.append(
                f"• {sym} | امتیاز: {score} | "
                f"RSI: {info.get('rsi', 'N/A')} | "
                f"ROE: {info.get('roe', 'N/A')}% | "
                f"P/E: {info.get('pe', 'N/A')} | "
                f"بازده: {safe_float(info.get('return_1d'), 0):+.1f}%"
            )

        return {"text": "\n".join(lines), "type": "filter", "data": {"count": len(results), "conditions": conditions}}

    @staticmethod
    def _extract_filter_conditions(text: str) -> dict[str, float]:
        conditions: dict[str, float] = {}

        patterns = {
            "rsi": re.findall(r"RSI\s*(<=|>=|<|>)\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE),
            "roe": re.findall(r"ROE\s*(<=|>=|<|>)\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE),
            "pe": re.findall(r"P/E\s*(<=|>=|<|>)\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE),
            "ret": re.findall(r"(?:RETURN|بازده)\s*(<=|>=|<|>)\s*(-?\d+(?:\.\d+)?)", text, re.IGNORECASE),
        }

        def _apply(prefix: str, matches: list[tuple[str, str]]):
            for op, value in matches:
                val = float(value)
                if op in (">", ">="):
                    conditions[f"{prefix}_min"] = val
                elif op in ("<", "<="):
                    conditions[f"{prefix}_max"] = val

        _apply("rsi", patterns["rsi"])
        _apply("roe", patterns["roe"])
        _apply("pe", patterns["pe"])
        _apply("return", patterns["ret"])

        return conditions

    async def _get_tech_analysis(self, symbol: str) -> dict[str, Any] | None:
        history = await self._get_stock_history(symbol)
        if not history or len(history) < 20:
            return None
        closes = [safe_float(h.get("close"), 0) for h in history]
        closes = [c for c in closes if c > 0]
        if not closes:
            return None
        return TechnicalIndicators.advanced_analysis(closes)

    async def _get_recommendation(self, symbol: str) -> dict[str, Any]:
        stocks = await self._get_all_stocks()
        stock_map = {s["symbol"]: s for s in stocks}
        info = stock_map.get(symbol)

        if not info:
            return {"text": f"سهم '{symbol}' پیدا نشد.", "type": "error"}

        tech = await self._get_tech_analysis(symbol)
        score = _calculate_score(info, tech)
        rec = _recommendation_text(score)

        factors = []
        pe = safe_float(info.get("pe"), 0)
        roe = safe_float(info.get("roe"), 0)
        rsi_val = safe_float(info.get("rsi"), 50)
        ret = safe_float(info.get("return_1d"), 0)

        if pe > 0:
            if pe < 5:
                factors.append("🟢 P/E بسیار پایین")
            elif pe < 8:
                factors.append("🟢 P/E مناسب")
            elif pe > 12:
                factors.append("🔴 P/E بالا")

        if roe > 30:
            factors.append("🟢 ROE عالی")
        elif roe > 20:
            factors.append("🟢 ROE خوب")
        elif roe < 15:
            factors.append("🔴 ROE پایین")

        if rsi_val < 30:
            factors.append("🟢 اشباع فروش")
        elif rsi_val > 70:
            factors.append("🔴 اشباع خرید")

        if ret > 2:
            factors.append("🟢 بازده روزانه قوی")
        elif ret < -2:
            factors.append("🔴 افت روزانه شدید")

        if tech:
            sma20 = tech.get("sma_20")
            sma50 = tech.get("sma_50")
            if sma20 is not None and sma50 is not None:
                if sma20 > sma50:
                    factors.append("🟢 روند کوتاه‌مدت صعودی")
                else:
                    factors.append("🔴 روند کوتاه‌مدت نزولی")

        lines = [
            f"📊 تحلیل کامل {symbol}",
            "═" * 50,
            f"نام: {info.get('name', '-')}",
            f"گروه: {info.get('sector', '-')}",
            f"قیمت: {safe_float(info.get('price'), 0):,.0f}",
            f"P/E: {info.get('pe', 'N/A')} | ROE: {info.get('roe', 'N/A')}% | RSI: {info.get('rsi', 'N/A')}",
            f"بازده روز: {safe_float(info.get('return_1d'), 0):+.2f}% | حجم: {safe_int(info.get('volume'), 0):,}",
        ]

        if tech:
            lines.append(
                f"SMA20: {tech.get('sma_20', 'N/A')} | "
                f"SMA50: {tech.get('sma_50', 'N/A')} | "
                f"RSI14: {round(tech['rsi_14'], 2) if tech.get('rsi_14') is not None else 'N/A'}"
            )

        if factors:
            lines.append("")
            lines.append("عوامل مهم:")
            for f in factors[:6]:
                lines.append(f"• {f}")

        lines.append("")
        lines.append(f"امتیاز کلی: {score} از 100")
        lines.append(f"پیشنهاد: {rec}")
        lines.append("⚠️ این تحلیل توصیه مالی قطعی نیست.")

        return {
            "text": "\n".join(lines),
            "type": "recommendation",
            "data": {"symbol": symbol, "score": score, "recommendation": rec},
        }

    async def _analyze_all(self) -> dict[str, Any]:
        stocks = await self._get_all_stocks()
        if not stocks:
            return {"text": "داده‌ای برای تحلیل وجود ندارد.", "type": "error"}

        analyzed = []
        for s in stocks[:20]:
            tech = await self._get_tech_analysis(s["symbol"])
            score = _calculate_score(s, tech)
            analyzed.append({"symbol": s["symbol"], "score": score, "info": s, "tech": tech})

        analyzed.sort(key=lambda x: x["score"], reverse=True)

        lines = [f"📊 تحلیل {len(analyzed)} سهم", "═" * 60]
        for i, item in enumerate(analyzed[:5], 1):
            info = item["info"]
            tech = item["tech"]
            lines.append(f"{i}. {item['symbol']} | امتیاز: {item['score']} | {_recommendation_text(item['score'])}")
            lines.append(
                f"   P/E: {info.get('pe', 'N/A')} | ROE: {info.get('roe', 'N/A')}% | "
                f"RSI: {info.get('rsi', 'N/A')} | بازده: {safe_float(info.get('return_1d'), 0):+.1f}%"
            )

        best = analyzed[0]
        worst = analyzed[-1]
        lines.append("═" * 60)
        lines.append(f"⭐ بهترین: {best['symbol']} (امتیاز {best['score']})")
        lines.append(f"⚠️ ضعیف‌ترین: {worst['symbol']} (امتیاز {worst['score']})")

        return {
            "text": "\n".join(lines),
            "type": "analysis",
            "data": {"count": len(analyzed), "best": best["symbol"], "worst": worst["symbol"]},
        }

    async def _portfolio_handler(self, text: str) -> dict[str, Any]:
        if re.search(r"اضافه|add|خرید", text):
            match = re.search(r"(\S+)\s+(\d+)\s+(?:به\s+)?(?:قیمت\s+)?(\d+)", text)
            if match:
                symbol, qty, price = match.group(1), int(match.group(2)), float(match.group(3))
                self.portfolio.add_holding(symbol, qty, price)
                return {"text": f"✅ {symbol} به پرتفوی اضافه شد ({qty} سهم به قیمت {price:,.0f})", "type": "portfolio"}

        if re.search(r"حذف|remove|فروش", text):
            match = re.search(r"(\S+)", text)
            if match:
                symbol = match.group(1)
                self.portfolio.remove_holding(symbol)
                return {"text": f"✅ {symbol} از پرتفوی حذف شد.", "type": "portfolio"}

        if re.search(r"خلاصه|summary|وضعیت", text):
            stocks = await self._get_all_stocks()
            prices = {s["symbol"]: safe_float(s.get("price"), 0) for s in stocks}
            self.portfolio.update_prices(prices)
            summary = self.portfolio.get_summary()

            if not summary["holdings"]:
                return {
                    "text": "پرتفوی خالی است. با دستور «اضافه [نماد] [تعداد] [قیمت]» سهم اضافه کنید.",
                    "type": "portfolio",
                }

            lines = [
                "💼 خلاصه پرتفوی",
                "═" * 50,
                f"ارزش کل: {summary['total_value']:,.0f} ریال",
                f"سود/زیان: {summary['total_pnl']:+,.0f} ریال ({summary['total_pnl_pct']:+.2f}%)",
                "",
                "دارایی‌ها:",
            ]
            for h in summary["holdings"]:
                emoji = "🟢" if h["pnl"] >= 0 else "🔴"
                lines.append(
                    f"  {emoji} {h['symbol']}: {h['quantity']} سهم | "
                    f"میانگین: {h['avg_price']:,.0f} | فعلی: {h['current_price']:,.0f} | "
                    f"سود: {h['pnl']:+,.0f} ({h['pnl_pct']:+.2f}%) | وزن: {h['weight']:.1f}%"
                )

            return {"text": "\n".join(lines), "type": "portfolio", "data": summary}

        return {
            "text": (
                "💼 مدیریت پرتفوی\n\n"
                "دستورات:\n"
                "• «اضافه فولاد 100 50000» — اضافه کردن سهم\n"
                "• «حذف فولاد» — حذف سهم\n"
                "• «خلاصه پرتفوی» — نمایش وضعیت"
            ),
            "type": "portfolio",
        }

    async def _alert_handler(self, text: str) -> dict[str, Any]:
        if re.search(r"اضافه|add|جدید", text):
            match = re.search(
                r"(\S+)\s+(rsi|price|قیمت|hajm|حجم)\s*(above|below|بالاتر|پایین‌تر)\s*(\d+(?:\.\d+)?)",
                text,
                re.IGNORECASE,
            )
            if match:
                symbol = match.group(1)
                alert_type = "rsi" if "rsi" in match.group(2).lower() else "price"
                condition = "above" if "above" in match.group(3).lower() or "بالاتر" in match.group(3) else "below"
                threshold = float(match.group(4))
                self.alert_manager.add_alert(symbol, alert_type, condition, threshold)
                return {"text": f"✅ هشدار ثبت شد: {symbol} {alert_type} {condition} {threshold}", "type": "alert"}

            return {"text": "فرمت نادرست. مثال: هشدار فولاد rsi above 70", "type": "error"}

        if re.search(r"لیست|list|همه|active", text):
            alerts = self.alert_manager.get_active_alerts()
            if not alerts:
                return {"text": "هشداری ثبت نشده است.", "type": "alert"}

            lines = ["🔔 هشدارهای فعال:", "═" * 40]
            for a in alerts:
                status = "✅ فعال" if not a["triggered"] else "🔔 فعال شده"
                lines.append(f"• {a['symbol']} | {a['type']} {a['condition']} {a['threshold']} | {status}")
            return {"text": "\n".join(lines), "type": "alert"}

        if re.search(r"حذف|remove|delete", text):
            match = re.search(r"(\S+)", text)
            if match:
                symbol = match.group(1)
                self.alert_manager.remove_alert(symbol)
                return {"text": f"✅ هشدارهای {symbol} حذف شد.", "type": "alert"}

        return {
            "text": (
                "🔔 مدیریت هشدارها\n\n"
                "دستورات:\n"
                "• «هشدار فولاد rsi above 70» — هشدار جدید\n"
                "• «لیست هشدارها» — نمایش هشدارها\n"
                "• «حذف هشدار فولاد» — حذف هشدار"
            ),
            "type": "alert",
        }

    async def _report_handler(self, text: str) -> dict[str, Any]:
        stocks = await self._get_all_stocks()
        alerts = self.alert_manager.get_active_alerts()
        report = self.report_generator.daily_market_report(stocks, alerts)
        return {"text": report, "type": "report"}

    async def _pattern_handler(self, text: str) -> dict[str, Any]:
        symbol = await self._extract_symbol(text)
        if not symbol:
            return {"text": "نمادی شناسایی نشد. مثال: الگوهای فولاد", "type": "error"}

        history = await self._get_stock_history(symbol)
        if not history or len(history) < 5:
            return {"text": f"داده کافی برای {symbol} موجود نیست.", "type": "error"}

        opens = [h.get("open", h.get("close", 0)) for h in history]
        highs = [h.get("high", h.get("close", 0)) for h in history]
        lows = [h.get("low", h.get("close", 0)) for h in history]
        closes = [h.get("close", 0) for h in history]

        patterns = CandlestickPatterns.detect_all(opens, highs, lows, closes)

        if not patterns:
            return {"text": f"الگوی خاصی برای {symbol} شناسایی نشد.", "type": "pattern"}

        lines = [f"🕯️ الگوهای شمعی {symbol}:", "═" * 40]
        for p in patterns:
            emoji = "🟢" if p["type"] == "bullish" else "🔴" if p["type"] == "bearish" else "🟡"
            lines.append(f"  {emoji} {p['name']}: {p['description']}")

        return {"text": "\n".join(lines), "type": "pattern", "data": {"symbol": symbol, "patterns": patterns}}

    async def _multi_timeframe_handler(self, text: str) -> dict[str, Any]:
        symbol = await self._extract_symbol(text)
        if not symbol:
            return {"text": "نمادی شناسایی نشد. مثال: تحلیل چند بازه فولاد", "type": "error"}

        history = await self._get_stock_history(symbol)
        if not history or len(history) < 20:
            return {"text": f"داده کافی برای {symbol} موجود نیست.", "type": "error"}

        mtf = MultiTimeframeAnalysis.analyze_multi_timeframe(history)

        lines = [
            f"📊 تحلیل چند بازه زمانی {symbol}",
            "═" * 50,
            f"روزانه: {mtf['daily_trend']}",
            f"  SMA5: {mtf.get('daily_sma5', 'N/A')} | SMA20: {mtf.get('daily_sma20', 'N/A')}",
            f"هفتگی: {mtf['weekly_trend']}",
            f"  SMA5: {mtf.get('weekly_sma5', 'N/A')}",
            f"ماهانه: {mtf['monthly_trend']}",
            f"  SMA3: {mtf.get('monthly_sma3', 'N/A')}",
        ]

        trends = [mtf["daily_trend"], mtf["weekly_trend"], mtf["monthly_trend"]]
        if all(t == "صعودی" for t in trends):
            lines.append("\n🟢 روند هماهنگ صعودی در تمام بازه‌ها")
        elif all(t == "نزولی" for t in trends):
            lines.append("\n🔴 روند هماهنگ نزولی در تمام بازه‌ها")
        else:
            lines.append("\n⚠️ روند ناهمگون - احتیاط لازم است")

        return {"text": "\n".join(lines), "type": "multi_timeframe", "data": mtf}

    async def _volume_profile_handler(self, text: str) -> dict[str, Any]:
        symbol = await self._extract_symbol(text)
        if not symbol:
            return {"text": "نمادی شناسایی نشد. مثال: حجم در قیمت فولاد", "type": "error"}

        history = await self._get_stock_history(symbol)
        if not history or len(history) < 10:
            return {"text": f"داده کافی برای {symbol} موجود نیست.", "type": "error"}

        closes = [h.get("close", 0) for h in history]
        volumes = [h.get("volume", 0) for h in history]
        vp = self.volume_profile.calculate(closes, volumes)

        if not vp:
            return {"text": "محاسبه حجم در قیمت ممکن نبود.", "type": "error"}

        lines = [
            f"📊 حجم در قیمت {symbol}",
            "═" * 50,
            f"POC (نقطه کنترل): {vp['poc']:,.2f}",
            f"منطقه ارزش بالا: {vp['value_area_high']:,.2f}",
            f"منطقه ارزش پایین: {vp['value_area_low']:,.2f}",
            f"حجم کل: {vp['total_volume']:,.0f}",
            "",
            "بیشترین حجم در سطوح:",
        ]
        for level in vp.get("levels", [])[:5]:
            lines.append(f"  • {level['price']:,.2f}: {level['volume']:,.0f}")

        return {"text": "\n".join(lines), "type": "volume_profile", "data": vp}

    async def _correlation_handler(self, text: str) -> dict[str, Any]:
        # Extract target symbol from various Persian query formats
        # "همبستگی فولاد خودرو" or "نماد موج با کدام سهم همبستگی دارد"
        clean = (
            text.replace("همبستگی", "")
            .replace("correlation", "")
            .replace("با کدام سهم", "")
            .replace("دارد", "")
            .replace("نماد", "")
            .strip()
        )
        symbols = re.findall(r"[\u0600-\u06FF\w]+", clean)
        # Filter out common non-symbol words
        stopwords = {
            "با",
            "کدام",
            "سهم",
            "هست",
            "هستند",
            "دارد",
            "دارند",
            "کند",
            "کنید",
            "بده",
            "بدهید",
            "نماد",
            "ها",
            "های",
        }
        symbols = [s for s in symbols if s not in stopwords and len(s) >= 2]

        target_symbol = symbols[0] if symbols else None
        compare_symbols = symbols[1:] if len(symbols) > 1 else []

        # If only target symbol, find similar stocks from same sector
        if target_symbol and not compare_symbols:
            try:
                all_stocks = await self._get_all_stocks()
                # Get target's sector
                target_sector = None
                for s in all_stocks:
                    if s.get("symbol") == target_symbol:
                        target_sector = s.get("sector", "")
                        break
                # Find stocks from same sector
                if target_sector:
                    compare_symbols = [
                        s["symbol"]
                        for s in all_stocks
                        if s.get("sector") == target_sector and s.get("symbol") != target_symbol
                    ][:8]
                if not compare_symbols:
                    compare_symbols = [s["symbol"] for s in all_stocks if s.get("symbol") != target_symbol][:8]
            except Exception:
                pass

        if not target_symbol:
            return {
                "text": "لطفاً نماد مورد نظر را مشخص کنید.\nمثال: «همبستگی فولاد خودرو» یا «نماد موج با کدام سهم همبستگی دارد»",
                "type": "error",
            }

        all_symbols = [target_symbol] + compare_symbols

        history_data = {}
        for sym in all_symbols[:10]:
            try:
                history = await self._get_stock_history(sym)
                if history and len(history) >= 10:
                    history_data[sym] = [h.get("close", 0) for h in history]
            except Exception:
                continue

        if len(history_data) < 2:
            return {
                "text": f"داده کافی برای محاسبه همبستگی {target_symbol} موجود نیست.\nممکن است نماد در دیتابیس وجود نداشته باشد یا تاریخچه کافی ثبت نشده باشد.",
                "type": "error",
            }

        correlations = CorrelationAnalysis.sector_correlation(history_data)

        # Filter correlations that involve the target symbol
        target_corrs = {k: v for k, v in correlations.items() if target_symbol in k}

        if not target_corrs:
            target_corrs = correlations

        lines = [f"📊 همبستگی {target_symbol} با سایر سهام:", "═" * 50]
        sorted_corrs = sorted(target_corrs.items(), key=lambda x: abs(x[1]), reverse=True)

        for pair, corr in sorted_corrs[:10]:
            strength = (
                "خیلی قوی" if abs(corr) > 0.8 else "قوی" if abs(corr) > 0.6 else "متوسط" if abs(corr) > 0.4 else "ضعیف"
            )
            if corr > 0.6:
                emoji = "🟢"
            elif corr < -0.4:
                emoji = "🔴"
            else:
                emoji = "🟡"
            lines.append(f"  {emoji} {pair}: {corr:.3f} ({strength})")

        lines.append(f"\nتعداد نمادهای مقایسه شده: {len(history_data)}")
        return {"text": "\n".join(lines), "type": "correlation", "data": target_corrs}

    # ── Backtest handlers ────────────────────────────

    async def _backtest_handler(self, text: str) -> dict[str, Any]:
        """Handle backtest-related commands."""
        lines = [
            "📊 بک‌تست (Backtest)",
            "═" * 60,
            "",
            "بک‌تست به شما امکان می‌دهد استراتژی‌های معاملاتی را روی داده‌های تاریخی",
            "آزمایش کنید و عملکرد آنها را بسنجید.",
            "",
            "📋 استراتژی‌های موجود:",
            "• moving_average_cross — تقاطع میانگین‌های متحرک",
            "• momentum — استراتژی مومنتوم",
            "• mean_reversion — بازگشت به میانگین",
            "• breakout — شکست قیمتی",
            "• rsi_reversion — بازگشت RSI",
            "• volatility_breakout — شکست نوسانی",
            "• half_trend — نصف روند",
            "• squeeze_momentum — مومنتوم فشرده",
            "• support_resistance — حمایت و مقاومت",
            "",
            "🔧 پارامترهای قابل تنظیم:",
            "• سرمایه اولیه (initial_capital)",
            "• حد ضرر (stop_loss_pct)",
            "• حد سود (take_profit_pct)",
            "• کارمزد (commission_pct)",
            "• Slippage (slippage_bps)",
            "• روش حجم معامله (sizing_method)",
            "",
            "💡 مثال:",
            "«بک‌تست moving_average_cross روی فولاد با سرمایه ۱ میلیارد»",
            "«بک‌تست با حد ضرر ۵٪ و حد سود ۱۰٪»",
            "«مقایسه همه استراتژی‌ها روی فولاد»",
            "",
            "⚙️ قابلیت‌های پیشرفته:",
            "• بهینه‌سازی پارامترها (Walk-Forward, Monte Carlo)",
            "• بک‌تست پرتفوی (چند سهم همزمان)",
            "• تولید خودکار استراتژی (Grid Search, Genetic)",
            "• مقایسه همزمان همه استراتژی‌ها",
        ]
        return {"text": "\\n".join(lines), "type": "info"}

    async def _optimization_handler(self, text: str) -> dict[str, Any]:
        """Handle optimization-related commands."""
        lines = [
            "⚙️ بهینه‌سازی پارامترها",
            "═" * 50,
            "",
            "سه روش بهینه‌سازی در دسترس است:",
            "",
            "۱. Walk-Forward Optimization",
            "   • داده به چند پنجره آموزش/تست تقسیم می‌شود",
            "   • از overfitting جلوگیری می‌کند",
            "   • بهترین پارامترها را در پنجره‌های مختلف انتخاب می‌کند",
            "",
            "۲. Monte Carlo Simulation",
            "   • با شبیه‌سازی ۱۰۰۰+ بار معاملات",
            "   • فاصله اطمینان بازده را محاسبه می‌کند",
            "   • ریسک واقعی استراتژی را نشان می‌دهد",
            "",
            "۳. Grid Search",
            "   • همه ترکیب‌های ممکن پارامترها را امتحان می‌کند",
            "   • بهترین ترکیب را بر اساس معیار مورد نظر انتخاب می‌کند",
            "",
            "💡 مثال:",
            "«بهینه‌سازی moving_average_cross روی فولاد»",
            "«walk forward روی فولاد»",
            "«مونت کارلو فولاد»",
        ]
        return {"text": "\\n".join(lines), "type": "info"}

    async def _strategy_handler(self, text: str) -> dict[str, Any]:
        """List available strategies for backtesting."""
        from backtesting.strategies.registry import get_strategy_registry, register_all_strategies

        registry = get_strategy_registry()
        if not registry.list_names():
            register_all_strategies()
        strategies = registry.list_strategies()
        lines = ["📋 استراتژی‌های موجود برای بک‌تست:", "═" * 60]
        for s in strategies:
            name = s.get("name", "")
            desc = s.get("description", "")
            lines.append(f"• {name}")
            if desc:
                lines.append(f"  {desc[:100]}")
        return {"text": "\\n".join(lines), "type": "info"}

    async def _compare_strategies_handler(self, text: str) -> dict[str, Any]:
        """Handle strategy comparison commands."""
        lines = [
            "⚖️ مقایسه استراتژی‌ها",
            "═" * 50,
            "",
            "می‌توانید همه استراتژی‌ها را روی یک نماد مقایسه کنید.",
            "",
            "معیارهای مقایسه:",
            "• Total Return — بازده کل",
            "• Sharpe Ratio — نسبت بازده به ریسک",
            "• Win Rate — درصد معاملات برنده",
            "• Max Drawdown — حداکثر کاهش سرمایه",
            "• Profit Factor — نسبت سود به زیان",
            "• Deflated Sharpe — تعدیل شده برای تعداد استراتژی‌ها",
            "",
            "💡 مثال:",
            "«مقایسه همه استراتژی‌ها روی فولاد»",
            "«بهترین استراتژی برای خودرو کدومه»",
        ]
        return {"text": "\\n".join(lines), "type": "info"}

    async def _strategy_generation_handler(self, text: str) -> dict[str, Any]:
        """Handle strategy generation commands."""
        lines = [
            "🧬 تولید خودکار استراتژی",
            "═" * 50,
            "",
            "سیستم می‌تواند به صورت خودکار هزاران استراتژی را با ترکیب",
            "پارامترهای مختلف تولید، آزمایش و فیلتر کند.",
            "",
            "روش‌های تولید:",
            "• Grid Search — جستجوی کامل همه ترکیب‌ها (تا ۵۰۰۰)",
            "• Genetic Algorithm — بهینه‌سازی ژنتیک (تا ۱۲ نسل)",
            "",
            "فیلترهای اعمال شده:",
            "• Sharpe > 1",
            "• Win Rate > 40%",
            "• Max Drawdown < 30%",
            "• Profit Factor > 1.3",
            "• تعداد معاملات > ۱۰",
            "",
            "💡 مثال:",
            "«تولید استراتژی برای فولاد»",
            "«ساخت ۵۰۰۰ استراتژی با grid search»",
        ]
        return {"text": "\\n".join(lines), "type": "info"}
