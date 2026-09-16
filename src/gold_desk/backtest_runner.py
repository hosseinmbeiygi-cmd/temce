"""Backtest Runner — اجرای استراتژی DCA روی داده‌های تاریخی ۹۰ روز اخیر.

از سند مرجع GapGPT:
- شبیه‌سازی خرید در سه پله (30/40/30) با triggerهای واقعی
- مقایسه با buy-and-hold
- محاسبه hit rate، max drawdown، Sharpe ratio (ساده‌شده)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.time import utc_now_naive

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BacktestTrade:
    date: date
    tranche: int
    price: float
    amount_irt: float
    units: float
    trigger_met: bool


@dataclass(frozen=True)
class BacktestMetrics:
    period_start: date
    period_end: date
    initial_capital: float
    final_value: float
    total_return_pct: float
    buy_hold_return_pct: float
    alpha_pct: float  # اختلاف با buy-hold
    hit_rate_pct: float
    n_trades: int
    n_successful: int
    max_drawdown_pct: float
    sharpe_ratio: float  # ساده‌شده
    trades: list[BacktestTrade] = field(default_factory=list)
    warning: str | None = None


async def _fetch_daily_closes(session: AsyncSession, symbol: str, days: int) -> list[tuple[date, float]]:
    """خواندن close روزانه."""
    try:
        from brsapi.models.commodity import GoldCoinHistoryModel

        cutoff = (utc_now_naive() - timedelta(days=days)).strftime("%Y-%m-%d")
        stmt = (
            select(GoldCoinHistoryModel.date, GoldCoinHistoryModel.price_close)
            .where(
                GoldCoinHistoryModel.symbol == symbol,
                GoldCoinHistoryModel.date >= cutoff,
            )
            .order_by(GoldCoinHistoryModel.date)
        )
        result = await session.execute(stmt)
        out: list[tuple[date, float]] = []
        for r in result.all():
            if r[1] and r[1] > 0:
                d = r[0]
                if isinstance(d, str):
                    try:
                        d = datetime.strptime(d, "%Y-%m-%d").date()
                    except ValueError:
                        continue
                out.append((d, float(r[1])))
        return out
    except Exception as exc:
        logger.warning("backtest_runner fetch failed: %s", exc)
        return []


def _simulate_dca(
    closes: list[tuple[date, float]],
    tranches_pct: list[float],
    bubble_trigger: float,
) -> list[BacktestTrade]:
    """شبیه‌سازی DCA سه‌پله‌ای.

    پله 1: اگر حباب < threshold → خرید
    پله 2: اگر قیمت از خرید قبلی 3-5% اصلاح → خرید
    پله 3: در آخرین روز → خرید
    """
    if len(closes) < 10:
        return []

    trades: list[BacktestTrade] = []
    last_buy_price: float | None = None
    capital_remaining = 1.0  # نرمال‌شده

    n_days = len(closes)
    cutoffs = [n_days // 3, 2 * n_days // 3, n_days - 1]

    for tranche_idx, (pct, cutoff) in enumerate(zip(tranches_pct, cutoffs, strict=False)):
        d, price = closes[cutoff]
        if tranche_idx == 0:
            # پله 1: bubble_pct = (price - avg) / avg × 100 (ساده‌شده)
            avg30 = np.mean([c for _, c in closes[max(0, cutoff - 30) : cutoff + 1]])
            bubble = (price - avg30) / avg30 * 100
            trigger_met = bubble < bubble_trigger
        elif tranche_idx == 1 and last_buy_price:
            # پله 2: اصلاح 3-5% از پله قبلی
            change_pct = (price - last_buy_price) / last_buy_price * 100
            trigger_met = -5 < change_pct < -3
        else:
            # پله 3: آخرین روز، همیشه trigger می‌شود
            trigger_met = True

        if trigger_met:
            amount = capital_remaining * pct
            units = amount / price if price > 0 else 0
            trades.append(
                BacktestTrade(
                    date=d,
                    tranche=tranche_idx + 1,
                    price=price,
                    amount_irt=amount,
                    units=units,
                    trigger_met=True,
                )
            )
            capital_remaining -= amount
            last_buy_price = price

    return trades


def _compute_metrics(
    closes: list[tuple[date, float]],
    trades: list[BacktestTrade],
    initial_capital: float,
) -> BacktestMetrics:
    if not closes or not trades:
        return BacktestMetrics(
            period_start=closes[0][0] if closes else date.today(),
            period_end=closes[-1][0] if closes else date.today(),
            initial_capital=initial_capital,
            final_value=0,
            total_return_pct=0,
            buy_hold_return_pct=0,
            alpha_pct=0,
            hit_rate_pct=0,
            n_trades=0,
            n_successful=0,
            max_drawdown_pct=0,
            sharpe_ratio=0,
            warning="insufficient data",
        )

    start_date = closes[0][0]
    end_date = closes[-1][0]
    start_price = closes[0][1]
    end_price = closes[-1][1]

    # Total DCA value
    total_units = sum(t.units for t in trades)
    final_value = total_units * end_price

    total_return = (final_value / initial_capital - 1) * 100 if initial_capital > 0 else 0
    bh_return = (end_price / start_price - 1) * 100
    alpha = total_return - bh_return

    # Hit rate: چند درصد پله‌ها به قیمت نهایی منجر به سود شدند
    successful = sum(1 for t in trades if t.price < end_price)
    n = len(trades)
    hit_rate = (successful / n * 100) if n else 0

    # Max drawdown
    values = np.array([t.units for t in trades])
    prices = np.array([t.price for t in trades])
    portfolio = np.cumsum(values) * end_price  # ساده‌شده
    peak = np.maximum.accumulate(portfolio)
    drawdown = (peak - portfolio) / peak * 100
    max_dd = float(np.max(drawdown)) if len(drawdown) > 0 else 0

    # Sharpe ساده‌شده: فرض risk-free = 0
    if len(closes) > 2:
        prices = np.array([c for _, c in closes], dtype=float)
        # daily simple returns
        daily_returns = (prices[1:] - prices[:-1]) / prices[:-1]
        if len(daily_returns) > 1 and np.std(daily_returns) > 1e-9:
            sharpe = float(np.sqrt(252) * np.mean(daily_returns) / np.std(daily_returns))
        else:
            sharpe = 0.0
    else:
        sharpe = 0.0

    warn = None
    if n < 3:
        warn = f"only {n} trades — sample too small"

    return BacktestMetrics(
        period_start=start_date,
        period_end=end_date,
        initial_capital=initial_capital,
        final_value=final_value,
        total_return_pct=round(total_return, 2),
        buy_hold_return_pct=round(bh_return, 2),
        alpha_pct=round(alpha, 2),
        hit_rate_pct=round(hit_rate, 1),
        n_trades=n,
        n_successful=successful,
        max_drawdown_pct=round(max_dd, 2),
        sharpe_ratio=round(sharpe, 2),
        trades=trades,
        warning=warn,
    )


async def run_strategy_backtest(
    session: AsyncSession,
    symbol: str = "IR_COIN_EMAMI",
    days: int = 90,
    tranches_pct: tuple[float, ...] = (0.30, 0.40, 0.30),
    bubble_trigger: float = 5.0,
    initial_capital: float = 100_000_000.0,
) -> BacktestMetrics:
    """اجرای کامل backtest استراتژی DCA."""
    closes = await _fetch_daily_closes(session, symbol, days)
    trades = _simulate_dca(closes, list(tranches_pct), bubble_trigger)
    return _compute_metrics(closes, trades, initial_capital)
