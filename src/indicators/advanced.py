"""Advanced Technical Indicators for Iranian Market Strategy Generation.

10 new indicators that complement the existing 20 from general.py, stocks.py, and trend_momentum.py.
All functions operate on plain Python lists (no numpy/pandas dependency).
"""
from __future__ import annotations


def _ema(data: list[float], period: int) -> list[float | None]:
    """Exponential Moving Average helper."""
    result: list[float | None] = []
    k = 2 / (period + 1)
    for i, val in enumerate(data):
        if i < period - 1:
            result.append(None)
        elif i == period - 1:
            result.append(sum(data[:period]) / period)
        else:
            prev = result[-1]
            if prev is not None:
                result.append((val - prev) * k + prev)
            else:
                result.append(None)
    return result


def _sma(data: list[float], period: int) -> list[float | None]:
    """Simple Moving Average helper."""
    result: list[float | None] = []
    for i in range(len(data)):
        if i < period - 1:
            result.append(None)
        else:
            result.append(sum(data[i - period + 1: i + 1]) / period)
    return result


def _true_range(high: list[float], low: list[float], close: list[float]) -> list[float]:
    """True Range helper."""
    trs: list[float] = []
    for i in range(len(high)):
        if i == 0:
            trs.append(high[i] - low[i])
        else:
            tr = max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1]),
            )
            trs.append(tr)
    return trs


def _atr(high: list[float], low: list[float], close: list[float], period: int) -> list[float | None]:
    """Average True Range helper."""
    trs = _true_range(high, low, close)
    result: list[float | None] = []
    for i in range(len(trs)):
        if i < period - 1:
            result.append(None)
        else:
            result.append(sum(trs[i - period + 1: i + 1]) / period)
    return result


# ── 21. EMA Crossover ─────────────────────────────────────────────────────────────

def calculate_ema_crossover(
    close: list[float],
    fast_period: int = 10,
    slow_period: int = 30,
) -> dict[str, list]:
    """EMA Crossover: golden cross (buy) and death cross (sell).

    Returns:
        {"fast_ema": [...], "slow_ema": [...], "golden_cross": [bool], "death_cross": [bool]}
    """
    fast = _ema(close, fast_period)
    slow = _ema(close, slow_period)

    golden_cross: list[bool] = [False] * len(close)
    death_cross: list[bool] = [False] * len(close)

    for i in range(1, len(close)):
        if fast[i] is not None and slow[i] is not None and fast[i - 1] is not None and slow[i - 1] is not None:
            if fast[i - 1] <= slow[i - 1] and fast[i] > slow[i]:
                golden_cross[i] = True
            elif fast[i - 1] >= slow[i - 1] and fast[i] < slow[i]:
                death_cross[i] = True

    return {"fast_ema": fast, "slow_ema": slow, "golden_cross": golden_cross, "death_cross": death_cross}


# ── 22. Stochastic Oscillator ─────────────────────────────────────────────────────

def calculate_stochastic(
    high: list[float],
    low: list[float],
    close: list[float],
    k_period: int = 14,
    d_period: int = 3,
    smooth: int = 3,
) -> dict[str, list]:
    """Stochastic Oscillator: %K and %D lines.

    Returns:
        {"k": [...], "d": [...], "oversold": [bool], "overbought": [bool]}
    """
    raw_k: list[float | None] = []
    for i in range(len(close)):
        if i < k_period - 1:
            raw_k.append(None)
        else:
            period_high = max(high[i - k_period + 1: i + 1])
            period_low = min(low[i - k_period + 1: i + 1])
            if period_high == period_low:
                raw_k.append(50.0)
            else:
                raw_k.append(((close[i] - period_low) / (period_high - period_low)) * 100)

    # Smooth %K
    k_values = [v for v in raw_k if v is not None]
    k_smooth = _sma(k_values, smooth) if len(k_values) >= smooth else [None] * len(k_values)
    # Pad to match original length
    k: list[float | None] = [None] * (len(close) - len(k_smooth)) + k_smooth

    # %D = SMA of %K
    k_for_d = [v for v in k if v is not None]
    d_smooth = _sma(k_for_d, d_period) if len(k_for_d) >= d_period else [None] * len(k_for_d)
    d: list[float | None] = [None] * (len(close) - len(d_smooth)) + d_smooth

    oversold: list[bool] = [False] * len(close)
    overbought: list[bool] = [False] * len(close)
    for i in range(len(close)):
        if k[i] is not None:
            if k[i] < 20:
                oversold[i] = True
            elif k[i] > 80:
                overbought[i] = True

    return {"k": k, "d": d, "oversold": oversold, "overbought": overbought}


# ── 23. ADX (Average Directional Index) ───────────────────────────────────────────

def calculate_adx(
    high: list[float],
    low: list[float],
    close: list[float],
    period: int = 14,
) -> dict[str, list]:
    """ADX: measures trend strength (directionless).

    Returns:
        {"adx": [...], "plus_di": [...], "minus_di": [...], "strong_trend": [bool], "weak_trend": [bool]}
    """
    if len(close) < period + 1:
        none_list = [None] * len(close)
        return {"adx": none_list, "plus_di": none_list, "minus_di": none_list,
                "strong_trend": [False] * len(close), "weak_trend": [False] * len(close)}

    plus_dm: list[float] = [0.0]
    minus_dm: list[float] = [0.0]
    tr_list: list[float] = []

    for i in range(1, len(close)):
        up_move = high[i] - high[i - 1]
        down_move = low[i - 1] - low[i]

        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)

        tr = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
        tr_list.append(tr)

    # Smoothed TR, +DM, -DM
    smoothed_tr = sum(tr_list[:period])
    smoothed_plus = sum(plus_dm[1:period + 1])
    smoothed_minus = sum(minus_dm[1:period + 1])

    plus_di_list: list[float | None] = [None] * period
    minus_di_list: list[float | None] = [None] * period
    dx_list: list[float] = []

    for i in range(period, len(tr_list)):
        smoothed_tr = smoothed_tr - smoothed_tr / period + tr_list[i]
        smoothed_plus = smoothed_plus - smoothed_plus / period + plus_dm[i + 1]
        smoothed_minus = smoothed_minus - smoothed_minus / period + minus_dm[i + 1]

        pdi = (smoothed_plus / smoothed_tr * 100) if smoothed_tr > 0 else 0
        mdi = (smoothed_minus / smoothed_tr * 100) if smoothed_tr > 0 else 0

        plus_di_list.append(pdi)
        minus_di_list.append(mdi)

        dx = abs(pdi - mdi) / (pdi + mdi) * 100 if (pdi + mdi) > 0 else 0
        dx_list.append(dx)

    # ADX = smoothed DX
    adx_list: list[float | None] = [None] * period
    if len(dx_list) >= period:
        adx_val = sum(dx_list[:period]) / period
        adx_list.append(adx_val)
        for dx in dx_list[period:]:
            adx_val = (adx_val * (period - 1) + dx) / period
            adx_list.append(adx_val)

    # Pad to match original length
    pad = len(close) - len(adx_list)
    adx_list = [None] * pad + adx_list
    plus_di_list = [None] * (len(close) - len(plus_di_list)) + plus_di_list
    minus_di_list = [None] * (len(close) - len(minus_di_list)) + minus_di_list

    strong_trend = [False] * len(close)
    weak_trend = [False] * len(close)
    for i in range(len(close)):
        if adx_list[i] is not None:
            if adx_list[i] > 25:
                strong_trend[i] = True
            elif adx_list[i] < 20:
                weak_trend[i] = True

    return {"adx": adx_list, "plus_di": plus_di_list, "minus_di": minus_di_list,
            "strong_trend": strong_trend, "weak_trend": weak_trend}


# ── 24. Ichimoku Cloud ────────────────────────────────────────────────────────────

def calculate_ichimoku(
    high: list[float],
    low: list[float],
    close: list[float],
    tenkan_period: int = 9,
    kijun_period: int = 26,
    senkou_b_period: int = 52,
) -> dict[str, list]:
    """Ichimoku Cloud: Tenkan-sen, Kijun-sen, Senkou Span A/B, Chikou Span.

    Returns:
        {"tenkan": [...], "kijun": [...], "senkou_a": [...], "senkou_b": [...],
         "bullish_cloud": [bool], "bearish_cloud": [bool]}
    """
    def _midpoint(data: list[float], period: int) -> list[float | None]:
        result: list[float | None] = []
        for i in range(len(data)):
            if i < period - 1:
                result.append(None)
            else:
                h = max(data[i - period + 1: i + 1])
                lo = min(data[i - period + 1: i + 1])
                result.append((h + lo) / 2)
        return result

    tenkan = _midpoint(high, tenkan_period)
    kijun = _midpoint(high, kijun_period)

    # Shifted forward by kijun_period
    senkou_a: list[float | None] = [None] * len(close)
    senkou_b: list[float | None] = [None] * len(close)

    for i in range(len(close)):
        src_idx = i - kijun_period
        if src_idx >= 0 and tenkan[src_idx] is not None and kijun[src_idx] is not None:
            senkou_a[i] = (tenkan[src_idx] + kijun[src_idx]) / 2
        if src_idx >= 0 and src_idx < len(close):
            h = max(high[max(0, src_idx - senkou_b_period + 1): src_idx + 1])
            lo = min(low[max(0, src_idx - senkou_b_period + 1): src_idx + 1])
            senkou_b[i] = (h + lo) / 2

    bullish_cloud = [False] * len(close)
    bearish_cloud = [False] * len(close)
    for i in range(len(close)):
        if senkou_a[i] is not None and senkou_b[i] is not None:
            if close[i] > max(senkou_a[i], senkou_b[i]):
                bullish_cloud[i] = True
            elif close[i] < min(senkou_a[i], senkou_b[i]):
                bearish_cloud[i] = True

    return {"tenkan": tenkan, "kijun": kijun, "senkou_a": senkou_a, "senkou_b": senkou_b,
            "bullish_cloud": bullish_cloud, "bearish_cloud": bearish_cloud}


# ── 25. VWAP ──────────────────────────────────────────────────────────────────────

def calculate_vwap(
    close: list[float],
    high: list[float],
    low: list[float],
    volume: list[float],
    period: int = 20,
) -> dict[str, list]:
    """VWAP: Volume Weighted Average Price over rolling period.

    Returns:
        {"vwap": [...], "above_vwap": [bool], "below_vwap": [bool]}
    """
    typical_price = [(h + lo + c) / 3 for h, lo, c in zip(high, low, close, strict=False)]
    tp_vol = [tp * v for tp, v in zip(typical_price, volume, strict=False)]

    vwap: list[float | None] = []
    for i in range(len(close)):
        if i < period - 1 or sum(volume[i - period + 1: i + 1]) == 0:
            vwap.append(None)
        else:
            vwap.append(sum(tp_vol[i - period + 1: i + 1]) / sum(volume[i - period + 1: i + 1]))

    above = [False] * len(close)
    below = [False] * len(close)
    for i in range(len(close)):
        if vwap[i] is not None:
            if close[i] > vwap[i]:
                above[i] = True
            elif close[i] < vwap[i]:
                below[i] = True

    return {"vwap": vwap, "above_vwap": above, "below_vwap": below}


# ── 26. OBV (On Balance Volume) ───────────────────────────────────────────────────

def calculate_obv(
    close: list[float],
    volume: list[float],
    sma_period: int = 20,
) -> dict[str, list]:
    """OBV: On Balance Volume with SMA smoothing.

    Returns:
        {"obv": [...], "obv_sma": [...], "obv_rising": [bool], "obv_falling": [bool]}
    """
    obv: list[float] = [0.0]
    for i in range(1, len(close)):
        if close[i] > close[i - 1]:
            obv.append(obv[-1] + volume[i])
        elif close[i] < close[i - 1]:
            obv.append(obv[-1] - volume[i])
        else:
            obv.append(obv[-1])

    obv_sma = _sma(obv, sma_period)

    rising = [False] * len(close)
    falling = [False] * len(close)
    for i in range(1, len(close)):
        if obv_sma[i] is not None and obv_sma[i - 1] is not None:
            if obv_sma[i] > obv_sma[i - 1]:
                rising[i] = True
            elif obv_sma[i] < obv_sma[i - 1]:
                falling[i] = True

    return {"obv": obv, "obv_sma": obv_sma, "obv_rising": rising, "obv_falling": falling}


# ── 27. Williams %R ───────────────────────────────────────────────────────────────

def calculate_williams_r(
    high: list[float],
    low: list[float],
    close: list[float],
    period: int = 14,
) -> dict[str, list]:
    """Williams %R: overbought/oversold oscillator (-100 to 0).

    Returns:
        {"williams_r": [...], "oversold": [bool], "overbought": [bool]}
    """
    wr: list[float | None] = []
    for i in range(len(close)):
        if i < period - 1:
            wr.append(None)
        else:
            period_high = max(high[i - period + 1: i + 1])
            period_low = min(low[i - period + 1: i + 1])
            if period_high == period_low:
                wr.append(-50.0)
            else:
                wr.append(((period_high - close[i]) / (period_high - period_low)) * -100)

    oversold = [False] * len(close)
    overbought = [False] * len(close)
    for i in range(len(close)):
        if wr[i] is not None:
            if wr[i] < -80:
                oversold[i] = True
            elif wr[i] > -20:
                overbought[i] = True

    return {"williams_r": wr, "oversold": oversold, "overbought": overbought}


# ── 28. CCI (Commodity Channel Index) ─────────────────────────────────────────────

def calculate_cci(
    high: list[float],
    low: list[float],
    close: list[float],
    period: int = 20,
) -> dict[str, list]:
    """CCI: Commodity Channel Index.

    Returns:
        {"cci": [...], "oversold": [bool], "overbought": [bool]}
    """
    tp = [(h + lo + c) / 3 for h, lo, c in zip(high, low, close, strict=False)]
    sma_tp = _sma(tp, period)

    cci: list[float | None] = []
    for i in range(len(close)):
        if sma_tp[i] is None or i < period - 1:
            cci.append(None)
        else:
            # Mean deviation
            md = sum(abs(tp[j] - sma_tp[i]) for j in range(i - period + 1, i + 1)) / period
            if md == 0:
                cci.append(0.0)
            else:
                cci.append((tp[i] - sma_tp[i]) / (0.015 * md))

    oversold = [False] * len(close)
    overbought = [False] * len(close)
    for i in range(len(close)):
        if cci[i] is not None:
            if cci[i] < -100:
                oversold[i] = True
            elif cci[i] > 100:
                overbought[i] = True

    return {"cci": cci, "oversold": oversold, "overbought": overbought}


# ── 29. Parabolic SAR ─────────────────────────────────────────────────────────────

def calculate_parabolic_sar(
    high: list[float],
    low: list[float],
    close: list[float],
    step: float = 0.02,
    max_af: float = 0.2,
) -> dict[str, list]:
    """Parabolic SAR: stop and reverse indicator.

    Returns:
        {"sar": [...], "buy_signal": [bool], "sell_signal": [bool], "uptrend": [bool]}
    """
    if len(close) < 2:
        return {"sar": [None] * len(close), "buy_signal": [False] * len(close),
                "sell_signal": [False] * len(close), "uptrend": [False] * len(close)}

    sar: list[float | None] = [None]
    uptrend: list[bool] = [True]
    af = step
    ep = high[0]
    sar_val = low[0]

    for i in range(1, len(close)):
        prev_sar = sar_val
        sar_val = prev_sar + af * (ep - prev_sar)

        if uptrend[-1]:
            sar_val = min(sar_val, low[i - 1])
            if i >= 2:
                sar_val = min(sar_val, low[i - 2])

            if low[i] < sar_val:
                # Reverse to downtrend
                uptrend.append(False)
                sar_val = ep
                ep = low[i]
                af = step
            else:
                uptrend.append(True)
                if high[i] > ep:
                    ep = high[i]
                    af = min(af + step, max_af)
        else:
            sar_val = max(sar_val, high[i - 1])
            if i >= 2:
                sar_val = max(sar_val, high[i - 2])

            if high[i] > sar_val:
                # Reverse to uptrend
                uptrend.append(True)
                sar_val = ep
                ep = high[i]
                af = step
            else:
                uptrend.append(False)
                if low[i] < ep:
                    ep = low[i]
                    af = min(af + step, max_af)

        sar.append(sar_val)

    buy_signal = [False] * len(close)
    sell_signal = [False] * len(close)
    for i in range(1, len(close)):
        if uptrend[i] and not uptrend[i - 1]:
            buy_signal[i] = True
        elif not uptrend[i] and uptrend[i - 1]:
            sell_signal[i] = True

    return {"sar": sar, "buy_signal": buy_signal, "sell_signal": sell_signal, "uptrend": uptrend}


# ── 30. Keltner Channel Position ──────────────────────────────────────────────────

def calculate_keltner_position(
    high: list[float],
    low: list[float],
    close: list[float],
    period: int = 20,
    multiplier: float = 2.0,
) -> dict[str, list]:
    """Keltner Channel: position of price within the channel.

    Returns:
        {"upper": [...], "lower": [...], "middle": [...],
         "above_upper": [bool], "below_lower": [bool], "position": [...]}  # position: 0-1
    """
    ema = _ema(close, period)
    atr = _atr(high, low, close, period)

    upper: list[float | None] = [None] * len(close)
    lower: list[float | None] = [None] * len(close)
    middle: list[float | None] = [None] * len(close)
    position: list[float | None] = [None] * len(close)

    for i in range(len(close)):
        if ema[i] is not None and atr[i] is not None:
            middle[i] = ema[i]
            upper[i] = ema[i] + multiplier * atr[i]
            lower[i] = ema[i] - multiplier * atr[i]
            if upper[i] != lower[i]:
                position[i] = (close[i] - lower[i]) / (upper[i] - lower[i])

    above_upper = [False] * len(close)
    below_lower = [False] * len(close)
    for i in range(len(close)):
        if upper[i] is not None and lower[i] is not None:
            if close[i] > upper[i]:
                above_upper[i] = True
            elif close[i] < lower[i]:
                below_lower[i] = True

    return {"upper": upper, "lower": lower, "middle": middle,
            "above_upper": above_upper, "below_lower": below_lower, "position": position}
