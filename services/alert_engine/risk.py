"""Shared-capital portfolio risk and position sizing (pure — no I/O).

One capital pool (tomans) is shared by every monitored instrument. Positions exist only
through confirmed ledger entries; a recommendation is never treated as executed, and an
unconfirmed exit never frees cash. Market prices arrive in rials and are converted in
exactly one place (``settings.rial_to_toman``).
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

from services.alert_engine.settings import RiskSettings, rial_to_toman

ENTRY_TYPES = ("buy", "sell", "deposit", "withdrawal")
CONSTRAINT_LABELS = {
    "risk_budget": "بودجهٔ ریسک هر معامله", "regime_ceiling": "سقف تخصیص رژیم بازار", "concentration": "سقف تمرکز تک‌ابزار",
    "available_cash": "نقدینگی در دسترس", "stress_gap": "سناریوی تنش (شکاف قیمتی)",
    "liquidity_participation": "سهم از حجم معاملات", "visible_depth": "عمق قابل مشاهدهٔ عرضه",
}
BOOKS = ("actual", "paper")


class LedgerError(ValueError):
    """A ledger entry is invalid or inconsistent with the recorded holdings."""


def validate_entry(entry: dict[str, Any], holdings: dict[str, float] | None = None) -> None:
    kind = entry.get("entry_type")
    if kind not in ENTRY_TYPES:
        raise LedgerError(f"entry_type must be one of {ENTRY_TYPES}")
    if entry.get("book") not in BOOKS:
        raise LedgerError(f"book must be one of {BOOKS}")
    if kind in ("buy", "sell"):
        qty, price = entry.get("quantity"), entry.get("price_rial")
        if not entry.get("symbol"):
            raise LedgerError("symbol is required for buy/sell")
        if not isinstance(qty, (int, float)) or qty <= 0 or int(qty) != qty:
            raise LedgerError("quantity must be a positive whole number of units")
        if not isinstance(price, (int, float)) or price <= 0:
            raise LedgerError("price_rial (actual execution price, rials) must be positive")
        if (entry.get("fees_toman") or 0) < 0:
            raise LedgerError("fees_toman cannot be negative")
        if kind == "sell" and holdings is not None and qty > holdings.get(entry["symbol"], 0):
            raise LedgerError("cannot record a sale larger than the confirmed holding")
    else:
        amount = entry.get("amount_toman")
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise LedgerError("amount_toman must be positive for deposit/withdrawal")


def build_book(entries: list[dict[str, Any]], capital_toman: float, book: str = "actual",
               before: date | None = None) -> dict[str, Any]:
    """Replay the ledger (oldest first) into cash + average-cost positions.

    ``before`` limits the replay to entries executed strictly before that date — used for
    the start-of-day reference.
    """
    cash = capital_toman
    flows = 0.0
    realized = 0.0
    fees = 0.0
    positions: dict[str, dict[str, float]] = {}
    for e in sorted((x for x in entries if x.get("book") == book), key=lambda x: x["executed_at"]):
        when: datetime = e["executed_at"]
        if before is not None and when.date() >= before:
            continue
        kind = e["entry_type"]
        if kind == "deposit":
            cash += e["amount_toman"]
            flows += e["amount_toman"]
        elif kind == "withdrawal":
            cash -= e["amount_toman"]
            flows -= e["amount_toman"]
        else:
            qty = float(e["quantity"])
            gross = rial_to_toman(qty * float(e["price_rial"])) or 0.0
            fee = float(e.get("fees_toman") or 0.0)
            fees += fee
            pos = positions.setdefault(e["symbol"], {"quantity": 0.0, "cost_toman": 0.0})
            if kind == "buy":
                cash -= gross + fee
                pos["quantity"] += qty
                pos["cost_toman"] += gross + fee
            else:
                if qty > pos["quantity"] + 1e-9:
                    raise LedgerError(f"ledger sells more {e['symbol']} than was bought")
                avg = pos["cost_toman"] / pos["quantity"]
                cash += gross - fee
                realized += gross - fee - avg * qty
                pos["quantity"] -= qty
                pos["cost_toman"] -= avg * qty
    positions = {s: p for s, p in positions.items() if p["quantity"] > 1e-9}
    return {"cash_toman": cash, "net_flows_toman": flows, "realized_pnl_toman": realized,
            "fees_toman": fees, "positions": positions}


def portfolio_state(settings: RiskSettings, entries: list[dict[str, Any]],
                    marks: dict[str, dict[str, Any]], *, today: date,
                    hwm_toman: float | None = None, hwm_flows_toman: float = 0.0,
                    book: str = "actual") -> dict[str, Any]:
    """Equity, exposure, daily P&L and drawdown for one book.

    ``marks[symbol]`` = ``{"price_rial", "price_yesterday_rial", "quality"}``. A position
    without a valid mark is carried at cost and the equity is flagged incomplete — it is
    not valued at zero and not dropped.
    """
    now_book = build_book(entries, settings.capital_toman, book)
    sod_book = build_book(entries, settings.capital_toman, book, before=today)

    rows: list[dict[str, Any]] = []
    unmarked: list[str] = []
    exposure = 0.0
    for symbol, pos in sorted(now_book["positions"].items()):
        mark = marks.get(symbol) or {}
        price = mark.get("price_rial")
        avg_cost_toman = pos["cost_toman"] / pos["quantity"]
        if price and price > 0 and mark.get("quality") in ("valid", "last_session"):
            value = rial_to_toman(pos["quantity"] * price) or 0.0
            marked = True
        else:
            value = pos["cost_toman"]
            marked = False
            unmarked.append(symbol)
        exposure += value
        rows.append({
            "symbol": symbol, "quantity": pos["quantity"], "avg_cost_toman": avg_cost_toman,
            "mark_price_rial": price if marked else None, "value_toman": value,
            "unrealized_pnl_toman": value - pos["cost_toman"] if marked else None,
            "marked": marked, "mark_quality": mark.get("quality", "missing"),
        })
    equity = now_book["cash_toman"] + exposure
    for row in rows:
        row["weight_pct"] = row["value_toman"] / equity * 100 if equity > 0 else None

    # start-of-day reference: yesterday's holdings at yesterday's close; carried risk is kept
    sod_value = 0.0
    sod_complete = True
    for symbol, pos in sod_book["positions"].items():
        prev = (marks.get(symbol) or {}).get("price_yesterday_rial")
        if prev and prev > 0:
            sod_value += rial_to_toman(pos["quantity"] * prev) or 0.0
        else:
            sod_value += pos["cost_toman"]
            sod_complete = False
    sod_equity = sod_book["cash_toman"] + sod_value
    flows_today = now_book["net_flows_toman"] - sod_book["net_flows_toman"]
    daily_pnl = equity - sod_equity - flows_today

    budgets = settings.budgets_toman(equity)
    daily_stop = sod_equity * settings.daily_loss_stop_pct / 100
    # high-water mark moves with external cash flows so deposits are not "performance"
    flows_cum = now_book["net_flows_toman"]
    base_hwm = settings.capital_toman if hwm_toman is None else hwm_toman + (flows_cum - hwm_flows_toman)
    new_hwm = max(base_hwm, equity)
    drawdown_pct = (new_hwm - equity) / new_hwm * 100 if new_hwm > 0 else 0.0

    return {
        "book": book, "currency": "IRT",
        "allocated_capital_toman": settings.capital_toman,
        "net_external_flows_toman": flows_cum,
        "cash_toman": now_book["cash_toman"],
        "exposure_toman": exposure,
        "exposure_pct": exposure / equity * 100 if equity > 0 else None,
        "equity_toman": equity,
        "equity_complete": not unmarked,
        "unmarked_symbols": unmarked,
        "realized_pnl_toman": now_book["realized_pnl_toman"],
        "fees_paid_toman": now_book["fees_toman"],
        "positions": rows,
        "daily": {
            "start_of_day_equity_toman": sod_equity, "reference_complete": sod_complete,
            "external_flows_today_toman": flows_today, "pnl_toman": daily_pnl,
            "pnl_pct": daily_pnl / sod_equity * 100 if sod_equity > 0 else None,
            "loss_stop_toman": daily_stop, "loss_breached": daily_pnl <= -daily_stop,
            "convention": "equity now − (yesterday's holdings at yesterday's close + cash) − today's deposits/withdrawals; realized + unrealized",
        },
        "drawdown": {
            "high_water_mark_toman": new_hwm, "high_water_mark_flows_toman": flows_cum,
            "pct": drawdown_pct, "review_threshold_pct": settings.drawdown_review_pct,
            "review_required": drawdown_pct >= settings.drawdown_review_pct,
            "convention": "from the cash-flow-adjusted equity high-water mark",
        },
        "budgets_toman": budgets,
        "risk_budget_usage": {
            "daily_loss_used_pct": max(0.0, -daily_pnl) / daily_stop * 100 if daily_stop > 0 else None,
        },
    }


def new_entries_blocked(settings: RiskSettings, state: dict[str, Any], kill_switch_on: bool = False) -> list[str]:
    """Reasons no risk-increasing recommendation may be issued right now."""
    reasons = []
    if kill_switch_on:
        reasons.append("کلید توقف سراسری سامانه فعال است")
    if settings.halt_new_entries:
        reasons.append("توصیهٔ ورود جدید در تنظیمات متوقف شده است")
    if state["daily"]["loss_breached"]:
        reasons.append("حد زیان روزانه نقض شده است — امروز ریسک جدیدی توصیه نمی‌شود (پایش موقعیت‌های موجود ادامه دارد)")
    if state["drawdown"]["review_required"]:
        reasons.append("افت سرمایه به آستانهٔ بازبینی رسیده است — پیش از ورود جدید، بازبینی راهبرد لازم است")
    return reasons


def size_position(settings: RiskSettings, *, state: dict[str, Any], regime: str, symbol: str,
                  entry_price_rial: float | None, daily_vol_pct: float | None,
                  spread_pct: float | None, price_yesterday_rial: float | None,
                  low_limit_rial: float | None, ask_depth_volume: float | None,
                  avg_daily_volume: float | None, buy_fee: float, sell_fee: float,
                  lot_size: int = 1) -> dict[str, Any]:
    """Largest position that respects *every* measured constraint; the tightest one binds.

    Returns ``units == 0`` with a reason when no tradable size fits — "no trade" is a result.
    """
    out: dict[str, Any] = {"units": 0, "constraints": {}, "not_measured": [], "binding": None,
                           "assumptions": {"buy_fee": buy_fee, "sell_fee": sell_fee,
                                           "fee_note": "all-in rate table in domain.trading.iran_costs; re-verify against the broker schedule"}}
    if not entry_price_rial or entry_price_rial <= 0:
        out["reason"] = "قیمت قابل اجرا برای ورود در دسترس نیست"
        return out
    if daily_vol_pct is None:
        out["reason"] = "نوسان روزانه در دسترس نیست (تاریخچهٔ قیمت پاکِ کافی وجود ندارد) — حد ضرر تحلیلی قابل تعیین نیست"
        return out

    entry_toman = rial_to_toman(entry_price_rial) or 0.0
    equity = state["equity_toman"]
    slippage_pct = max(settings.min_slippage_bps / 100, (spread_pct or 0.0) / 2)
    stop_pct = max(settings.min_stop_distance_pct, settings.stop_vol_multiple * daily_vol_pct)
    cost_pct = (buy_fee + sell_fee) * 100 + 2 * slippage_pct
    loss_per_unit = entry_toman * (stop_pct + cost_pct) / 100

    budget = settings.budgets_toman(equity)["per_trade_risk"]
    daily_room = state["daily"]["loss_stop_toman"] + min(0.0, state["daily"]["pnl_toman"])
    budget = min(budget, max(0.0, daily_room))

    c = out["constraints"]
    c["risk_budget"] = math.floor(budget / loss_per_unit) if loss_per_unit > 0 else 0
    ceiling_room = equity * settings.ceiling_for(regime) / 100 - state["exposure_toman"]
    c["regime_ceiling"] = math.floor(max(0.0, ceiling_room) / entry_toman)
    held = next((p["value_toman"] for p in state["positions"] if p["symbol"] == symbol), 0.0)
    single_room = equity * settings.max_single_instrument_pct / 100 - held
    c["concentration"] = math.floor(max(0.0, single_room) / entry_toman)
    c["available_cash"] = math.floor(max(0.0, state["cash_toman"]) / (entry_toman * (1 + buy_fee)))

    if low_limit_rial and price_yesterday_rial and price_yesterday_rial > low_limit_rial > 0:
        band_pct = (price_yesterday_rial - low_limit_rial) / price_yesterday_rial * 100
        stress_per_unit = entry_toman * (stop_pct + band_pct + cost_pct) / 100
        c["stress_gap"] = math.floor(settings.stress_loss_multiple * budget / stress_per_unit)
        out["stress"] = {"scenario": "exit fills only after one further limit-down session beyond the stop",
                         "limit_band_pct": band_pct, "loss_per_unit_toman": stress_per_unit,
                         "note": "model estimate, not a prediction; multi-session queues can exceed it"}
    else:
        out["not_measured"].append("stress_gap (daily limits unavailable)")
    if avg_daily_volume and avg_daily_volume > 0:
        c["liquidity_participation"] = math.floor(avg_daily_volume * settings.max_participation_pct / 100)
    else:
        out["not_measured"].append("liquidity_participation (average volume unavailable)")
    if ask_depth_volume is not None:
        c["visible_depth"] = math.floor(ask_depth_volume * settings.max_depth_multiple)
    else:
        out["not_measured"].append("visible_depth (order book unavailable)")

    binding = min(c, key=lambda k: c[k])
    units = max(0, c[binding]) // lot_size * lot_size
    out.update({
        "units": int(units), "binding": binding,
        "entry_price_rial": entry_price_rial, "entry_value_toman": units * entry_toman,
        "stop_distance_pct": stop_pct, "analytical_stop_rial": entry_price_rial * (1 - stop_pct / 100),
        "slippage_pct_each_way": slippage_pct, "round_trip_cost_pct": cost_pct,
        "planned_loss_toman": units * loss_per_unit, "risk_budget_toman": budget,
        "allocation_ceiling_pct": settings.ceiling_for(regime),
        "position_pct_of_equity": units * entry_toman / equity * 100 if equity > 0 else None,
    })
    if units < lot_size:
        out["units"] = 0
        out["reason"] = f"اندازهٔ قابل معامله‌ای نمی‌گنجد: محدودیت «{CONSTRAINT_LABELS.get(binding, binding)}» کمتر از یک واحد اجازه می‌دهد"
    return out
