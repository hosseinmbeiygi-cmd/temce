"""📊 Fund Quant Engine — متریک‌های مالی و بک‌تست (بخش ۵ معماری Enterprise).

مؤلفه‌ها:
  - Sharpe, Sortino, Max Drawdown, Calmar, Alpha, Beta, Tracking Error
  - Score = w1·Return + w2·Risk + w3·Liquidity + w4·Stability (قابل تنظیم)
  - شبیه‌ساز استراتژی: Buy&Hold | DCA ماهانه | خرید در افت (Dip Buying)
    با کارمزد و تقویم بازار ایران (پنجشنبه/جمعه تعطیل).

قاعده سخت: هیچ تابعی به داده‌های آینده دسترسی ندارد (No Look-Ahead Bias) —
همه متریک‌ها فقط از دنباله تا نقطهٔ ارزیابی محاسبه می‌شوند.
"""

from __future__ import annotations

import contextlib
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Literal

import jdatetime

from core.logging import get_logger

logger = get_logger(__name__)

# ── فرضیات بازار ایران ───────────────────────────────────────────────────────

TRADING_FEE_PCT = 0.005952        # کارمزد معامله واحد صندوق (خالص تقریبی)
DEFAULT_ANNUAL_RISK_FREE = 0.23   # نرخ بدون ریسک سالانه (تقریبی ۲۳٪)
IRAN_HOLIDAYS: set[date] = set()  # در صورت نیاز از config پر می‌شود


def is_iran_trading_day(d: date) -> bool:
    """تقویم ساده بازار ایران: پنجشنبه/جمعه تعطیل + تعطیلات ثبت‌شده."""
    if d in IRAN_HOLIDAYS:
        return False
    return d.weekday() not in (3, 4)  # Thursday=3, Friday=4


def next_trading_day(d: date) -> date:
    nxt = d
    for _ in range(15):
        if is_iran_trading_day(nxt):
            return nxt
        nxt += timedelta(days=1)
    return d


# ══════════════════════════════════════════════════════════════════════════════
# متریک‌های مالی — ورودی: دنباله NAV (قدیمی → جدید)
# ══════════════════════════════════════════════════════════════════════════════


def daily_returns(nav_series: list[float]) -> list[float]:
    """بازدهی روزانه ساده — اولین نقطه حذف می‌شود."""
    if len(nav_series) < 2:
        return []
    out: list[float] = []
    for prev, cur in zip(nav_series, nav_series[1:], strict=False):
        if prev and prev > 0 and cur is not None:
            out.append(cur / prev - 1.0)
    return out


def annualize(vol_daily: float) -> float:
    """سالانه‌سازی نوسان با ۲۵۰ روز کاری بازار ایران."""
    return vol_daily * math.sqrt(250)


def compute_sharpe(nav_series: list[float], risk_free_annual: float = DEFAULT_ANNUAL_RISK_FREE) -> float | None:
    rets = daily_returns(nav_series)
    if len(rets) < 20:
        return None
    mean_daily = sum(rets) / len(rets)
    variance = sum((r - mean_daily) ** 2 for r in rets) / (len(rets) - 1)
    std_daily = math.sqrt(variance) if variance > 0 else 0.0
    if std_daily == 0:
        return None
    rf_daily = (1.0 + risk_free_annual) ** (1 / 250) - 1.0
    return ((mean_daily - rf_daily) / std_daily) * math.sqrt(250)


def compute_sortino(nav_series: list[float], risk_free_annual: float = DEFAULT_ANNUAL_RISK_FREE) -> float | None:
    rets = daily_returns(nav_series)
    if len(rets) < 20:
        return None
    mean_daily = sum(rets) / len(rets)
    downside = [min(r, 0.0) for r in rets]
    d_var = sum(d * d for d in downside) / max(len(downside), 1)
    d_std = math.sqrt(d_var) if d_var > 0 else 0.0
    if d_std == 0:
        return None
    rf_daily = (1.0 + risk_free_annual) ** (1 / 250) - 1.0
    return ((mean_daily - rf_daily) / d_std) * math.sqrt(250)


def compute_max_drawdown(nav_series: list[float]) -> tuple[float, int, int]:
    """(max_drawdown_pct مثبت، index peak، index trough)."""
    peak = nav_series[0] if nav_series else 0.0
    peak_i = trough_i = 0
    max_dd = 0.0
    peak_idx = 0
    for i, v in enumerate(nav_series):
        if v > peak:
            peak = v
            peak_idx = i
        dd = (peak - v) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
            peak_i, trough_i = peak_idx, i
    return (max_dd * 100.0, peak_i, trough_i)


def compute_calmar(nav_series: list[float]) -> float | None:
    if len(nav_series) < 30:
        return None
    total_return = nav_series[-1] / nav_series[0] - 1.0 if nav_series[0] > 0 else 0.0
    years = max(len(nav_series) / 250.0, 1 / 12)
    cagr = (1.0 + total_return) ** (1 / years) - 1.0
    max_dd_pct, _, _ = compute_max_drawdown(nav_series)
    if max_dd_pct <= 0:
        return None
    return cagr / (max_dd_pct / 100.0)


def compute_alpha_beta(
    fund_nav: list[float],
    index_nav: list[float],
) -> tuple[float | None, float | None]:
    """Alpha (سالانه، درصد) و Beta نسبت به شاخص کل — هم‌راستاسازی طول.

    No Look-Ahead: هم‌راستاسازی از انتها انجام می‌شود (آخرین نقطه = امروز)
    تا فقط داده‌های گذشته استفاده شود.
    """
    n = min(len(fund_nav), len(index_nav))
    if n < 30:
        return (None, None)
    f = fund_nav[-n:]
    b = index_nav[-n:]
    rf_rets = daily_returns(f)
    rb_rets = daily_returns(b)
    if len(rf_rets) < 20:
        return (None, None)
    mean_f = sum(rf_rets) / len(rf_rets)
    mean_b = sum(rb_rets) / len(rb_rets)
    cov = sum((x - mean_f) * (y - mean_b) for x, y in zip(rf_rets, rb_rets, strict=False)) / max(len(rf_rets) - 1, 1)
    var_b = sum((y - mean_b) ** 2 for y in rb_rets) / max(len(rb_rets) - 1, 1)
    beta = cov / var_b if var_b > 0 else None
    alpha_daily = mean_f - (DEFAULT_ANNUAL_RISK_FREE / 250) - (beta or 0.0) * (mean_b - DEFAULT_ANNUAL_RISK_FREE / 250)
    alpha_annual_pct = ((1.0 + alpha_daily) ** 250 - 1.0) * 100.0 if alpha_daily > -1 else None
    return (alpha_annual_pct, beta)


def compute_tracking_error(fund_nav: list[float], benchmark_nav: list[float]) -> float | None:
    """Historical Tracking Error سالانه (درصد)."""
    n = min(len(fund_nav), len(benchmark_nav))
    if n < 30:
        return None
    diff = [
        (f / pf - 1.0) - (b / pb - 1.0)
        for f, pf, b, pb in zip(
            fund_nav[-n:], fund_nav[-n - 1 : -1] or fund_nav[-n:],
            benchmark_nav[-n:], benchmark_nav[-n - 1 : -1] or benchmark_nav[-n:],
            strict=False,
        )
    ]
    if len(diff) < 20:
        return None
    mean_d = sum(diff) / len(diff)
    var = sum((d - mean_d) ** 2 for d in diff) / max(len(diff) - 1, 1)
    return annualize(math.sqrt(var)) * 100.0


# ══════════════════════════════════════════════════════════════════════════════
# موتور امتیازدهی (Score = w1·Return + w2·Risk + w3·Liquidity + w4·Stability)
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class ScoreWeights:
    """وزن‌های استاندارد — قابل تنظیم از config / env."""

    return_w: float = 0.35
    risk_w: float = 0.30
    liquidity_w: float = 0.20
    stability_w: float = 0.15

    def normalized(self) -> ScoreWeights:
        total = self.return_w + self.risk_w + self.liquidity_w + self.stability_w
        if total <= 0:
            return ScoreWeights(0.25, 0.25, 0.25, 0.25)
        return ScoreWeights(
            self.return_w / total,
            self.risk_w / total,
            self.liquidity_w / total,
            self.stability_w / total,
        )


def _norm_return_score(total_return_1y_pct: float | None) -> float:
    """۰٪→۵۰، +۳۰٪→۹۰، −۲۰٪→۱۰ (piecewise)."""
    if total_return_1y_pct is None:
        return 50.0
    if total_return_1y_pct >= 40:
        return 95.0
    if total_return_1y_pct >= 0:
        return 50.0 + total_return_1y_pct * 1.125
    if total_return_1y_pct >= -30:
        return 50.0 + total_return_1y_pct * 2.0
    return 5.0


def _norm_risk_score(sharpe: float | None, max_dd_pct: float | None) -> float:
    s = 50.0
    if sharpe is not None:
        s = min(100.0, max(0.0, 50.0 + sharpe * 25.0))
    if max_dd_pct is not None:
        dd_component = max(0.0, 100.0 - max_dd_pct * 2.5)
        s = 0.6 * s + 0.4 * dd_component
    return s


def _norm_liquidity_score(avg_daily_value: float | None) -> float:
    """میلیارد ریال در روز: ≥۱۰ → ۹۵، ≥۱ → ۷۰، ≥۰.۱ → ۴۵، زیر → ۲۰."""
    if avg_daily_value is None:
        return 50.0
    if avg_daily_value >= 10e9:
        return 95.0
    if avg_daily_value >= 1e9:
        return 70.0
    if avg_daily_value >= 1e8:
        return 45.0
    return 20.0


def _norm_stability_score(max_dd_pct: float | None, vol_annual: float | None) -> float:
    s = 50.0
    if vol_annual is not None:
        s = max(0.0, min(100.0, 100.0 - vol_annual * 100.0))
    if max_dd_pct is not None:
        s = 0.5 * s + 0.5 * max(0.0, 100.0 - max_dd_pct * 2.0)
    return s


@dataclass
class FundQuantScore:
    total: float
    return_component: float
    risk_component: float
    liquidity_component: float
    stability_component: float
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": round(self.total, 1),
            "components": {
                "return": round(self.return_component, 1),
                "risk": round(self.risk_component, 1),
                "liquidity": round(self.liquidity_component, 1),
                "stability": round(self.stability_component, 1),
            },
            "metrics": self.metrics,
        }


def score_fund(
    nav_series: list[float],
    benchmark_series: list[float] | None = None,
    avg_daily_trade_value: float | None = None,
    weights: ScoreWeights | None = None,
) -> FundQuantScore:
    """امتیازدهی کامل — فقط با داده‌های گذشته."""
    w = (weights or ScoreWeights()).normalized()
    rets = daily_returns(nav_series)
    mean_daily = sum(rets) / len(rets) if rets else 0.0
    variance = sum((r - mean_daily) ** 2 for r in rets) / max(len(rets) - 1, 1)
    vol_annual = annualize(math.sqrt(variance)) if len(rets) > 1 else None

    total_return_1y: float | None = None
    if len(nav_series) >= 2 and nav_series[0] > 0:
        n_points = min(len(nav_series), 251)
        window = nav_series[-n_points:]
        total_return_1y = (window[-1] / window[0] - 1.0) * 100.0

    sharpe = compute_sharpe(nav_series)
    max_dd_pct, _, _ = compute_max_drawdown(nav_series) if len(nav_series) > 2 else (None, 0, 0)

    alpha, beta = (None, None)
    if benchmark_series:
        alpha, beta = compute_alpha_beta(nav_series, benchmark_series)

    ret_c = _norm_return_score(total_return_1y)
    risk_c = _norm_risk_score(sharpe, max_dd_pct)
    liq_c = _norm_liquidity_score(avg_daily_trade_value)
    stab_c = _norm_stability_score(max_dd_pct, vol_annual)

    total = w.return_w * ret_c + w.risk_w * risk_c + w.liquidity_w * liq_c + w.stability_w * stab_c

    return FundQuantScore(
        total=total,
        return_component=ret_c,
        risk_component=risk_c,
        liquidity_component=liq_c,
        stability_component=stab_c,
        metrics={
            "total_return_1y_pct": total_return_1y,
            "volatility_annual_pct": vol_annual * 100.0 if vol_annual is not None else None,
            "sharpe": sharpe,
            "sortino": compute_sortino(nav_series),
            "max_drawdown_pct": max_dd_pct,
            "calmar": compute_calmar(nav_series),
            "alpha_annual_pct": alpha,
            "beta": beta,
            "tracking_error_pct": (
                compute_tracking_error(nav_series, benchmark_series) if benchmark_series else None
            ),
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# موتور بک‌تست — Buy&Hold | DCA | Dip-Buying (بدون داده آینده)
# ══════════════════════════════════════════════════════════════════════════════

StrategyName = Literal["buy_hold", "dca_monthly", "dip_buying"]


@dataclass
class BacktestTrade:
    date: str
    action: str      # buy
    price: float
    units: float
    amount: float


@dataclass
class BacktestResult:
    strategy: StrategyName
    start_date: str
    end_date: str
    total_invested: float
    final_value: float
    total_return_pct: float
    annualized_return_pct: float | None
    max_drawdown_pct: float
    trade_count: int
    trades: list[BacktestTrade] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "total_invested": round(self.total_invested, 0),
            "final_value": round(self.final_value, 0),
            "total_return_pct": round(self.total_return_pct, 2),
            "annualized_return_pct": (
                round(self.annualized_return_pct, 2) if self.annualized_return_pct is not None else None
            ),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "trade_count": self.trade_count,
            "trades": [
                {"date": t.date, "action": t.action, "price": t.price, "units": round(t.units, 2), "amount": round(t.amount, 0)}
                for t in self.trades[-50:]  # آخرین ۵۰ معامله برای UI
            ],
        }


def _equity_curve(units: float, nav_series: list[float]) -> list[float]:
    return [units * nav for nav in nav_series]


def run_backtest(
    nav_points: list[dict[str, Any]],   # [{date, nav}] — قدیمی → جدید
    strategy: StrategyName = "buy_hold",
    initial_amount: float = 100_000_000.0,   # ریال
    monthly_amount: float = 10_000_000.0,
    dip_threshold_pct: float = -3.0,
    fee_pct: float = TRADING_FEE_PCT,
) -> BacktestResult | None:
    """شبیه‌سازی — هر تصمیم فقط با قیمتِ همان روز یا قبل‌تر گرفته می‌شود.

    - buy_hold: یک خرید در اولین روز معاملاتی.
    - dca_monthly: خرید ثابت در اولین روز معاملاتی هر ماه شمسی.
    - dip_buying: خرید فقط وقتی افت از کف اخیر بیش از آستانه باشد
      (کف اخیر = حداقل ۲۰ روز قبل — بدون آینده‌نگری).
    """
    if len(nav_points) < 30:
        return None

    dates = [p["date"] for p in nav_points]
    navs = [float(p["nav"]) for p in nav_points]

    units = 0.0
    invested = 0.0
    trades: list[BacktestTrade] = []

    parsed_dates: list[date] = []
    for d in dates:
        gd = _parse_any_date(d)
        parsed_dates.append(gd or date(2020, 1, 1))

    seen_months: set[str] = set()
    days_since_last_buy = 999

    for i, (d, nav) in enumerate(zip(parsed_dates, navs, strict=False)):
        buy = False
        amount = 0.0
        if strategy == "buy_hold":
            if i == 0:
                buy, amount = True, initial_amount
        elif strategy == "dca_monthly":
            month_key = jdatetime.date.fromgregorian(date=d).strftime("%Y-%m")
            if month_key not in seen_months and is_iran_trading_day(d):
                seen_months.add(month_key)
                buy, amount = True, monthly_amount
        elif strategy == "dip_buying":
            # افت از سقف ۲۰ روزِ «گذشته» — فقط با داده تا امروز (No Look-Ahead)
            window = navs[max(0, i - 20) : i + 1]
            recent_high = max(window)
            change_from_high = (nav - recent_high) / recent_high if recent_high > 0 else 0.0
            # خرید وقتی قیمت حداقل به اندازه آستانه زیر سقف اخیر است،
            # حداکثر هر ۵ روز معاملاتی یک بار (کنترل هزینه و درگیری سرمایه)
            if (
                change_from_high <= dip_threshold_pct / 100.0
                and days_since_last_buy >= 5
                and is_iran_trading_day(d)
            ):
                buy, amount = True, monthly_amount

        if buy and amount > 0 and nav > 0:
            net_amount = amount * (1.0 - fee_pct)
            bought_units = net_amount / nav
            units += bought_units
            invested += amount
            days_since_last_buy = 0
            trades.append(BacktestTrade(date=str(dates[i]), action="buy", price=nav, units=bought_units, amount=amount))
        else:
            days_since_last_buy += 1

    if invested <= 0 or units <= 0:
        return None

    equity = _equity_curve(units, navs)
    # منحنی ارزش فقط بعد از اولین خرید معنادار است؛ ساده‌سازی: از ابتدا
    max_dd_pct, _, _ = compute_max_drawdown(equity)
    final_value = units * navs[-1]
    days_span = (parsed_dates[-1] - parsed_dates[0]).days
    years = max(days_span / 365.25, 1 / 365.25)
    annualized = ((final_value / invested) ** (1 / years) - 1.0) * 100.0 if final_value > 0 and invested > 0 else None

    return BacktestResult(
        strategy=strategy,
        start_date=str(dates[0]),
        end_date=str(dates[-1]),
        total_invested=invested,
        final_value=final_value,
        total_return_pct=(final_value / invested - 1.0) * 100.0,
        annualized_return_pct=annualized,
        max_drawdown_pct=max_dd_pct,
        trade_count=len(trades),
        trades=trades,
    )


def run_all_strategies(
    nav_points: list[dict[str, Any]],
    initial_amount: float = 100_000_000.0,
    monthly_amount: float = 10_000_000.0,
) -> dict[str, Any]:
    """اجرای هر سه استراتژی برای تب «بک‌تست» UI."""
    out: dict[str, Any] = {"strategies": {}, "available": False}
    for strat in ("buy_hold", "dca_monthly", "dip_buying"):
        res = run_backtest(
            nav_points,
            strategy=strat,  # type: ignore[arg-type]
            initial_amount=initial_amount,
            monthly_amount=monthly_amount,
        )
        if res is not None:
            out["strategies"][strat] = res.to_dict()
            out["available"] = True
    return out


def _parse_any_date(raw: Any) -> date | None:
    """پارس تاریخ شمسی یا میلادی از NAV points."""
    if raw is None:
        return None
    s = str(raw).strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    # میلادی ISO
    with contextlib.suppress(ValueError):
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    # شمسی
    parts = s[:10].replace("/", "-").split("-")
    if len(parts) == 3:
        try:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            if 1300 <= y <= 1500:
                return jdatetime.date(y, m, d).togregorian()
            return date(y, m, d)
        except (ValueError, OverflowError):
            return None
    return None
