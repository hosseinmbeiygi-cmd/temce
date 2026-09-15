"""Backtest — بازتست استراتژی روی داده‌های تاریخی ۹۰ روز اخیر.

بررسی: آیا وقتی score>80 بوده، ۳۰ روز بعد بازدهی مثبت بوده؟
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BacktestResult:
    total_days: int
    score_above_threshold_days: int
    forward_return_30d_avg: float
    forward_return_30d_positive: int
    forward_return_30d_negative: int
    hit_rate: float
    sample_warning: str | None


async def _daily_bubble_pct(session: AsyncSession, symbol: str, days: int) -> list[tuple[str, float, float]]:
    """بازگشت: لیست (date, bubble_pct vs SMA30, forward_30d_return)."""
    try:
        import numpy as np

        from brsapi.models.commodity import GoldCoinHistoryModel

        cutoff = (datetime.utcnow() - timedelta(days=days + 60)).strftime("%Y-%m-%d")
        stmt = (
            select(GoldCoinHistoryModel.date, GoldCoinHistoryModel.price_close)
            .where(
                GoldCoinHistoryModel.symbol == symbol,
                GoldCoinHistoryModel.date >= cutoff,
            )
            .order_by(GoldCoinHistoryModel.date)
        )
        result = await session.execute(stmt)
        rows = result.all()
        closes = [(str(r[0]), float(r[1])) for r in rows if r[1] and r[1] > 0]
        if len(closes) < 35:
            return []
        prices = np.array([p for _, p in closes], dtype=float)
        # SMA30 برای حباب تکنیکال
        sma30 = np.convolve(prices, np.ones(30) / 30, mode="same")
        # forward + bubble
        out: list[tuple[str, float, float]] = []
        for i, (d, p) in enumerate(closes):
            if i < 30 or i + 30 >= len(closes):
                continue
            bubble = (p - sma30[i]) / sma30[i] * 100.0 if sma30[i] else 0.0
            fwd = (closes[i + 30][1] - p) / p * 100.0
            out.append((d, bubble, fwd))
        return out
    except Exception as exc:
        logger.warning("backtest fetch failed: %s", exc)
        return []


async def run_backtest(
    session: AsyncSession,
    symbol: str = "IR_COIN_EMAMI",
    days: int = 90,
    bubble_threshold: float = 8.0,
) -> BacktestResult:
    """اجرای بک‌تست.

    ساده‌شده: bubble_threshold به‌جای امتیاز (score نیاز به همه componentها دارد).
    """
    rows = await _daily_bubble_pct(session, symbol, days)
    if not rows:
        return BacktestResult(
            total_days=0,
            score_above_threshold_days=0,
            forward_return_30d_avg=0.0,
            forward_return_30d_positive=0,
            forward_return_30d_negative=0,
            hit_rate=0.0,
            sample_warning="no data",
        )

    # فیلتر درست: روزهای حباب بالا (TACTICAL bubble vs SMA30)
    above = [(d, fwd) for d, bubble, fwd in rows if bubble > bubble_threshold]
    if not above:
        return BacktestResult(
            total_days=len(rows),
            score_above_threshold_days=0,
            forward_return_30d_avg=0.0,
            forward_return_30d_positive=0,
            forward_return_30d_negative=0,
            hit_rate=0.0,
            sample_warning="no signal days",
        )

    fwd_returns = [f for _, f in above]
    pos = sum(1 for r in fwd_returns if r > 0)
    neg = sum(1 for r in fwd_returns if r < 0)
    avg = sum(fwd_returns) / len(fwd_returns) if fwd_returns else 0.0
    hit_rate = (pos / len(fwd_returns) * 100.0) if fwd_returns else 0.0

    warn = None
    if len(above) < 5:
        warn = f"only {len(above)} signal days — sample too small for reliable hit rate"

    return BacktestResult(
        total_days=len(rows),
        score_above_threshold_days=len(above),
        forward_return_30d_avg=avg,
        forward_return_30d_positive=pos,
        forward_return_30d_negative=neg,
        hit_rate=hit_rate,
        sample_warning=warn,
    )
