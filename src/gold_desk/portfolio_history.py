"""تاریخچهٔ ارزش پرتفوی + بازده وزنی‌زمان (TWR) + مقایسه با بنچمارک.

چرا این ماژول وجود دارد: ``/gold/portfolio`` فقط P&L لحظه‌ای می‌ساخت و هیچ سری
زمانی ذخیره نمی‌شد. بدون سری ارزش نمی‌توان TWR (مستقل از زمان‌بندی واریز/برداشت)
یا مقایسه با طلا/دلار/شاخص ساخت.

قواعد:
  * یک ردیف در روز (کلید ``as_of``) در ``gold_portfolio_values``.
  * ``net_flow_irt`` = جریان نقدی بیرونی همان روز (واریز مثبت، برداشت منفی) از
    همان منطق ``portfolio.build_cash_flows`` تا با XIRR ناسازگار نشود.
  * هیچ مقدار جعلی ساخته نمی‌شود: سری ناکافی یا بنچمارک بدون داده → ``None``
    همراه دلیل در ``unavailable``.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.time import now_tehran

from . import performance as perf
from .constants import (
    PORTFOLIO_BENCHMARKS,
    PORTFOLIO_PERFORMANCE_WINDOW_DAYS,
    PORTFOLIO_SYMBOL_VEHICLE_OVERRIDES,
    PORTFOLIO_TARGET_WEIGHTS,
)
from .models import GoldPortfolioValueModel
from .portfolio import (
    build_cash_flows,
    get_current_prices,
    get_holdings_grouped,
    load_holdings_and_trades,
)

logger = logging.getLogger(__name__)

# ── سری بنچمارک‌ها ────────────────────────────────────────────────
# نکتهٔ دادهٔ مهم: در این جدول‌ها ``gregorian_date`` **تاریخ ثبت (fetch)** است نه
# تاریخ معامله. یک بک‌فیل انبوه کل تاریخ را زیر یک روز fetch درج کرده (مثلاً ۲۳۹۸
# ردیف طلای آب‌شده زیر 2026-07-23 با بازهٔ قیمت ۶۵۹ هزار تا ۹۷ میلیون) و استفاده از
# آن بازده‌های بی‌معنی می‌سازد. تاریخ واقعی معامله ستون ``date`` است (شمسی)؛
# ``brsapi_index_values`` برعکس، ``date`` خالی دارد و ``gregorian_date`` معتبر است.
# به همین دلیل ردیف‌ها را می‌گیریم و در پایتون تاریخشان را نرمال می‌کنیم.
_BENCHMARK_SQL: dict[str, str] = {
    # تاریخ شمسی (با جداکننده‌های '/' یا '-') — آخرین ردیف هر تاریخ.
    "gold_coin_history": """
        SELECT DISTINCT ON (date) date, price_close
        FROM brsapi_gold_coin_history
        WHERE symbol = :symbol AND price_close > 0 AND date <> ''
        ORDER BY date DESC, id DESC
        LIMIT :row_limit
    """,
    "gcph_daily": """
        SELECT DISTINCT ON (date) date, price_close
        FROM brsapi_gold_currency_pro_daily_history
        WHERE symbol = :symbol AND price_close > 0 AND date <> ''
        ORDER BY date DESC, id DESC
        LIMIT :row_limit
    """,
    # تاریخ میلادی معتبر (date خالی است).
    "index_values": """
        SELECT DISTINCT ON (gregorian_date) gregorian_date, index_value
        FROM brsapi_index_values
        WHERE name = :name AND index_value > 0 AND gregorian_date IS NOT NULL
        ORDER BY gregorian_date DESC, id DESC
        LIMIT :row_limit
    """,
}


def _to_gregorian(raw: object) -> date | None:
    """تاریخ سری بنچمارک را به میلادی تبدیل می‌کند (شمسی = رشته)."""
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if not isinstance(raw, str):
        return None
    text_date = raw.strip().replace("/", "-")
    if not text_date:
        return None
    parts = text_date.split("-")
    if len(parts) < 3:
        return None
    try:
        year, month, day = (int(float(p)) for p in parts[:3])
    except ValueError:
        return None
    if 1700 <= year <= 2200:  # از قبل میلادی
        try:
            return date(year, month, day)
        except ValueError:
            return None
    try:
        import jdatetime

        return jdatetime.date(year, month, day).togregorian()
    except Exception:  # noqa: BLE001 — تاریخ نامعتبر بهتر از کرش است
        return None


# ── طبقه‌بندی ابزار (برای ری‌بالانس) ──────────────────────────────


def classify_vehicle(symbol: str) -> str:
    """کلاس ابزار یک نماد: ``coin`` | ``melted`` | ``etf``.

    تشخیص خودکار با override صریح از ``PORTFOLIO_SYMBOL_VEHICLE_OVERRIDES``.
    """
    raw = (symbol or "").strip()
    if raw in PORTFOLIO_SYMBOL_VEHICLE_OVERRIDES:
        return PORTFOLIO_SYMBOL_VEHICLE_OVERRIDES[raw]
    sym = raw.upper()
    if "COIN" in sym:
        return "coin"
    if any(t in sym for t in ("MELTED", "18K", "24K", "GERAMI", "IR_GOLD_1G")):
        return "melted"
    return "etf"


def allocation_drift_pct(
    class_weights: Mapping[str, float],
    targets: Mapping[str, float] | None = None,
) -> tuple[float | None, dict[str, float]]:
    """انحراف وزن کلاس‌ها از وزن هدف (نقاط درصدی).

    بازمی‌گرداند ``(بیشترین انحراف قدرمطلق یا None، نگاشت کلاس→انحراف)``.
    اگر هیچ وزنی وجود نداشته باشد ``(None, {})``.
    """
    target_map = dict(targets if targets is not None else PORTFOLIO_TARGET_WEIGHTS)
    if not class_weights:
        return None, {}
    classes = set(class_weights) | set(target_map)
    drift: dict[str, float] = {}
    for cls in sorted(classes):
        actual = float(class_weights.get(cls, 0.0))
        target = float(target_map.get(cls, 0.0))
        drift[cls] = actual - target
    return max(abs(v) for v in drift.values()), drift


def class_weights_from_holdings(holdings: Iterable[object]) -> dict[str, float]:
    """وزن درصدی هر کلاس بر اساس ارزش فعلی holdingهای قیمت‌دار."""
    by_class: dict[str, float] = {}
    for h in holdings:
        value = getattr(h, "current_value", None)
        if value is None or value <= 0:
            continue
        cls = classify_vehicle(getattr(h, "symbol", ""))
        by_class[cls] = by_class.get(cls, 0.0) + float(value)
    total = sum(by_class.values())
    if total <= 0:
        return {}
    return {cls: v / total * 100.0 for cls, v in by_class.items()}


# ── جریان نقدی روزانه + ثبت ارزش ─────────────────────────────────


def daily_net_flow_irt(holdings: Iterable[object], trades: Iterable[object], as_of: date) -> float:
    """جریان نقدی بیرونی یک روز: واریز مثبت، برداشت منفی.

    از ``build_cash_flows`` استفاده می‌کند (خرید = خروج پول ⇒ علامت منفی) و
    علامت را برمی‌گرداند تا با کنوانسیون TWR (واریز مثبت) بخواند.
    """
    total = 0.0
    for flow_date, signed in build_cash_flows(holdings=holdings, trades=trades):
        if flow_date == as_of:
            total += -float(signed)
    return total


async def capture_portfolio_value(
    session: AsyncSession,
    *,
    snapshot: dict | None = None,
    prices: Mapping[str, float] | None = None,
    asof: date | None = None,
    user_id: str | None = None,
) -> GoldPortfolioValueModel:
    """ثبت/به‌روزرسانی ارزش پرتفوی برای یک روز (idempotent روی user+as_of)."""
    day = asof or now_tehran().date()
    holdings, trades = await load_holdings_and_trades(session, user_id=user_id)
    live = dict(prices) if prices is not None else get_current_prices(snapshot)
    summary = await get_holdings_grouped(session, live, user_id=user_id)
    net_flow = daily_net_flow_irt(holdings, trades, day)

    stmt = select(GoldPortfolioValueModel).where(GoldPortfolioValueModel.as_of == day)
    if user_id is not None:
        stmt = stmt.where(GoldPortfolioValueModel.user_id == user_id)
    else:
        stmt = stmt.where(GoldPortfolioValueModel.user_id.is_(None))
    row = (await session.execute(stmt)).scalars().first()

    if row is None:
        row = GoldPortfolioValueModel(
            user_id=user_id,
            as_of=day,
            total_value_irt=summary.total_value,
            total_cost_irt=summary.total_cost,
            net_flow_irt=net_flow,
            unpriced_holdings=getattr(summary, "unpriced_holdings", 0),
        )
        session.add(row)
    else:
        row.total_value_irt = summary.total_value
        row.total_cost_irt = summary.total_cost
        row.net_flow_irt = net_flow
        row.unpriced_holdings = getattr(summary, "unpriced_holdings", 0)

    await session.commit()
    await session.refresh(row)
    return row


async def load_value_history(
    session: AsyncSession,
    *,
    days: int = PORTFOLIO_PERFORMANCE_WINDOW_DAYS,
    user_id: str | None = None,
) -> list[GoldPortfolioValueModel]:
    """سری ارزش پرتفوی در پنجرهٔ ``days`` روز گذشته (صعودی، محدود به مالک)."""
    cutoff = now_tehran().date() - timedelta(days=max(1, int(days)))
    stmt = (
        select(GoldPortfolioValueModel)
        .where(GoldPortfolioValueModel.as_of >= cutoff)
        .order_by(GoldPortfolioValueModel.as_of)
    )
    if user_id is not None:
        stmt = stmt.where(GoldPortfolioValueModel.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


def value_series(rows: Sequence[GoldPortfolioValueModel]) -> tuple[list[date], list[float], list[float]]:
    """از ردیف‌های DB به ``(تاریخ‌ها، ارزش‌ها، جریان‌های نقدی)``."""
    days = [r.as_of for r in rows]
    values = [float(r.total_value_irt) for r in rows]
    flows = [float(r.net_flow_irt or 0.0) for r in rows]
    return days, values, flows


# ── سری بنچمارک ───────────────────────────────────────────────────


async def load_benchmark_series(
    session: AsyncSession, key: str, *, start: date, end: date
) -> dict[date, float]:
    """سری روزانهٔ یک بنچمارک (کلید از ``PORTFOLIO_BENCHMARKS``)."""
    cfg = PORTFOLIO_BENCHMARKS.get(key)
    if not cfg:
        return {}
    sql = _BENCHMARK_SQL.get(str(cfg.get("kind", "")))
    if not sql:
        return {}
    # سری از تازه‌ترین به قدیمی‌ترین خوانده می‌شود؛ به‌اندازهٔ پنجره + حاشیهٔ
    # تعطیلات/آخر هفته کافی است.
    row_limit = max(30, (end - start).days + 30)
    params = {
        "symbol": cfg.get("symbol"),
        "name": cfg.get("name"),
        "row_limit": row_limit,
    }
    try:
        async with session.begin_nested():
            rows = (await session.execute(text(sql), params)).fetchall()
    except Exception as exc:  # noqa: BLE001 — منبع نبود بهتر از پاسخ 500 است
        logger.warning("benchmark %s series unavailable: %s", key, exc)
        return {}
    series: dict[date, float] = {}
    for raw_day, raw_value in rows:
        day = _to_gregorian(raw_day)
        if day is None or raw_value is None:
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if value <= 0 or not (start <= day <= end):
            continue
        # صعودی ذخیره می‌شود؛ DISTINCT ON قبلاً یک ردیف در هر روز داده است.
        series.setdefault(day, value)
    return series


def benchmark_return_pct(
    series: Mapping[date, float], *, start: date | None = None, end: date | None = None
) -> float | None:
    """بازده بنچمارک از اولین تا آخرین نقطهٔ موجود در پنجره (None اگر < ۲ نقطه)."""
    points = sorted(
        (d, v)
        for d, v in series.items()
        if (start is None or d >= start) and (end is None or d <= end)
    )
    if len(points) < 2 or not points[0][1]:
        return None
    return (points[-1][1] / points[0][1] - 1.0) * 100.0


# ── گزارش کارایی ──────────────────────────────────────────────────


@dataclass(frozen=True)
class PortfolioPerformance:
    """کارایی و ریسک پرتفوی + مقایسه با بنچمارک‌ها."""

    window_days: int
    start: date | None
    end: date | None
    points: int
    total_value_irt: float
    total_cost_irt: float
    unpriced_holdings: int
    twr_pct: float | None
    simple_return_pct: float | None
    annualized_volatility_pct: float | None
    sharpe_ratio: float | None
    sortino_ratio: float | None
    max_drawdown_pct: float | None
    var_95_pct: float | None
    cvar_95_pct: float | None
    concentration_pct: float | None
    max_drift_pct: float | None
    drift_by_class: dict[str, float] = field(default_factory=dict)
    benchmarks: dict[str, dict] = field(default_factory=dict)
    unavailable: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "window_days": self.window_days,
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "points": self.points,
            "total_value_irt": self.total_value_irt,
            "total_cost_irt": self.total_cost_irt,
            "unpriced_holdings": self.unpriced_holdings,
            "twr_pct": self.twr_pct,
            "simple_return_pct": self.simple_return_pct,
            "annualized_volatility_pct": self.annualized_volatility_pct,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "max_drawdown_pct": self.max_drawdown_pct,
            "var_95_pct": self.var_95_pct,
            "cvar_95_pct": self.cvar_95_pct,
            "concentration_pct": self.concentration_pct,
            "max_drift_pct": self.max_drift_pct,
            "drift_by_class": self.drift_by_class,
            "benchmarks": self.benchmarks,
            "unavailable": self.unavailable,
        }

    def risk_metrics(self) -> dict[str, float | None]:
        """معیارهای موردنیاز موتور هشدار (تمرکز / انحراف / افت / TWR)."""
        return {
            "portfolio_concentration_pct": self.concentration_pct,
            "portfolio_drift_pct": self.max_drift_pct,
            "portfolio_drawdown_pct": self.max_drawdown_pct,
            "portfolio_twr_pct": self.twr_pct,
        }


async def build_performance_report(
    session: AsyncSession,
    *,
    days: int = PORTFOLIO_PERFORMANCE_WINDOW_DAYS,
    snapshot: dict | None = None,
    prices: Mapping[str, float] | None = None,
    include_benchmarks: bool = True,
    user_id: str | None = None,
) -> PortfolioPerformance:
    """کارایی/ریسک پرتفوی از سری ارزش ذخیره‌شده + مقایسه با طلا/دلار/شاخص.

    ``include_benchmarks=False`` برای مسیر هشدارها (ارزان‌تر): بدون پرس‌وجوی
    سری بنچمارک‌ها فقط معیارهای ریسک محاسبه می‌شود.
    """
    window = max(1, int(days))
    end = now_tehran().date()
    start = end - timedelta(days=window)
    unavailable: dict[str, str] = {}

    rows = await load_value_history(session, days=window, user_id=user_id)
    _, valuations, flows = value_series(rows)
    points = len(valuations)

    live = dict(prices) if prices is not None else get_current_prices(snapshot)
    summary = await get_holdings_grouped(session, live, user_id=user_id)

    latest_value = valuations[-1] if valuations else summary.total_value
    latest_cost = float(rows[-1].total_cost_irt) if rows else summary.total_cost
    unpriced = int(rows[-1].unpriced_holdings or 0) if rows else getattr(summary, "unpriced_holdings", 0)

    if points >= 2:
        twr = perf.time_weighted_return_pct(valuations, flows)
        simple = perf.total_return_pct(valuations)
        returns = perf.simple_returns(valuations)
        volatility = perf.annualized_volatility_pct(returns)
        sharpe = perf.sharpe_ratio(returns)
        sortino = perf.sortino_ratio(returns)
        drawdown = perf.max_drawdown_pct(valuations)
        var95 = perf.value_at_risk_pct(returns, 0.95)
        cvar95 = perf.conditional_value_at_risk_pct(returns, 0.95)
    else:
        twr = simple = volatility = sharpe = sortino = drawdown = var95 = cvar95 = None
        unavailable["twr_pct"] = (
            f"تنها {points} نقطه در تاریخچهٔ ارزش ذخیره شده — TWR به حداقل ۲ روز نیاز دارد"
        )

    if points < 20:
        for key in ("annualized_volatility_pct", "sharpe_ratio", "sortino_ratio", "var_95_pct", "cvar_95_pct"):
            unavailable.setdefault(key, "نمونهٔ کمتر از ۲۰ روز — معیار معنادار نیست")

    # تمرکز + انحراف ری‌بالانس از holdingهای قیمت‌دار فعلی
    weights = [h.current_value for h in summary.holdings if h.current_value]
    concentration = perf.concentration_pct(weights) if weights else None
    if concentration is None:
        unavailable["concentration_pct"] = "هیچ دارایی قیمت‌داری در پرتفوی نیست"

    class_weights = class_weights_from_holdings(summary.holdings)
    max_drift, drift_by_class = allocation_drift_pct(class_weights)
    if max_drift is None:
        unavailable["max_drift_pct"] = "وزن کلاس‌ها محاسبه نشد (holding قیمت‌دار نیست)"

    # بنچمارک‌ها روی همان پنجره
    benchmarks: dict[str, dict] = {}
    for key, cfg in (PORTFOLIO_BENCHMARKS.items() if include_benchmarks else ()):
        series = await load_benchmark_series(session, key, start=start, end=end)
        bench_return = benchmark_return_pct(series, start=start, end=end)
        entry: dict = {
            "label": cfg.get("label", key),
            "points": len(series),
            "return_pct": bench_return,
            "relative_pct": None,
        }
        if bench_return is None:
            entry["unavailable"] = "سری بنچمارک در این پنجره کمتر از ۲ نقطه دارد"
        else:
            base = twr if twr is not None else simple
            entry["relative_pct"] = perf.relative_to_benchmark_pct(base, bench_return)
            if entry["relative_pct"] is None:
                entry["unavailable"] = "بازده پرتفوی در دسترس نیست"
        benchmarks[key] = entry

    return PortfolioPerformance(
        window_days=window,
        start=start,
        end=end,
        points=points,
        total_value_irt=latest_value,
        total_cost_irt=latest_cost,
        unpriced_holdings=unpriced,
        twr_pct=twr,
        simple_return_pct=simple,
        annualized_volatility_pct=volatility,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        max_drawdown_pct=drawdown,
        var_95_pct=var95,
        cvar_95_pct=cvar95,
        concentration_pct=concentration,
        max_drift_pct=max_drift,
        drift_by_class=drift_by_class,
        benchmarks=benchmarks,
        unavailable=unavailable,
    )


__all__ = [
    "PortfolioPerformance",
    "allocation_drift_pct",
    "benchmark_return_pct",
    "build_performance_report",
    "capture_portfolio_value",
    "class_weights_from_holdings",
    "classify_vehicle",
    "daily_net_flow_irt",
    "load_benchmark_series",
    "load_value_history",
    "value_series",
]
