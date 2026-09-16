"""📐 TSE Technical Engine — اندیکاتورهای کامل با الگوریتم‌های واقعی.

بخش ۳-ب معماری Enterprise سهام:
  - RSI(14) با Wilder smoothing + کشف واگرایی‌های RD+/RD-/HD+/HD- بر پایه اکسترمم‌های محلی
  - MACD(12,26,9) با کراس سیگنال/صفر
  - EMA 20/50/100/200 + Golden/Death Cross
  - Ichimoku کامل (تنکانسن، کیجونسن، سنکو A/B، وضعیت ابر، Kumo Twist)
  - Bollinger(20,2) + Keltner(20,1.5×ATR) → Squeeze
  - VWAP (روزانه و لنگردار)
  - ATR(14) با Wilder، MFI(14)
  - Pivot Points (Standard / Camarilla / Fibonacci)

همه توابع خالص‌اند — ورودی: کندل‌های OLHC(V) قدیمی→جدید. No Look-Ahead.
"""

from __future__ import annotations

import math
from typing import Any

Candle = dict[str, float]  # {date, open, high, low, close, volume, value?}


# ── ابزار پایه ───────────────────────────────────────────────────────────────


def _sma(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    running = sum(values[:period])
    out[period - 1] = running / period
    for i in range(period, len(values)):
        running += values[i] - values[i - period]
        out[i] = running / period
    return out


def _ema(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    k = 2.0 / (period + 1.0)
    ema = sum(values[:period]) / period
    out[period - 1] = ema
    for i in range(period, len(values)):
        ema = values[i] * k + ema * (1 - k)
        out[i] = ema
    return out


def _wilder_smooth(values: list[float], period: int) -> list[float | None]:
    """هموارسازی Wilder (مبنای RSI/ATR کلاسیک)."""
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    avg = sum(values[:period]) / period
    out[period - 1] = avg
    for i in range(period, len(values)):
        avg = (avg * (period - 1) + values[i]) / period
        out[i] = avg
    return out


def _last_valid(series: list[float | None]) -> float | None:
    for v in reversed(series):
        if v is not None and not math.isnan(v):
            return v
    return None


# ── RSI + واگرایی‌ها ─────────────────────────────────────────────────────────


def rsi(closes: list[float], period: int = 14) -> list[float | None]:
    gains: list[float] = [0.0]
    losses: list[float] = [0.0]
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    avg_gain = _wilder_smooth(gains, period)
    avg_loss = _wilder_smooth(losses, period)
    out: list[float | None] = [None] * len(closes)
    for i in range(len(closes)):
        g, loss_v = avg_gain[i], avg_loss[i]
        if g is None or loss_v is None:
            continue
        if loss_v == 0:
            out[i] = 100.0 if g > 0 else 50.0
        else:
            rs = g / loss_v
            out[i] = 100.0 - 100.0 / (1.0 + rs)
    return out


def _local_extrema(values: list[float], lookback: int = 3) -> tuple[list[int], list[int]]:
    """یافتن اکسترمم‌های محلی (peaks و troughs) با پنجره lookback."""
    peaks: list[int] = []
    troughs: list[int] = []
    n = len(values)
    for i in range(lookback, n - lookback):
        window = values[i - lookback : i + lookback + 1]
        if values[i] == max(window):
            peaks.append(i)
        if values[i] == min(window):
            troughs.append(i)
    return peaks, troughs


def detect_rsi_divergence(
    closes: list[float], rsi_values: list[float | None], lookback: int = 3
) -> str | None:
    """کشف واگرایی RSI با مقایسه دو اکسترمم اخیر.

    RD+ : کف قیمت پایین‌تر + کف RSI بالاتر (صعودی)
    RD- : سقف قیمت بالاتر + سقف RSI پایین‌تر (نزولی)
    HD+ : کف قیمت بالاتر + کف RSI پایین‌تر (ادامه صعود — مخفی مثبت)
    HD- : سقف قیمت پایین‌تر + سقف RSI بالاتر (ادامه نزول — مخفی منفی)
    """
    if len(closes) < 40:
        return None
    peaks, troughs = _local_extrema(closes, lookback)
    if len(peaks) >= 2:
        p1, p2 = peaks[-2], peaks[-1]
        r1, r2 = rsi_values[p1], rsi_values[p2]
        if r1 is not None and r2 is not None:
            if closes[p2] > closes[p1] and r2 < r1:
                return "RD-"
            if closes[p2] < closes[p1] and r2 > r1:
                return "HD-"
    if len(troughs) >= 2:
        t1, t2 = troughs[-2], troughs[-1]
        r1, r2 = rsi_values[t1], rsi_values[t2]
        if r1 is not None and r2 is not None:
            if closes[t2] < closes[t1] and r2 > r1:
                return "RD+"
            if closes[t2] > closes[t1] and r2 < r1:
                return "HD+"
    return None


# ── MACD ─────────────────────────────────────────────────────────────────────


def macd(
    closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> dict[str, list[float | None] | str]:
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    macd_line: list[float | None] = [
        (f - s) if (f is not None and s is not None) else None
        for f, s in zip(ema_fast, ema_slow, strict=False)
    ]
    valid = [v for v in macd_line if v is not None]
    sig: list[float | None] = [None] * len(closes)
    if len(valid) >= signal:
        sig_valid = _ema(valid, signal)
        j = 0
        for i in range(len(closes)):
            if macd_line[i] is not None:
                if j < len(sig_valid):
                    sig[i] = sig_valid[j]
                j += 1
    hist = [
        (m - s) if (m is not None and s is not None) else None
        for m, s in zip(macd_line, sig, strict=False)
    ]
    cross = "none"
    for i in range(1, len(closes)):
        m0, s0 = macd_line[i - 1], sig[i - 1]
        m1, s1 = macd_line[i], sig[i]
        if None in (m0, s0, m1, s1):
            continue
        if m0 <= s0 and m1 > s1:  # type: ignore[operator]
            cross = "bullish_cross"
        elif m0 >= s0 and m1 < s1:  # type: ignore[operator]
            cross = "bearish_cross"
    return {"macd": macd_line, "signal": sig, "hist": hist, "cross": cross}


# ── EMA + Golden/Death Cross ─────────────────────────────────────────────────


def ema_cross(closes: list[float]) -> tuple[dict[str, float | None], str]:
    e20 = _ema(closes, 20)
    e50 = _ema(closes, 50)
    e100 = _ema(closes, 100)
    e200 = _ema(closes, 200)
    cross = "none"
    for i in range(1, len(closes)):
        a0, b0 = e50[i - 1], e200[i - 1] if len(e200) > i - 1 else None
        a1, b1 = e50[i], e200[i] if len(e200) > i else None
        if None in (a0, b0, a1, b1):
            continue
        if a0 <= b0 and a1 > b1:  # type: ignore[operator]
            cross = "golden"
        elif a0 >= b0 and a1 < b1:  # type: ignore[operator]
            cross = "death"
    vals = {"ema_20": _last_valid(e20), "ema_50": _last_valid(e50), "ema_100": _last_valid(e100), "ema_200": _last_valid(e200)}
    return vals, cross


# ── Ichimoku ─────────────────────────────────────────────────────────────────


def ichimoku(
    candles: list[Candle], tenkan_p: int = 9, kijun_p: int = 26, senkou_p: int = 52
) -> dict[str, Any]:
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    closes = [c["close"] for c in candles]

    def midpoint(period: int, series_h: list[float], series_l: list[float]) -> list[float | None]:
        out: list[float | None] = [None] * len(series_h)
        for i in range(period - 1, len(series_h)):
            out[i] = (max(series_h[i - period + 1 : i + 1]) + min(series_l[i - period + 1 : i + 1])) / 2.0
        return out

    tenkan = midpoint(tenkan_p, highs, lows)
    kijun = midpoint(kijun_p, highs, lows)

    # Senkou A/B با شیفت +26 به جلو (مقدار «امروزِ» ابرِ آتی = مقادیر ۲۶ کندل قبل)
    span_a_now: list[float | None] = [None] * len(candles)
    span_b_now: list[float | None] = [None] * len(candles)
    for i in range(len(candles)):
        j = i - kijun_p  # شیفت ۲۶ دوره به عقب برای ابرِ فعلی
        if j < 0:
            continue
        ta, tb = tenkan[j], kijun[j]
        sa = (ta + tb) / 2.0 if ta is not None and tb is not None else None
        hb = highs[j - senkou_p + 1 : j + 1]
        lb = lows[j - senkou_p + 1 : j + 1]
        sb = (max(hb) + min(lb)) / 2.0 if len(hb) == senkou_p else None
        span_a_now[i] = sa
        span_b_now[i] = sb

    price = closes[-1]
    sa = _last_valid(span_a_now)
    sb = _last_valid(span_b_now)
    if sa is not None and sb is not None:
        cloud_top, cloud_bot = max(sa, sb), min(sa, sb)
        if price > cloud_top:
            state = "above_kumo"
        elif price < cloud_bot:
            state = "below_kumo"
        else:
            state = "inside_kumo"
        twist = "bullish_twist" if sa > sb else "bearish_twist"
    else:
        state, twist = "insufficient", "insufficient"

    tk_cross = "none"
    for i in range(max(1, kijun_p), len(candles)):
        t0, k0, t1, k1 = tenkan[i - 1], kijun[i - 1], tenkan[i], kijun[i]
        if None in (t0, k0, t1, k1):
            continue
        if t0 <= k0 and t1 > k1:  # type: ignore[operator]
            tk_cross = "tk_bullish"
        elif t0 >= k0 and t1 < k1:  # type: ignore[operator]
            tk_cross = "tk_bearish"

    return {
        "tenkan": _last_valid(tenkan),
        "kijun": _last_valid(kijun),
        "senkou_a": sa,
        "senkou_b": sb,
        "state": state,
        "kumo_twist": twist,
        "tk_cross": tk_cross,
    }


# ── Bollinger + Keltner Squeeze ──────────────────────────────────────────────


def bollinger(closes: list[float], period: int = 20, mult: float = 2.0) -> dict[str, float | None]:
    mid = _sma(closes, period)
    m = _last_valid(mid)
    if m is None:
        return {"upper": None, "middle": None, "lower": None, "bandwidth": None}
    window = closes[-period:]
    variance = sum((c - m) ** 2 for c in window) / period
    sd = math.sqrt(variance)
    upper = m + mult * sd
    lower = m - mult * sd
    return {"upper": upper, "middle": m, "lower": lower, "bandwidth": (upper - lower) / m if m else None}


def keltner(candles: list[Candle], period: int = 20, atr_mult: float = 1.5) -> dict[str, float | None]:
    closes = [c["close"] for c in candles]
    m = _last_valid(_ema(closes, period))
    atr_v = atr(candles, 14)
    if m is None or atr_v is None:
        return {"upper": None, "lower": None}
    return {"upper": m + atr_mult * atr_v, "lower": m - atr_mult * atr_v}


def squeeze_state(bb: dict[str, Any], kc: dict[str, Any]) -> str | None:
    """Squeeze: باندهای بولینگر داخل کانال کلتنر → انتظار انفجار قیمت."""
    if None in (bb.get("upper"), bb.get("lower"), kc.get("upper"), kc.get("lower")):
        return None
    if bb["lower"] > kc["lower"] and bb["upper"] < kc["upper"]:
        return "squeeze"
    return "no_squeeze"


# ── ATR / MFI / VWAP ─────────────────────────────────────────────────────────


def atr(candles: list[Candle], period: int = 14) -> float | None:
    if len(candles) < period + 1:
        return None
    trs: list[float] = [0.0]
    for i in range(1, len(candles)):
        h, low_v = candles[i]["high"], candles[i]["low"]
        pc = candles[i - 1]["close"]
        trs.append(max(h - low_v, abs(h - pc), abs(low_v - pc)))
    smoothed = _wilder_smooth(trs, period)
    return _last_valid(smoothed)


def mfi(candles: list[Candle], period: int = 14) -> float | None:
    if len(candles) < period + 1:
        return None
    pos_flow = 0.0
    neg_flow = 0.0
    for i in range(len(candles) - period, len(candles)):
        tp = (candles[i]["high"] + candles[i]["low"] + candles[i]["close"]) / 3.0
        tp_prev = (candles[i - 1]["high"] + candles[i - 1]["low"] + candles[i - 1]["close"]) / 3.0
        flow = tp * candles[i]["volume"]
        if tp > tp_prev:
            pos_flow += flow
        elif tp < tp_prev:
            neg_flow += flow
    if neg_flow == 0:
        return 100.0 if pos_flow > 0 else None
    return 100.0 - 100.0 / (1.0 + pos_flow / neg_flow)


def vwap_intraday(ticks_or_candles: list[dict[str, Any]]) -> float | None:
    """VWAP روزانه: Σ(price×volume) / Σ(volume) — از کندل‌های درون‌روزی یا تیک."""
    notional = 0.0
    volume = 0.0
    for item in ticks_or_candles:
        p = float(item.get("price") or item.get("close") or 0)
        v = float(item.get("volume") or 0)
        if p > 0 and v > 0:
            notional += p * v
            volume += v
    return notional / volume if volume > 0 else None


def vwap_anchored(candles: list[Candle], anchor_index: int) -> float | None:
    """VWAP لنگردار از یک رویداد (مجمع/افزایش سرمایه/کف تاریخی) تا امروز."""
    if anchor_index < 0 or anchor_index >= len(candles):
        return None
    window = candles[anchor_index:]
    return vwap_intraday(window)


# ── Pivot Points ─────────────────────────────────────────────────────────────


def pivot_points(high: float, low: float, close: float) -> dict[str, Any]:
    """سه استاندارد: Classic، Camarilla، Fibonacci — برای حمایت/مقاومت روز بعد."""
    p = (high + low + close) / 3.0
    rng = high - low
    classic = {
        "P": p,
        "R1": 2 * p - low, "S1": 2 * p - high,
        "R2": p + rng, "S2": p - rng,
        "R3": high + 2 * (p - low), "S3": low - 2 * (high - p),
    }
    # Camarilla با ضرایب استاندارد
    cam = {
        "H4": close + rng * 1.1 / 2.0,
        "H3": close + rng * 1.1 / 4.0,
        "L3": close - rng * 1.1 / 4.0,
        "L4": close - rng * 1.1 / 2.0,
    }
    fib = {
        "R_618": p + 0.618 * rng, "R_382": p + 0.382 * rng,
        "S_382": p - 0.382 * rng, "S_618": p - 0.618 * rng,
    }
    return {"classic": classic, "camarilla": cam, "fibonacci": fib}


# ── همگرایی چند تایم‌فریمی (MTF) ────────────────────────────────────────────


def trend_alignment_score(
    daily_closes: list[float], weekly_closes: list[float]
) -> float | None:
    """امتیاز همگرایی روند Daily/Weekly بر اساس ساختار EMA20/EMA50 هر تایم.

    100 = هر دو تایم صعودی | 0 = هر دو نزولی | 50 = مغایرت.
    """
    if len(daily_closes) < 50 or len(weekly_closes) < 50:
        return None

    def _trend(closes: list[float]) -> int:
        e20 = _last_valid(_ema(closes, 20))
        e50 = _last_valid(_ema(closes, 50))
        if e20 is None or e50 is None:
            return 0
        if closes[-1] > e20 > e50:
            return 1
        if closes[-1] < e20 < e50:
            return -1
        return 0

    d, w = _trend(daily_closes), _trend(weekly_closes)
    if d == 1 and w == 1:
        return 100.0
    if d == -1 and w == -1:
        return 0.0
    if d == 1 or w == 1:
        return 65.0   # یک تایم صعودی
    if d == -1 or w == -1:
        return 35.0
    return 50.0


# ── Aggregate snapshot ───────────────────────────────────────────────────────


def compute_indicator_snapshot(candles: list[Candle]) -> dict[str, Any]:
    """اسنپ‌شات کامل اندیکاتورها از کندل‌های روزانه (قدیمی→جدید)."""
    closes = [c["close"] for c in candles]
    if len(closes) < 30:
        return {"ok": False, "reason": "insufficient_candles"}

    r = rsi(closes)
    rsi_last = _last_valid(r)
    divergence = detect_rsi_divergence(closes, r)
    macd_res = macd(closes)
    emas, ema_cross_state = ema_cross(closes)
    ich = ichimoku(candles)
    bb = bollinger(closes)
    kc = keltner(candles)
    sq = squeeze_state(bb, kc)
    atr_v = atr(candles)
    mfi_v = mfi(candles)

    # حمایت/مقاومت از پیوت دیروز
    yesterday = candles[-2] if len(candles) >= 2 else candles[-1]
    pivots = pivot_points(yesterday["high"], yesterday["low"], yesterday["close"])

    weekly = [closes[i : i + 5][-1] for i in range(0, len(closes) - 4, 5)]
    tas = trend_alignment_score(closes, weekly)

    return {
        "ok": True,
        "rsi_14": rsi_last,
        "rsi_divergence": divergence or "none",
        "macd": _last_valid(macd_res["macd"]),  # type: ignore[arg-type]
        "macd_signal": _last_valid(macd_res["signal"]),  # type: ignore[arg-type]
        "macd_hist": _last_valid(macd_res["hist"]),  # type: ignore[arg-type]
        "macd_cross": macd_res["cross"],
        **emas,
        "ema_cross": ema_cross_state,
        **{f"bb_{k}": v for k, v in bb.items()},
        "squeeze": sq,
        "ichimoku": ich,
        "atr_14": atr_v,
        "mfi_14": mfi_v,
        "pivots": pivots,
        "trend_alignment_score": tas,
    }
