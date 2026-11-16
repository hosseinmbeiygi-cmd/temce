"""The recommendation contract (pure — no I/O).

Turns verified inputs into one conditional, explainable conclusion per instrument. The
rules are a transparent heuristic (``RULES_VERSION``), unvalidated out of sample, so:

* every output is labelled paper/decision-support and carries a *descriptive* confidence,
  never a numeric probability;
* conflicting evidence is listed on both sides and is not netted by majority vote —
  an entry needs every required condition, and any hard blocker wins;
* "no trade" and "insufficient data" are first-class results;
* no price target is produced (nothing here supports one); downside scenarios are.

Critical-data dependency map (a missing/stale/invalid critical input blocks that decision):

    new entry            → identity, quote, price history, market breadth (regime)
    position management  → identity, quote
    fund premium/discount→ official NAV (non-critical: reported as missing information)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from services.alert_engine import MODE_PAPER, RULES_VERSION, risk
from services.alert_engine.settings import RiskSettings

USABLE = ("valid", "last_session")
CRITICAL = {
    "new_entry": ("quote", "history", "market_breadth"),
    "position": ("quote",),
}
STATE_LABELS = {
    "conditional_entry": "ورود مشروط",
    "await_confirmation": "در انتظار تأیید",
    "hold": "نگهداری",
    "reduce": "کاهش موقعیت",
    "exit": "خروج",
    "exit_infeasible": "خروج فعلاً ممکن نیست",
    "no_trade": "بدون معامله",
    "insufficient_data": "دادهٔ ناکافی — تحلیل معتبر متوقف است",
    "unsupported": "این نوع ابزار پشتیبانی نمی‌شود",
    "restricted": "فقط نمایش توصیفی — توصیهٔ معاملهٔ اختیار خارج از دامنه است",
}
ALLOWED_TRADING_STATES = ("مجاز",)


def _ev(factor: str, text: str, value: Any = None) -> dict[str, Any]:
    return {"factor": factor, "text": text, "value": value}


def _fmt(value: float | None, digits: int = 2) -> str:
    return "—" if value is None else f"{value:,.{digits}f}"


def _coverage_gaps(coverage: dict[str, dict[str, Any]], purpose: str) -> list[str]:
    out = []
    for key in CRITICAL[purpose]:
        item = coverage.get(key) or {"status": "missing"}
        if item["status"] not in USABLE:
            out.append(f"{key}: {item['status']}" + (f" ({item.get('detail')})" if item.get("detail") else ""))
    return out


def _missing_info(coverage: dict[str, dict[str, Any]], identity: dict[str, Any]) -> list[str]:
    out = [f"{k}: {v['status']}" + (f" — {v['detail']}" if v.get("detail") else "")
           for k, v in coverage.items() if v["status"] not in (*USABLE, "not_applicable")]
    out.extend(identity.get("limitations") or [])
    return out


def build(ctx: dict[str, Any]) -> dict[str, Any]:
    """Assemble the contract. ``ctx`` keys: identity, coverage, metrics, regime, options, nav,
    position, sizing, portfolio, blocked, settings, now, market_open, events."""
    identity: dict[str, Any] = ctx["identity"]
    coverage: dict[str, dict[str, Any]] = ctx["coverage"]
    settings: RiskSettings = ctx["settings"]
    now: datetime = ctx["now"]
    m: dict[str, Any] | None = ctx.get("metrics")
    position: dict[str, Any] | None = ctx.get("position")
    market_open: bool = bool(ctx.get("market_open"))
    regime = (ctx.get("regime") or {}).get("regime", "disrupted")

    validity = timedelta(minutes=settings.recommendation_validity_minutes) if market_open else timedelta(hours=18)
    rec: dict[str, Any] = {
        "instrument": {k: identity.get(k) for k in ("symbol", "name", "ins_id", "isin", "category", "category_label", "market")},
        "created_at": now.isoformat(), "valid_until": (now + validity).isoformat(),
        "horizon": "intraday, with a conditional multi-session hold assessed separately",
        "mode": MODE_PAPER, "rules_version": RULES_VERSION,
        "subject": "confirmed_position" if position else "new_position",
        "position_confirmed": bool(position),
        "state": "insufficient_data", "reasons": [],
        "activation_conditions": [], "invalidation_conditions": [],
        "entry": None, "sizing": ctx.get("sizing"), "exit_assessment": None,
        "targets": None,
        "targets_note": "هدف قیمتی ارائه نمی‌شود: هیچ مدل اعتبارسنجی‌شده‌ای برای آن وجود ندارد.",
        "supporting": [], "opposing": [], "missing": _missing_info(coverage, identity),
        "confidence": {"level": "low", "basis": "قواعد اکتشافیِ شفاف و اعتبارسنجی‌نشده (خارج از نمونه)؛ عدد احتمال ارائه نمی‌شود."},
        "portfolio_implications": [], "regime": regime,
        "next_review": "در پایش بعدی (هر چند دقیقه در ساعات بازار)" if market_open else "پیش از بازگشایی جلسهٔ بعد",
        "limitations": list((m or {}).get("limitations") or []),
    }

    def done(state: str, *reasons: str) -> dict[str, Any]:
        rec["state"] = state
        rec["state_label"] = STATE_LABELS[state]
        rec["reasons"].extend(reasons)
        return rec

    # ── scope gates ──
    if not identity.get("supported"):
        return done("unsupported", identity.get("support_note") or "نوع ابزار در دامنهٔ تحلیل نیست.")
    if identity.get("category") == "option":
        return done("restricted", "افزودن قرارداد اختیار به هشدارها مجوز توصیهٔ معاملهٔ اختیار نیست؛ این قابلیت تأیید جداگانه می‌خواهد.")

    purpose = "position" if position else "new_entry"
    gaps = _coverage_gaps(coverage, purpose)
    if m is None or gaps:
        if position:
            rec["exit_assessment"] = {"class": "D", "label": "اطلاعات کافی برای توصیهٔ معتبر نیست",
                                      "note": "موقعیت ثبت‌شده همچنان نمایش داده می‌شود و هشدار قطع داده ارسال می‌شود."}
        return done("insufficient_data", "دادهٔ حیاتی در دسترس یا تازه نیست: " + "؛ ".join(gaps or ["quote"]))

    queue = m["queue"]["state"]
    spread = m["spread"]
    trading_state = identity.get("trading_state")
    halted = trading_state is not None and trading_state not in ALLOWED_TRADING_STATES

    # ── evidence (kept on both sides; correlated readings share one factor) ──
    r5, r20 = m.get("return_5d_pct"), m.get("return_20d_pct")
    if r5 is not None and r20 is not None:
        side = "supporting" if r5 > 0 and r20 > 0 else "opposing" if r5 < 0 and r20 < 0 else None
        text = f"بازده ۵ جلسه {_fmt(r5)}٪ و ۲۰ جلسه {_fmt(r20)}٪"
        if side:
            rec[side].append(_ev("trend", text, {"r5": r5, "r20": r20}))
        else:
            rec["opposing"].append(_ev("trend", text + " — روند کوتاه‌مدت و میان‌مدت هم‌جهت نیستند", {"r5": r5, "r20": r20}))
    else:
        rec["missing"].append("trend: تاریخچهٔ قیمت پاک کافی نیست")
    vs_vwap = m.get("price_vs_vwap_pct")
    if vs_vwap is not None:
        rec["supporting" if vs_vwap >= 0 else "opposing"].append(
            _ev("intraday_flow", f"قیمت {_fmt(vs_vwap)}٪ نسبت به میانگین وزنی جلسه", vs_vwap))
    if queue == "sell_queue":
        rec["opposing"].append(_ev("queue", f"صف فروش در کف مجاز ({_fmt(m['queue']['volume'], 0)} واحد)", m["queue"]))
    elif queue == "buy_queue":
        rec["opposing"].append(_ev("queue", "صف خرید در سقف مجاز — خرید قابل اجرا نیست", m["queue"]))
    elif queue == "unknown":
        rec["missing"].append("queue: دامنهٔ مجاز روز در دسترس نیست؛ وضعیت صف نامشخص است")
    if spread["state"] != "two_sided":
        rec["opposing"].append(_ev("liquidity", f"دفتر سفارش دوطرفه نیست ({spread['state']})"))
    elif spread["pct"] > settings.max_spread_pct:
        rec["opposing"].append(_ev("liquidity", f"شکاف خرید/فروش {_fmt(spread['pct'])}٪ (بیش از حد {settings.max_spread_pct}٪)", spread["pct"]))
    rv = m.get("relative_volume")
    if rv is not None:
        rec["supporting" if rv >= 1 else "opposing"].append(_ev("volume", f"حجم امروز {_fmt(rv)} برابر میانگین ماهانه", rv))
    nav = ctx.get("nav") or {}
    if nav.get("premium_pct") is not None:
        p = nav["premium_pct"]
        rec["opposing" if p > 0 else "supporting"].append(
            _ev("valuation", f"قیمت {_fmt(abs(p))}٪ {'حباب مثبت' if p > 0 else 'تخفیف'} نسبت به NAV رسمی {nav.get('official_date')}", p))
    opt = ctx.get("options") or {}
    if opt.get("state") == "available" and opt["summary"].get("nearest_expiry_days") is not None \
            and opt["summary"]["nearest_expiry_days"] <= 3:
        rec["opposing"].append(_ev("event", f"سررسید اختیارهای مرتبط تا {int(opt['summary']['nearest_expiry_days'])} روز دیگر — نوسان پیرامون سررسید"))
    reg = ctx.get("regime") or {}
    rec["supporting" if regime == "favorable" else "opposing" if regime in ("unfavorable", "disrupted") else "missing"].append(
        _ev("regime", f"رژیم بازار (آزمایشی): {regime} — " + "؛ ".join(reg.get("reasons") or [])) if regime != "neutral"
        else "regime: خنثی/نامطمئن (طبقه‌بند آزمایشی)")

    # ── confirmed position: manage it, never assume an exit happened ──
    if position:
        return _manage_position(rec, done, ctx, m, halted, queue, market_open)

    # ── new position ──
    rec["invalidation_conditions"] = [
        "تشکیل صف فروش یا توقف نماد", "گسترش شکاف خرید/فروش فراتر از حد تنظیم‌شده",
        "کهنه یا نامعتبر شدن دادهٔ قیمت", "تغییر رژیم بازار به نامطلوب/مختل",
    ]
    blocked: list[str] = ctx.get("blocked") or []
    if blocked:
        return done("no_trade", *blocked)
    if halted:
        return done("no_trade", f"وضعیت معاملاتی نماد «{trading_state}» است.")
    if queue == "sell_queue":
        return done("no_trade", "نماد در صف فروش قفل است؛ در صورت ورود، خروج قابل اجرا نیست.")
    if settings.ceiling_for(regime) <= 0:
        return done("no_trade", f"سقف تخصیص در رژیم «{regime}» صفر است.")
    if queue == "buy_queue":
        rec["activation_conditions"] = ["خروج از صف خرید و تشکیل عرضهٔ قابل معامله در دامنهٔ مجاز"]
        return done("await_confirmation", "نماد در صف خرید قفل است؛ سفارش خرید در صف می‌ماند و اجرا تضمین نیست.")
    sizing = ctx.get("sizing") or {}
    if not sizing.get("units"):
        return done("no_trade", sizing.get("reason") or "اندازهٔ قابل معامله‌ای در محدودیت‌های ریسک نمی‌گنجد.")

    rec["entry"] = {
        "estimated_executable_price_rial": sizing["entry_price_rial"],
        "basis": "بهترین پیشنهاد فروش فعلی؛ اجرا با لغزش و عمق واقعی تضمین نمی‌شود",
        "analytical_stop_rial": sizing["analytical_stop_rial"],
        "stop_note": "حد ضرر تحلیلی است؛ در صف فروش یا شکاف قیمتی ممکن است قابل اجرا نباشد.",
        "units": sizing["units"], "value_toman": sizing["entry_value_toman"],
        "planned_loss_toman": sizing["planned_loss_toman"],
        "binding_constraint": risk.CONSTRAINT_LABELS.get(sizing["binding"], sizing["binding"]),
        "round_trip_cost_pct": sizing["round_trip_cost_pct"],
    }
    rec["portfolio_implications"].append(
        f"اندازهٔ پیشنهادی {_fmt(sizing.get('position_pct_of_equity'))}٪ از سرمایهٔ مشترک؛ سقف رژیم {sizing['allocation_ceiling_pct']}٪؛ "
        "این نقدینگی با سایر توصیه‌های هم‌زمان مشترک است.")
    rec["invalidation_conditions"].insert(0, f"معامله زیر {_fmt(sizing['analytical_stop_rial'], 0)} ریال (حد ضرر تحلیلی)")

    waits: list[str] = []
    if not market_open:
        waits.append("بازار بسته است؛ پس از بازگشایی و با دادهٔ تازه دوباره ارزیابی می‌شود")
    if queue == "buy_queue":
        waits.append("خروج از صف خرید و تشکیل عرضهٔ قابل معامله")
    if queue == "unknown":
        waits.append("تأیید دامنهٔ مجاز روز و نبودِ صف")
    if spread["state"] != "two_sided" or spread["pct"] > settings.max_spread_pct:
        waits.append(f"شکاف خرید/فروش دوطرفه و کمتر از {settings.max_spread_pct}٪")
    if not (r5 is not None and r20 is not None and r5 > 0 and r20 > 0):
        waits.append("هم‌جهت و مثبت شدن بازده ۵ و ۲۰ جلسه")
    if vs_vwap is None or vs_vwap < 0:
        waits.append("تثبیت قیمت بالای میانگین وزنی جلسه")
    if waits:
        rec["activation_conditions"] = waits
        return done("await_confirmation", "شرایط لازم برای ورود هنوز کامل نیست.")
    rec["activation_conditions"] = ["همهٔ شرایط قاعده برقرار است؛ پیش از اقدام قیمت و عمق را دوباره ببینید"]
    return done("conditional_entry", "شرایط قاعدهٔ اکتشافی برقرار است (حالت کاغذی؛ اجرا با کاربر است).")


def _manage_position(rec: dict[str, Any], done: Any, ctx: dict[str, Any], m: dict[str, Any],
                     halted: bool, queue: str, market_open: bool) -> dict[str, Any]:
    settings: RiskSettings = ctx["settings"]
    position: dict[str, Any] = ctx["position"]
    portfolio: dict[str, Any] = ctx["portfolio"]
    qty = position["quantity"]
    last = m["price_last"]
    avg_cost_rial = position["avg_cost_toman"] * 10
    vol = m.get("daily_volatility_pct")
    stop_pct = max(settings.min_stop_distance_pct, settings.stop_vol_multiple * vol) if vol is not None else settings.min_stop_distance_pct
    stop = avg_cost_rial * (1 - stop_pct / 100)
    value_toman = qty * last / 10
    budget = portfolio["budgets_toman"]["per_trade_risk"]
    open_loss = max(0.0, (avg_cost_rial - last) * qty / 10)
    bid_volume = m["bid_depth"]["volume"]
    fill_share = min(1.0, bid_volume / qty) if qty > 0 else 0.0

    band_pct = None
    if m.get("low_limit") and m.get("price_yesterday") and m["price_yesterday"] > m["low_limit"]:
        band_pct = (m["price_yesterday"] - m["low_limit"]) / m["price_yesterday"] * 100
    overnight = {
        "gap_scenario": None if band_pct is None else {
            "description": "بازگشایی جلسهٔ بعد در کف دامنهٔ مجاز (برآورد مدل، نه پیش‌بینی)",
            "loss_toman": value_toman * band_pct / 100, "band_pct": band_pct},
        "exposure_toman": value_toman,
        "exposure_ceiling_pct": settings.ceiling_for(rec["regime"]),
        "upcoming_events": ctx.get("events") or [],
        "reassess": "پیش از بازگشایی جلسهٔ بعد",
        "note": "ریسک شبانه/تعطیلات و اخبار خارج از ساعات بازار در حد ضرر تحلیلی دیده نمی‌شود.",
    }
    rec["invalidation_conditions"] = [f"معامله زیر {stop:,.0f} ریال (حد ضرر تحلیلی از میانگین خرید)",
                                      "تشکیل صف فروش یا توقف نماد", "نقض حد زیان روزانهٔ پرتفوی"]
    if open_loss > budget:
        rec["portfolio_implications"].append(
            f"زیان باز این موقعیت ({open_loss:,.0f} تومان) از بودجهٔ ریسک هر معامله ({budget:,.0f} تومان) بیشتر است — این تعارض حتی اگر خروج ممکن نباشد پابرجاست.")
    if portfolio["daily"]["loss_breached"]:
        rec["portfolio_implications"].append("حد زیان روزانه نقض شده: توصیهٔ افزایش ریسک صادر نمی‌شود؛ خروج فوری فرض نمی‌شود.")

    def assess(klass: str, label: str, **extra: Any) -> None:
        rec["exit_assessment"] = {"class": klass, "label": label, "overnight": overnight,
                                  "visible_bid_volume": bid_volume, "share_of_position_at_visible_bids": fill_share,
                                  "note": "قیمت آخرین معامله دلیل امکان خروج کل موقعیت در آن قیمت نیست.", **extra}

    if halted:
        assess("C", "ناتوانی در خروج: نماد متوقف است")
        return done("exit_infeasible", f"وضعیت معاملاتی «{ctx['identity'].get('trading_state')}»؛ نگهداری غیرارادی است، نه توصیه به نگهداری.")
    if queue == "sell_queue":
        assess("C", "ناتوانی در خروج: صف فروش قفل است", queue=m["queue"])
        return done("exit_infeasible", "صف فروش در کف مجاز؛ سفارش فروش در صف می‌ماند و اجرا تضمین نیست. قفل بودن بازار دلیلِ مطلوب بودن نگهداری نیست.")
    if not market_open:
        assess("B", "بازار بسته است — نگهداری تا جلسهٔ بعد با ارزیابی مجدد")
        state = "exit" if last <= stop else "hold"
        return done(state, ("قیمت پایانی زیر حد ضرر تحلیلی است؛ در بازگشایی، خروج مشروط به امکان اجرا بررسی شود."
                            if state == "exit" else "ابطال رخ نداده است؛ پیش از جلسهٔ بعد دوباره ارزیابی می‌شود."))
    assess("A", "خروج عملی قابل بررسی است" if fill_share >= 1 else
           f"خروج بخشی قابل بررسی است (حدود {fill_share:.0%} در تقاضای قابل مشاهده)")
    if last <= stop:
        return done("exit", f"قیمت ({last:,.0f}) به حد ضرر تحلیلی ({stop:,.0f}) رسیده است. خروج تا تأیید اجرا توسط کاربر ثبت نمی‌شود.")
    r5, vs_vwap = m.get("return_5d_pct"), m.get("price_vs_vwap_pct")
    if r5 is not None and r5 < 0 and vs_vwap is not None and vs_vwap < 0:
        return done("reduce", "روند کوتاه‌مدت منفی و قیمت زیر میانگین وزنی جلسه است؛ کاهش موقعیت قابل بررسی است.")
    rec["exit_assessment"]["class"] = "B" if rec["regime"] != "unfavorable" else "A"
    rec["exit_assessment"]["label"] = "نگهداری مشروط" if rec["regime"] != "unfavorable" else "خروج عملی قابل بررسی است (رژیم نامطلوب)"
    return done("hold", "شرط ابطال فعال نشده است.")
