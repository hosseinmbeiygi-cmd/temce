"""اندیکاتورهای سری‌زمانی برای بک‌تست و تشخیص الگو — **فقط trailing**.

قاعدهٔ واحد این ماژول: مقدار در ایندکس ``i`` تنها از ``values[: i + 1]`` ساخته
می‌شود؛ هیچ پنجره‌ای به آینده نگاه نمی‌کند. ورودی کوتاه‌تر از پنجره ⇒ ``nan``
(نه پر کردن با میانگین آینده و نه backfill با اولین مقدار معتبر).

پیش‌تر سه پیاده‌سازی مستقل از همین محاسبه وجود داشت:
``backtest.py`` با ``np.convolve(mode="same")`` (میانگین ۱۵ قیمت آینده)،
``pattern_detector.pd_rolling_mean`` (backfill با داده آینده) و
``backtest_runner`` (میانگین ساده داخل حلقه). هر سه اکنون از اینجا می‌خوانند.
"""

from __future__ import annotations

import numpy as np

from .constants import SMA_BUBBLE_WINDOW


def _as_array(values) -> np.ndarray:
    return np.asarray(values, dtype=float)


def sma(values, window: int = SMA_BUBBLE_WINDOW) -> np.ndarray:
    """میانگین متحرک سادهٔ trailing.

    عناصر ``i < window - 1`` برابر ``nan`` هستند. اگر طول سری کمتر از پنجره
    باشد، خروجی تماماً ``nan`` است.
    """
    if window <= 0:
        raise ValueError(f"window must be > 0: {window}")
    arr = _as_array(values)
    out = np.full(arr.shape, np.nan, dtype=float)
    if arr.size < window:
        return out
    cumulative = np.cumsum(np.insert(arr, 0, 0.0))
    out[window - 1 :] = (cumulative[window:] - cumulative[:-window]) / window
    return out


def ema(values, period: int) -> np.ndarray:
    """میانگین متحرک نمایی trailing با ``alpha = 2/(period+1)``.

    بذر (seed) میانگین سادهٔ ``period`` مقدار اول است تا مقدار هر ایندکس فقط به
    گذشته وابسته باشد. عناصر ``i < period - 1`` برابر ``nan`` هستند.
    """
    if period <= 0:
        raise ValueError(f"period must be > 0: {period}")
    arr = _as_array(values)
    out = np.full(arr.shape, np.nan, dtype=float)
    if arr.size < period:
        return out
    alpha = 2.0 / (period + 1)
    out[period - 1] = arr[:period].mean()
    for i in range(period, arr.size):
        out[i] = arr[i] * alpha + out[i - 1] * (1 - alpha)
    return out


def rsi(values, period: int = 14) -> np.ndarray:
    """RSI ویلدر به‌صورت سری (نه فقط آخرین نقطه).

    عناصر ``i < period`` برابر ``nan`` هستند (برای RSI در ``i`` به ``period``
    تغییر نیاز است). سری بدون تغییر ⇒ ۵۰ (خنثی)، نه ۱۰۰ (E-L5).
    """
    if period <= 0:
        raise ValueError(f"period must be > 0: {period}")
    arr = _as_array(values)
    out = np.full(arr.shape, np.nan, dtype=float)
    if arr.size < period + 1:
        return out

    deltas = np.diff(arr)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = gains[:period].mean()
    avg_loss = losses[:period].mean()
    out[period] = _rsi_value(avg_gain, avg_loss)
    for i in range(period, deltas.size):
        # هموارسازی ویلدر: هر تغییر جدید وزن ۱/period می‌گیرد
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out[i + 1] = _rsi_value(avg_gain, avg_loss)
    return out


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0 and avg_gain == 0:
        return 50.0
    if avg_loss == 0:
        return 100.0
    return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))


def bubble_pct(values, window: int = SMA_BUBBLE_WINDOW) -> np.ndarray:
    """حباب تکنیکال: درصد فاصلهٔ قیمت از SMA trailing.

    ``nan`` وقتی پنجره کامل نیست یا میانگین صفر است؛ مصرف‌کننده باید ردیف‌های
    ``nan`` را کنار بگذارد (نه اینکه با صفر پر کند).
    """
    arr = _as_array(values)
    mean = sma(arr, window)
    out = np.full(arr.shape, np.nan, dtype=float)
    valid = ~np.isnan(mean) & (mean > 0)
    out[valid] = (arr[valid] - mean[valid]) / mean[valid] * 100.0
    return out


__all__ = ["sma", "ema", "rsi", "bubble_pct"]
