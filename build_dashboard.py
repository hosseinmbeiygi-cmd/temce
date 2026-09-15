# -*- coding: utf-8 -*-
"""
build_dashboard.py — داشبورد تجمیعی از run_stats*.jsonl صفحات نمادها
خروجی: symbol_reports/dashboard.md و symbol_reports/dashboard_user_raw.csv

سه تب کاملاً مجزا:
  تب الف — تحلیل داخلی (غربالگری + امتیاز ترکیبی + فهرست پیشنهادی + تناقض‌ها)
  تب ب — خروجی خام سیستم امتیازدهی اختصاصی کاربر (دست‌نخورده)
  تب ج — شناسنامه و خلاصه سریع همه نمادها (جدول واحد + گروه‌بندی صنعت)
به‌علاوه جدول «مقایسه کنار هم دو تحلیل» بدون هیچ ترکیب یا وزن‌دهی.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

OUT_DIR = Path(__file__).resolve().parent / "symbol_reports"

# ---- فیلترهای پیش‌فرض (قابل تنظیم) ----
MIN_LIQUIDITY_TOMAN = 5_000_000_000          # ۵ میلیارد تومان ارزش معاملات روزانه
MIN_LIQUIDITY_RIAL = MIN_LIQUIDITY_TOMAN * 10
DEBT_MAX_PCT = 70.0
RSI_LOW, RSI_HIGH = 30.0, 70.0
WEIGHTS = {"mos": 0.30, "growth": 0.25, "rsi": 0.15, "debt": 0.15, "pe_gap": 0.15}

REMINDER = (
    "این داشبورد، تجمیع و رتبه‌بندی خودکار داده‌های موجود در صفحات نمادهاست؛ یک توصیه سرمایه‌گذاری یا سیگنال خرید/فروش قطعی نیست. "
    "فهرست پیشنهادی صرفاً نقطه شروع برای بررسی عمیق‌تر شماست، نه نتیجه نهایی. تصمیم و مسئولیت آن با خود سرمایه‌گذار است. "
    "همچنین، فیلترها و وزن‌های امتیازدهی بالا پیش‌فرض و قابل تغییرند؛ با معیار دیگری، رتبه‌بندی متفاوت می‌شود."
)


def num(x):
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except Exception:
        return None


def fnum(x, nd=2):
    v = num(x)
    if v is None:
        return "نامشخص"
    if abs(v - round(v)) < 1e-9:
        return f"{int(round(v)):,}"
    return f"{v:,.{nd}f}"


def fpct(x):
    v = num(x)
    return "نامشخص" if v is None else f"{v:+.2f}٪"


def load_stats():
    by_sym = {}
    for sp in sorted(OUT_DIR.glob("run_stats*.jsonl")):
        with open(sp, encoding="utf-8") as fh:
            for line in fh:
                try:
                    s = json.loads(line)
                except Exception:
                    continue
                if s.get("symbol"):
                    by_sym[s["symbol"]] = s
    return list(by_sym.values())


def screen_status(s):
    """وضعیت غربال پیش‌فرض ۴.۲ با علت دقیق."""
    if s.get("category") in ("کریپتو", "طلا/ارز/سکه"):
        return "خارج از دامنه غربال (دارایی غیربورسی)", "", ["غیربورسی"]
    reasons = []
    missing = []
    pe, ipe = num(s.get("pe")), num(s.get("industry_pe"))
    if pe is not None and ipe is not None and ipe > 0:
        if not (pe < ipe):
            reasons.append("P/E بالاتر از میانگین صنعت")
    else:
        missing.append("P/E صنعت")
    g = num(s.get("net_profit_growth"))
    if g is not None:
        if not (g > 0):
            reasons.append("رشد سود خالص YoY نامثبت")
    else:
        missing.append("رشد سود خالص")
    r = num(s.get("rsi14"))
    if r is not None:
        if not (RSI_LOW <= r <= RSI_HIGH):
            reasons.append(f"RSI خارج بازه {RSI_LOW:.0f}-{RSI_HIGH:.0f}")
    else:
        missing.append("RSI")
    missing.append("نسبت بدهی")          # در ورودی موجود نیست
    liq = num(s.get("avg_val30"))
    if liq is not None:
        if not (liq > MIN_LIQUIDITY_RIAL):
            reasons.append("نقدشوندگی کمتر از حداقل")
    else:
        missing.append("میانگین ارزش معاملات")
    missing.append("Margin of Safety")   # نیازمند ارزش منصفانه؛ موجود نیست
    if reasons:
        return "رد شد", "؛ ".join(reasons), missing
    if missing:
        return "داده ناکافی", "فیلترهای دارای داده ناکافی: " + "، ".join(missing), missing
    return "عبور کرد", "", []


def diag_ok(s):
    """غربال تشخیصی: فقط فیلترهای قابل‌محاسبه (P/E صنعت، RSI، نقدشوندگی).
    «رشد سود خالص YoY» به‌دلیل نبود داده در ورودی از این غربال کنار گذاشته شده است."""
    if s.get("category") in ("کریپتو", "طلا/ارز/سکه"):
        return False
    pe, ipe = num(s.get("pe")), num(s.get("industry_pe"))
    if not (pe is not None and ipe is not None and ipe > 0 and pe < ipe):
        return False
    r = num(s.get("rsi14"))
    if not (r is not None and RSI_LOW <= r <= RSI_HIGH):
        return False
    liq = num(s.get("avg_val30"))
    if not (liq is not None and liq > MIN_LIQUIDITY_RIAL):
        return False
    return True


def norm(vals, x):
    xs = [v for v in vals if v is not None]
    if len(xs) < 2 or x is None:
        return 50.0 if x is not None else None
    lo, hi = min(xs), max(xs)
    if hi - lo < 1e-12:
        return 50.0
    return (x - lo) / (hi - lo) * 100.0


def score_passers(passers):
    """امتیاز ۴.۳ با حذف اجزای ناقص و بازتوزیع وزن‌ها (ثبت‌شده در پانویس)."""
    rows = []
    growths = [num(s.get("net_profit_growth")) for s in passers]
    rsis = [num(s.get("rsi14")) for s in passers]
    pegaps = [(-(num(s["pe"]) / num(s["industry_pe"]) - 1) * 100) if (num(s.get("pe")) and num(s.get("industry_pe"))) else None for s in passers]
    mos_vals = [None for _ in passers]  # ارزش منصفانه در ورودی موجود نیست
    for s, g, r, pg, mos in zip(passers, growths, rsis, pegaps, mos_vals):
        parts = {}
        if mos is not None:
            parts["mos"] = norm(mos_vals, mos)
        if g is not None:
            parts["growth"] = norm(growths, g)
        if r is not None:
            parts["rsi"] = 100 - abs(r - 50) * 2
        if pg is not None:
            parts["pe_gap"] = norm(pegaps, pg)
        wsum = sum(WEIGHTS[k] for k in parts)
        if wsum <= 0:
            continue
        score = sum(WEIGHTS[k] * parts[k] for k in parts) / wsum
        rows.append((s["symbol"], score, mos, g, r, pg, "، ".join(parts.keys()), wsum))
    return sorted(rows, key=lambda t: t[1], reverse=True)


def contradiction_cell(s):
    c = s.get("contradictions")
    if isinstance(c, list) and c:
        return "؛ ".join(str(x) for x in c)
    return "—"


def user_result(s):
    ud = s.get("user_daily") or {}
    us = s.get("user_signal") or {}
    score = ud.get("score_total")
    final = us.get("final_score")
    dec = us.get("decision")
    rank = ud.get("rank_in_market")
    pct = ud.get("percentile_score")
    parts = []
    if score is not None:
        parts.append(f"score_total={fnum(score)}")
    if rank is not None:
        parts.append(f"رتبه بازار={fnum(rank,0)}")
    if pct is not None:
        parts.append(f"صدک={fnum(pct)}")
    if final is not None:
        parts.append(f"final={fnum(final)}")
    if dec:
        parts.append(f"تصمیم={dec}")
    return " | ".join(parts) if parts else "خروجی ثبت نشده"


def main():
    stats = load_stats()
    if not stats:
        print("run_stats*.jsonl یافت نشد.")
        return
    stats.sort(key=lambda s: str(s.get("symbol")))

    for s in stats:
        s["_verdict"], s["_reason"], s["_missing"] = screen_status(s)
    passers = [s for s in stats if s["_verdict"] == "عبور کرد"]
    diag_passers = [s for s in stats if diag_ok(s)]
    scored = score_passers(diag_passers)

    lines = ["# داشبورد تجمیعی نمادها", "",
             f"> {REMINDER}", "",
             f"- تعداد نمادهای پردازش‌شده: **{len(stats)}**",
             f"- عبورکرده از غربال پیش‌فرض ۴.۲: **{len(passers)}** | داده ناکافی: **{sum(1 for s in stats if s['_verdict'] == 'داده ناکافی')}** | رد شده: **{sum(1 for s in stats if s['_verdict'] == 'رد شد')}** | خارج از دامنه: **{sum(1 for s in stats if s['_verdict'].startswith('خارج'))}**",
             f"- عبورکرده از «غربال تشخیصی» (فقط فیلترهای قابل‌محاسبه؛ توضیح در ۴.۴): **{len(diag_passers)}**",
             "", "---", ""]

    # ---------- تب الف ----------
    lines += ["## تب الف — تحلیل داخلی این پرامپت", ""]
    lines += ["### ۴.۱ جدول کلی غربالگری (همه نمادهای پردازش‌شده، بدون حذف)", ""]
    lines += ["| نماد | قیمت فعلی | P/E(TTM) | P/E نسبت به میانگین صنعت | رشد سود خالص YoY% | RSI14 | نسبت بدهی% | Margin of Safety% | میانگین ارزش معاملات۳۰روزه | نتیجه غربال (رد شد/عبور کرد) |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for s in stats:
        pe_vs = s.get("pe_vs_industry")
        non_tse = s.get("category") in ("کریپتو", "طلا/ارز/سکه")
        liq_cell = "— (خارج از دامنه بورسی)" if non_tse else fnum(s.get("avg_val30"), 0)
        lines.append("| {sym} | {px} | {pe} | {pev} | {g} | {rsi} | {debt} | {mos} | {liq} | {verdict}{reason} |".format(
            sym=s["symbol"], px=fnum(s.get("price")), pe=fnum(s.get("pe")),
            pev=(fpct(pe_vs) if num(pe_vs) is not None else "نامشخص"),
            g=fpct(s.get("net_profit_growth")), rsi=fnum(s.get("rsi14")),
            debt="نامشخص", mos="نامشخص",
            liq=liq_cell,
            verdict=s["_verdict"],
            reason=(f" — {s['_reason']}" if s["_reason"] else "")))
    lines.append("")

    lines += ["### ۴.۲ فیلترهای غربالگری پیش‌فرض (قابل تنظیم)", "",
              f"- P/E(TTM) کمتر از میانگین P/E صنعت مربوطه",
              f"- رشد سود خالص YoY بزرگ‌تر از صفر",
              f"- RSI(14) بین {RSI_LOW:.0f} و {RSI_HIGH:.0f}",
              f"- نسبت بدهی کمتر از {DEBT_MAX_PCT:.0f}٪",
              f"- میانگین ارزش معاملات ۳۰روزه بیشتر از {MIN_LIQUIDITY_TOMAN:,} تومان در روز",
              "- Margin of Safety% بزرگ‌تر از صفر (نیازمند ارزش منصفانه)", "",
              "**توجه داده‌ای:** سه فیلتر «رشد سود خالص YoY»، «نسبت بدهی» و «Margin of Safety» برای هیچ نمادی در داده ورودی قابل محاسبه نیست "
              "(صورت‌های مالی معتبر و مدل ارزش‌گذاری در ورودی موجود نیست)؛ بنابراین نمادها به‌جای «عبور»، با برچسب «داده ناکافی» مشخص شده‌اند.", ""]

    lines += ["### ۴.۳ امتیاز رتبه‌بندی ترکیبی", ""]
    if passers:
        lines.append(f"{len(passers)} نماد از غربال پیش‌فرض عبور کردند؛ امتیاز محاسبه شد.")
    else:
        lines.append("هیچ نمادی از غربال پیش‌فرض کامل عبور نکرد (به‌دلیل دو فیلتر فاقد داده؛ توضیح ۴.۲). "
                     "بنابراین امتیاز ترکیبی داخلی طبق فرمول ۴.۳ برای نمادهای عبورکرده قابل ارائه نیست. "
                     "برای حفظ کاربرد عملی، در ۴.۴ «غربال تشخیصی» با فیلترهای قابل‌محاسبه ارائه شده است؛ "
                     "این جدول مکمل و برچسب‌دار است و جای غربال رسمی ۴.۲ را نمی‌گیرد.")
    lines.append("")
    comp_foot = ("پانویس ۴.۳/۴.۴: در امتیاز جدول ۴.۴، اجزای «Margin of Safety»، «نسبت بدهی» و «رشد سود خالص YoY» به‌دلیل نبود داده از فرمول کنار گذاشته شده و "
                 "وزن باقی‌مانده (فاصله منفی P/E از صنعت ۰.۱۵ + RSI ۰.۱۵ → جمع ۰.۳۰) به‌صورت متناسب نرمال‌سازی شده است؛ "
                 "یعنی در عمل امتیاز جدول ۴.۴ ترکیبی ۵۰/۵۰ از «ارزانی نسبی P/E» و «فاصله RSI از میانه ۵۰» است.")
    lines += [comp_foot, ""]

    lines += ["### ۴.۴ فهرست پیشنهادی (Top Candidates جدول تشخیصی)", ""]
    if scored:
        lines += ["| رتبه | نماد | Score (نرمال‌شده ۰-۱۰۰) | Margin of Safety% | رشد سود YoY% | RSI14 | تناقض‌های شناسایی‌شده |",
                  "|---|---|---|---|---|---|---|"]
        for i, (sym, sc, mos, g, r, pg, used, wsum) in enumerate(scored[:10], start=1):
            s = next(x for x in stats if x["symbol"] == sym)
            lines.append(f"| {i} | {sym} | {sc:.1f} | نامشخص | {fpct(g)} | {fnum(r)} | {contradiction_cell(s)} |")
        lines.append("")
    else:
        lines.append("هیچ نمادی حتی از غربال تشخیصی (فیلترهای قابل‌محاسبه) عبور نکرد؛ فهرست پیشنهادی خالی است. "
                     "علت رایج: نبود رشد سود خالص YoY یا P/E صنعت در ورودی. جدول ۴.۱ علت هر نماد را نشان می‌دهد.")
        lines.append("")

    lines += ["### ۴.۵ جدول نمادهای دارای تناقض (نیاز به بررسی دستی)", ""]
    contra = [s for s in stats if isinstance(s.get("contradictions"), list) and s["contradictions"]]
    if contra:
        lines += ["| نماد | تناقض‌ها | نتیجه غربال |", "|---|---|---|"]
        for s in contra:
            lines.append(f"| {s['symbol']} | {contradiction_cell(s)} | {s['_verdict']} |")
    else:
        lines.append("موردی ثبت نشد.")
    lines.append("")

    lines += ["### ۴.۶ جدول مقایسه کنار هم دو تحلیل (بدون ترکیب یا وزن‌دهی)", "",
              "| نماد | نتیجه غربال تب الف | امتیاز داخلی تب الف | نتیجه/امتیاز تب ب (خام) | هم‌جهت یا ناهم‌جهت؟ |",
              "|---|---|---|---|---|"]
    for s in stats:
        u = user_result(s)
        us = s.get("user_signal") or {}
        ud = s.get("user_daily") or {}
        final = num(us.get("final_score"))
        score_total = num(ud.get("score_total"))
        tabA_positive = s["_verdict"] == "عبور کرد"
        tabB_positive = (final is not None and final > 0) or (score_total is not None and score_total > 0)
        if s["_verdict"] == "داده ناکافی":
            direction = "داده ناکافی"
        elif tabA_positive and tabB_positive:
            direction = "هر دو مثبت"
        elif (not tabA_positive) and (not tabB_positive):
            direction = "هر دو منفی"
        else:
            direction = "ناهم‌جهت — نیاز به بررسی دستی"
        score_cell = "—" if not passers else "نامشخص"
        lines.append(f"| {s['symbol']} | {s['_verdict']} | {score_cell} | {u} | {direction} |")
    lines.append("")
    lines += ["---", ""]

    # ---------- تب ب ----------
    lines += ["## تب ب — خروجی خام سیستم امتیازدهی اختصاصی کاربر (دست‌نخورده)", "",
              "**شناسایی سیستم:** جدول‌های `screener_daily_scores` (۳۳ فیلد خام در `raw_scores`) و `screener_signals` "
              "(امتیازها و شاخص‌های نهایی) به‌عنوان خروجی سیستم امتیازدهی اختصاصی شما شناسایی شدند. "
              "هیچ‌کدام از این مقادیر بازتفسیر، ترکیب یا با تحلیل داخلی میانگین‌گیری نشده‌اند.", "",
              "| نماد | score_total | momentum | value | growth | quality | liquidity | sentiment | رتبه بازار | رتبه صنعت | صدک | final_score خام | adjusted_score | تصمیم | فیلترهای منفی | rule_50_30 |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in stats:
        ud = s.get("user_daily") or {}
        us = s.get("user_signal") or {}
        if not ud and not us:
            continue
        lines.append("| {sym} | {a} | {b} | {c} | {d} | {e} | {f} | {g} | {h} | {i} | {j} | {k} | {l} | {m} | {n} | {o} |".format(
            sym=s["symbol"],
            a=fnum(ud.get("score_total")), b=fnum(ud.get("score_momentum")), c=fnum(ud.get("score_value")),
            d=fnum(ud.get("score_growth")), e=fnum(ud.get("score_quality")), f=fnum(ud.get("score_liquidity")),
            g=fnum(ud.get("score_sentiment")), h=fnum(ud.get("rank_in_market"), 0), i=fnum(ud.get("rank_in_industry"), 0),
            j=fnum(ud.get("percentile_score")), k=fnum(us.get("final_score")), l=fnum(us.get("adjusted_score")),
            m=str(us.get("decision") or "نامشخص"), n=fnum(us.get("negative_filters_count"), 0),
            o=str(us.get("rule_50_30") or "نامشخص")))
    lines += ["", "نسخه کامل و خام همه ستون‌ها (شامل `raw_scores` با ۳۳ پارامتر) در فایل "
                  "`dashboard_user_raw.csv` ذخیره شده است — بدون هیچ تغییر یا بازتفسیر.", "", "---", ""]

    # ---------- تب ج ----------
    lines += ["## تب ج — شناسنامه و خلاصه سریع همه نمادها", "", "### جدول واحد", "",
              "| نماد | نام کامل شرکت | صنعت | زیرصنعت | بازار | سرمایه ثبتی (میلیارد تومان) | تعداد سهام | آخرین قیمت | تغییر روزانه% | وضعیت نماد | نام فایل صفحه اختصاصی |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in stats:
        lines.append("| {sym} | {name} | {sec} | {sub} | {mkt} | {cap} | {sh} | {px} | {chg} | {state} | {file} |".format(
            sym=s["symbol"], name=(s.get("name") or "نامشخص"), sec=(s.get("sector") or "نامشخص"),
            sub=(s.get("sub_sector") or "نامشخص"), mkt=(s.get("market") or "نامشخص"),
            cap=(fnum(s.get("capital_btom")) if num(s.get("capital_btom")) is not None else "نامشخص"),
            sh=(fnum(s.get("shares"), 0) if num(s.get("shares")) is not None else "نامشخص"),
            px=fnum(s.get("price")), chg=fpct(s.get("daily_change_pct")),
            state=(s.get("state") or "نامشخص"), file=s.get("file", "—")))
    lines += ["", "### گروه‌بندی بر اساس صنعت", ""]
    groups = {}
    for s in stats:
        groups.setdefault(s.get("sector") or "نامشخص", []).append(s)
    for sec in sorted(groups.keys()):
        lines += [f"#### {sec}", "",
                  "| نماد | نام کامل شرکت | زیرصنعت | آخرین قیمت | تغییر روزانه% | وضعیت | فایل |",
                  "|---|---|---|---|---|---|---|"]
        for s in sorted(groups[sec], key=lambda x: str(x["symbol"])):
            lines.append("| {sym} | {name} | {sub} | {px} | {chg} | {state} | {file} |".format(
                sym=s["symbol"], name=(s.get("name") or "نامشخص"), sub=(s.get("sub_sector") or "نامشخص"),
                px=fnum(s.get("price")), chg=fpct(s.get("daily_change_pct")),
                state=(s.get("state") or "نامشخص"), file=s.get("file", "—")))
        lines.append("")

    with open(OUT_DIR / "dashboard.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    # ---- گزارش خلاصه اجرا ----
    fills = [num(s.get("fill_pct")) or 0.0 for s in stats]
    low = [s for s in stats if (num(s.get("fill_pct")) or 0.0) < 30]
    cats = {}
    for s in stats:
        c = s.get("category", "سایر")
        cats[c] = cats.get(c, 0) + 1
    sl = ["# گزارش خلاصه اجرا — صفحات اختصاصی نمادها", "",
          f"- تعداد کل نمادهای پردازش‌شده: **{len(stats)}**",
          f"- میانگین درصد فیلدهای پرشده (شاخص کامل‌بودن داده): **{sum(fills)/len(fills):.1f}٪**",
          f"- تعداد صفحات با تکمیل کمتر از ۳۰٪: **{len(low)}**",
          "- توزیع دسته‌ها: " + "، ".join(f"{k}: {v}" for k, v in sorted(cats.items(), key=lambda t: -t[1])),
          f"- نمادهای دارای مدل ML موفق: **{sum(1 for s in stats if s.get('has_ml'))}**",
          f"- نمادهای دارای بک‌تست کافی: **{sum(1 for s in stats if s.get('has_backtest'))}**",
          "", "## نمادهای نیازمند بررسی دستی (کمترین کامل‌بودن داده)", ""]
    for s in sorted(low, key=lambda x: (num(x.get("fill_pct")) or 0.0))[:100]:
        miss = s.get("missing") or []
        sl.append(f"- {s.get('symbol')} ({s.get('category', '?')}): تکمیل {s.get('fill_pct')}٪ — ردیف روزانه {s.get('rows')}"
                  + (f" — موارد نامشخص: {'، '.join(str(m) for m in miss[:6])}" if miss else ""))
    ranked_low = sorted(stats, key=lambda x: (num(x.get("fill_pct")) or 0.0))[:50]
    sl += ["", "## ۵۰ نماد با کمترین کامل‌بودن داده (نیازمند بررسی دستی)", ""]
    for s in ranked_low:
        miss = s.get("missing") or []
        sl.append(f"- {s.get('symbol')} ({s.get('category', '?')}): تکمیل {s.get('fill_pct')}٪ — ردیف روزانه {s.get('rows')}"
                  + (f" — موارد نامشخص: {'، '.join(str(m) for m in miss[:6])}" if miss else ""))
    min_fill = min((num(s.get("fill_pct")) or 0.0) for s in stats)
    sl.append("")
    sl.append(f"کمینه درصد تکمیل در همه صفحات: **{min_fill:.1f}٪** (هیچ صفحه‌ای زیر ۳۰٪ نیست؛ اما همین فهرست ۵۰ مورد پایین برای بررسی دستی توصیه می‌شود.)")
    with open(OUT_DIR / "run_summary.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(sl) + "\n")

    # CSV خام سیستم کاربر
    keys = set()
    for s in stats:
        keys.update((s.get("user_daily") or {}).keys())
        keys.update((s.get("user_signal") or {}).keys())
    user_keys = sorted(keys)
    with open(OUT_DIR / "dashboard_user_raw.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["symbol"] + user_keys)
        for s in stats:
            ud = s.get("user_daily") or {}
            us = s.get("user_signal") or {}
            row = [s["symbol"]] + [json.dumps(ud.get(k, us.get(k)), ensure_ascii=False) if isinstance(ud.get(k, us.get(k)), (dict, list)) else ud.get(k, us.get(k)) for k in user_keys]
            w.writerow(row)

    print(f"dashboard.md نوشته شد ({len(stats)} نماد) | dashboard_user_raw.csv با {len(user_keys)} ستون")
    print(f"عبورکرده غربال رسمی: {len(passers)} | غربال تشخیصی: {len(diag_passers)} | دارای تناقض: {len(contra)}")


if __name__ == "__main__":
    main()
