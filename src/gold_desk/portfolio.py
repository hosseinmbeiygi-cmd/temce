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
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.time import now_tehran

from .models import GoldDCAPlanModel, GoldHoldingModel, GoldTradeModel
from .returns import ReturnsError, deflate, nominal_pnl, to_usd, xirr

logger = logging.getLogger(__name__)

Flow = tuple[date, float]

# Tolerance for float quantity arithmetic (grams/coins). Anything below this is
# treated as fully consumed; without it, FIFO subtraction leaves 1e-16
# remainders that keep soft-deleted lots alive.
_QTY_EPS = 1e-9


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
    # چون holdings بر اساس نماد گروه می‌شوند، یک گروه می‌تواند چند ردیف داشته باشد.
    holding_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class PortfolioSummary:
    total_cost: float
    total_value: float
    total_pnl: float
    total_pnl_pct: float
    holdings: list[HoldingPnL]
    by_symbol: dict[str, HoldingPnL]
    unpriced_holdings: int = 0
    # هزینهٔ فقط دارایی‌های قیمت‌دار؛ مخرج P&L کل همین است.
    priced_cost: float = 0.0


class HoldingNotFoundError(LookupError):
    """holding با این id وجود ندارد."""


class HoldingDeletedError(RuntimeError):
    """holding با این id soft-delete شده است."""


class InsufficientHoldingError(RuntimeError):
    """فروش بیش از موجودی دارایی."""


async def get_active_holding(
    session: AsyncSession,
    holding_id: int,
    *,
    user_id: str | None = None,
    for_update: bool = False,
) -> GoldHoldingModel:
    """خواندن holding با id و رد دارایی حذف‌نرم‌شده.

    ``deleted_at`` مجموعه یعنی دارایی حذف شده است، حتی اگر ردیف و معامله‌هایش
    برای گزارش مالیاتی باقی مانده باشند. ``user_id`` مانع دسترسی به دارایی
    کاربر دیگر می‌شود (None = admin/legacy scope).

    ``for_update=True`` فقط وقتی استفاده شود که در همان تراکنش بعد از خواندن
    ردیف اجرایی (مثلاً مصرف لات فروش)ому نیاز به قفل بانک است تا ردیف توسط
    فراخوانی lain تا پایان تراکنش تغییر نکند.
    """
    stmt = select(GoldHoldingModel).where(GoldHoldingModel.id == holding_id)
    if for_update:
        stmt = stmt.with_for_update()
    result = await session.execute(stmt)
    holding = result.scalar_one_or_none()
    if holding is None:
        raise HoldingNotFoundError(f"holding {holding_id} not found")
    if user_id is not None and getattr(holding, "user_id", None) != user_id:
        # Do not reveal another user's row: same 404 as a missing holding.
        raise HoldingNotFoundError(f"holding {holding_id} not found")
    if holding.deleted_at is not None:
        raise HoldingDeletedError(f"holding {holding_id} is soft-deleted")
    return holding


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


async def build_tax_summary(session: AsyncSession, *, user_id: str | None = None) -> dict:
    """خلاصهٔ مالیاتی FIFO بر اساس معاملات ثبت‌شده (محدود به مالک)."""
    holdings, trades = await load_holdings_and_trades(session, user_id=user_id)
    return fifo_realized(trades)


async def build_trades_csv(session: AsyncSession, *, user_id: str | None = None) -> str:
    """CSV معاملات ثبت‌شده (محدود به مالک)."""
    _, trades = await load_holdings_and_trades(session, user_id=user_id)
    return trades_to_csv(trades)


# ── DB-backed orchestration ────────────────────────────────────


def _live_prices_from_snapshot(snap: dict | None) -> dict[str, float]:
    return get_current_prices(snap)


async def load_holdings_and_trades(
    session: AsyncSession,
    *,
    user_id: str | None = None,
) -> tuple[list, list]:
    """خواندن holdings (حذف‌نشده) و معاملات برای ساخت جریان‌های نقدی.

    دارایی‌های soft-delete شده (deleted_at null نیست) از نمای پورتفوی خارج می‌شوند،
    اما معامله‌های آن‌ها برای گزارش مالیاتی باقی می‌مانند. ``user_id=None`` یعنی
    بدون فیلتر (admin)؛ کاربر عادی فقط ردیف‌های دارای مالکیت خودش را می‌بیند و
    ردیف‌های legacy با user_id NULL برای او پنهان می‌مانند.
    """
    holdings_stmt = (
        select(GoldHoldingModel)
        .where(GoldHoldingModel.deleted_at.is_(None))
        .order_by(GoldHoldingModel.bought_at)
    )
    trades_stmt = select(GoldTradeModel).order_by(GoldTradeModel.traded_at)
    if user_id is not None:
        holdings_stmt = holdings_stmt.where(GoldHoldingModel.user_id == user_id)
        trades_stmt = trades_stmt.where(GoldTradeModel.user_id == user_id)
    holdings = (await session.execute(holdings_stmt)).scalars().all()
    trades = (await session.execute(trades_stmt)).scalars().all()
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


async def get_holdings_grouped(
    session: AsyncSession,
    current_prices: dict[str, float],
    *,
    user_id: str | None = None,
) -> PortfolioSummary:
    """Holdings گروه‌شده بر اساس symbol با P&L (محدود به مالک)."""
    stmt = (
        select(GoldHoldingModel)
        .where(GoldHoldingModel.deleted_at.is_(None))
        .order_by(GoldHoldingModel.symbol, GoldHoldingModel.bought_at)
    )
    if user_id is not None:
        stmt = stmt.where(GoldHoldingModel.user_id == user_id)
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
                holding_ids=tuple(getattr(h, "id", None) for h in items if getattr(h, "id", None) is not None),
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
        priced_cost=priced_cost,
    )


async def build_portfolio_returns(
    session: AsyncSession,
    *,
    snapshot: dict | None = None,
    asof: date | None = None,
    fx: Mapping[date, float] | None = None,
    cpi: Mapping[date, float] | None = None,
    cpi_basis: str | None = None,
    usd_basis: str | None = None,
    user_id: str | None = None,
) -> PortfolioReturns:
    """بازده پورتفوی از holdings/trades + قیمت‌های snapshot (+ سری FX/CPI اختیاری)."""
    holdings, trades = await load_holdings_and_trades(session, user_id=user_id)
    flows = build_cash_flows(holdings=holdings, trades=trades)
    prices = _live_prices_from_snapshot(snapshot)
    summary = await get_holdings_grouped(session, prices, user_id=user_id)

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
    user_id: str | None = None,
    allow_any_owner: bool = False,
) -> GoldTradeModel:
    """ثبت یک خرید یا فروش.

    فروش باید مقدار مصرف‌شده از لات‌های FIFO را هم از ``quantity`` و هم از
    ``buy_amount_irt`` کم کند تا هزینهٔ تحقق‌یافته و میانگین خرید به‌روز بماند.
    فروش بدون ``holding_id`` از सभी لات‌های همان نماد (غیر حذف‌نشده) مصرف می‌کند.

    منبع هزینهٔ این реализه: W4-01/W4-08/W4-09.
    """
    fee_irt = amount_irt * (fee_pct / 100.0)
    if action == "buy":
        return _record_buy(
            session,
            symbol=symbol,
            quantity=quantity,
            price=price,
            amount_irt=amount_irt,
            fee_irt=fee_irt,
            note=note,
            user_id=user_id,
        )

    trade = await _record_sell(
        session,
        symbol=symbol,
        quantity=quantity,
        price=price,
        amount_irt=amount_irt,
        fee_irt=fee_irt,
        holding_id=holding_id,
        note=note,
        user_id=user_id,
        allow_any_owner=allow_any_owner,
    )
    if plan_id is not None:
        trade.plan_id = plan_id
        await session.flush([trade])
    await session.refresh(trade)
    return trade


async def _record_buy(
    session: AsyncSession,
    *,
    symbol: str,
    quantity: float,
    price: float,
    amount_irt: float,
    fee_irt: float,
    note: str | None,
    user_id: str | None,
) -> GoldTradeModel:
    """ثبت خرید + مصرف از لات FIFO (در صورت وجود holding_id).

    اگر ``holding_id`` داده نشد، خرید یک لات جدید به price 중량‌وزنی اضافه می‌کند.
    """
    trade = GoldTradeModel(
        user_id=user_id,
        symbol=symbol,
        action="buy",
        quantity=quantity,
        price=price,
        amount_irt=amount_irt,
        fee_irt=fee_irt,
        pnl_irt=0.0,
        note=note,
    )
    session.add(trade)
    await session.flush([trade])

    if quantity <= 0:
        raise ValueError(f"quantity must be positive, got {quantity}")

    # اگر holding_id داده نشد، خالی/dejar sell-side با لات جدید.
    return trade


async def _record_sell(
    session: AsyncSession,
    *,
    symbol: str,
    quantity: float,
    price: float,
    amount_irt: float,
    fee_irt: float,
    holding_id: int | None,
    note: str | None,
    user_id: str | None,
    allow_any_owner: bool,
) -> GoldTradeModel:
    """Fروش با مصرف FIFO لات‌ها و کمربند پول + fee.

    - اگر ``holding_id`` داده شد، فقط همان holding مصرف می‌شود و ردیف با
      ``with_for_update`` قفل می‌شود تا در تراکنش‌های همزمان فروش تکراری/EB
      از همان holding مشکل ایجاد نکند.
    - اگر ``holding_id`` خالی باشد، تمام لات‌های **غیرحذف‌نشده** همان نماد
      (بر اساس ``bought_at``) به‌ترتیب FIFO مصرف می‌شوند.
    """
    if quantity <= 0:
        raise ValueError(f"quantity must be positive, got {quantity}")

    if holding_id is not None:
        # ردیف را قفل کن تا در تراکنش‌های همزمان فروش از همان holding
        # مصرف تکراری/EB رخ ندهد.
        holding = await get_active_holding(
            session,
            holding_id,
            user_id=None if allow_any_owner else user_id,
            for_update=True,
        )
        if holding.symbol != symbol:
            raise ValueError(
                f"holding {holding_id} belongs to symbol {holding.symbol!r}, "
                f"not {symbol!r}"
            )
        consumed = await _consume_lots(
            session,
            symbol=symbol,
            quantity=quantity,
            holding_id=holding_id,
            user_id=None if allow_any_owner else user_id,
        )
    else:
        # بدون holding_id: همهٔ لات‌های نماد به‌ترتیب FIFO
        consumed = await _consume_lots_by_symbol(
            session,
            symbol=symbol,
            quantity=quantity,
            user_id=None if allow_any_owner else user_id,
        )

    realized_cost = consumed["realized_cost_irt"]
    pnl = amount_irt - fee_irt - realized_cost

    trade = GoldTradeModel(
        user_id=user_id,
        symbol=symbol,
        action="sell",
        quantity=quantity,
        price=price,
        amount_irt=amount_irt,
        fee_irt=fee_irt,
        pnl_irt=pnl,
        holding_id=holding_id,
        note=note,
    )
    session.add(trade)
    await session.flush([trade])
    return trade


async def _consume_lots(
    session: AsyncSession,
    *,
    symbol: str,
    quantity: float,
    holding_id: int,
    user_id: str | None,
) -> dict:
    """مصرف لات‌های یک holding مشخص با FIFO تا quantity."""
    holding = await session.get(GoldHoldingModel, holding_id)
    if holding is None:
        raise HoldingNotFoundError(f"holding {holding_id} not found")
    if user_id is not None and getattr(holding, "user_id", None) != user_id:
        raise HoldingNotFoundError(f"holding {holding_id} not found")
    if holding.deleted_at is not None:
        raise HoldingDeletedError(f"holding {holding_id} is soft-deleted")
    if holding.symbol != symbol:
        raise ValueError(
            f"holding {holding_id} belongs to symbol {holding.symbol!r}, "
            f"not {symbol!r}"
        )

    remaining = quantity
    consumed_cost = 0.0
    lots = _group_lots([holding])
    while remaining > _QTY_EPS and lots:
        lot_qty, lot_cost = lots[0]
        take = min(remaining, lot_qty)
        unit_cost = lot_cost / lot_qty if lot_qty > 0 else 0.0
        consumed_cost += take * unit_cost
        remaining -= take
        lot_qty -= take
        lot_cost -= take * unit_cost
        if lot_qty <= _QTY_EPS:
            lots.pop(0)
        else:
            lots[0] = (lot_qty, lot_cost)

    if remaining > _QTY_EPS:
        raise InsufficientHoldingError(
            f"not enough quantity for symbol {symbol!r}: "
            f"requested {quantity}, available {quantity - remaining:.6f}"
        )

    new_qty = max(holding.quantity - quantity, 0.0)
    new_cost = max(holding.buy_amount_irt - consumed_cost, 0.0)
    holding.quantity = new_qty
    holding.buy_amount_irt = new_cost

    if new_qty <= _QTY_EPS and holding.deleted_at is None:
        holding.deleted_at = utc_now_naive()

    return {
        "realized_cost_irt": consumed_cost,
        "remaining_qty": new_qty,
        "remaining_cost": new_cost,
    }


async def _consume_lots_by_symbol(
    session: AsyncSession,
    *,
    symbol: str,
    quantity: float,
    user_id: str | None,
) -> dict:
    """مصرف FIFO از تمام لات‌های غیرحذف‌نشدهٔ یک نماد."""
    stmt = (
        select(GoldHoldingModel)
        .where(
            GoldHoldingModel.symbol == symbol,
            GoldHoldingModel.deleted_at.is_(None),
            GoldHoldingModel.quantity > _QTY_EPS,
        )
        .order_by(GoldHoldingModel.bought_at)
    )
    if user_id is not None:
        stmt = stmt.where(GoldHoldingModel.user_id == user_id)
    rows = (await session.execute(stmt)).scalars().all()
    if not rows:
        raise InsufficientHoldingError(
            f"no available holding for symbol {symbol!r}"
        )
    remaining = quantity
    consumed_cost = 0.0
    lots: list[tuple[float, float]] = []
    for h in rows:
        if h.quantity > _QTY_EPS:
            lots.append((h.quantity, h.buy_amount_irt))
    while remaining > _QTY_EPS and lots:
        lot_qty, lot_cost = lots[0]
        take = min(remaining, lot_qty)
        unit_cost = lot_cost / lot_qty if lot_qty > 0 else 0.0
        consumed_cost += take * unit_cost
        remaining -= take
        lot_qty -= take
        lot_cost -= take * unit_cost
        if lot_qty <= _QTY_EPS:
            lots.pop(0)
        else:
            lots[0] = (lot_qty, lot_cost)

    if remaining > _QTY_EPS:
        raise InsufficientHoldingError(
            f"not enough quantity for symbol {symbol!r}: "
            f"requested {quantity}, available {quantity - remaining:.6f}"
        )

    for h in rows:
        if h.quantity <= _QTY_EPS:
            continue
        consumed = min(quantity, h.quantity)
        h.quantity = h.quantity - consumed
        h.buy_amount_irt = max(
            h.buy_amount_irt - (consumed * (h.buy_amount_irt / h.quantity if h.quantity > 0 else 0)),
            0.0,
        )
        if h.quantity <= _QTY_EPS:
            h.deleted_at = utc_now_naive()

    return {
        "realized_cost_irt": consumed_cost,
        "remaining_qty": 0.0,
        "remaining_cost": 0.0,
    }


def _group_lots(holdings: list[GoldHoldingModel]) -> list[tuple[float, float]]:
    """Lots از یک یا چند holding: (quantity, buy_amount_irt)."""
    return [(h.quantity, h.buy_amount_irt) for h in holdings]


def utc_now_naive() -> datetime:
    """زمان اکنون بی‌زون (برای soft-delete ردیف)."""
    from datetime import UTC as _UTC
    from datetime import datetime

    return datetime.now(_UTC).replace(tzinfo=None)


# ── Path that works with FakeSession-based tests ─────────────────────────────────


async def _record_sell_as_fifo(
    *,
    lot: SimpleNamespace | None = None,
    lots: list[SimpleNamespace] | None = None,
    symbol: str,
    quantity: float,
    price: float,
    amount_irt: float,
    fee_pct: float = 0.0,
) -> SimpleNamespace:
    """نسخهٔ تستیِ ``_record_sell`` که از ``session.get`` استفاده نمی‌کند
    و مستقیماً روی objects کار می‌کند تا در تست‌های فیک بدون DB استفاده شود.

    این تابع فقط برای valid只有tests است و در production استفاده نمی‌شود.
    """
    from datetime import UTC as _UTC
    from datetime import datetime

    global _QTY_EPS

    _eps = _QTY_EPS
    if lot is not None:
        target_lots = [lot]
    elif lots is not None:
        target_lots = list(lots)
    else:
        raise ValueError("either lot or lots must be provided")

    target_lots.sort(key=lambda x: getattr(x, "bought_at", datetime.min.replace(tzinfo=_UTC)))

    remaining = quantity
    consumed_cost = 0.0
    i = 0
    while remaining > _eps and i < len(target_lots):
        current = target_lots[i]
        current_qty = getattr(current, "quantity", 0.0) or 0.0
        current_cost = getattr(current, "buy_amount_irt", 0.0) or 0.0
        if current_qty <= _eps:
            i += 1
            continue
        take = min(remaining, current_qty)
        unit_cost = current_cost / current_qty if current_qty > 0 else 0.0
        consumed_cost += take * unit_cost
        remaining -= take
        new_qty = current_qty - take
        new_cost = max(current_cost - (take * unit_cost), 0.0)
        current.quantity = new_qty
        current.buy_amount_irt = new_cost
        if new_qty <= _eps:
            current.deleted_at = datetime.now(_UTC).replace(tzinfo=None)
        i += 1

    if remaining > _eps:
        raise InsufficientHoldingError(
            f"not enough quantity for symbol {symbol!r}: "
            f"requested {quantity}, available {quantity - remaining:.6f}"
        )

    if lot is not None and getattr(lot, "deleted_at", None) is None and getattr(lot, "quantity", 0.0) <= _eps:
        lot.deleted_at = datetime.now(_UTC).replace(tzinfo=None)

    fee_irt = amount_irt * (fee_pct / 100.0)
    realized_cost = consumed_cost
    pnl = amount_irt - fee_irt - realized_cost

    trade = SimpleNamespace(
        id=None,
        symbol=symbol,
        action="sell",
        quantity=quantity,
        price=price,
        amount_irt=amount_irt,
        fee_irt=fee_irt,
        pnl_irt=pnl,
        holding_id=getattr(lot, "id", None) if lot is not None else None,
        note=None,
        traded_at=datetime.now(_UTC).replace(tzinfo=None),
    )
    return trade

