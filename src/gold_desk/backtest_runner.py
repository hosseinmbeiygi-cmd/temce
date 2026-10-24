"""Backtest Runner — شبیه‌سازی استراتژی DCA و مقایسه با buy & hold.

اقتصاد شبیه‌سازی (بازنویسی E-C1..E-H4):
- هر پله با **سرمایه واقعی** خرید می‌کند: ``amount = initial_capital × pct`` و
  ``units = (amount − fee) / price``؛ پس واحدها و درصدها هم‌مقیاس‌اند.
- پله‌ها **رویدادمحور و زنجیره‌ای**اند: پلهٔ بعد فقط وقتی بررسی می‌شود که پلهٔ
  قبل اجرا شده باشد و شرط خودش برقرار شود؛ پول اجرانشده نقد می‌ماند و در NAV
  شمرده می‌شود.
- متریک‌ها از **NAV روزانهٔ استراتژی** (نقد + ارزش روز واحدها) می‌آیند:
  max drawdown، Sharpe و alpha روی همان NAV محاسبه می‌شوند، نه روی دارایی پایه.
- کارمزد از ``constants.VEHICLE_FEES`` گرفته می‌شود.
- متریک‌های کل دوره و همچنین دورهٔ **خارج از نمونه** (۳۰٪ پایانی) گزارش می‌شوند.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import jdatetime
from core.time import now_tehran

from . import indicators
from .constants import COIN_WEIGHTS, SMA_BUBBLE_WINDOW, VEHICLE_FEES
from .dates import jalali_days_ago

logger = logging.getLogger(__name__)

# ── آستانه‌های استراتژی (واحد: درصد تغییر قیمت) ──────────────────────
# پلهٔ دوم فقط با اصلاح این بازه نسبت به قیمت خرید قبلی اجرا می‌شود.
TRANCHE2_PULLBACK_MIN_PCT: float = 3.0
TRANCHE2_PULLBACK_MAX_PCT: float = 5.0
# حداقل تعداد کندل برای معنادار بودن شبیه‌سازی.
MIN_SIMULATION_DAYS: int = 10
# سهم پایانی دوره که به‌عنوان نمونهٔ خارج از نمونه گزارش می‌شود.
OOS_FRACTION: float = 0.30
# تعداد روز معاملاتی در سال برای سالانه‌سازی شارپ.
TRADING_DAYS_PER_YEAR: int = 252


@dataclass(frozen=True)
class BacktestTrade:
    date: date
    tranche: int
    price: float
    amount_irt: float
    units: float
    trigger_met: bool
    # کارمزد پرداختی این خرید (تومان). مقدار پیش‌فرض برای سازگاری عقب‌رو.
    fee_irt: float = 0.0


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
    sharpe_ratio: float  # روی NAV روزانهٔ استراتژی، rf=0
    trades: list[BacktestTrade] = field(default_factory=list)
    warning: str | None = None
    # ── فیلدهای افزایشی ──
    cash_remaining: float = 0.0
    total_fee_paid: float = 0.0
    oos_start: date | None = None
    oos_total_return_pct: float | None = None
    oos_buy_hold_return_pct: float | None = None
    oos_alpha_pct: float | None = None
    oos_max_drawdown_pct: float | None = None


def _parse_stored_date(value: object) -> date | None:
    """تاریخ ذخیره‌شده (شمسی ``YYYY-MM-DD``) را به ``date`` میلادی تبدیل می‌کند.

    پیش‌تر ``strptime(value, "%Y-%m-%d")`` مستقیم روی رشتهٔ شمسی اجرا می‌شد و
    ``date(1405, ...)`` می‌ساخت؛ نتیجه در API به‌صورت سال ۱۴۰۵ نمایش داده می‌شد.
    """
    if isinstance(value, date):
        return value
    parts = str(value).strip().replace("/", "-").split("-")
    if len(parts) != 3:
        return None
    try:
        return jdatetime.date(int(parts[0]), int(parts[1]), int(parts[2])).togregorian()
    except (TypeError, ValueError):
        logger.warning("unparsable history date %r", value)
        return None


async def _fetch_daily_closes(session: AsyncSession, symbol: str, days: int) -> list[tuple[date, float]]:
    """خواندن close روزانه (تاریخ میلادی)."""
    try:
        from brsapi.models.commodity import GoldCoinHistoryModel

        # ستون date شمسی است؛ cutoff میلادی همیشه صفر ردیف مطابقت می‌داد (GS-03).
        cutoff = jalali_days_ago(days)
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
                parsed = _parse_stored_date(r[0])
                if parsed is None:
                    continue
                out.append((parsed, float(r[1])))
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("backtest_runner fetch failed: %s", exc, exc_info=True)
        return []


def _vehicle_for_symbol(symbol: str) -> str:
    """کلاس ابزار برای انتخاب کارمزد از ``VEHICLE_FEES``."""
    if symbol in COIN_WEIGHTS:
        return "coin"
    if "GOLD" in symbol:
        return "melted"
    return "etf"


def _fee_pct_for_symbol(symbol: str) -> float:
    return VEHICLE_FEES[_vehicle_for_symbol(symbol)]["buy_pct"] / 100.0


def _simulate_dca(
    closes: list[tuple[date, float]],
    tranches_pct: list[float],
    bubble_trigger: float,
    initial_capital: float = 100_000_000.0,
    fee_pct: float = 0.0,
) -> list[BacktestTrade]:
    """شبیه‌سازی DCA پله‌ای **رویدادمحور**.

    - پلهٔ ۱: اولین روزی که حباب تکنیکال (نسبت به SMA trailing) کمتر از آستانه است.
    - پلهٔ ۲: فقط اگر پلهٔ ۱ اجرا شده و قیمت ۳–۵٪ از قیمت خرید قبلی اصلاح کرده.
    - پلهٔ ۳: فقط اگر پلهٔ ۲ اجرا شده و قیمت از قیمت خرید قبلی عبور کرده.

    هر پله فقط یک بار اجرا می‌شود و بودجه‌اش از **کل سرمایه** است (نه از
    باقی‌مانده)، پس مجموع پله‌ها از سرمایه بیشتر نمی‌شود و نقدِ اجرانشده می‌ماند.
    """
    if len(closes) < MIN_SIMULATION_DAYS or not tranches_pct:
        return []

    prices = np.array([p for _, p in closes], dtype=float)
    bubble = indicators.bubble_pct(prices, SMA_BUBBLE_WINDOW)

    trades: list[BacktestTrade] = []
    cash = float(initial_capital)
    last_buy_price: float | None = None
    tranche_idx = 0  # شمارهٔ پلهٔ بعدی که باید بررسی شود

    for i, (d, price) in enumerate(closes):
        if tranche_idx >= len(tranches_pct) or price <= 0:
            continue

        pct = tranches_pct[tranche_idx]
        if pct <= 0:
            tranche_idx += 1
            continue

        trigger_met = False
        if tranche_idx == 0:
            trigger_met = (not np.isnan(bubble[i])) and bool(bubble[i] < bubble_trigger)
        elif tranche_idx == 1 and last_buy_price:
            change_pct = (price - last_buy_price) / last_buy_price * 100.0
            pullback = -change_pct
            trigger_met = TRANCHE2_PULLBACK_MIN_PCT <= pullback <= TRANCHE2_PULLBACK_MAX_PCT
        elif tranche_idx >= 2 and last_buy_price:
            # شکست قیمت خرید قبلی (ادامهٔ روند) — بدون آستانهٔ درصدی جدید.
            trigger_met = price > last_buy_price

        if not trigger_met:
            continue

        budget = min(initial_capital * pct, cash)
        if budget <= 0:
            continue
        fee = budget * fee_pct
        units = (budget - fee) / price
        trades.append(
            BacktestTrade(
                date=d,
                tranche=tranche_idx + 1,
                price=price,
                amount_irt=budget,
                units=units,
                trigger_met=True,
                fee_irt=fee,
            )
        )
        cash -= budget
        last_buy_price = price
        tranche_idx += 1

    return trades


def _daily_nav(
    closes: list[tuple[date, float]],
    trades: list[BacktestTrade],
    initial_capital: float,
) -> np.ndarray:
    """NAV روزانهٔ استراتژی = نقد باقی‌مانده + ارزش روزِ واحدهای نگه‌داشته."""
    pending = sorted(trades, key=lambda t: t.date)
    nav: list[float] = []
    cash = float(initial_capital)
    units = 0.0
    idx = 0
    for d, price in closes:
        while idx < len(pending) and pending[idx].date <= d:
            cash -= pending[idx].amount_irt
            units += pending[idx].units
            idx += 1
        nav.append(cash + units * price)
    return np.asarray(nav, dtype=float)


def _max_drawdown_pct(nav: np.ndarray) -> float:
    if nav.size == 0:
        return 0.0
    peak = np.maximum.accumulate(nav)
    valid = peak > 0
    if not valid.any():
        return 0.0
    drawdown = np.zeros_like(nav)
    drawdown[valid] = (peak[valid] - nav[valid]) / peak[valid] * 100.0
    return float(np.max(drawdown))


def _annualized_sharpe(nav: np.ndarray) -> float:
    """شارپ روی بازده‌های روزانهٔ NAV استراتژی (rf=0)."""
    if nav.size < 3:
        return 0.0
    previous = nav[:-1]
    valid = previous > 0
    if not valid.any():
        return 0.0
    daily_returns = np.diff(nav)[valid] / previous[valid]
    if daily_returns.size < 2:
        return 0.0
    std = float(np.std(daily_returns))
    if std < 1e-12:
        return 0.0
    return float(np.sqrt(TRADING_DAYS_PER_YEAR) * np.mean(daily_returns) / std)


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

    nav = _daily_nav(closes, trades, initial_capital)
    final_value = float(nav[-1])
    total_return = (final_value / initial_capital - 1) * 100 if initial_capital > 0 else 0.0
    bh_return = (end_price / start_price - 1) * 100 if start_price > 0 else 0.0
    alpha = total_return - bh_return

    successful = sum(1 for t in trades if t.price < end_price)
    n = len(trades)
    hit_rate = (successful / n * 100) if n else 0.0

    max_dd = _max_drawdown_pct(nav)
    sharpe = _annualized_sharpe(nav)

    # ── خارج از نمونه: ۳۰٪ پایانی همان پنجره ──
    oos_idx = int(len(closes) * (1 - OOS_FRACTION))
    oos_start: date | None = None
    oos_total = oos_bh = oos_alpha = oos_dd = None
    if 0 < oos_idx < len(closes) - 1:
        oos_start = closes[oos_idx][0]
        segment_nav = nav[oos_idx:]
        if segment_nav[0] > 0:
            oos_total = (segment_nav[-1] / segment_nav[0] - 1) * 100.0
        oos_start_price = closes[oos_idx][1]
        if oos_start_price > 0:
            oos_bh = (end_price / oos_start_price - 1) * 100.0
        if oos_total is not None and oos_bh is not None:
            oos_alpha = oos_total - oos_bh
        oos_dd = _max_drawdown_pct(segment_nav)

    cash_remaining = float(initial_capital) - sum(t.amount_irt for t in trades)
    total_fee = sum(t.fee_irt for t in trades)

    warning_parts: list[str] = []
    if n < 3:
        warning_parts.append(f"only {n} trades — sample too small")
    warning_parts.append(
        f"out-of-sample = last {int(OOS_FRACTION * 100)}% of the window; "
        "returns are historical simulation, not a forecast (no slippage/tax, "
        "one row per trading session)"
    )

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
        warning="; ".join(warning_parts),
        cash_remaining=round(cash_remaining, 2),
        total_fee_paid=round(total_fee, 2),
        oos_start=oos_start,
        oos_total_return_pct=None if oos_total is None else round(oos_total, 2),
        oos_buy_hold_return_pct=None if oos_bh is None else round(oos_bh, 2),
        oos_alpha_pct=None if oos_alpha is None else round(oos_alpha, 2),
        oos_max_drawdown_pct=None if oos_dd is None else round(oos_dd, 2),
    )


async def run_strategy_backtest(
    session: AsyncSession,
    symbol: str = "IR_COIN_EMAMI",
    days: int = 90,
    tranches_pct: tuple[float, ...] = (0.30, 0.40, 0.30),
    bubble_trigger: float = 5.0,
    initial_capital: float = 100_000_000.0,
) -> BacktestMetrics:
    """اجرای کامل backtest استراتژی DCA (با کارمزد ابزار و متریک خارج از نمونه)."""
    closes = await _fetch_daily_closes(session, symbol, days)
    trades = _simulate_dca(
        closes,
        list(tranches_pct),
        bubble_trigger,
        initial_capital=initial_capital,
        fee_pct=_fee_pct_for_symbol(symbol),
    )
    return _compute_metrics(closes, trades, initial_capital)
