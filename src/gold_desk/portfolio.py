"""Portfolio Service — P&L calculator + DCA tracking.

هر holding → قیمت فعلی از snapshot → P&L.
هر DCA plan → current tranche وضعیت + چه زمانی پله بعدی فعال می‌شود.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from operator import attrgetter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.time import now_tehran

from .models import GoldDCAPlanModel, GoldHoldingModel, GoldTradeModel
from .returns import ReturnsError, deflate, nominal_pnl, to_usd, xirr

logger = logging.getLogger(__name__)

Flow = tuple[date, float]


@dataclass(frozen=True)
class HoldingPnL:
    symbol: str
    display_name: str
    quantity: float
    avg_buy_price: float
    # None یعنی قیمت فعلی در دسترس نیست — نه «حباب/P&L صفر». پیش‌تر به‌جای None
    # از ``avg_buy`` استفاده می‌شد و P&L صفر کاذب می‌ساخت (GS-17).
    current_price: float | None
    cost_basis: float
    current_value: float | None
    pnl_irt: float | None
    pnl_pct: float | None
    n_purchases: int


@dataclass(frozen=True)
class PortfolioSummary:
    total_cost: float
    total_value: float
    total_pnl: float
    total_pnl_pct: float
    holdings: list[HoldingPnL]
    by_symbol: dict[str, HoldingPnL]
    unpriced_holdings: int = 0


def _add_prices(target: dict[str, float], assets) -> None:
    """افزودن قیمت‌های مثبت یک بلوک snapshot (dict یا list از asset)."""
    items = assets.values() if isinstance(assets, dict) else (assets or [])
    for a in items:
        if not isinstance(a, dict):
            continue
        price = a.get("market_price")
        if not price or float(price) <= 0:
            # قیمت ناموجود/صفر نباید جای قیمت واقعی را بگیرد.
            continue
        target[a.get("symbol") or ""] = float(price)


def get_current_prices(snap: dict | None) -> dict[str, float]:
    """استخراج قیمت فعلی از snapshot (طلا، سکه و صندوق‌ها).

    صندوق‌های طلا نیز قیمت بازار دارند و holdingهای صندوقی بدون این بلوک
    «بدون قیمت» می‌ماندند و P&L کل را ناقص می‌کردند.
    """
    if not snap:
        return {}
    prices: dict[str, float] = {}
    _add_prices(prices, snap.get("coins", {}))
    _add_prices(prices, snap.get("gold", {}))
    _add_prices(prices, snap.get("funds", []))
    return prices


# ── Cash flows + returns (اسمی / واقعی / دلاری) ────────────────


def _flow_date(value: object) -> date:
    """تاریخ جریان نقدی از یک datetime/date."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise TypeError(f"flow date must be datetime/date, got {value!r}")


def cash_flows_from_trades(trades: Iterable[object]) -> list[Flow]:
    """جریان نقدی امضاشده از معاملات: خرید خروج پول (منفی)، فروش ورود پول (مثبت)."""
    flows: list[Flow] = []
    for t in trades:
        when = getattr(t, "traded_at", None)
        if when is None:
            continue
        action = str(getattr(t, "action", "") or "").lower()
        amount = float(getattr(t, "amount_irt", 0) or 0.0)
        signed = amount if action == "sell" else -amount
        flows.append((_flow_date(when), signed))
    return flows


def build_cash_flows(
    *,
    holdings: Iterable[object] | None = None,
    trades: Iterable[object] | None = None,
) -> list[Flow]:
    """جریان نقدی پورتفوی.

    اگر معامله‌ای ثبت شده باشد، همان‌ها مرجع هستند (شامل فروش/برداشت)؛ در غیر این
    صورت هر holding یک خرید فرض می‌شود.
    """
    trades_list = list(trades or [])
    if trades_list:
        return cash_flows_from_trades(trades_list)
    flows: list[Flow] = []
    for h in holdings or []:
        when = getattr(h, "bought_at", None)
        if when is None:
            continue
        flows.append((_flow_date(when), -float(getattr(h, "buy_amount_irt", 0) or 0.0)))
    return flows


@dataclass(frozen=True)
class PortfolioReturns:
    nominal_pnl_irt: float
    nominal_pnl_pct: float | None
    nominal_xirr: float | None
    real_xirr: float | None
    usd_xirr: float | None
    cpi_basis: str | None
    usd_basis: str | None
    # نام معیار → دلیل در دسترس نبودن (هیچ مقدار جعلی ساخته نمی‌شود)
    unavailable: dict[str, str] = field(default_factory=dict)


def _xirr_or_none(
    flows: Sequence[Flow], unavailable: dict[str, str], key: str
) -> float | None:
    try:
        return xirr(flows)
    except ReturnsError as exc:
        unavailable[key] = str(exc)
        return None


def compute_returns(
    flows: Iterable[Flow],
    *,
    ending_value: float,
    asof: date,
    fx: Mapping[date, float] | None = None,
    cpi: Mapping[date, float] | None = None,
    cpi_basis: str | None = None,
    usd_basis: str | None = None,
) -> PortfolioReturns:
    """بازده اسمی/واقعی/دلاری از جریان‌های نقدی + ارزش پایانی.

    ``ending_value`` به‌عنوان یک ورودی در ``asof`` به جریان‌ها اضافه می‌شود تا XIRR
    تعریف شود. نبود سری FX/CPI به‌جای حدس، معیار را «در دسترس نیست» می‌کند.
    """
    flows_list = [(d, float(cf)) for d, cf in flows]
    contributions = sum(-cf for _, cf in flows_list if cf < 0)
    withdrawals = sum(cf for _, cf in flows_list if cf > 0)
    pnl = nominal_pnl(float(ending_value), contributions, withdrawals)
    pnl_pct = (pnl / contributions * 100.0) if contributions > 0 else None

    unavailable: dict[str, str] = {}
    terminal: list[Flow] = [*flows_list, (asof, float(ending_value))]
    nominal = _xirr_or_none(terminal, unavailable, "nominal_xirr")

    if cpi:
        base = min(d for d, _ in terminal)
        try:
            real_flows = deflate(terminal, cpi, base=base)
        except ReturnsError as exc:
            unavailable["real_xirr"] = str(exc)
            real = None
        else:
            real = _xirr_or_none(real_flows, unavailable, "real_xirr")
    else:
        unavailable["real_xirr"] = "no CPI series provided"
        real = None

    if fx:
        try:
            usd_flows = to_usd(terminal, fx)
        except ReturnsError as exc:
            unavailable["usd_xirr"] = str(exc)
            usd = None
        else:
            usd = _xirr_or_none(usd_flows, unavailable, "usd_xirr")
    else:
        unavailable["usd_xirr"] = "no FX series provided"
        usd = None

    return PortfolioReturns(
        nominal_pnl_irt=pnl,
        nominal_pnl_pct=pnl_pct,
        nominal_xirr=nominal,
        real_xirr=real,
        usd_xirr=usd,
        cpi_basis=cpi_basis,
        usd_basis=usd_basis,
        unavailable=unavailable,
    )


# ── FIFO cost basis + tax reporting ────────────────────────────


def fifo_realized(trades: Iterable[object]) -> dict:
    """بهای تمام‌شده و سود/زیان تحقق‌یافته با روش FIFO از مجموع معاملات.

    هر فروش، لات‌های تمام‌شدهٔ قدیمی‌ترین خریدِ خود نماد را مصرف می‌کند (FIFO
    per-symbol). اگر فروش از نمادی بدون لات باز شود، استثنای صریح raise می‌شود
    به‌جای اینکه بای تحقق‌یافته را صفر بگیرد و از اعداد مالیاتی درست نباشد.
    """
    ordered = sorted(
        (t for t in trades if getattr(t, "traded_at", None) is not None),
        key=attrgetter("traded_at"),
    )
    lots_by_symbol: dict[str, list[list[float]]] = {}
    realized = 0.0
    sold_qty = 0.0
    for t in ordered:
        action = str(getattr(t, "action", "") or "").lower()
        symbol = str(getattr(t, "symbol", "") or "")
        qty = float(getattr(t, "quantity", 0) or 0.0)
        price = float(getattr(t, "price", 0) or 0.0)
        if qty <= 0 or not symbol:
            continue
        if action == "sell":
            lots = lots_by_symbol.setdefault(symbol, [])
            remaining = qty
            while remaining > 1e-9 and lots:
                lot = lots[0]
                take = min(remaining, lot[0])
                realized += (price - lot[1]) * take
                lot[0] -= take
                remaining -= take
                if lot[0] <= 1e-9:
                    lots.pop(0)
            if remaining > 1e-9:
                raise ValueError(
                    "FifoError: فروش به مقدار "
                    f"{qty} از نماد '{symbol}' متولد شد؛ لات‌های باز فراهم نیستند، "
                    f"{remaining} واحد لحاظ به‌دست نمی‌آید (بدون لات برای تحقیق)"
                )
            sold_qty += qty
        else:
            lots_by_symbol.setdefault(symbol, []).append([qty, price])

    open_lots = [lot for sym_lots in lots_by_symbol.values() for lot in sym_lots]
    return {
        "realized_pnl_irt": realized,
        "sold_quantity": sold_qty,
        "open_lots": [{"quantity": q, "price": p} for q, p in open_lots],
        "open_quantity": sum(lot[0] for lot in open_lots),
        "open_cost_basis_irt": sum(lot[0] * lot[1] for lot in open_lots),
    }


_TRADE_EXPORT_COLUMNS = [
    "traded_at",
    "symbol",
    "action",
    "quantity",
    "price",
    "amount_irt",
    "fee_irt",
    "pnl_irt",
    "note",
]


def trades_to_csv(trades: Iterable[object]) -> str:
    """خروجی CSV معاملات (سرستون‌ها + ردیف‌ها) برای گزارش/مالیات."""
    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_TRADE_EXPORT_COLUMNS)
    for t in trades:
        writer.writerow([str(getattr(t, c, "") if getattr(t, c, None) is not None else "") for c in _TRADE_EXPORT_COLUMNS])
    return buf.getvalue()


async def build_tax_summary(session: AsyncSession) -> dict:
    """خلاصهٔ مالیاتی FIFO بر اساس معاملات ثبت‌شده."""
    holdings, trades = await load_holdings_and_trades(session)
    return fifo_realized(trades)


async def build_trades_csv(session: AsyncSession) -> str:
    """CSV معاملات ثبت‌شده."""
    _, trades = await load_holdings_and_trades(session)
    return trades_to_csv(trades)


# ── DB-backed orchestration ────────────────────────────────────


def _live_prices_from_snapshot(snap: dict | None) -> dict[str, float]:
    return get_current_prices(snap)


async def load_holdings_and_trades(session: AsyncSession) -> tuple[list, list]:
    """خواندن holdings (حذف‌نشده) و معاملات برای ساخت جریان‌های نقدی.

    دارایی‌های soft-delete شده (deleted_at null نیست) از نمای پورتفوی خارج می‌شوند،
    اما معامله‌های آن‌ها برای گزارش مالیاتی remain می‌مانند.
    """
    holdings = (
        await session.execute(
            select(GoldHoldingModel)
            .where(GoldHoldingModel.deleted_at.is_(None))
            .order_by(GoldHoldingModel.bought_at)
        )
    ).scalars().all()
    trades = (
        (await session.execute(select(GoldTradeModel).order_by(GoldTradeModel.traded_at)))
        .scalars()
        .all()
    )
    return list(holdings), list(trades)


async def _load_fx_series(session: AsyncSession) -> dict[date, float]:
    """سری نرخ دلار (ریال→دلار) برای تبدیل دلاری بازده.

    تاریخ‌های ``brsapi_gold_currency_pro_daily_history`` شمسی هستند و به میلادی
    تبدیل می‌شوند تا با تاریخ جریان‌های نقدی (میلادی) بخوانند.
    """
    import jdatetime
    from sqlalchemy import text

    try:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT date, price_close
                    FROM brsapi_gold_currency_pro_daily_history
                    WHERE symbol = 'USD' AND price_close > 0
                    ORDER BY date
                    """
                )
            )
        ).fetchall()
    except Exception:  # noqa: BLE001
        return {}
    series: dict[date, float] = {}
    for d, price in rows:
        try:
            y, m, day = (int(x) for x in str(d).split("-")[:3])
            g = jdatetime.date(y, m, day).togregorian()
        except Exception:  # noqa: BLE001
            continue
        series[g] = float(price)
    return series


async def build_portfolio_returns(
    session: AsyncSession,
    *,
    snapshot: dict | None = None,
    asof: date | None = None,
    fx: Mapping[date, float] | None = None,
    cpi: Mapping[date, float] | None = None,
    cpi_basis: str | None = None,
    usd_basis: str | None = None,
) -> PortfolioReturns:
    """بازده پورتفوی از holdings/trades + قیمت‌های snapshot (+ سری FX/CPI اختیاری)."""
    holdings, trades = await load_holdings_and_trades(session)
    flows = build_cash_flows(holdings=holdings, trades=trades)
    prices = _live_prices_from_snapshot(snapshot)
    summary = await get_holdings_grouped(session, prices)

    if fx is None:
        loaded = await _load_fx_series(session)
        if loaded:
            fx = loaded
            usd_basis = usd_basis or "brsapi_gold_currency_pro_daily_history:USD"

    return compute_returns(
        flows,
        ending_value=summary.total_value,
        asof=asof or now_tehran().date(),
        fx=fx,
        cpi=cpi,
        cpi_basis=cpi_basis,
        usd_basis=usd_basis,
    )


async def get_holdings_grouped(
    session: AsyncSession,
    current_prices: dict[str, float],
) -> PortfolioSummary:
    """Holdings گروه‌شده بر اساس symbol با P&L."""
    stmt = (
        select(GoldHoldingModel)
        .where(GoldHoldingModel.deleted_at.is_(None))
        .order_by(GoldHoldingModel.symbol, GoldHoldingModel.bought_at)
    )
    rows = (await session.execute(stmt)).scalars().all()

    by_symbol: dict[str, list] = {}
    for h in rows:
        by_symbol.setdefault(h.symbol, []).append(h)

    holdings: list[HoldingPnL] = []
    total_cost = 0.0
    total_value = 0.0
    priced_cost = 0.0
    unpriced = 0

    for sym, items in by_symbol.items():
        total_qty = sum(h.quantity for h in items)
        total_cost_sym = sum(h.buy_amount_irt for h in items)
        avg_buy = total_cost_sym / total_qty if total_qty else 0
        current = current_prices.get(sym)
        if current is None or current <= 0:
            current_val = None
            pnl_irt = None
            pnl_pct = None
            unpriced += 1
        else:
            current_val = total_qty * current
            pnl_irt = current_val - total_cost_sym
            pnl_pct = (pnl_irt / total_cost_sym * 100) if total_cost_sym else 0
            total_value += current_val
            priced_cost += total_cost_sym
        holdings.append(
            HoldingPnL(
                symbol=sym,
                display_name=items[0].display_name,
                quantity=total_qty,
                avg_buy_price=avg_buy,
                current_price=current if (current and current > 0) else None,
                cost_basis=total_cost_sym,
                current_value=current_val,
                pnl_irt=pnl_irt,
                pnl_pct=pnl_pct,
                n_purchases=len(items),
            )
        )
        total_cost += total_cost_sym

    # P&L فقط روی holdingهای قیمت‌دار محاسبه می‌شود؛ قیمت ناموجود نباید P&L را
    # صفر یا منفی جعلی کند.
    total_pnl = total_value - priced_cost
    total_pnl_pct = (total_pnl / priced_cost * 100) if priced_cost else 0

    holdings.sort(key=lambda h: h.symbol)
    return PortfolioSummary(
        total_cost=total_cost,
        total_value=total_value,
        total_pnl=total_pnl,
        total_pnl_pct=total_pnl_pct,
        holdings=holdings,
        by_symbol={h.symbol: h for h in holdings},
        unpriced_holdings=unpriced,
    )


# ── DCA Plan helpers ──────────────────────────────────────────


@dataclass(frozen=True)
class DCAPlanStatus:
    plan_id: int
    name: str
    total_capital: float
    executed: int
    remaining: int
    next_tranche_pct: float
    next_tranche_amount: float
    next_trigger: str
    current_score: int
    stop_loss_pct: float
    take_profit_pct: float


def get_plan_status(plan: GoldDCAPlanModel, current_score: int) -> DCAPlanStatus:
    """وضعیت فعلی پلن DCA + شرط پله بعدی."""
    try:
        ladder = json.loads(plan.ladder_json)
    except Exception:
        ladder = []

    executed = plan.executed_tranches
    if executed >= len(ladder):
        return DCAPlanStatus(
            plan_id=plan.id,
            name=plan.name,
            total_capital=plan.total_capital_irt,
            executed=executed,
            remaining=0,
            next_tranche_pct=0,
            next_tranche_amount=0,
            next_trigger="پلن کامل اجرا شد",
            current_score=current_score,
            stop_loss_pct=plan.stop_loss_pct,
            take_profit_pct=plan.take_profit_pct,
        )

    next_t = ladder[executed]
    return DCAPlanStatus(
        plan_id=plan.id,
        name=plan.name,
        total_capital=plan.total_capital_irt,
        executed=executed,
        remaining=len(ladder) - executed,
        next_tranche_pct=next_t.get("pct", 0),
        next_tranche_amount=next_t.get("amount_irt", 0),
        next_trigger=next_t.get("trigger", "—"),
        current_score=current_score,
        stop_loss_pct=plan.stop_loss_pct,
        take_profit_pct=plan.take_profit_pct,
    )


# ── P&L snapshot (روزانه) ────────────────────────────────────


async def record_trade(
    session: AsyncSession,
    *,
    symbol: str,
    action: str,
    quantity: float,
    price: float,
    amount_irt: float,
    fee_pct: float = 0.0,
    holding_id: int | None = None,
    plan_id: int | None = None,
    note: str | None = None,
) -> GoldTradeModel:
    fee_irt = amount_irt * (fee_pct / 100.0)
    pnl = 0.0
    if action == "sell" and holding_id:
        h = await session.get(GoldHoldingModel, holding_id)
        if h:
            pnl = (price - h.buy_price) * quantity
    trade = GoldTradeModel(
        symbol=symbol,
        action=action,
        quantity=quantity,
        price=price,
        amount_irt=amount_irt,
        fee_irt=fee_irt,
        pnl_irt=pnl,
        holding_id=holding_id,
        plan_id=plan_id,
        note=note,
    )
    session.add(trade)
    await session.commit()
    await session.refresh(trade)
    return trade
