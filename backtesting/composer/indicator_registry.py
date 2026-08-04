"""Indicator Registry: maps all 30 indicators with their functions, parameters, and signal conditions."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class IndicatorSpec:
    """Specification for a single indicator."""
    id: str
    name: str
    name_fa: str
    group: str  # momentum, trend, volatility, volume, price, flow, structure, relative
    compute_fn: Callable[..., dict[str, list]]
    params: dict[str, list[Any]]  # param_name -> list of possible values
    conditions: dict[str, str]  # condition_name -> output key to check (True = signal)
    description: str = ""


# ── All 30 Indicators ─────────────────────────────────────────────────────────────

REGISTRY: list[IndicatorSpec] = [
    # ═══ MOMENTUM ═══
    IndicatorSpec(
        id="rsi", name="RSI", name_fa="شاخص قدرت نسبی",
        group="momentum",
        compute_fn=lambda close, period=14: _compute_rsi(close, period),
        params={"period": [7, 10, 14, 21]},
        conditions={"oversold": "oversold", "overbought": "overbought"},
    ),
    IndicatorSpec(
        id="macd", name="MACD", name_fa="همگرایی واگرایی میانگین",
        group="momentum",
        compute_fn=lambda close, fast=12, slow=26, signal=9: _compute_macd(close, fast, slow, signal),
        params={"fast": [8, 12, 16], "slow": [21, 26, 30], "signal": [7, 9, 12]},
        conditions={"bullish_cross": "bullish_cross", "bearish_cross": "bearish_cross",
                     "positive": "positive_histogram", "negative": "negative_histogram"},
    ),
    IndicatorSpec(
        id="squeeze_momentum", name="Squeeze Momentum", name_fa="فشردگی مومنتوم",
        group="momentum",
        compute_fn=lambda high, low, close, bb_period=20, bb_std=2.0, kc_period=20, kc_mult=1.5:
            _compute_squeeze(high, low, close, bb_period, bb_std, kc_period, kc_mult),
        params={"bb_period": [15, 20, 25], "bb_std": [1.5, 2.0, 2.5],
                "kc_period": [15, 20, 25], "kc_mult": [1.0, 1.5, 2.0]},
        conditions={"squeeze_release": "squeeze_release", "momentum_positive": "momentum_positive",
                     "momentum_negative": "momentum_negative"},
    ),
    IndicatorSpec(
        id="stochastic", name="Stochastic", name_fa="استوکاستیک",
        group="momentum",
        compute_fn=lambda high, low, close, k_period=14, d_period=3, smooth=3:
            _compute_stochastic(high, low, close, k_period, d_period, smooth),
        params={"k_period": [9, 14, 21], "d_period": [3, 5], "smooth": [3, 5]},
        conditions={"oversold": "oversold", "overbought": "overbought"},
    ),
    IndicatorSpec(
        id="williams_r", name="Williams %R", name_fa="ویلیامز آر",
        group="momentum",
        compute_fn=lambda high, low, close, period=14: _compute_williams_r(high, low, close, period),
        params={"period": [10, 14, 21]},
        conditions={"oversold": "oversold", "overbought": "overbought"},
    ),
    IndicatorSpec(
        id="cci", name="CCI", name_fa="شاخص کانال کالا",
        group="momentum",
        compute_fn=lambda high, low, close, period=20: _compute_cci(high, low, close, period),
        params={"period": [14, 20, 28]},
        conditions={"oversold": "oversold", "overbought": "overbought"},
    ),

    # ═══ TREND ═══
    IndicatorSpec(
        id="ema_crossover", name="EMA Crossover", name_fa="تقاطع اکسپنشنال",
        group="trend",
        compute_fn=lambda close, fast=10, slow=30: _compute_ema_cross(close, fast, slow),
        params={"fast": [5, 10, 15], "slow": [20, 30, 50]},
        conditions={"golden_cross": "golden_cross", "death_cross": "death_cross"},
    ),
    IndicatorSpec(
        id="adx", name="ADX", name_fa="شاخص جهت‌دار میانگین",
        group="trend",
        compute_fn=lambda high, low, close, period=14: _compute_adx(high, low, close, period),
        params={"period": [14, 20, 28]},
        conditions={"strong_trend": "strong_trend", "weak_trend": "weak_trend"},
    ),
    IndicatorSpec(
        id="half_trend", name="Half-Trend", name_fa="نیم‌رونده",
        group="trend",
        compute_fn=lambda high, low, close, amplitude=2, channel_deviation=2.0:
            _compute_half_trend(high, low, close, amplitude, channel_deviation),
        params={"amplitude": [1, 2, 3, 4, 5], "channel_deviation": [1.0, 1.5, 2.0, 2.5, 3.0]},
        conditions={"buy_signal": "buy_signal", "sell_signal": "sell_signal"},
    ),
    IndicatorSpec(
        id="parabolic_sar", name="Parabolic SAR", name_fa="پارابولیک",
        group="trend",
        compute_fn=lambda high, low, close, step=0.02, max_af=0.2:
            _compute_parabolic_sar(high, low, close, step, max_af),
        params={"step": [0.01, 0.02, 0.03], "max_af": [0.1, 0.2, 0.3]},
        conditions={"buy_signal": "buy_signal", "sell_signal": "sell_signal"},
    ),
    IndicatorSpec(
        id="ichimoku", name="Ichimoku", name_fa="ایچیموکو",
        group="trend",
        compute_fn=lambda high, low, close, tenkan=9, kijun=26, senkou=52:
            _compute_ichimoku(high, low, close, tenkan, kijun, senkou),
        params={"tenkan": [7, 9, 12], "kijun": [22, 26, 30], "senkou": [52, 60]},
        conditions={"bullish_cloud": "bullish_cloud", "bearish_cloud": "bearish_cloud"},
    ),

    # ═══ VOLATILITY ═══
    IndicatorSpec(
        id="atr", name="ATR", name_fa="میانگین واقعی دامنه",
        group="volatility",
        compute_fn=lambda high, low, close, period=14: _compute_atr(high, low, close, period),
        params={"period": [10, 14, 20, 28]},
        conditions={"high_volatility": "high_volatility", "low_volatility": "low_volatility"},
    ),
    IndicatorSpec(
        id="bollinger_bw", name="Bollinger Bandwidth", name_fa="پهنای بولینگر",
        group="volatility",
        compute_fn=lambda high, low, close, period=20, std=2.0:
            _compute_bollinger_bw(high, low, close, period, std),
        params={"period": [15, 20, 25], "std": [1.5, 2.0, 2.5]},
        conditions={"squeeze": "squeeze", "expansion": "expansion"},
    ),
    IndicatorSpec(
        id="keltner_position", name="Keltner Position", name_fa="موقعیت کلتنر",
        group="volatility",
        compute_fn=lambda high, low, close, period=20, mult=2.0:
            _compute_keltner(high, low, close, period, mult),
        params={"period": [10, 20, 30], "mult": [1.5, 2.0, 2.5]},
        conditions={"above_upper": "above_upper", "below_lower": "below_lower"},
    ),
    IndicatorSpec(
        id="compression_ratio", name="Compression Ratio", name_fa="نسبت فشردگی",
        group="volatility",
        compute_fn=lambda high, low, close, short_p=5, long_p=20:
            _compute_compression(high, low, close, short_p, long_p),
        params={"short_p": [3, 5, 7], "long_p": [15, 20, 25]},
        conditions={"compressed": "compressed", "expanded": "expanded"},
    ),

    # ═══ VOLUME ═══
    IndicatorSpec(
        id="relative_volume", name="Relative Volume", name_fa="حجم نسبی",
        group="volume",
        compute_fn=lambda close, volume, period=20: _compute_rvol(close, volume, period),
        params={"period": [10, 15, 20, 30]},
        conditions={"high_volume": "high_volume", "low_volume": "low_volume"},
    ),
    IndicatorSpec(
        id="obv", name="OBV", name_fa="حجم تعادلی",
        group="volume",
        compute_fn=lambda close, volume, sma_p=20: _compute_obv(close, volume, sma_p),
        params={"sma_p": [10, 15, 20, 30]},
        conditions={"obv_rising": "obv_rising", "obv_falling": "obv_falling"},
    ),
    IndicatorSpec(
        id="vwap", name="VWAP", name_fa="میانگین وزنی حجمی",
        group="volume",
        compute_fn=lambda close, high, low, volume, period=20:
            _compute_vwap(close, high, low, volume, period),
        params={"period": [10, 15, 20, 30]},
        conditions={"above_vwap": "above_vwap", "below_vwap": "below_vwap"},
    ),
    IndicatorSpec(
        id="supply_dryness", name="Supply Dryness", name_fa="خشکی عرضه",
        group="volume",
        compute_fn=lambda close, volume, period=20: _compute_supply_dryness(close, volume, period),
        params={"period": [10, 15, 20, 30]},
        conditions={"dry": "dry", "abundant": "abundant"},
    ),

    # ═══ PRICE ═══
    IndicatorSpec(
        id="clv", name="CLV", name_fa="موقعیت بسته شدن",
        group="price",
        compute_fn=lambda close, high, low: _compute_clv(close, high, low),
        params={},
        conditions={"strong_close": "strong_close", "weak_close": "weak_close"},
    ),
    IndicatorSpec(
        id="recovery_ratio", name="Recovery Ratio", name_fa="نسبت بازیابی",
        group="price",
        compute_fn=lambda close, high, low: _compute_recovery(close, high, low),
        params={},
        conditions={"strong_recovery": "strong_recovery", "weak_recovery": "weak_recovery"},
    ),

    # ═══ FLOW (Iranian Market) ═══
    IndicatorSpec(
        id="buyer_power", name="Buyer Power Ratio", name_fa="نسبت قدرت خریدار",
        group="flow",
        compute_fn=lambda buy_val, buy_cnt, sell_val, sell_cnt:
            _compute_buyer_power(buy_val, buy_cnt, sell_val, sell_cnt),
        params={},
        conditions={"strong_buyers": "strong_buyers", "strong_sellers": "strong_sellers"},
    ),
    IndicatorSpec(
        id="net_real_flow", name="Net Real Flow", name_fa="خالص جریان پول واقعی",
        group="flow",
        compute_fn=lambda net_flow, free_float: _compute_real_flow(net_flow, free_float),
        params={},
        conditions={"inflow": "inflow", "outflow": "outflow"},
    ),
    IndicatorSpec(
        id="supply_absorption", name="Supply Absorption", name_fa="جذب عرضه",
        group="flow",
        compute_fn=lambda sell_pressure, ret: _compute_absorption(sell_pressure, ret),
        params={},
        conditions={"absorbing": "absorbing"},
    ),

    # ═══ STRUCTURE ═══
    IndicatorSpec(
        id="support_resistance", name="Support/Resistance", name_fa="حمایت/مقاومت",
        group="structure",
        compute_fn=lambda high, low, close, lookback=20:
            _compute_sr(high, low, close, lookback),
        params={"lookback": [10, 15, 20, 25, 30]},
        conditions={"break_up": "break_up", "break_down": "break_down", "pullback": "pullback"},
    ),
    IndicatorSpec(
        id="breakout_quality", name="Breakout Quality", name_fa="کیفیت شکست",
        group="structure",
        compute_fn=lambda close, high, low, volume, period=20:
            _compute_breakout_quality(close, high, low, volume, period),
        params={"period": [15, 20, 25, 30]},
        conditions={"strong_breakout": "strong_breakout", "weak_breakout": "weak_breakout"},
    ),

    # ═══ RELATIVE ═══
    IndicatorSpec(
        id="volume_zscore", name="Volume Z-Score", name_fa="z-اسکور حجم",
        group="volume",
        compute_fn=lambda close, volume, period=20: _compute_volume_zscore(close, volume, period),
        params={"period": [10, 15, 20, 30]},
        conditions={"high_zscore": "high_zscore", "low_zscore": "low_zscore"},
    ),
    IndicatorSpec(
        id="amihud_illiquidity", name="Amihud Illiquidity", name_fa="عدم نقدینگی آمیhud",
        group="liquidity",
        compute_fn=lambda close, volume, period=20: _compute_amihud(close, volume, period),
        params={"period": [10, 15, 20, 30]},
        conditions={"illiquid": "illiquid", "liquid": "liquid"},
    ),
    IndicatorSpec(
        id="normalized_volatility", name="Normalized Volatility", name_fa="نوسان نرمال‌شده",
        group="volatility",
        compute_fn=lambda high, low, close, period=14: _compute_norm_vol(high, low, close, period),
        params={"period": [10, 14, 20, 28]},
        conditions={"high_volatility": "high_volatility", "low_volatility": "low_volatility"},
    ),
    IndicatorSpec(
        id="relative_strength", name="Relative Strength", name_fa="قدر نسبی",
        group="relative",
        compute_fn=lambda asset_price, benchmark_price, period=20:
            _compute_rs(asset_price, benchmark_price, period),
        params={"period": [10, 15, 20, 30]},
        conditions={"outperforming": "outperforming", "underperforming": "underperforming"},
    ),
]


# ── Helper compute functions (wrap existing indicators) ───────────────────────────

def _compute_rsi(close: list[float], period: int) -> dict[str, list]:
    if len(close) < period + 1:
        n = len(close)
        return {"rsi": [None] * n, "oversold": [False] * n, "overbought": [False] * n}
    deltas = [close[i] - close[i - 1] for i in range(1, len(close))]
    gains = [max(d, 0) for d in deltas]
    losses = [max(-d, 0) for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    rsi: list[float | None] = [None] * period
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        rsi.append(100 - 100 / (1 + rs))
    rsi = [None] + rsi  # pad for index 0
    oversold = [v is not None and v < 30 for v in rsi]
    overbought = [v is not None and v > 70 for v in rsi]
    return {"rsi": rsi, "oversold": oversold, "overbought": overbought}


def _compute_macd(close: list[float], fast: int, slow: int, signal: int) -> dict[str, list]:
    def ema(data, p):
        r = []
        k = 2 / (p + 1)
        for i, v in enumerate(data):
            if i < p - 1:
                r.append(None)
            elif i == p - 1:
                r.append(sum(data[:p]) / p)
            else:
                r.append((v - r[-1]) * k + r[-1])
        return r
    fast_ema = ema(close, fast)
    slow_ema = ema(close, slow)
    macd_line = [(f - s) if f is not None and s is not None else None for f, s in zip(fast_ema, slow_ema, strict=False)]
    macd_vals = [v for v in macd_line if v is not None]
    sig = ema(macd_vals, signal) if len(macd_vals) >= signal else [None] * len(macd_vals)
    sig_padded = [None] * (len(close) - len(sig)) + sig
    macd_padded = [None] * (len(close) - len(macd_vals)) + macd_vals
    hist = [(m - s) if m is not None and s is not None else None for m, s in zip(macd_padded, sig_padded, strict=False)]
    bullish_cross = [False] * len(close)
    bearish_cross = [False] * len(close)
    for i in range(1, len(close)):
        if hist[i] is not None and hist[i - 1] is not None:
            if hist[i - 1] <= 0 and hist[i] > 0:
                bullish_cross[i] = True
            elif hist[i - 1] >= 0 and hist[i] < 0:
                bearish_cross[i] = True
    positive_h = [v is not None and v > 0 for v in hist]
    negative_h = [v is not None and v < 0 for v in hist]
    return {"macd": macd_padded, "signal": sig_padded, "histogram": hist,
            "bullish_cross": bullish_cross, "bearish_cross": bearish_cross,
            "positive_histogram": positive_h, "negative_histogram": negative_h}


def _compute_squeeze(high, low, close, bb_p, bb_s, kc_p, kc_m):
    from src.indicators.trend_momentum import calculate_squeeze_momentum
    r = calculate_squeeze_momentum(high, low, close, bb_p, bb_s, kc_p, kc_m)
    prev_squeeze = [False] + r["squeeze_on"][:-1]
    release = [not r["squeeze_on"][i] and prev_squeeze[i] for i in range(len(close))]
    return {"squeeze_on": r["squeeze_on"], "momentum": r["momentum"],
            "momentum_positive": r["momentum_positive"], "momentum_negative": [not v for v in r["momentum_positive"]],
            "squeeze_release": release}


def _compute_stochastic(high, low, close, k_p, d_p, smooth):
    from src.indicators.advanced import calculate_stochastic
    return calculate_stochastic(high, low, close, k_p, d_p, smooth)


def _compute_williams_r(high, low, close, period):
    from src.indicators.advanced import calculate_williams_r
    return calculate_williams_r(high, low, close, period)


def _compute_cci(high, low, close, period):
    from src.indicators.advanced import calculate_cci
    return calculate_cci(high, low, close, period)


def _compute_ema_cross(close, fast, slow):
    from src.indicators.advanced import calculate_ema_crossover
    return calculate_ema_crossover(close, fast, slow)


def _compute_adx(high, low, close, period):
    from src.indicators.advanced import calculate_adx
    return calculate_adx(high, low, close, period)


def _compute_half_trend(high, low, close, amp, dev):
    from src.indicators.trend_momentum import calculate_half_trend
    return calculate_half_trend(high, low, close, amp, dev)


def _compute_parabolic_sar(high, low, close, step, max_af):
    from src.indicators.advanced import calculate_parabolic_sar
    return calculate_parabolic_sar(high, low, close, step, max_af)


def _compute_ichimoku(high, low, close, tenkan, kijun, senkou):
    from src.indicators.advanced import calculate_ichimoku
    return calculate_ichimoku(high, low, close, tenkan, kijun, senkou)


def _compute_atr(high, low, close, period):
    from src.indicators.advanced import _atr as atr_fn
    atr_vals = atr_fn(high, low, close, period)
    vol = [None if v is None else (v / close[i] * 100 if close[i] > 0 else 0) for i, v in enumerate(atr_vals)]
    hv = [v is not None and v > 3.0 for v in vol]
    lv = [v is not None and v < 1.0 for v in vol]
    return {"atr": atr_vals, "normalized": vol, "high_volatility": hv, "low_volatility": lv}


def _compute_bollinger_bw(high, low, close, period, std):
    from src.indicators.advanced import _sma
    mid = _sma(close, period)
    bw: list[float | None] = []
    for i in range(len(close)):
        if mid[i] is None:
            bw.append(None)
        else:
            window = close[i - period + 1: i + 1]
            s = (sum((x - mid[i]) ** 2 for x in window) / period) ** 0.5
            u = mid[i] + std * s
            lo = mid[i] - std * s
            bw.append((u - lo) / mid[i] * 100 if mid[i] > 0 else 0)
    squeeze = [v is not None and v < 5.0 for v in bw]
    expansion = [v is not None and v > 15.0 for v in bw]
    return {"bandwidth": bw, "squeeze": squeeze, "expansion": expansion}


def _compute_keltner(high, low, close, period, mult):
    from src.indicators.advanced import calculate_keltner_position
    return calculate_keltner_position(high, low, close, period, mult)


def _compute_compression(high, low, close, short_p, long_p):
    from src.indicators.advanced import _atr
    short_atr = _atr(high, low, close, short_p)
    long_atr = _atr(high, low, close, long_p)
    ratio: list[float | None] = []
    for s, lval in zip(short_atr, long_atr, strict=False):
        if s is not None and lval is not None and lval > 0:
            ratio.append(s / lval)
        else:
            ratio.append(None)
    compressed = [v is not None and v < 0.7 for v in ratio]
    expanded = [v is not None and v > 1.3 for v in ratio]
    return {"ratio": ratio, "compressed": compressed, "expanded": expanded}


def _compute_rvol(close, volume, period):
    from src.indicators.advanced import _sma
    avg = _sma(volume, period)
    rvol = [v / a if a and a > 0 else None for v, a in zip(volume, avg, strict=False)]
    high_v = [v is not None and v > 2.0 for v in rvol]
    low_v = [v is not None and v < 0.5 for v in rvol]
    return {"relative_volume": rvol, "high_volume": high_v, "low_volume": low_v}


def _compute_obv(close, volume, sma_p):
    from src.indicators.advanced import calculate_obv
    return calculate_obv(close, volume, sma_p)


def _compute_vwap(close, high, low, volume, period):
    from src.indicators.advanced import calculate_vwap
    return calculate_vwap(close, high, low, volume, period)


def _compute_supply_dryness(close, volume, period):
    from src.indicators.advanced import _sma
    avg = _sma(volume, period)
    dryness = [1 - (v / a) if a and a > 0 else None for v, a in zip(volume, avg, strict=False)]
    dry = [v is not None and v > 0.5 for v in dryness]
    abundant = [v is not None and v < -0.3 for v in dryness]
    return {"dryness": dryness, "dry": dry, "abundant": abundant}


def _compute_clv(close, high, low):
    from src.indicators.general import calculate_clv
    clv = [calculate_clv(c, h, idx) for c, h, idx in zip(close, high, low, strict=False)]
    strong = [v > 0.3 for v in clv]
    weak = [v < -0.3 for v in clv]
    return {"clv": clv, "strong_close": strong, "weak_close": weak}


def _compute_recovery(close, high, low):
    from src.indicators.general import calculate_recovery_ratio
    rr = [calculate_recovery_ratio(c, h, idx) for c, h, idx in zip(close, high, low, strict=False)]
    strong = [v > 0.7 for v in rr]
    weak = [v < 0.3 for v in rr]
    return {"recovery": rr, "strong_recovery": strong, "weak_recovery": weak}


def _compute_buyer_power(buy_val, buy_cnt, sell_val, sell_cnt):
    avg_buy = buy_val / buy_cnt if buy_cnt > 0 else 0
    avg_sell = sell_val / sell_cnt if sell_cnt > 0 else 0
    ratio = avg_buy / avg_sell if avg_sell > 0 else float("inf")
    return {"ratio": ratio, "strong_buyers": ratio > 1.2, "strong_sellers": ratio < 0.8}


def _compute_real_flow(net_flow, free_float):
    normalized = net_flow / free_float if free_float > 0 else 0
    return {"normalized": normalized, "inflow": normalized > 0.01, "outflow": normalized < -0.01}


def _compute_absorption(sell_pressure, ret):
    score = sell_pressure / (abs(ret) + 1e-10) if ret != 0 else 0
    return {"score": score, "absorbing": score > 5.0}


def _compute_sr(high, low, close, lookback):
    from src.indicators.trend_momentum import calculate_support_resistance
    return calculate_support_resistance(high, low, close, lookback)


def _compute_breakout_quality(close, high, low, volume, period):
    from src.indicators.advanced import _sma
    avg_vol = _sma(volume, period)
    rvol = [v / a if a and a > 0 else 0 for v, a in zip(volume, avg_vol, strict=False)]
    price_change = [(close[i] - close[i - 1]) / close[i - 1] * 100 if close[i - 1] > 0 else 0 for i in range(1, len(close))]
    price_change = [0] + price_change
    quality = [r * abs(pc) for r, pc in zip(rvol, price_change, strict=False)]
    threshold = sum(q for q in quality if q > 0) / max(1, sum(1 for q in quality if q > 0))
    strong = [q > threshold * 1.5 for q in quality]
    weak = [q < threshold * 0.5 for q in quality]
    return {"quality": quality, "strong_breakout": strong, "weak_breakout": weak}


def _compute_volume_zscore(close, volume, period):
    from src.indicators.advanced import _sma
    avg = _sma(volume, period)
    # Compute rolling std
    std_list = [None] * len(close)
    for i in range(period - 1, len(close)):
        window = volume[i - period + 1: i + 1]
        m = avg[i]
        if m is not None and m > 0:
            s = (sum((v - m) ** 2 for v in window) / period) ** 0.5
            std_list[i] = s
    zscore = [None] * len(close)
    for i in range(len(close)):
        if avg[i] is not None and std_list[i] is not None and std_list[i] > 0:
            zscore[i] = (volume[i] - avg[i]) / std_list[i]
    high_z = [v is not None and v > 2.0 for v in zscore]
    low_z = [v is not None and v < -1.0 for v in zscore]
    return {"zscore": zscore, "high_zscore": high_z, "low_zscore": low_z}


def _compute_amihud(close, volume, period):
    # returns
    returns = [0.0]
    for i in range(1, len(close)):
        returns.append((close[i] - close[i - 1]) / close[i - 1] if close[i - 1] > 0 else 0.0)
    # traded value
    tv = [c * v for c, v in zip(close, volume, strict=False)]
    # rolling amihud
    amihud: list[float | None] = []
    for i in range(len(close)):
        if i < period - 1:
            amihud.append(None)
        else:
            window_tv = sum(tv[i - period + 1: i + 1]) / period
            window_ret = sum(abs(returns[j]) for j in range(i - period + 1, i + 1)) / period
            amihud.append(window_ret / window_tv if window_tv > 0 else 0.0)
    # threshold: median
    valid = sorted(v for v in amihud if v is not None)
    median = valid[len(valid) // 2] if valid else 0.0
    illiquid = [v is not None and v > median * 1.5 for v in amihud]
    liquid = [v is not None and v < median * 0.5 for v in amihud]
    return {"amihud": amihud, "illiquid": illiquid, "liquid": liquid}


def _compute_norm_vol(high, low, close, period):
    from src.indicators.advanced import _atr
    atr_vals = _atr(high, low, close, period)
    norm = [None] * len(close)
    for i in range(len(close)):
        if atr_vals[i] is not None and close[i] > 0:
            norm[i] = atr_vals[i] / close[i] * 100
    valid = [v for v in norm if v is not None]
    median = sorted(valid)[len(valid) // 2] if valid else 0.0
    hv = [v is not None and v > median * 1.5 for v in norm]
    lv = [v is not None and v < median * 0.5 for v in norm]
    return {"normalized_vol": norm, "high_volatility": hv, "low_volatility": lv}


def _compute_rs(asset_price, benchmark_price, period):
    from src.indicators.advanced import _sma
    asset_sma = _sma(asset_price, period)
    bench_sma = _sma(benchmark_price, period)
    rs = [a / b if a is not None and b is not None and b > 0 else None for a, b in zip(asset_sma, bench_sma, strict=False)]
    # Compare current to N bars ago
    outperform = [False] * len(rs)
    underperform = [False] * len(rs)
    for i in range(period, len(rs)):
        if rs[i] is not None and rs[i - period] is not None and rs[i - period] > 0:
            if rs[i] > rs[i - period]:
                outperform[i] = True
            else:
                underperform[i] = True
    return {"rs": rs, "outperforming": outperform, "underperforming": underperform}


# ── Lookup helpers ────────────────────────────────────────────────────────────────

_INDICATOR_MAP: dict[str, IndicatorSpec] = {spec.id: spec for spec in REGISTRY}


def get_indicator(spec_id: str) -> IndicatorSpec | None:
    return _INDICATOR_MAP.get(spec_id)


def get_indicators_by_group(group: str) -> list[IndicatorSpec]:
    return [s for s in REGISTRY if s.group == group]


def list_all_indicators() -> list[dict[str, Any]]:
    return [{"id": s.id, "name": s.name, "name_fa": s.name_fa, "group": s.group,
             "params": s.params, "conditions": list(s.conditions.keys())} for s in REGISTRY]
