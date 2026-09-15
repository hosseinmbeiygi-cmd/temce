from __future__ import annotations


def _ema(data: list[float], period: int) -> list[float | None]:
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


def _atr(high: list[float], low: list[float], close: list[float], period: int) -> list[float | None]:
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

    result: list[float | None] = []
    for i in range(len(trs)):
        if i < period - 1:
            result.append(None)
        else:
            result.append(sum(trs[i - period + 1 : i + 1]) / period)
    return result


def _linreg(data: list[float], period: int) -> list[float | None]:
    result: list[float | None] = []
    for i in range(len(data)):
        if i < period - 1:
            result.append(None)
        else:
            window = data[i - period + 1 : i + 1]
            n = len(window)
            x_mean = (n - 1) / 2
            y_mean = sum(window) / n
            num = sum((j - x_mean) * (window[j] - y_mean) for j in range(n))
            den = sum((j - x_mean) ** 2 for j in range(n))
            slope = num / den if den != 0 else 0.0
            result.append(slope)
    return result


def calculate_half_trend(
    high: list[float],
    low: list[float],
    close: list[float],
    amplitude: int = 2,
    channel_deviation: float = 2.0,
) -> dict[str, list]:
    n = len(close)
    atr_vals = _atr(high, low, close, amplitude)
    ema_vals = _ema(close, amplitude)

    trend: list[int] = []
    half_trend_line: list[float | None] = []
    buy_signal: list[bool] = []
    sell_signal: list[bool] = []

    prev_trend = 0
    for i in range(n):
        if atr_vals[i] is None or ema_vals[i] is None:
            trend.append(0)
            half_trend_line.append(None)
            buy_signal.append(False)
            sell_signal.append(False)
            continue

        atr_val = atr_vals[i]
        ema_val = ema_vals[i]
        upper = ema_val + channel_deviation * atr_val
        lower = ema_val - channel_deviation * atr_val

        if close[i] > upper:
            current_trend = 1
        elif close[i] < lower:
            current_trend = -1
        else:
            current_trend = prev_trend if prev_trend != 0 else 0

        is_buy = current_trend == 1 and prev_trend != 1
        is_sell = current_trend == -1 and prev_trend != -1

        trend.append(current_trend)
        half_trend_line.append(ema_val)
        buy_signal.append(is_buy)
        sell_signal.append(is_sell)

        prev_trend = current_trend

    return {
        "trend": trend,
        "half_trend_line": half_trend_line,
        "buy_signal": buy_signal,
        "sell_signal": sell_signal,
    }


def calculate_squeeze_momentum(
    high: list[float],
    low: list[float],
    close: list[float],
    bb_period: int = 20,
    bb_std: float = 2.0,
    kc_period: int = 20,
    kc_mult: float = 1.5,
) -> dict[str, list]:
    n = len(close)
    ema_close = _ema(close, kc_period)
    atr_vals = _atr(high, low, close, kc_period)

    squeeze_on: list[bool] = []
    momentum: list[float | None] = []
    momentum_positive: list[bool] = []

    for i in range(n):
        if ema_close[i] is None or atr_vals[i] is None:
            squeeze_on.append(False)
            momentum.append(None)
            momentum_positive.append(False)
            continue

        kc_mid = ema_close[i]
        kc_upper = kc_mid + kc_mult * atr_vals[i]
        kc_lower = kc_mid - kc_mult * atr_vals[i]

        # Bollinger Bands using rolling window
        start = max(0, i - bb_period + 1)
        window = close[start : i + 1]
        bb_mean = sum(window) / len(window)
        variance = sum((x - bb_mean) ** 2 for x in window) / len(window)
        bb_std_val = variance**0.5

        bb_upper = bb_mean + bb_std * bb_std_val
        bb_lower = bb_mean - bb_std * bb_std_val

        is_squeeze = bb_lower > kc_lower and bb_upper < kc_upper
        squeeze_on.append(is_squeeze)

        # Momentum: linear regression of (close - middle) over bb_period
        start_lr = max(0, i - bb_period + 1)
        lr_window = [close[j] - bb_mean for j in range(start_lr, i + 1)]
        if len(lr_window) >= 2:
            n_lr = len(lr_window)
            x_mean = (n_lr - 1) / 2
            y_mean = sum(lr_window) / n_lr
            num = sum((j - x_mean) * (lr_window[j] - y_mean) for j in range(n_lr))
            den = sum((j - x_mean) ** 2 for j in range(n_lr))
            mom_val = num / den if den != 0 else 0.0
        else:
            mom_val = 0.0

        momentum.append(mom_val)
        momentum_positive.append(mom_val > 0)

    return {
        "squeeze_on": squeeze_on,
        "momentum": momentum,
        "momentum_positive": momentum_positive,
    }


def calculate_support_resistance(
    high: list[float],
    low: list[float],
    close: list[float],
    lookback: int = 20,
    volume: list[float] | None = None,
    vol_threshold: float = 1.5,
) -> dict[str, list]:
    n = len(close)
    support: list[float | None] = []
    resistance: list[float | None] = []
    break_up: list[bool] = []
    break_down: list[bool] = []
    pullback: list[bool] = []

    prev_above_resistance = False
    prev_below_support = False

    for i in range(n):
        start = max(0, i - lookback)
        window_high = high[start : i + 1]
        window_low = low[start : i + 1]

        sup = min(window_low)
        res = max(window_high)
        support.append(sup)
        resistance.append(res)

        # Volume confirmation
        vol_confirmed = True
        if volume is not None and i >= lookback:
            avg_vol = sum(volume[start : i + 1]) / len(volume[start : i + 1])
            if avg_vol > 0:
                vol_confirmed = volume[i] > vol_threshold * avg_vol

        is_break_up = close[i] > res and vol_confirmed
        is_break_down = close[i] < sup and vol_confirmed

        # Pullback: price broke resistance/support then returned to it
        is_pullback = False
        if prev_above_resistance and close[i] <= res and close[i] >= res * 0.99:
            is_pullback = True
        if prev_below_support and close[i] >= sup and close[i] <= sup * 1.01:
            is_pullback = True

        break_up.append(is_break_up)
        break_down.append(is_break_down)
        pullback.append(is_pullback)

        prev_above_resistance = is_break_up
        prev_below_support = is_break_down

    return {
        "support": support,
        "resistance": resistance,
        "break_up": break_up,
        "break_down": break_down,
        "pullback": pullback,
    }
