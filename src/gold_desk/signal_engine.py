"""Signal Engine — RSI(14)، EMA، SMA، MACD، Bollinger + EMA bubble.

از brsapi_gold_coin_history می‌خواند (daily OHLC). محاسبه در Python (numpy).
"""

from __future__ import annotations

import numpy as np
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession


async def fetch_closes(session: AsyncSession, symbol: str, days: int) -> list[float]:
    """آخرین N روز close prices."""
    try:
        from brsapi.models.commodity import GoldCoinHistoryModel

        stmt = (
            select(GoldCoinHistoryModel.price_close)
            .where(GoldCoinHistoryModel.symbol == symbol)
            .order_by(desc(GoldCoinHistoryModel.date))
            .limit(days + 10)
        )
        result = await session.execute(stmt)
        closes = [float(r[0]) for r in result.all() if r[0] and r[0] > 0]
        return list(reversed(closes[-days:]))
    except Exception:
        return []


def calc_rsi(closes: list[float], period: int = 14) -> float | None:
    """RSI با rolling 14 روز. Wilder smoothing."""
    if len(closes) < period + 1:
        return None
    arr = np.array(closes, dtype=float)
    deltas = np.diff(arr)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - (100 / (1 + rs)))


def calc_ema(closes: list[float], period: int = 14) -> float | None:
    """EMA آخرین نقطه."""
    if len(closes) < period:
        return None
    arr = np.array(closes, dtype=float)
    alpha = 2.0 / (period + 1)
    ema = arr[0]
    for price in arr[1:]:
        ema = price * alpha + ema * (1 - alpha)
    return float(ema)


def calc_sma(closes: list[float], period: int = 20) -> float | None:
    """SMA ساده."""
    if len(closes) < period:
        return None
    return float(np.mean(closes[-period:]))


def calc_bollinger(closes: list[float], period: int = 20, k: float = 2.0) -> dict | None:
    """Bollinger Bands: middle=SMA, upper/lower = SMA ± k*std."""
    if len(closes) < period:
        return None
    arr = np.array(closes[-period:], dtype=float)
    sma = float(np.mean(arr))
    std = float(np.std(arr, ddof=0))
    return {"middle": sma, "upper": sma + k * std, "lower": sma - k * std, "width_pct": (2 * k * std / sma * 100) if sma else 0}


def calc_macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict | None:
    """MACD line = EMA12 - EMA26, signal = EMA9(MACD)."""
    if len(closes) < slow + signal:
        return None
    arr = np.array(closes, dtype=float)

    def _ema(a: np.ndarray, p: int) -> np.ndarray:
        alpha = 2.0 / (p + 1)
        out = np.empty_like(a, dtype=float)
        out[0] = a[0]
        for i in range(1, len(a)):
            out[i] = a[i] * alpha + out[i - 1] * (1 - alpha)
        return out

    ema_fast = _ema(arr, fast)
    ema_slow = _ema(arr, slow)
    macd_line = ema_fast - ema_slow
    sig_line = _ema(macd_line, signal)
    hist = macd_line[-1] - sig_line[-1]
    return {
        "macd": float(macd_line[-1]),
        "signal": float(sig_line[-1]),
        "histogram": float(hist),
        "bullish": bool(hist > 0),
    }


def calc_ema_bubble(closes: list[float], period: int = 20) -> float | None:
    """فاصله قیمت از EMA به‌صورت درصد — حباب تکنیکال."""
    if len(closes) < period:
        return None
    ema = calc_ema(closes, period)
    if ema is None or ema == 0:
        return None
    return float((closes[-1] - ema) / ema * 100.0)


async def get_xau_rsi(session: AsyncSession, days: int = 30) -> float | None:
    """RSI 14 روزه XAUUSD."""
    closes = await fetch_closes(session, "XAUUSD", days)
    return calc_rsi(closes, 14) if closes else None


async def get_xau_ema(session: AsyncSession, days: int = 30) -> float | None:
    """EMA 14 روزه XAUUSD."""
    closes = await fetch_closes(session, "XAUUSD", days)
    return calc_ema(closes, 14) if closes else None


async def get_xau_indicators(session: AsyncSession, days: int = 40) -> dict:
    """همه اندیکاتورهای XAUUSD به‌صورت یکجا."""
    closes = await fetch_closes(session, "XAUUSD", days)
    if not closes:
        return {"rsi": None, "ema": None, "sma": None, "bollinger": None, "macd": None, "ema_bubble_pct": None}
    return {
        "rsi": calc_rsi(closes, 14),
        "ema": calc_ema(closes, 14),
        "sma": calc_sma(closes, 20),
        "bollinger": calc_bollinger(closes, 20),
        "macd": calc_macd(closes),
        "ema_bubble_pct": calc_ema_bubble(closes, 20),
        "closes": closes,
    }
