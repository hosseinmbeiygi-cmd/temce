"""
build_symbol_reports.py
سازنده «صفحه اختصاصی نماد» از جداول خام واقعی (TimescaleDB + فایل‌های داده).

قواعد:
 - هر عدد از داده واقعی محاسبه می‌شود؛ هرجا داده کافی نباشد «نامشخص» درج می‌شود.
 - مفروضات با برچسب «فرض محاسباتی» از داده واقعی جدا می‌شوند.
 - خروجی: symbol_reports/<نماد>.md + detection_log.csv + run_stats.jsonl + run_summary.md
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import gzip
import json
import math
import os
import re
import sys
import time
import traceback
import warnings
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from core.time import now_tehran

warnings.filterwarnings("ignore", category=UserWarning)

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "symbol_reports"
HISTORY_DIR = ROOT / "history_data"
CRYPTO_HISTORY_DIR = ROOT / "crypto_history"
FUNDS_DIR = ROOT / "data" / "top50_funds_intraday" / "funds"
CODAL_FILES_DIR = ROOT / "codal_data"

UNKNOWN = "نامشخص"
NOT_COMPUTABLE = "قابل محاسبه نیست"
NOT_APPLICABLE = "فاقد موضوعیت"
NO_DATA = "فاقد داده"
TOTAL_FIELDS = 160
ML_WARNING = (
    "داده تاریخی بازار ایران برای این نماد معمولاً محدود است؛ مدل مستعد Overfitting است؛ "
    "این پیش‌بینی صرفاً آزمایش آماری اکتشافی است، نه سیگنال معاملاتی، و عملکرد گذشته ضمانتی برای آینده نیست."
)
DECISION_REMINDER = (
    "این خلاصه تجمیع خودکار داده‌های همین صفحه است، نه توصیه سرمایه‌گذاری؛ "
    "تصمیم نهایی و مسئولیت آن با خود سرمایه‌گذار است."
)

# ----------------------------------------------------------------------------
# اتصال دیتابیس
# ----------------------------------------------------------------------------

def db_connect():
    import psycopg2

    host = os.getenv("PG_HOST", "localhost")
    port = os.getenv("PG_PORT", "5432")
    dbname = os.getenv("PG_DATABASE", "my_first_db")
    user = os.getenv("PG_USER", "hossein")
    password = os.getenv("PG_PASSWORD") or os.getenv("DB_PASSWORD") or "1343"
    try:
        conn = psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password)
    except Exception:
        conn = psycopg2.connect(host="localhost", port=5432, dbname="my_first_db", user="hossein", password="1343")
    conn.autocommit = True
    return conn


# ----------------------------------------------------------------------------
# کمکی‌ها
# ----------------------------------------------------------------------------

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def fa_digits_to_ascii(s: str) -> str:
    return str(s).translate(_PERSIAN_DIGITS)


def norm_symbol(s) -> str:
    if s is None:
        return ""
    s = str(s).strip().replace("\u064a", "\u06cc").replace("\u0643", "\u06a9")
    s = s.replace("\u200c", "").replace("\u200f", "").replace("\u200e", "")
    s = re.sub(r"\s+", " ", s)
    return s


def safe_name(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "-", str(s)).strip() or "unnamed"


def fmt_num(x, nd=2):
    if x is None:
        return UNKNOWN
    try:
        xf = float(x)
    except Exception:
        return UNKNOWN
    if math.isnan(xf) or math.isinf(xf):
        return UNKNOWN
    if abs(xf) >= 1e12:
        return f"{xf:,.0f}"
    if abs(xf - round(xf)) < 1e-9:
        return f"{int(round(xf)):,}"
    return f"{xf:,.{nd}f}"


def fmt_pct(x, nd=2):
    if x is None:
        return UNKNOWN
    try:
        xf = float(x)
    except Exception:
        return UNKNOWN
    if math.isnan(xf) or math.isinf(xf):
        return UNKNOWN
    return f"{xf:+.{nd}f}٪"


def jdate_to_greg(s: str):
    """تبدیل تاریخ شمسی 1405/06/23 یا 1405-06-23 (و ارقام فارسی) به میلادی."""
    s = fa_digits_to_ascii(s)
    m = re.match(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})", s.strip())
    if not m:
        return None
    try:
        import jdatetime
        return jdatetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).togregorian()
    except Exception:
        return None


def parse_any_date(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = fa_digits_to_ascii(str(v)).strip()
    if not s:
        return None
    m = re.match(r"^(\d{4})[/-](\d{2})[/-](\d{2})$", s)
    if m:
        y = int(m.group(1))
        if 1200 <= y <= 1500:
            return jdate_to_greg(s)
        try:
            return date(y, int(m.group(2)), int(m.group(3)))
        except Exception:
            return None
    try:
        return pd.to_datetime(s, errors="coerce").date()
    except Exception:
        return None


OHLC_COLS = ["open", "high", "low", "close"]


def clean_ohlc(df, drop_close=True):
    """صفر در ستون‌های قیمتی یعنی داده نامعتبر؛ به NaN تبدیل و (در صورت نیاز) ردیف‌های بدون پایانی حذف می‌شوند."""
    if df is None or len(df) == 0:
        return df
    df = df.copy()
    for c in OHLC_COLS:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
            df.loc[df[c] <= 0, c] = np.nan
    if "volume" in df:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    if drop_close and "close" in df:
        df = df.dropna(subset=["close"])
    return df


def jsonable(v):
    if v is None or isinstance(v, (str, int, float, bool)):
        with contextlib.suppress(Exception):
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                return None
        return v
    if isinstance(v, dict):
        return {str(k): jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [jsonable(x) for x in v]
    with contextlib.suppress(Exception):
        import numpy as np
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            return None if (math.isnan(float(v)) or math.isinf(float(v))) else float(v)
        if isinstance(v, (np.bool_,)):
            return bool(v)
    try:
        return str(v)
    except Exception:
        return None


def md_table(headers, rows) -> str:
    out = ["| " + " | ".join(str(h) for h in headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join("" if c is None else str(c) for c in r) + " |")
    return "\n".join(out)


def bullet(label, value) -> str:
    return f"- **{label}**: {value}"


# ----------------------------------------------------------------------------
# شناسایی خودکار ستون‌ها (نام‌محور → آماری)
# ----------------------------------------------------------------------------

NAME_PATTERNS = {
    "date": [r"^date$", r"^تاریخ$", r"trade_date", r"gregorian_date", r"shamsi_date", r"تاریخ"],
    "open": [r"^open$", r"بازگشایی", r"price_open", r"^price_first$"],
    "high": [r"^high$", r"سقف", r"بیشترین", r"price_high", r"^price_max$"],
    "low": [r"^low$", r"کف", r"کمترین", r"price_low", r"^price_min$"],
    "close": [r"^close$", r"پایانی", r"price_close", r"^price_last$", r"آخرین"],
    "volume": [r"^volume$", r"^vol$", r"حجم", r"trade_volume"],
    "value": [r"^value$", r"ارزش", r"trade_value"],
    "symbol": [r"^symbol$", r"نماد", r"ticker", r"instrument"],
    "time": [r"^time$", r"ساعت", r"زمان"],
    "count": [r"^count$", r"^trade_count$", r"تعداد معاملات"],
    "buy_real_value": [r"buy_real_value", r"خرید حقیقی.*ارزش"],
    "sell_real_value": [r"sell_real_value", r"فروش حقیقی.*ارزش"],
    "nav_issue": [r"nav_issue"],
    "nav_redemption": [r"nav_redemption"],
}


def detect_columns(df: pd.DataFrame, source_name: str, sample_desc: str = ""):
    """تشخیص نام‌محور؛ در صورت ناکامی، مسیر آماری. خروجی: (mapping, log_rows)."""
    if df is None or len(df) == 0:
        return {}, []
    mapping = {}
    log_rows = []
    cols = list(df.columns)

    def match_role(role):
        pats = NAME_PATTERNS[role]
        best = None
        for c in cols:
            if c in mapping.values():
                continue
            cl = str(c).strip().lower()
            for p in pats:
                if re.search(p, cl):
                    best = c
                    break
            if best:
                break
        return best

    for role in ["date", "close", "open", "high", "low", "volume", "value", "symbol",
                 "time", "count", "buy_real_value", "sell_real_value", "nav_issue", "nav_redemption"]:
        c = match_role(role)
        if c is not None:
            mapping[role] = c
            log_rows.append(dict(نام_فایل=source_name, ستون_انتخابی=c, نوع_محتوای_تشخیص_داده_شده=role,
                                 مسیر_تشخیص="نام‌محور", درجه_اطمینان="بالا", توضیح=sample_desc))
    # مسیر آماری برای نقش‌های نیافته
    num_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]

    if "date" not in mapping:
        best_c, best_rate = None, 0.0
        s = df.head(300)
        for c in cols:
            try:
                vals = s[c].dropna().astype(str)
                if len(vals) == 0:
                    continue
                rate = vals.map(lambda v: parse_any_date(v) is not None or
                                (len(fa_digits_to_ascii(v)) >= 5 and re.match(r"^\d{1,2}:\d{2}", fa_digits_to_ascii(v)) is not None)).mean()
            except Exception:
                continue
            if rate > best_rate:
                best_c, best_rate = c, rate
        if best_c is not None and best_rate >= 0.6:
            mapping["date"] = best_c
            conf = "متوسط" if best_rate >= 0.9 else "پایین"
            log_rows.append(dict(نام_فایل=source_name, ستون_انتخابی=best_c, نوع_محتوای_تشخیص_داده_شده="date",
                                 مسیر_تشخیص="آماری", درجه_اطمینان=conf, توضیح=f"نرخ تبدیل {best_rate:.2f}"))

    numeric_candidates = [c for c in num_cols if c != mapping.get("date")]
    if any(r not in mapping for r in ["close", "open", "high", "low"]) and len(numeric_candidates) >= 2:
        s = df[numeric_candidates].apply(pd.to_numeric, errors="coerce").head(300)
        corr = s.corr().abs()
        used = set()
        clusters = []
        for i, c1 in enumerate(numeric_candidates):
            if c1 in used:
                continue
            grp = [c1]
            for c2 in numeric_candidates[i + 1:]:
                if c2 in used:
                    continue
                if pd.notna(corr.loc[c1, c2]) and corr.loc[c1, c2] > 0.85:
                    grp.append(c2)
                    used.add(c2)
            used.add(c1)
            if len(grp) >= 2:
                clusters.append(grp)
        for grp in clusters:
            means = {c: pd.to_numeric(df[c], errors="coerce").mean() for c in grp}
            ordered = sorted(grp, key=lambda c: (means[c] if pd.notna(means[c]) else -np.inf), reverse=True)
            roles = [r for r in ["high", "close", "open", "low"] if r not in mapping]
            for role, col in zip(roles, ordered, strict=False):
                mapping[role] = col
                log_rows.append(dict(نام_فایل=source_name, ستون_انتخابی=col, نوع_محتوای_تشخیص_داده_شده=role,
                                     مسیر_تشخیص="آماری", درجه_اطمینان="متوسط",
                                     توضیح=f"خوشه قیمتی همبستگی>{0.85}"))
        if "volume" not in mapping:
            remaining = [c for c in numeric_candidates if c not in mapping.values()]
            if remaining:
                means = {c: pd.to_numeric(df[c], errors="coerce").mean() for c in remaining}
                volc = max(remaining, key=lambda c: means[c] if pd.notna(means[c]) else -np.inf)
                if pd.notna(means[volc]) and means[volc] > 0:
                    mapping["volume"] = volc
                    log_rows.append(dict(نام_فایل=source_name, ستون_انتخابی=volc, نوع_محتوای_تشخیص_داده_شده="volume",
                                         مسیر_تشخیص="آماری", درجه_اطمینان="پایین", توضیح="بزرگ‌ترین مقیاس میانگین"))
    if "symbol" not in mapping:
        for c in cols:
            if c in num_cols:
                continue
            try:
                v = df[c].astype(str)
                ratio = v.nunique() / max(1, len(v.dropna()))
                if ratio < 0.5 and len(v.dropna()) > 0:
                    mapping["symbol"] = c
                    log_rows.append(dict(نام_فایل=source_name, ستون_انتخابی=c, نوع_محتوای_تشخیص_داده_شده="symbol",
                                         مسیر_تشخیص="آماری", درجه_اطمینان="متوسط",
                                         توضیح=f"نسبت یکتا {ratio:.2f}"))
                    break
            except Exception:
                continue
    return mapping, log_rows


# ----------------------------------------------------------------------------
# محاسبات تکنیکال (طبق فرمول‌های وظیفه)
# ----------------------------------------------------------------------------

def ema(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(span=n, adjust=False).mean()


def wilder_rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    rsi[avg_loss == 0] = 100.0
    return rsi


def wilder_atr(high, low, close, n: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / n, adjust=False).mean()
    return atr


def compute_technical(df: pd.DataFrame) -> dict:
    """df: date (datetime), open, high, low, close, volume (اختیاری). خروجی: دیکشنری اعداد."""
    d = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
    if len(d) < 5:
        return {}
    res = {}
    close = d["close"].astype(float)
    high = (d["high"].astype(float) if "high" in d else close).fillna(close)
    low = (d["low"].astype(float) if "low" in d else close).fillna(close)
    res["n_rows"] = len(d)
    res["last_date"] = d["date"].iloc[-1]
    res["close"] = float(close.iloc[-1])
    res["prev_close"] = float(close.iloc[-2])
    res["chg_pct"] = (close.iloc[-1] / close.iloc[-2] - 1) * 100 if close.iloc[-2] else None
    for n in (20, 50):
        if len(d) >= n:
            res[f"sma{n}"] = float(close.rolling(n).mean().iloc[-1])
        else:
            res[f"sma{n}"] = None
    if len(d) >= 26:
        m = ema(close, 12) - ema(close, 26)
        sig = m.ewm(span=9, adjust=False).mean()
        res["macd"] = float(m.iloc[-1])
        res["macd_signal"] = float(sig.iloc[-1])
        res["macd_hist"] = float(m.iloc[-1] - sig.iloc[-1])
        res["macd_hist_prev"] = float((m - sig).iloc[-2]) if len(m) > 1 else None
    if len(d) >= 15:
        r = wilder_rsi(close, 14)
        res["rsi14"] = float(r.iloc[-1])
    if len(d) >= 20:
        mid = close.rolling(20).mean()
        sd = close.rolling(20).std(ddof=0)
        up = mid + 2 * sd
        lo = mid - 2 * sd
        res["bb_mid"] = float(mid.iloc[-1])
        res["bb_up"] = float(up.iloc[-1])
        res["bb_low"] = float(lo.iloc[-1])
        width = (up.iloc[-1] - lo.iloc[-1])
        res["bb_pctb"] = float((close.iloc[-1] - lo.iloc[-1]) / width) if width else None
    if len(d) >= 15:
        res["atr14"] = float(wilder_atr(high, low, close, 14).iloc[-1])
    last20 = d.tail(20)
    res["support20"] = float(last20["low"].min())
    res["resist20"] = float(last20["high"].max())
    imax = d["high"].idxmax()
    imin = d["low"].idxmin()
    res["hist_high"] = float(d["high"].max())
    res["hist_high_date"] = d.loc[imax, "date"]
    res["hist_low"] = float(d["low"].min())
    res["hist_low_date"] = d.loc[imin, "date"]
    res["dist_to_high_pct"] = (close.iloc[-1] / res["hist_high"] - 1) * 100
    for n, key in [(5, "ret_1w"), (21, "ret_1m"), (63, "ret_3m"), (252, "ret_12m")]:
        if len(d) > n:
            res[key] = float((close.iloc[-1] / close.iloc[-1 - n] - 1) * 100)
    ret = close.pct_change().dropna()
    res["annual_vol"] = float(ret.std(ddof=1) * math.sqrt(252) * 100) if len(ret) > 30 else None
    peak = close.cummax()
    dd = (peak - close) / peak
    res["max_dd_hist"] = float(dd.max() * 100) if len(dd) else None
    if "volume" in d and d["volume"].notna().any():
        v = d["volume"].astype(float)
        tail = d.tail(30)
        res["avg_vol30"] = float(tail["volume"].mean())
        res["avg_val30"] = float((tail["volume"] * tail["close"]).mean())
    return res


def halted_filter(df: pd.DataFrame, const_run: int = 10):
    """حذف ردیف‌های بدون معامله واقعی: حجم صفر یا قیمت ثابت طولانی‌مدت."""
    d = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
    if len(d) == 0:
        return d, 0, 0
    zero_vol = 0
    if "volume" in d and d["volume"].notna().any():
        zero_mask = (d["volume"].fillna(0) <= 0)
        zero_vol = int(zero_mask.sum())
    else:
        zero_mask = pd.Series(False, index=d.index)
    same = d["close"].diff().abs() < 1e-12
    grp = (~same).cumsum()
    run_len = same.groupby(grp).transform("sum") + 1
    const_mask = run_len >= const_run
    const_dup = const_mask & same
    keep = ~(zero_mask | const_dup)
    n_const = int(const_dup.sum())
    return d[keep].reset_index(drop=True), zero_vol, n_const


# ----------------------------------------------------------------------------
# بک‌تست (SMA20/50 + کارمزد ۰.۵٪ هر طرف + تفکیک IS/OOS)
# ----------------------------------------------------------------------------

def backtest_segment(df: pd.DataFrame, fee: float = 0.005) -> dict:
    d = df.sort_values("date").reset_index(drop=True)
    close = d["close"].astype(float)
    if len(d) < 60:
        return {"n_trades": 0, "reason": "داده ناکافی"}
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    pos = (sma20 > sma50).astype(float)
    pos_exec = pos.shift(1).fillna(0.0).values
    ret = close.pct_change().fillna(0.0).values
    changes = np.abs(np.diff(np.concatenate([[0.0], pos_exec])))
    strat = pos_exec * ret - changes * fee
    equity = np.cumprod(1 + strat)
    total_return = equity[-1] - 1 if len(equity) else None
    days = max(1, (d["date"].iloc[-1] - d["date"].iloc[0]).days)
    cagr = (equity[-1] ** (365.0 / days) - 1) if equity[-1] > 0 else None
    peak = np.maximum.accumulate(equity)
    dd = (peak - equity) / peak
    max_dd = float(dd.max()) if len(dd) else None
    sd = np.std(strat, ddof=1) if len(strat) > 1 else 0.0
    sharpe = float(np.mean(strat) / sd * math.sqrt(252)) if sd > 0 else None
    trades = []
    entry_px = None
    entry_dt = None
    for i in range(len(d)):
        if pos_exec[i] > 0 and entry_px is None:
            entry_px = close.iloc[i]
            entry_dt = d["date"].iloc[i]
        elif pos_exec[i] == 0 and entry_px is not None:
            exit_px = close.iloc[i]
            trades.append((entry_dt, d["date"].iloc[i], exit_px / entry_px - 1))
            entry_px = None
    wins = [t[2] for t in trades if t[2] > 2 * fee]
    losses = [t[2] for t in trades if t[2] <= 2 * fee]
    win_rate = (len(wins) / len(trades) * 100) if trades else None
    pf = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else None
    return {"n_trades": len(trades), "win_rate": win_rate, "profit_factor": pf,
            "total_return": (total_return * 100) if total_return is not None else None,
            "cagr": (cagr * 100) if cagr is not None else None,
            "max_dd": (max_dd * 100) if max_dd is not None else None,
            "sharpe": sharpe, "n_rows": len(d)}


def backtest_full(df: pd.DataFrame, fee: float = 0.005) -> dict:
    d = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
    if len(d) < 60:
        return {"status": "داده ناکافی", "n_rows": len(d)}
    split = int(len(d) * 0.7)
    is_df = d.iloc[:split].reset_index(drop=True)
    oos_df = d.iloc[split:].reset_index(drop=True)
    res = {"n_rows": len(d), "start": d["date"].iloc[0], "end": d["date"].iloc[-1],
           "in_sample": backtest_segment(is_df, fee), "out_sample": backtest_segment(oos_df, fee)}
    # Buy & Hold (بدون کارمزد، به‌عنوان معیار مقایسه)
    for seg, key in ((is_df, "in_sample"), (oos_df, "out_sample")):
        if len(seg) > 1:
            bh = (seg["close"].iloc[-1] / seg["close"].iloc[0] - 1) * 100
            res[key]["buy_hold"] = float(bh)
        else:
            res[key]["buy_hold"] = None
    total_tr = res["in_sample"]["n_trades"] + res["out_sample"]["n_trades"]
    res["verdict"] = ("داده ناکافی برای نتیجه‌گیری آماری" if total_tr < 3 else
                      ("نشانه Overfitting" if (res["in_sample"].get("total_return") or 0) > 5 and
                       (res["out_sample"].get("total_return") or 0) < -5 else "نسبتاً پایدار در بازه داده"))
    return res


# ----------------------------------------------------------------------------
# مدل ML (هدف: رشد ≥۲٪ در ۵ روز آینده)
# ----------------------------------------------------------------------------

def ml_features(df: pd.DataFrame):
    d = df.sort_values("date").reset_index(drop=True)
    close = d["close"].astype(float)
    f = pd.DataFrame(index=d.index)
    f["ret1"] = close.pct_change(1)
    f["ret5"] = close.pct_change(5)
    f["ret10"] = close.pct_change(10)
    f["ret20"] = close.pct_change(20)
    if len(d) >= 15:
        f["rsi14"] = wilder_rsi(close, 14)
    if len(d) >= 26:
        m = ema(close, 12) - ema(close, 26)
        f["macd_hist"] = m - m.ewm(span=9, adjust=False).mean()
    if len(d) >= 20:
        sma20 = close.rolling(20).mean()
        sma50 = close.rolling(50).mean()
        f["dist_sma20"] = close / sma20 - 1
        f["dist_sma50"] = close / sma50 - 1
        mid = close.rolling(20).mean()
        sd = close.rolling(20).std(ddof=0)
        width = 4 * sd
        f["pctB"] = (close - (mid - 2 * sd)) / width
    if "high" in d and "low" in d and len(d) >= 15:
        hi = d["high"].astype(float).fillna(close)
        lo = d["low"].astype(float).fillna(close)
        f["atr14"] = wilder_atr(hi, lo, close, 14) / close
    vol_ok = "volume" in d and d["volume"].notna().sum() > 20
    if vol_ok:
        v = d["volume"].astype(float)
        f["vol_ratio"] = v / v.rolling(20).mean()
    target = (close.shift(-5) / close - 1 >= 0.02).astype(float)
    target[close.shift(-5).isna()] = np.nan
    f["target"] = target
    f["date"] = d["date"].values
    feature_cols = [c for c in f.columns if c not in ("target", "date")]
    f = f.dropna(subset=feature_cols + ["target"]).reset_index(drop=True)
    return f, feature_cols, vol_ok


def ml_train(df: pd.DataFrame) -> dict:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score

    f, feature_cols, vol_ok = ml_features(df)
    n_total = len(f)
    ml_capped = False
    if len(f) > 2500:
        f = f.tail(2500).reset_index(drop=True)
        ml_capped = True
    n = len(f)
    if n < 150:
        return {"status": "داده ناکافی", "n": n, "vol_ok": vol_ok}
    X = f[feature_cols].values.astype(float)
    y = f["target"].values.astype(int)
    n_tr = int(n * 0.7)
    n_val = int(n * 0.15)
    Xtr, ytr = X[:n_tr], y[:n_tr]
    Xval, yval = X[n_tr:n_tr + n_val], y[n_tr:n_tr + n_val]
    Xte, yte = X[n_tr + n_val:], y[n_tr + n_val:]
    if len(Xte) < 20:
        return {"status": "داده ناکافی", "n": n, "n_total": n_total, "vol_ok": vol_ok}
    if len(set(ytr)) < 2 or len(set(yte)) < 2:
        return {"status": "داده ناکافی", "n": n, "n_total": n_total, "vol_ok": vol_ok,
                "note": "کلاس هدف در بازه آموزش یا آزمون تک‌مقداری است"}
    mu, sd = Xtr.mean(axis=0), Xtr.std(axis=0)
    sd[sd == 0] = 1.0
    Xtr_s, Xval_s, Xte_s = (Xtr - mu) / sd, (Xval - mu) / sd, (Xte - mu) / sd

    def met(model, Xt, yt):
        pred = model.predict(Xt)
        out = {"accuracy": float(accuracy_score(yt, pred)),
               "precision": float(precision_score(yt, pred, zero_division=0)),
               "recall": float(recall_score(yt, pred, zero_division=0)),
               "f1": float(f1_score(yt, pred, zero_division=0))}
        try:
            prob = model.predict_proba(Xt)[:, 1]
            out["auc"] = float(roc_auc_score(yt, prob)) if len(set(yt)) > 1 else None
        except Exception:
            out["auc"] = None
        return out

    lr = LogisticRegression(max_iter=2000, class_weight="balanced")
    lr.fit(Xtr_s, ytr)
    rf = RandomForestClassifier(n_estimators=120, max_depth=6, min_samples_leaf=10,
                                random_state=42, n_jobs=1, class_weight="balanced_subsample")
    rf.fit(Xtr, ytr)
    base = float(max(np.mean(yte), 1 - np.mean(yte))) if len(yte) else None
    importances = sorted(zip(feature_cols, rf.feature_importances_, strict=False), key=lambda t: t[1], reverse=True)
    return {
        "status": "ok", "n": n, "n_total": n_total, "ml_capped": ml_capped,
        "n_train": n_tr, "n_val": n_val, "n_test": len(Xte),
        "class_balance": float(np.mean(y)), "baseline": base,
        "lr_test": met(lr, Xte_s, yte), "rf_test": met(rf, Xte, yte),
        "top_features": importances[:5], "vol_ok": vol_ok,
    }


# ----------------------------------------------------------------------------
# بارگذاری منابع فایل‌محور
# ----------------------------------------------------------------------------

def load_history_file(path: Path):
    try:
        with open(path, encoding="utf-8") as fh:
            arr = json.load(fh)
        rows = []
        for r in arr:
            gd = jdate_to_greg(r.get("date", ""))
            if gd is None:
                continue
            try:
                rows.append(dict(date=pd.Timestamp(gd), open=float(r.get("open")), high=float(r.get("high")),
                                 low=float(r.get("low")), close=float(r.get("close")),
                                 volume=float(r["volume"]) if r.get("volume") is not None else np.nan))
            except Exception:
                continue
        df = pd.DataFrame(rows).drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
        df = clean_ohlc(df)
        return df
    except Exception:
        return pd.DataFrame()


def load_tick_file(path: Path):
    try:
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            df = pd.read_csv(fh)
        for c in ["price", "volume"]:
            if c in df:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        if "canceled" in df:
            df["canceled"] = df["canceled"].astype(str).str.lower().isin(["true", "1", "yes"])
        return df.dropna(subset=["price"])
    except Exception:
        return pd.DataFrame()


# ----------------------------------------------------------------------------
# Hub داده
# ----------------------------------------------------------------------------

class DataHub:
    def __init__(self, conn, table_syms=None):
        self.conn = conn
        self.table_syms = table_syms or {}
        with contextlib.suppress(Exception), conn.cursor() as c:
            c.execute("set statement_timeout = '25000'")
        self.details = pd.read_sql_query("select * from brsapi_symbol_details", conn)
        if "fetched_at" in self.details:
            self.details = self.details.sort_values("fetched_at")
        self.details_latest = self.details.groupby("symbol", as_index=False).tail(1)
        self.screener = pd.read_sql_query("select * from screener_profiles", conn)
        self.screener = self.screener.drop_duplicates(subset=["symbol"], keep="last")
        self.audit = pd.read_sql_query("select * from codal_audit_summary", conn)
        self.audit = self.audit.drop_duplicates(subset=["symbol"], keep="last")
        self.nav_all = pd.read_sql_query("select symbol, nav_issue, nav_redemption, date, time from brsapi_nav_records", conn)
        # سامانه امتیازدهی اختصاصی کاربر (خروجی خام سیستم ایشان)
        try:
            self.user_scores = pd.read_sql_query(
                "select distinct on (symbol) symbol, trade_date, score_total, score_momentum, score_value, "
                "score_growth, score_quality, score_liquidity, score_sentiment, rank_in_market, "
                "rank_in_industry, percentile_score, raw_scores from screener_daily_scores "
                "order by symbol, calculated_at desc", conn)
        except Exception:
            self.user_scores = pd.DataFrame()
        try:
            self.user_signals = pd.read_sql_query("select * from screener_signals", conn)
            self.user_signals = self.user_signals.drop_duplicates(subset=["symbol"], keep="last")
        except Exception:
            self.user_signals = pd.DataFrame()
        # بازدهی ۱۲ماهه گروهی (یک‌بار برای کل نمادها از سری تعدیل‌شده)
        self.ret12 = {}
        with contextlib.suppress(Exception):
            df = pd.read_sql_query(
                "with ranked as (select symbol, close, row_number() over (partition by symbol order by gregorian_date desc) rn "
                "from candlesticks where candle_type='3') "
                "select symbol, max(case when rn=1 then close end) c1, max(case when rn=252 then close end) c252 "
                "from ranked where rn in (1,252) group by symbol", conn)
            for _, r in df.iterrows():
                try:
                    if r["c1"] and r["c252"]:
                        self.ret12[r["symbol"]] = (float(r["c1"]) / float(r["c252"]) - 1) * 100
                except Exception:
                    continue
        # ماتریس هم‌گروهی
        pm = self.details_latest[["symbol", "sector", "market_value", "pe_ratio", "eps", "price_close"]].copy()
        scr_cols = [c for c in ["symbol", "industry", "industry_pe", "eps_current"] if c in self.screener.columns]
        pm = pm.merge(self.screener[scr_cols], on="symbol", how="left")
        aud_cols = [c for c in ["symbol", "net_margin", "revenue_growth", "net_profit_growth", "roe", "roa"] if c in self.audit.columns]
        pm = pm.merge(self.audit[aud_cols], on="symbol", how="left")
        pm["ret12"] = pm["symbol"].map(self.ret12)
        self.peer_metrics = pm
        self.quotes_symbols = set(pd.read_sql_query("select distinct symbol from quotes", conn)["symbol"])
        self._cache = {}

    def latest_details_row(self, symbol):
        row = self.details_latest[self.details_latest["symbol"] == symbol]
        return row.iloc[0].to_dict() if len(row) else {}

    def screener_row(self, symbol):
        row = self.screener[self.screener["symbol"] == symbol]
        return row.iloc[0].to_dict() if len(row) else {}

    def audit_row(self, symbol):
        row = self.audit[self.audit["symbol"] == symbol]
        return row.iloc[0].to_dict() if len(row) else {}

    def nav_rows(self, symbol):
        r = self.nav_all[self.nav_all["symbol"] == symbol].copy()
        if len(r) == 0:
            return r
        r["date"] = r["date"].astype(str)
        r = r.drop_duplicates(subset=["date"]).sort_values("date", ascending=False)
        return r

    def sector_rank(self, symbol, sector):
        if not sector:
            return None, None, 0
        d = self.details_latest[self.details_latest["sector"] == sector]
        d = d[d["market_value"].notna()].sort_values("market_value", ascending=False).reset_index(drop=True)
        if symbol not in set(d["symbol"]):
            return None, None, len(d)
        idx = int(d.index[d["symbol"] == symbol][0]) + 1
        return idx, len(d), d["market_value"].iloc[idx - 1]

    def user_system_row(self, symbol, variants=()):
        names = {symbol, *variants}
        row = {}
        if len(self.user_scores):
            m = self.user_scores[self.user_scores["symbol"].isin(names)]
            if len(m):
                row["daily"] = m.iloc[0].to_dict()
        if len(self.user_signals):
            m = self.user_signals[self.user_signals["symbol"].isin(names)]
            if len(m):
                row["signal"] = m.iloc[0].to_dict()
        return row

    def peer_table(self, symbol, sector, n=10):
        if self.peer_metrics is None or not len(self.peer_metrics) or not sector:
            return []
        d = self.peer_metrics[self.peer_metrics["sector"] == sector].copy()
        if "market_value" not in d.columns:
            return []
        d = d[d["market_value"].notna()].sort_values("market_value", ascending=False)
        rows = d.head(n).to_dict("records")
        if symbol not in [r["symbol"] for r in rows]:
            me = self.peer_metrics[self.peer_metrics["symbol"] == symbol].to_dict("records")
            rows = me + rows
        return rows[: n + 1]

    def peer_pe_mean(self, sector, symbol=None):
        if self.peer_metrics is None or not len(self.peer_metrics) or not sector:
            return None, 0
        d = self.peer_metrics[self.peer_metrics["sector"] == sector]
        vals = pd.to_numeric(d["pe_ratio"], errors="coerce")
        vals = vals[vals > 0]
        if len(vals) == 0:
            return None, 0
        return float(vals.mean()), int(len(vals))

    def fetch(self, key, symbol, variants):
        variants = list({symbol, *variants})
        cur = self.conn.cursor()
        out = {}

        def has(table):
            s = self.table_syms.get(table)
            if s is None:
                return True
            return any(v in s for v in variants)

        if has("candlesticks"):
            with contextlib.suppress(Exception):
                cur.execute(
                    "select gregorian_date, open, high, low, close, volume, candle_type "
                    "from candlesticks where symbol = any(%s) and candle_type in ('2','3') order by gregorian_date",
                    (variants,))
                rows = cur.fetchall()
                if rows:
                    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume", "ctype"])
                    df["date"] = pd.to_datetime(df["date"])
                    df = clean_ohlc(df)
                    out["candles_adj"] = df[df["ctype"] == "3"][["date", "open", "high", "low", "close", "volume"]].drop_duplicates("date").reset_index(drop=True)
                    out["candles_raw"] = df[df["ctype"] == "2"][["date", "open", "high", "low", "close", "volume"]].drop_duplicates("date").reset_index(drop=True)
        if has("quotes"):
            with contextlib.suppress(Exception):
                cur.execute(
                    "select gregorian_date, time, price_open, price_high, price_low, price_close, price_last, "
                    "volume, value, trade_count from quotes where symbol = any(%s) order by gregorian_date, time",
                    (variants,))
                rows = cur.fetchall()
                if rows:
                    q = pd.DataFrame(rows, columns=["date", "time", "open", "high", "low", "close", "last", "volume", "value", "trade_count"])
                    q["date"] = pd.to_datetime(q["date"])
                    q["last"] = pd.to_numeric(q["last"], errors="coerce")
                    q.loc[q["last"] <= 0, "last"] = np.nan
                    q = clean_ohlc(q, drop_close=False)
                    out["quotes"] = q[q["last"].notna()].reset_index(drop=True)
        if has("snapshots"):
            with contextlib.suppress(Exception):
                cur.execute(
                    "select time, fetched_at, price_last, price_close, price_first, price_yesterday, price_min, price_max, "
                    "trade_count, trade_volume, trade_value, buy_real_count, sell_real_count, buy_real_volume, sell_real_volume, "
                    "bid_price_1, bid_volume_1, bid_price_5, bid_volume_5, ask_price_1, ask_volume_1, ask_price_5, ask_volume_5, "
                    "gregorian_date "
                    "from brsapi_symbol_snapshots where symbol = any(%s) order by fetched_at desc limit 1",
                    (variants,))
                rows = cur.fetchall()
                if rows:
                    cols = ["time", "fetched_at", "price_last", "price_close", "price_first", "price_yesterday",
                            "price_min", "price_max", "trade_count", "trade_volume", "trade_value",
                            "buy_real_count", "sell_real_count", "buy_real_volume", "sell_real_volume",
                            "bid_price_1", "bid_volume_1", "bid_price_5", "bid_volume_5", "ask_price_1",
                            "ask_volume_1", "ask_price_5", "ask_volume_5", "gregorian_date"]
                    out["snapshot"] = dict(zip(cols, rows[0], strict=False))
        if has("real_legal"):
            with contextlib.suppress(Exception):
                cur.execute(
                    "select date, buy_real_count, sell_real_count, buy_legal_count, sell_legal_count, "
                    "buy_real_volume, sell_real_volume, buy_legal_volume, sell_legal_volume, "
                    "buy_real_value, sell_real_value, buy_legal_value, sell_legal_value "
                    "from brsapi_historical_real_legal where symbol = any(%s) order by date desc limit 25",
                    (variants,))
                rows = cur.fetchall()
                if rows:
                    cols = ["date", "buy_real_count", "sell_real_count", "buy_legal_count", "sell_legal_count",
                            "buy_real_volume", "sell_real_volume", "buy_legal_volume", "sell_legal_volume",
                            "buy_real_value", "sell_real_value", "buy_legal_value", "sell_legal_value"]
                    out["real_legal"] = pd.DataFrame(rows, columns=cols)
        if has("shareholders"):
            with contextlib.suppress(Exception):
                cur.execute(
                    "select shareholder_name, volume, percent, change, date from brsapi_shareholder_records "
                    "where symbol = any(%s) order by date desc, percent desc limit 60",
                    (variants,))
                rows = cur.fetchall()
                if rows:
                    out["shareholders"] = pd.DataFrame(rows, columns=["name", "volume", "percent", "change", "date"])
        if has("announcements"):
            with contextlib.suppress(Exception):
                cur.execute(
                    "select date_publish, date_send, time_publish, title, code, link_pdf, link "
                    "from brsapi_codal_announcements where symbol = any(%s) order by date_publish desc, time_publish desc limit 15",
                    (variants,))
                rows = cur.fetchall()
                if rows:
                    out["announcements"] = pd.DataFrame(rows, columns=["publish", "send", "time", "title", "code", "pdf", "link"])
        if has("gold_daily"):
            with contextlib.suppress(Exception):
                cur.execute(
                    "select date, price_open, price_high, price_low, price_close, null::bigint as volume "
                    "from brsapi_gold_currency_pro_daily_history where symbol = any(%s)",
                    (variants,))
                rows = cur.fetchall()
                if rows:
                    df = pd.DataFrame(rows, columns=["jdate", "open", "high", "low", "close", "volume"])
                    df["date"] = df["jdate"].map(lambda v: jdate_to_greg(str(v)))
                    df = df.dropna(subset=["date"])
                    df["date"] = pd.to_datetime(df["date"])
                    out["extra_daily"] = clean_ohlc(df[["date", "open", "high", "low", "close", "volume"]]).drop_duplicates("date", keep="last")
        if has("crypto_daily"):
            with contextlib.suppress(Exception):
                cur.execute(
                    "select date, price_open, price_high, price_low, price_close, volume "
                    "from brsapi_crypto_daily_history where symbol = any(%s)",
                    (variants,))
                rows = cur.fetchall()
                if rows:
                    df = pd.DataFrame(rows, columns=["jdate", "open", "high", "low", "close", "volume"])
                    df["date"] = df["jdate"].map(lambda v: jdate_to_greg(str(v)))
                    df = df.dropna(subset=["date"])
                    df["date"] = pd.to_datetime(df["date"])
                    df = clean_ohlc(df[["date", "open", "high", "low", "close", "volume"]]).drop_duplicates("date", keep="last")
                    out["extra_daily"] = df if "extra_daily" not in out else pd.concat([out["extra_daily"], df])
        return out


# ----------------------------------------------------------------------------
# سازنده متن صفحه
# ----------------------------------------------------------------------------

class Page:
    def __init__(self, symbol):
        self.symbol = symbol
        self.lines = [f"# صفحه اختصاصی نماد — {symbol}", ""]
        self.unknown = 0
        self.missing_fields = []

    def h(self, text):
        self.lines.append(text)
        self.lines.append("")

    def p(self, text=""):
        self.lines.append(text)

    def u(self, text=UNKNOWN):
        self.unknown += 1
        return text

    def n(self, text=NOT_COMPUTABLE):
        self.unknown += 1
        return text

    def m(self, label, text=UNKNOWN):
        self.missing_fields.append(str(label))
        self.unknown += 1
        return text

    def render(self):
        return "\n".join(self.lines) + "\n"


# ----------------------------------------------------------------------------
# ترکیب داده‌های نماد
# ----------------------------------------------------------------------------

def merge_series(candles_adj=None, candles_raw=None, quotes=None, file_daily=None, extra_daily=None):
    """ساخت سری روزانه: سری تعدیل‌شده/فایل + الحاق داده‌های جدیدتر (quotes / دیتابیس)."""

    def norm_frame(df):
        if df is None or len(df) == 0:
            return None
        out = clean_ohlc(df[["date", "open", "high", "low", "close", "volume"]].copy())
        if out is None or len(out) == 0:
            return None
        return out.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)

    base = None
    for cand, tag in ((candles_adj, "candles_adj"), (file_daily, "file"), (extra_daily, "db_daily")):
        f = norm_frame(cand)
        if f is not None and len(f):
            base = f.assign(src=tag)
            break
    if base is None:
        base = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "src"])
    last_dt = base["date"].max() if len(base) else None
    exts = []
    if quotes is not None and len(quotes):
        q = quotes.copy()
        q = q[["date", "open", "high", "low", "last", "volume"]].rename(columns={"last": "close"})
        q = q.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
        if last_dt is not None:
            q = q[q["date"] > last_dt]
        if len(q):
            exts.append(q.assign(src="quotes"))
    if extra_daily is not None and len(extra_daily) and base is not None and len(base):
        ed = norm_frame(extra_daily)
        if ed is not None and last_dt is not None:
            ed = ed[ed["date"] > last_dt]
        if len(ed):
            exts.append(ed.assign(src="db_daily"))
    full = pd.concat([base, *exts], ignore_index=True) if exts else base.copy()
    full = full.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
    raw = norm_frame(candles_raw)
    return full, raw


def signal_words(text: str):
    t = str(text or "")
    pos = ["افزایش سرمایه", "سود نقدی", "تقسیم سود", "بازگشایی", "رشد", "افزایش تولید", "قرارداد", "پیشرفت"]
    neg = ["زیان", "توقف", "کاهش", "لغو", "تاخیر", "تأخیر", "جریمه", "اختلاف", "ممنوع"]
    if any(w in t for w in pos):
        return "مثبت بنیادی (تشخیص کلیدواژه‌ای)"
    if any(w in t for w in neg):
        return "منفی بنیادی (تشخیص کلیدواژه‌ای)"
    return "نامشخص"


def effect_words(text: str):
    t = str(text or "")
    if any(w in t for w in ["افزایش سرمایه", "سود نقدی", "تقسیم سود", "بازگشایی"]):
        return "مثبت بنیادی (تشخیص کلیدواژه‌ای)"
    if any(w in t for w in ["زیان", "توقف", "لغو", "جریمه", "ممنوع", "کاهش سرمایه"]):
        return "منفی بنیادی (تشخیص کلیدواژه‌ای)"
    if any(w in t for w in ["صورت‌های مالی", "گزارش فعالیت", "اطلاعات و صورت", "مجمع", "نرخ"]):
        return "خنثی/اطلاعاتی (تشخیص کلیدواژه‌ای)"
    return "نامشخص"


def compose_page(symbol, hub: DataHub, sources: list, data: dict, detection_note: dict) -> tuple[str, dict]:
    p = Page(symbol)
    det = data.get("details", {})
    scr = data.get("screener", {})
    audit = data.get("audit", {})
    snap = data.get("snapshot", {}) or {}
    series = data.get("series")
    raw_series = data.get("raw_series")
    ticks = data.get("ticks")
    tech = data.get("technical", {})
    bt = data.get("backtest", {})
    ml = data.get("ml", {})
    cat = data.get("category", "سایر")
    is_fund = data.get("is_fund", False)

    name = det.get("name") or scr.get("name") or symbol
    name_en = det.get("name_en")
    isin = det.get("isin") or scr.get("isin")
    sector = det.get("sector") or scr.get("industry")
    sub_sector = det.get("sub_sector") or scr.get("sub_industry")
    market = det.get("market")
    board = det.get("board")
    shares = det.get("shares_count")
    price_src_note = data.get("price_note", UNKNOWN)

    p.p(f"> دسته دارایی: **{cat}** | منبع سری قیمت: {price_src_note} | تعداد ردیف داده روزانه معتبر: "
        f"{fmt_num(tech.get('n_rows') if tech else None, 0)} | تولید: {now_tehran().strftime('%Y-%m-%d %H:%M')}")
    p.p()

    # ۱ شناسنامه
    non_corp = cat in ("طلا/ارز/سکه", "کریپتو")
    p.h("## ۱. شناسنامه نماد")
    p.p(bullet("نام کامل شرکت", name or (p.u(NOT_APPLICABLE) if non_corp else p.u())))
    p.p(bullet("نماد فارسی", symbol))
    p.p(bullet("نماد لاتین", det.get("code_4") or det.get("code_5") or (symbol if non_corp else p.u())))
    p.p(bullet("کد ISIN", isin or (p.u(NOT_APPLICABLE) if non_corp else p.u())))
    p.p(bullet("صنعت", sector or (p.u(NOT_APPLICABLE) if non_corp else p.u())))
    p.p(bullet("زیرصنعت", sub_sector or (p.u(NOT_APPLICABLE) if non_corp else p.u())))
    p.p(bullet("بازار", market or (p.u(NOT_APPLICABLE) if non_corp else p.u())))
    p.p(bullet("تابلو", board or (p.u(NOT_APPLICABLE) if non_corp else p.u())))
    p.p(bullet("تاریخ پذیرش", p.u(NOT_APPLICABLE) if non_corp else p.m("تاریخ پذیرش")))
    if shares:
        cap_btom = float(shares) * 1000 / 1e10
        p.p(bullet("سرمایه ثبتی (میلیارد تومان)",
                   f"{fmt_num(cap_btom)} — محاسبه: {fmt_num(shares,0)} سهم × ارزش اسمی ۱۰۰۰ ریال "
                   f"(**فرض محاسباتی**؛ ارزش اسمی در داده ورودی نیست)"))
    else:
        p.p(bullet("سرمایه ثبتی (میلیارد تومان)", p.u(NOT_APPLICABLE) if non_corp else p.m("سرمایه ثبتی")))
    p.p(bullet("تعداد کل سهام", fmt_num(shares, 0) if shares else (p.u(NOT_APPLICABLE) if non_corp else p.u())))
    ff = det.get("free_float_pct")
    if ff is None:
        p.p(bullet("درصد سهام شناور آزاد", p.u(NOT_APPLICABLE) if non_corp else p.m("سهام شناور آزاد")))
    elif float(ff) == 0:
        p.p(bullet("درصد سهام شناور آزاد", p.m("سهام شناور آزاد", "۰٪ ثبت‌شده در منبع — احتمالاً نامشخص")))
    else:
        p.p(bullet("درصد سهام شناور آزاد", f"{fmt_num(ff)}٪"))

    # ۲ وضعیت درون‌روز
    p.h("## ۲. وضعیت درون‌روز")
    if ticks is not None and len(ticks):
        t = ticks.dropna(subset=["price"]).copy()
        if "canceled" in t:
            canceled = int(t["canceled"].sum())
            t = t[~t["canceled"]]
        else:
            canceled = p.u()
        if len(t):
            t["volume"] = t["volume"].fillna(0)
            vwap = float((t["price"] * t["volume"]).sum() / t["volume"].sum()) if t["volume"].sum() else None
            p.p(bullet("آخرین قیمت لحظه‌ای", f"{fmt_num(t['price'].iloc[-1])} (تاریخ جلسه: {data.get('tick_date') or UNKNOWN})"))
            p.p(bullet("زمان آخرین بروزرسانی", str(t["time"].iloc[-1]) if "time" in t else p.u()))
            p.p(bullet("بازه زمانی داده", f"{t['time'].iloc[0]} تا {t['time'].iloc[-1]}" if "time" in t else p.u()))
            p.p(bullet("کمینه/بیشینه قیمت جلسه", f"{fmt_num(t['price'].min())} / {fmt_num(t['price'].max())}"))
            p.p(bullet("VWAP جلسه", fmt_num(vwap)))
            p.p(bullet("حجم و ارزش معاملات جلسه", f"{fmt_num(t['volume'].sum(),0)} سهم / {fmt_num((t['price']*t['volume']).sum(),0)} ریال"))
            p.p(bullet("تیک‌های باطل‌شده", fmt_num(canceled, 0)))
            p.p(bullet("بهترین قیمت و حجم صف خرید", p.m("صف خرید (داده سفارش موجود نیست)")))
            p.p(bullet("بهترین قیمت و حجم صف فروش", p.m("صف فروش (داده سفارش موجود نیست)")))
            p.p(bullet("وضعیت صف", p.m("وضعیت صف", "قابل تشخیص نیست (ردیف سفارش در داده درون‌روز فایل موجود نیست)")))
        else:
            p.p(bullet("آخرین قیمت لحظه‌ای", p.u()))
    else:
        last_px = snap.get("price_last") or det.get("price_close")
        upd = f"{snap.get('gregorian_date') or det.get('date') or ''} {snap.get('time') or det.get('time') or ''}".strip()
        p.p(bullet("آخرین قیمت لحظه‌ای", fmt_num(last_px) if last_px else p.u()))
        p.p(bullet("زمان آخرین بروزرسانی", upd or p.u()))
        bid1, bv1 = snap.get("bid_price_1"), snap.get("bid_volume_1")
        ask1, av1 = snap.get("ask_price_1"), snap.get("ask_volume_1")
        hi_lim, lo_lim = det.get("price_highest_allowed"), det.get("price_lowest_allowed")
        if bid1 or ask1:
            queue = "تعادل/نامشخص"
            if hi_lim and bid1 == hi_lim and (not av1 or av1 == 0):
                queue = "صف خرید فعال (به‌استناد بهترین تقاضا=سقف مجاز و نبود عرضه)"
            elif lo_lim and ask1 == lo_lim and (not bv1 or bv1 == 0):
                queue = "صف فروش فعال (به‌استناد بهترین عرضه=کف مجاز و نبود تقاضا)"
            p.p(bullet("بهترین قیمت و حجم صف خرید", f"{fmt_num(bid1)} / {fmt_num(bv1,0)} تام" if bid1 else NOT_COMPUTABLE))
            p.p(bullet("بهترین قیمت و حجم صف فروش", f"{fmt_num(ask1)} / {fmt_num(av1,0)} تام" if ask1 else NOT_COMPUTABLE))
            p.p(bullet("وضعیت صف", queue + " — **روش تشخیص خودکار بر پایه سقف/کف مجاز و حجم‌های سفارش**"))
        else:
            p.p(bullet("بهترین قیمت و حجم صف خرید", p.m("صف خرید")))
            p.p(bullet("بهترین قیمت و حجم صف فروش", p.m("صف فروش")))
            p.p(bullet("وضعیت صف", p.m("وضعیت صف")))
        vol = snap.get("trade_volume") or det.get("trade_volume")
        cnt = snap.get("trade_count") or det.get("trade_count")
        val = snap.get("trade_value") or det.get("trade_value")
        p.p(bullet("حجم و تعداد معاملات امروز", f"{fmt_num(vol,0)} سهم / {fmt_num(cnt,0)} معامله / {fmt_num(val,0)} ریال"
                   if (vol or cnt) else p.u()))

    # ۳ وضعیت بازار و کدال
    p.h("## ۳. وضعیت بازار و کدال")
    state = det.get("state") or p.u()
    p.p(bullet("وضعیت نماد", state))
    ann = data.get("announcements")
    titles = [str(x) for x in ann["title"].tolist()] if ann is not None and "title" in ann else []
    halt = [x for x in titles if "توقف" in x]
    resume = [x for x in titles if "بازگشایی" in x]
    superv = [x for x in titles if "نظارت" in x]
    p.p(bullet("دلیل توقف در صورت وجود", halt[0] if halt else p.m("دلیل توقف")))
    p.p(bullet("نماد تحت نظارت است؟", (superv[0] if superv else p.m("وضعیت نظارت"))))
    p.p(bullet("آخرین بازگشایی/توقف با تاریخ",
               (resume[0] if resume else (halt[0] if halt else p.m("آخرین بازگشایی/توقف")))))
    if ann is not None and len(ann):
        p.p("**۵ اطلاعیه اخیر کدال:**")
        rows = []
        for _, r in ann.head(5).iterrows():
            rows.append([r["publish"], str(r["title"])[:110]])
        p.p(md_table(["تاریخ", "موضوع"], rows))
    else:
        p.p(f"**۵ اطلاعیه اخیر کدال:** {p.m('اطلاعیه‌های کدال')}")
    p.p(bullet("گروه صنعت دقیق", f"{sector or '—'} / {sub_sector or '—'}"))
    rank, total, mv = hub.sector_rank(det.get("symbol") or symbol, sector)
    if rank:
        p.p(bullet("رتبه در صنعت بر مبنای ارزش بازار", f"{rank} از {total} نماد (ارزش بازار: {fmt_num(mv,0)} ریال)"))
    else:
        p.p(bullet("رتبه در صنعت بر مبنای ارزش بازار", p.m("رتبه صنعت")))

    # ۴ تکنیکال
    p.h("## ۴. قیمت و اندیکاتورهای تکنیکال")
    unit = "دلار" if (cat == "کریپتو" or str(symbol).upper() == "XAUUSD") else "ریال"
    p.p(f"**واحد قیمت این نماد در داده ورودی: {unit}**")
    if tech:
        p.p(bullet("تاریخ و قیمت آخرین روز", f"{tech['last_date'].date() if hasattr(tech['last_date'], 'date') else tech['last_date']} — {fmt_num(tech['close'])} {unit}"))
        p.p(bullet("درصد تغییر روزانه", fmt_pct(tech.get("chg_pct"))))
        for n in (20, 50):
            v = tech.get(f"sma{n}")
            if v:
                rel = "بالای" if tech["close"] > v else "زیر"
                p.p(bullet(f"SMA{n}", f"{fmt_num(v)} {unit} — قیمت {rel} آن است"))
            else:
                p.p(bullet(f"SMA{n}", p.m(f"SMA{n}", f"{NOT_COMPUTABLE} (تعداد ردیف کافی نیست)")))
        rsi = tech.get("rsi14")
        if rsi is not None:
            interp = "اشباع خرید" if rsi > 70 else ("اشباع فروش" if rsi < 30 else "ناحیه خنثی")
            p.p(bullet("RSI14 (وایلدر)", f"{fmt_num(rsi)} — تفسیر: {interp}"))
        else:
            p.p(bullet("RSI14", p.u()))
        if tech.get("macd") is not None:
            acc = "صعودی" if tech["macd_hist"] >= 0 else "نزولی"
            chg = ""
            if tech.get("macd_hist_prev") is not None:
                chg = "، شتاب در حال افزایش" if tech["macd_hist"] > tech["macd_hist_prev"] else "، شتاب در حال کاهش"
            p.p(bullet("MACD / Signal / Histogram", f"{fmt_num(tech['macd'])} / {fmt_num(tech['macd_signal'])} / {fmt_num(tech['macd_hist'])} — جهت {acc}{chg}"))
        else:
            p.p(bullet("MACD / Signal / Histogram", p.u()))
        if tech.get("bb_up") is not None:
            p.p(bullet("Bollinger (Upper/Middle/Lower)", f"{fmt_num(tech['bb_up'])} / {fmt_num(tech['bb_mid'])} / {fmt_num(tech['bb_low'])}"))
            p.p(bullet("درصد %B", fmt_num(tech.get("bb_pctb"), 3)))
        else:
            p.p(bullet("Bollinger", p.u()))
        p.p(bullet("ATR14 (وایلدر)", fmt_num(tech.get("atr14")) if tech.get("atr14") is not None else p.u()))
        p.p(bullet("حمایت و مقاومت نزدیک (۲۰ کندل)", f"{fmt_num(tech.get('support20'))} / {fmt_num(tech.get('resist20'))}"
                   if tech.get("support20") is not None else p.u()))
        if tech.get("hist_high") is not None:
            p.p(bullet("سقف و کف تاریخی بازه داده",
                       f"سقف {fmt_num(tech['hist_high'])} در {tech['hist_high_date'].date() if hasattr(tech['hist_high_date'],'date') else tech['hist_high_date']}"
                       f" | کف {fmt_num(tech['hist_low'])} در {tech['hist_low_date'].date() if hasattr(tech['hist_low_date'],'date') else tech['hist_low_date']}"))
            p.p(bullet("فاصله تا سقف تاریخی", fmt_pct(tech.get("dist_to_high_pct"))))
        for key, lab in [("ret_1w", "بازدهی ۱ هفته"), ("ret_1m", "بازدهی ۱ ماه"), ("ret_3m", "بازدهی ۳ ماه")]:
            p.p(bullet(lab, fmt_pct(tech.get(key)) if tech.get(key) is not None else p.u()))
        p.p(bullet("میانگین حجم و ارزش معاملات ۳۰ روزه",
                   f"{fmt_num(tech.get('avg_vol30'),0)} سهم / {fmt_num(tech.get('avg_val30'),0)} {unit}"
                   if tech.get("avg_vol30") is not None else p.u()))
        p.p(bullet("ردیف‌های حذف‌شده از محاسبات تکنیکال", data.get("halt_note", UNKNOWN)))
    else:
        p.p(f"**داده قیمت روزانه کافی برای محاسبات تکنیکال موجود نیست.** ({p.m('اندیکاتورهای تکنیکال')})")

    # ۵ عملکرد مالی
    p.h("## ۵. عملکرد مالی")
    fin_row = None
    if audit:
        rev = audit.get("revenue")
        npf = audit.get("net_profit")
        ta = audit.get("total_assets")
        te = audit.get("total_equity")
        if any(v is not None for v in [rev, npf, ta, te]):
            eps = audit.get("eps")
            gm = audit.get("gross_margin") if (rev is not None and audit.get("gross_margin") is not None) else p.u()
            om = p.n("حاشیه عملیاتی (سود عملیاتی در داده نیست)")
            if rev and npf is not None and rev != 0:
                nm = npf / rev * 100
            else:
                nm = p.u()
            roe = audit.get("roe") if (npf is not None and te) else p.u()
            roa = audit.get("roa") if (npf is not None and ta) else p.u()
            d2e = audit.get("debt_to_equity")
            debt_ratio = p.u()
            cr = audit.get("current_ratio")
            ic = audit.get("interest_coverage")
            fin_row = [audit.get("report_date") or p.u(), fmt_num(rev, 0), p.u(), p.n(), fmt_num(npf, 0), fmt_num(eps),
                       fmt_num(gm) if isinstance(gm, (int, float)) else gm, fmt_num(om), fmt_num(nm) if isinstance(nm, (int, float)) else nm,
                       fmt_num(audit.get("revenue_growth")), fmt_num(audit.get("net_profit_growth")),
                       fmt_num(roe) if isinstance(roe, (int, float)) else roe, fmt_num(roa) if isinstance(roa, (int, float)) else roa,
                       fmt_num(debt_ratio), fmt_num(d2e) if d2e not in (None,) else p.u(),
                       fmt_num(cr) if cr not in (None,) else p.u(), fmt_num(ic) if ic is not None else p.u()]
    if fin_row:
        p.p(md_table(["دوره", "درآمد عملیاتی", "سود ناخالص", "سود عملیاتی", "سود خالص", "EPS", "حاشیه ناخالص٪",
                      "حاشیه عملیاتی٪", "حاشیه خالص٪", "رشد درآمد YoY٪", "رشد سود خالص YoY٪", "ROE٪", "ROA٪",
                      "نسبت بدهی٪", "نسبت جاری", "پوشش هزینه مالی"], [fin_row]))
        p.p("منبع: جدول تحلیل پارسر کدال (`codal_audit_summary`)؛ اقلام ناقص با «نامشخص» درج شده و اعداد به‌صورت خام منبع آورده شده‌اند (درجه اطمینان: پایین).")
    else:
        p.p(md_table(["دوره", "درآمد عملیاتی", "سود ناخالص", "سود عملیاتی", "سود خالص", "EPS", "حاشیه ناخالص٪",
                      "حاشیه عملیاتی٪", "حاشیه خالص٪", "رشد درآمد YoY٪", "رشد سود خالص YoY٪", "ROE٪", "ROA٪",
                      "نسبت بدهی٪", "نسبت جاری", "پوشش هزینه مالی"],
                     [[p.u(), p.u(), p.u(), p.n(), p.u(), p.u(), p.u(), p.n(), p.u(), p.u(), p.u(), p.u(), p.u(), p.u(), p.u(), p.n()]]))
        p.p("داده صورت‌های مالی معتبر و کامل در ورودی موجود نیست؛ بنابراین نسبت‌های مالی «نامشخص» هستند و هیچ عدد جایگزینی ساخته نشده است.")

    # ۶ ارزش‌گذاری
    p.h("## ۶. ارزش‌گذاری")
    px = None
    if tech.get("close"):
        px = tech["close"]
    elif snap.get("price_last"):
        px = float(snap["price_last"])
    eps = det.get("eps") or scr.get("eps_current")
    if px and eps and float(eps) > 0:
        p.p(bullet("P/E محاسبه‌شده", f"{fmt_num(px / float(eps))} — قیمت {fmt_num(px)} ÷ EPS {fmt_num(eps)} (**EPS اعلامی منبع، نه لزوماً TTM**)"))
    else:
        p.p(bullet("P/E (TTM)", p.n("EPS مثبت/کافی برای محاسبه در داده نیست")))
    p.p(bullet("P/E اعلامی منبع", fmt_num(det.get("pe_ratio")) if det.get("pe_ratio") is not None else p.u()))
    p.p(bullet("P/B", p.n("حقوق صاحبان سهام و واحد آن در داده ورودی قابل اتکا نیست")))
    p.p(bullet("P/S", fmt_num(det.get("ps_ratio")) if det.get("ps_ratio") not in (None, 0) else p.u()))
    p.p(bullet("EV", p.n("نیاز به بدهی مالی و نقدینگی")))
    p.p(bullet("EV/EBITDA", p.n("نیاز به استهلاک و بدهی مالی")))
    if is_fund:
        nav_rows = data.get("nav_rows")
        if nav_rows is not None and len(nav_rows):
            latest = nav_rows.iloc[0]
            nav_red = latest.get("nav_redemption")
            if px and nav_red:
                bubble = (float(px) / float(nav_red) - 1) * 100
                p.p(bullet("NAV هر سهم و P/NAV", f"NAV ابطال {fmt_num(nav_red)} / P/NAV معادل: {fmt_num(float(px)/float(nav_red), 3)} — حباب/تخفیف {fmt_pct(bubble)}"))
            else:
                p.p(bullet("NAV هر سهم و P/NAV", p.u()))
        else:
            p.p(bullet("NAV هر سهم و P/NAV", p.u()))
    else:
        p.p(bullet("NAV هر سهم و P/NAV", NOT_APPLICABLE))
    p.p(bullet("مفروضات DCF", "**فرض محاسباتی**: هیچ‌یک از ورودی‌های لازم (R_f، ERP، β، FCFE) در داده ورودی موجود نیست؛ "
                               "β نیازمند تاریخ شاخص کل است که فقط ۱۱ روز در ورودی موجود است. لذا DCF "
                               + p.n()))
    p.p(bullet("ارزش هر سهم DCF", p.n()))
    p.p(bullet("ارزش هر سهم RIM", p.n("نیاز به سود خالص و حقوق صاحبان سهام معتبر") if not data.get("is_bank") else p.n()))
    p.p(bullet("ارزش هر سهم DDM", p.n("نیاز به DPS و نرخ رشد")))
    p.p(bullet("وزن هر مدل در ترکیب", p.n("مدل قابل محاسبه‌ای موجود نیست")))
    p.p(bullet("ارزش منصفانه ترکیبی نهایی", p.n()))
    p.p(bullet("Margin of Safety٪", p.n()))

    # ۷ NAV صندوق
    p.h("## ۷. NAV اختصاصی صندوق")
    if is_fund:
        nav_rows = data.get("nav_rows")
        fund_type = scr.get("fund_type") or ("صندوق سرمایه‌گذاری" if "صندوق" in str(sector or "") or "صندوق" in str(board or "") else p.u())
        p.p(bullet("نوع صندوق", fund_type if fund_type and fund_type != UNKNOWN else p.u()))
        if nav_rows is not None and len(nav_rows):
            latest = nav_rows.iloc[0]
            p.p(bullet("NAV صدور هر واحد", f"{fmt_num(latest.get('nav_issue'))} (تاریخ {latest.get('date')})"))
            p.p(bullet("NAV ابطال هر واحد", f"{fmt_num(latest.get('nav_redemption'))} (تاریخ {latest.get('date')})"))
            if px and latest.get("nav_redemption"):
                bubble = (float(px) / float(latest["nav_redemption"]) - 1) * 100
                p.p(bullet("قیمت بازار فعلی واحد", f"{fmt_num(px)} — درصد حباب/تخفیف نسبت به NAV ابطال: {fmt_pct(bubble)}"))
            else:
                p.p(bullet("قیمت بازار فعلی واحد", fmt_num(px) if px else p.u()))
                p.p(bullet("درصد حباب/تخفیف", p.u()))
            hist = nav_rows.head(6)[["date", "nav_issue", "nav_redemption"]].values.tolist()
            p.p("**تاریخچه اخیر NAV:**")
            p.p(md_table(["تاریخ", "NAV صدور", "NAV ابطال"], [[h[0], fmt_num(h[1]), fmt_num(h[2])] for h in hist]))
        else:
            p.p(bullet("NAV صدور/ابطال", p.u()))
            p.p(bullet("قیمت بازار فعلی واحد", fmt_num(px) if px else p.u()))
            p.p(bullet("درصد حباب/تخفیف", p.u()))
        p.p(bullet("ترکیب دارایی‌ها (سهام/اوراق/سپرده)", p.m("ترکیب دارایی‌ها")))
    else:
        p.p(NOT_APPLICABLE)

    # ۸ تابلوی حقیقی/حقوقی
    p.h("## ۸. تابلوی معاملات حقیقی/حقوقی")
    rl = data.get("real_legal")
    if rl is not None and len(rl):
        r = rl.iloc[0]
        def rv(col):
            try:
                return float(r[col]) if r[col] is not None else None
            except Exception:
                return None
        net_today = (rv("buy_real_value") or 0) - (rv("sell_real_value") or 0)
        rl_num = rl.head(20).copy()
        for c in ["buy_real_value", "sell_real_value"]:
            rl_num[c] = pd.to_numeric(rl_num[c], errors="coerce").fillna(0)
        net5 = float((rl_num.head(5)["buy_real_value"] - rl_num.head(5)["sell_real_value"]).sum())
        net20 = float((rl_num["buy_real_value"] - rl_num["sell_real_value"]).sum())
        p.p(f"**(تاریخ داده: {r['date']} شمسی — آخرین رکورد موجود)**")
        p.p(bullet("خرید و فروش حقیقی", f"خرید {fmt_num(rv('buy_real_volume'),0)} سهم / {fmt_num(rv('buy_real_value'),0)} ریال (≈ {fmt_num((rv('buy_real_value') or 0)/10,0)} تومان) — "
                                          f"فروش {fmt_num(rv('sell_real_volume'),0)} سهم / {fmt_num(rv('sell_real_value'),0)} ریال (≈ {fmt_num((rv('sell_real_value') or 0)/10,0)} تومان)"))
        p.p(bullet("خالص ورود-خروج پول حقیقی امروز", f"{fmt_num(net_today,0)} ریال (≈ {fmt_num(net_today/10,0)} تومان)"))
        p.p(bullet("خالص ورود-خروج پول حقیقی ۵روزه", f"{fmt_num(net5,0)} ریال (≈ {fmt_num(net5/10,0)} تومان)"))
        p.p(bullet("خالص ورود-خروج پول حقیقی ۲۰روزه", f"{fmt_num(net20,0)} ریال (≈ {fmt_num(net20/10,0)} تومان)"))
        brc = rv("buy_real_count")
        src_ = rv("sell_real_count")
        p.p(bullet("سرانه خرید حقیقی", fmt_num((rv('buy_real_value') or 0) / brc) if brc else p.u()))
        p.p(bullet("سرانه فروش حقیقی", fmt_num((rv('sell_real_value') or 0) / src_) if src_ else p.u()))
        brv, srv = rv("buy_real_volume"), rv("sell_real_volume")
        p.p(bullet("نسبت قدرت خریدار به فروشنده حقیقی", fmt_num(brv / srv, 3) if (brv and srv) else p.u()))
        p.p(bullet("تعداد خریداران و فروشندگان حقیقی", f"{fmt_num(brc,0)} / {fmt_num(src_,0)}"))
        p.p(bullet("خرید و فروش حقوقی", f"خرید {fmt_num(rv('buy_legal_volume'),0)} سهم / {fmt_num(rv('buy_legal_value'),0)} ریال — "
                                          f"فروش {fmt_num(rv('sell_legal_volume'),0)} سهم / {fmt_num(rv('sell_legal_value'),0)} ریال"))
        avg5 = abs(net5) / 5 if len(rl) >= 5 else None
        if avg5 and net20 > avg5 and net_today > 0:
            state_tab = "تجمیع در حال خرید (خالص مثبت حقیقی)"
        elif avg5 and net20 < -avg5 and net_today < 0:
            state_tab = "تجمیع در حال فروش (خالص منفی حقیقی)"
        else:
            state_tab = "خنثی/مختلط"
        p.p(bullet("وضعیت کلی تابلو", state_tab + " — **روش تشخیص خودکار بر پایه علامت و بزرگی خالص جریان**"))
    else:
        p.p("داده ریز حقیقی/حقوقی روزانه برای این نماد در ورودی موجود نیست.")
        for lab in ["خرید و فروش حقیقی", "خالص ورود-خروج پول حقیقی امروز", "خالص ۵روزه", "خالص ۲۰روزه",
                    "سرانه خرید", "سرانه فروش", "قدرت خریدار/فروشنده", "تعداد خریداران/فروشندگان", "خرید و فروش حقوقی"]:
            p.p(bullet(lab, p.u()))

    # ۹ بک‌تست
    p.h("## ۹. نتیجه بک‌تست")
    p.p("**استراتژی**: ورود در تقاطع صعودی SMA20/SMA50 و خروج در تقاطع نزولی (لانگ‌اونلی، اجرا در قیمت پایانی روز بعد سیگنال) | "
        "**کارمزد**: ۰.۵٪ هر طرف (**فرض محاسباتی**) | **نرخ بدون ریسک در شارپ**: صفر (**فرض محاسباتی**)")
    if bt.get("status") == "داده ناکافی":
        p.p(f"داده ناکافی برای بک‌تست معنادار (تعداد ردیف: {fmt_num(bt.get('n_rows'),0)}؛ حداقل لازم: ۶۰).")
    elif bt:
        p.p(f"بازه داده: {bt['start'].date()} تا {bt['end'].date()} | تعداد ردیف: {fmt_num(bt['n_rows'],0)}")

        def seg_table(name, s):
            return [name, fmt_num(s.get("n_trades"), 0), fmt_num(s.get("win_rate")) + "٪" if s.get("win_rate") is not None else UNKNOWN,
                    fmt_num(s.get("profit_factor"), 3), fmt_num(s.get("total_return")) + "٪" if s.get("total_return") is not None else UNKNOWN,
                    fmt_num(s.get("cagr")) + "٪" if s.get("cagr") is not None else UNKNOWN,
                    fmt_num(s.get("max_dd")) + "٪" if s.get("max_dd") is not None else UNKNOWN,
                    fmt_num(s.get("sharpe"), 3)]
        rows = [seg_table("In-Sample (۷۰٪)", bt["in_sample"]), seg_table("Out-of-Sample (۳۰٪)", bt["out_sample"])]
        p.p(md_table(["بازه", "تعداد معاملات", "Win Rate", "Profit Factor", "بازده کل", "CAGR", "Max Drawdown", "Sharpe"], rows))
        p.p(bullet("مقایسه با Buy&Hold (IS/OOS)", f"{fmt_num(bt['in_sample'].get('buy_hold'))}٪ / {fmt_num(bt['out_sample'].get('buy_hold'))}٪"))
        p.p(bullet("نتیجه‌گیری پایداری", bt.get("verdict")))
    else:
        p.p(p.m("بک‌تست", "انجام نشد"))

    # ۱۰ ML
    p.h("## ۱۰. نتیجه مدل ML")
    p.p("**هدف**: آیا قیمت پایانی در ۵ روز آینده حداقل ۲٪ رشد می‌کند؟ | تقسیم زمانی ۷۰/۱۵/۱۵ (بدون Shuffle) | "
        "استانداردسازی فقط با آمار Train")
    if ml.get("status") == "ok":
        p.p(bullet("تعداد نمونه معتبر و تقسیم", f"{ml['n']} نمونه → Train {ml['n_train']} / Val {ml['n_val']} / Test {ml['n_test']}"))
        if ml.get("ml_capped"):
            p.p("- **فرض محاسباتی کنترلی**: برای کنترل زمان محاسبات، فقط ۲۵۰۰ نمونه اخیر از کل "
                f"{fmt_num(ml.get('n_total'),0)} نمونه معتبر آموزش داده شده است.")
        p.p(bullet("Class Balance (نسبت کلاس ۱)", fmt_num(ml["class_balance"], 3)))
        rows = []
        for mname, key in [("Logistic Regression", "lr_test"), ("Random Forest", "rf_test")]:
            m = ml[key]
            rows.append([mname, fmt_num(m["accuracy"], 3), fmt_num(m["precision"], 3), fmt_num(m["recall"], 3),
                         fmt_num(m["f1"], 3), fmt_num(m["auc"], 3) if m.get("auc") is not None else UNKNOWN])
        p.p(md_table(["مدل", "Accuracy", "Precision", "Recall", "F1", "AUC-ROC"], rows))
        p.p(bullet("Accuracy Baseline (کلاس اکثریت)", fmt_num(ml["baseline"], 3)))
        feats = "، ".join(f"{f} ({fmt_num(v,3)})" for f, v in ml["top_features"])
        p.p(bullet("۵ فیچر برتر (Random Forest)", feats))
        if not ml.get("vol_ok"):
            p.p("- **توجه**: داده حجم در این نماد موجود نبود؛ فیچرهای حجمی از مدل حذف شده‌اند.")
        p.p(f"> ⚠️ {ML_WARNING}")
    elif ml.get("status") == "داده ناکافی":
        note = f" — {ml.get('note')}" if ml.get("note") else ""
        p.p(f"داده ناکافی برای آموزش مدل (نمونه معتبر: {fmt_num(ml.get('n'),0)}؛ حداقل لازم: ۱۵۰){note}.")
        p.p(f"> ⚠️ {ML_WARNING}")
    else:
        p.p(p.m("مدل ML", "اجرا نشد"))
        p.p(f"> ⚠️ {ML_WARNING}")

    # ۱۱ مالکیت
    p.h("## ۱۱. مالکیت، مدیریت و رویدادهای شرکتی")
    sh = data.get("shareholders")
    if sh is not None and len(sh):
        latest_date = sh["date"].iloc[0]
        latest = sh[sh["date"] == latest_date].head(10)
        p.p(f"**سهامداران عمده (تاریخ: {latest_date})**")
        p.p(md_table(["نام سهامدار", "حجم", "درصد"], [[str(r["name"])[:60], fmt_num(r["volume"], 0), fmt_num(r["percent"])]
                                                     for _, r in latest.iterrows()]))
    else:
        p.p(f"**سهامداران عمده:** {p.m('سهامداران عمده')}")
    p.p(bullet("مدیرعامل فعلی و تاریخ انتصاب", p.m("مدیرعامل")))
    inc_rows = []
    div_rows = []
    if ann is not None and len(ann):
        for _, r in ann.iterrows():
            t = str(r["title"])
            if "افزایش سرمایه" in t:
                inc_rows.append([r["publish"], t[:90], p.u()])
            if ("سود" in t and "مجمع" in t) or "سود نقدی" in t:
                div_rows.append([r["publish"], t[:90], p.u(), p.u()])
    if inc_rows:
        p.p("**افزایش سرمایه‌ها (از اطلاعیه‌ها):**")
        p.p(md_table(["تاریخ", "موضوع اطلاعیه", "درصد"], inc_rows[:5]))
    else:
        p.p(f"**جدول افزایش سرمایه‌ها:** {p.m('افزایش سرمایه')}")
    if div_rows:
        p.p("**سود تقسیمی/مجامع (از اطلاعیه‌ها):**")
        p.p(md_table(["تاریخ", "موضوع اطلاعیه", "DPS", "Payout٪"], div_rows[:5]))
    else:
        p.p(f"**جدول سود تقسیمی سالانه (سال، EPS، DPS، Payout٪):** {p.m('سود تقسیمی')}")

    # ۱۲ اخبار
    p.h("## ۱۲. اخبار و اطلاعیه‌های اثرگذار")
    if ann is not None and len(ann):
        rows = []
        for _, r in ann.head(8).iterrows():
            rows.append([r["publish"], str(r["title"])[:90], str(r["title"])[:90], effect_words(r["title"])])
        p.p(md_table(["تاریخ", "عنوان", "خلاصه یک‌خطی", "نوع اثر"], rows))
    else:
        p.p(f"{p.m('اطلاعیه‌های اثرگذار')} — اطلاعیه‌ای برای این نماد در داده ورودی یافت نشد.")

    # ۱۳ حسابرسی و کیفیت گزارشگری
    p.h("## ۱۳. حسابرسی و کیفیت گزارشگری")
    audit_rows = []
    if ann is not None and len(ann):
        for _, r in ann.iterrows():
            t = str(r["title"])
            if "حسابرسی" in t:
                audit_rows.append([r["publish"], t[:95], "حسابرسی‌نشده" if "نشده" in t else "حسابرسی‌شده"])
    if audit_rows:
        p.p("**گزارش‌های مالی دارای اشاره به وضعیت حسابرسی (از اطلاعیه‌ها):**")
        p.p(md_table(["تاریخ", "عنوان گزارش", "وضعیت حسابرسی"], audit_rows[:5]))
    else:
        p.p(f"**گزارش‌های مالی دارای اشاره به وضعیت حسابرسی:** {p.m('گزارش‌های حسابرسی')}")
    p.p(bullet("نام مؤسسه حسابرسی (۳ سال اخیر)", p.m("مؤسسه حسابرسی")))
    p.p(bullet("نوع اظهارنظر هر سال (مقبول/مشروط/مردود/عدم اظهارنظر)", p.m("نوع اظهارنظر")))
    p.p(bullet("بندهای مهم حسابرسی و برآورد اثر مالی آن‌ها", p.m("بندهای حسابرسی")))
    p.p(bullet("مطالبات مالیاتی حل‌نشده (در صورت افشا)", p.m("مطالبات مالیاتی")))
    p.p(bullet("تعهدات خارج از ترازنامه (در صورت افشا)", p.m("تعهدات خارج از ترازنامه")))

    # ۱۴ مقایسه با هم‌گروهی‌ها
    p.h("## ۱۴. مقایسه با هم‌گروهی‌ها (طبق ۲.۸)")
    peers = hub.peer_table(det.get("symbol") or symbol, sector, 10)
    peer_rows = []
    for pr in peers:
        peer_rows.append([pr.get("symbol"), fmt_num(pr.get("pe_ratio")) if pr.get("pe_ratio") not in (None, 0) else UNKNOWN,
                          UNKNOWN,  # P/B — واحد حقوق صاحبان سهام در ورودی قابل اتکا نیست
                          fmt_num(pr.get("net_margin")), fmt_num(pr.get("revenue_growth")),
                          fmt_num(pr.get("ret12"))])
    if peer_rows:
        p.p(md_table(["نماد", "P/E", "P/B", "حاشیه سود خالص٪", "رشد فروش سالانه٪", "بازدهی ۱۲ماهه٪"], peer_rows))
        p.p("P/B برای همه نمادها نامشخص است: واحد حقوق صاحبان سهام در داده ورودی قابل اتکا نیست.")
    else:
        p.p(f"داده هم‌گروهی برای صنعت «{sector or '—'}» در ورودی یافت نشد.")
    pe_mean, pe_n = hub.peer_pe_mean(sector)
    my_pe = det.get("pe_ratio")
    if my_pe and pe_mean:
        diff = (float(my_pe) / pe_mean - 1) * 100
        pos = "ارزان‌تر" if diff < 0 else "گران‌تر"
        peer_signal = f"{pos} از میانگین گروه (P/E نماد {fmt_num(my_pe)} در برابر میانگین {fmt_num(pe_mean)} صنعت، {pe_n} نماد) — اختلاف {fmt_pct(diff)}"
    else:
        peer_signal = p.m("جایگاه نسبی هم‌گروهی", "داده کافی برای میانگین P/E صنعت موجود نیست")
    p.p(f"**جایگاه نسبی نماد اصلی در این جدول:** {peer_signal}")

    # ۱۵ سناریوهای استرس‌تست کلان
    p.h("## ۱۵. سناریوهای استرس‌تست کلان (طبق ۲.۹)")
    stress_note = p.n("مفروضات کلیدی (نرخ ارز/انرژی) و صورت سود و زیان تفکیکی ارزی/انرژی در داده ورودی موجود نیست")
    p.p(md_table(["سناریو", "مفروضات کلیدی (نرخ ارز/انرژی)", "اثر بر EPS", "اثر بر ارزش منصفانه"],
                 [["خوش‌بینانه", stress_note, p.n(), p.n()],
                  ["پایه", stress_note, p.n(), p.n()],
                  ["بدبینانه", stress_note, p.n(), p.n()]]))
    reg_key = str(sector or "") + " " + str(sub_sector or "")
    if any(w in reg_key for w in ["پالایش", "فرآورده", "خودرو", "بانک", "دارو", "فولاد", "سیمان", "پتروشیمی", "معدن", "فلزات", "انرژی", "نیرو", "بیمه", "سرمایه‌گذاری", "هلدینگ", "شیمیایی"]):
        reg_risk = "متوسط تا شدید (صنعت مشمول قیمت‌گذاری/رگولاتوری) — **تشخیص کلیدواژه‌ای صنعت، نه ارزیابی مستند**"
    elif reg_key.strip():
        reg_risk = "نامشخص (برای این صنعت قاعده تشخیصی خودکاری تعریف نشده)"
    else:
        reg_risk = p.u()
    p.p(bullet("ریسک رگولاتوری/قیمت‌گذاری دستوری خاص صنعت", reg_risk))

    # ۱۶ معیارهای ریسک و نوسان
    p.h("## ۱۶. معیارهای ریسک و نوسان (طبق ۲.۷)")
    p.p(bullet("انحراف معیار سالانه بازده", f"{fmt_num(tech.get('annual_vol'))}٪" if tech.get("annual_vol") is not None else p.u()))
    p.p(bullet("بتا (β) نسبت به شاخص کل", p.n("داده هم‌زمان شاخص کل در ورودی کافی نیست (فقط ۱۱ روز)")))
    p.p(bullet("ضریب همبستگی با شاخص کل", p.n("داده هم‌زمان شاخص کل در ورودی کافی نیست (فقط ۱۱ روز)")))
    p.p(bullet("حداکثر افت تاریخی سهم در کل بازه داده", f"{fmt_num(tech.get('max_dd_hist'))}٪" if tech.get("max_dd_hist") is not None else p.u()))
    vol = tech.get("annual_vol")
    if vol is not None:
        band = "بالا" if vol > 60 else ("متوسط" if vol >= 30 else "پایین")
        p.p(f"- **فرض محاسباتی برای دسته‌بندی نوسان**: آستانه‌های >۶۰٪ بالا، ۳۰–۶۰٪ متوسط، <۳۰٪ پایین → دسته این نماد: {band}")

    # ۱۷ معاملات بلوکی و اشخاص وابسته
    p.h("## ۱۷. معاملات بلوکی و اشخاص وابسته")
    p.p(f"داده معاملات بلوکی/اشخاص وابسته در ورودی موجود نیست. ({p.m('معاملات بلوکی و اشخاص وابسته')})")
    p.p(md_table(["تاریخ", "نوع (بلوکی/وابسته)", "طرفین معامله", "تعداد سهم", "قیمت", "درصد نسبت به سرمایه"], []))

    # ۱۸ خلاصه تصمیم‌یار
    p.h("## ۱۸. خلاصه تصمیم‌یار")
    tech_sig = "نامشخص"
    if tech.get("rsi14") is not None and tech.get("sma20"):
        above = tech["close"] > tech["sma20"]
        if tech["rsi14"] > 70 or (tech.get("bb_pctb") is not None and tech["bb_pctb"] > 1):
            tech_sig = "اشباع خرید/کشش بالا"
        elif tech["rsi14"] < 30 or (tech.get("bb_pctb") is not None and tech["bb_pctb"] < 0):
            tech_sig = "اشباع فروش/کشش پایین"
        elif above:
            tech_sig = "مثبت ملایم (قیمت بالای میانگین‌ها)"
        else:
            tech_sig = "منفی ملایم (قیمت زیر میانگین‌ها)"
    fund_sig = "نامشخص (داده صورت مالی معتبر موجود نیست)"
    val_sig = "نامشخص (ارزش منصفانه قابل محاسبه نیست)"
    flow_sig = "نامشخص"
    if rl is not None and len(rl):
        r = rl.iloc[0]
        net = float(r["buy_real_value"] or 0) - float(r["sell_real_value"] or 0)
        flow_sig = "خالص ورود پول حقیقی" if net > 0 else ("خالص خروج پول حقیقی" if net < 0 else "خنثی")
    risks = []
    if tech.get("rsi14") is not None and tech["rsi14"] > 70:
        risks.append("RSI در اشباع خرید")
    if tech.get("hist_high") and tech.get("close") and tech["close"] >= tech["hist_high"] * 0.98:
        risks.append("نزدیکی به سقف تاریخی")
    if det.get("state") and "متوقف" in str(det.get("state")):
        risks.append("وضعیت نماد: " + str(det.get("state")))
    if bt.get("verdict") == "نشانه Overfitting":
        risks.append("نشانه Overfitting در بک‌تست")
    p.p(bullet("سیگنال تکنیکال کلی", tech_sig))
    p.p(bullet("سیگنال بنیادی کلی", fund_sig))
    p.p(bullet("سیگنال ارزش‌گذاری", val_sig))
    p.p(bullet("سیگنال جریان نقدینگی", flow_sig))
    p.p(bullet("سیگنال نسبی نسبت به هم‌گروهی‌ها", peer_signal))
    p.p(bullet("ریسک سناریو بدبینانه کلان (بخش ۱۵)", p.n("داده حساسیت ارز/انرژی موجود نیست")))
    if vol is not None:
        band = "بالا" if vol > 60 else ("متوسط" if vol >= 30 else "پایین")
        p.p(bullet("سطح ریسک نوسان نسبت به بازار", f"نوسان سالانه {fmt_num(vol)}٪ → دسته {band} (فرض محاسباتی آستانه‌ها؛ β نسبت به شاخص قابل محاسبه نیست)"))
    else:
        p.p(bullet("سطح ریسک نوسان نسبت به بازار", p.u()))
    p.p(bullet("ریسک‌های فعال شناسایی‌شده", "؛ ".join(risks) if risks else "موردی به‌صورت خودکار شناسایی نشد"))
    contradictions = []
    if "مثبت" in tech_sig and flow_sig.startswith("خالص خروج"):
        contradictions.append("تکنیکال مثبت در برابر خروج پول حقیقی")
    if "اشباع خرید" in tech_sig and flow_sig.startswith("خالص ورود"):
        contradictions.append("اشباع خرید همراه با ورود پول (احتمال ادامه روند یا تله)")
    if bt.get("verdict") == "نشانه Overfitting":
        contradictions.append("عملکرد مناسب In-Sample در برابر افت Out-of-Sample")
    if "گران‌تر" in str(peer_signal) and "مثبت" in tech_sig:
        contradictions.append("تکنیکال مثبت در برابر P/E گران‌تر از میانگین صنعت")
    if ml.get("status") == "ok" and ml.get("rf_test", {}).get("accuracy") is not None and ml.get("baseline") is not None:
        if ml["rf_test"]["accuracy"] < ml["baseline"]:
            contradictions.append("عملکرد مدل ML ضعیف‌تر از Baseline (مدل اکتشافی معنادار نیست)")
    p.p(bullet("تناقض‌های بین سیگنال‌ها", "؛ ".join(contradictions) if contradictions else "تناقض بارزی به‌صورت خودکار شناسایی نشد"))
    fill = max(0.0, (TOTAL_FIELDS - p.unknown) / TOTAL_FIELDS * 100)
    conf = "بالا" if fill >= 70 else ("متوسط" if fill >= 40 else "پایین")
    p.p(bullet("درجه اطمینان کلی سند", f"{conf} (فیلدهای پرشده تقریبی: {fmt_num(fill,1)}٪)"))
    p.p(f"> {DECISION_REMINDER}")

    # ۱۹ شفافیت
    p.h("## ۱۹. شفافیت تشخیص خودکار")
    uniq = []
    for f in p.missing_fields:
        if f not in uniq:
            uniq.append(f)
    p.p("**فیلدهای «نامشخص» مانده:** " + ("، ".join(uniq) if uniq else "موردی ثبت نشد"))
    src_rows = []
    for s in sources:
        note = detection_note.get(s, {})
        src_rows.append([s, note.get("columns", "—"), note.get("type", "—"), note.get("path", "—"), note.get("conf", "—")])
    p.p("**جدول درجه اطمینان تشخیص ستون‌ها:**")
    p.p(md_table(["فایل/جدول", "ستون(های) انتخابی", "نوع تشخیص‌داده‌شده", "مسیر تشخیص", "درجه اطمینان"], src_rows))
    stats = {"unknown": p.unknown, "missing": uniq, "fill_pct": fill,
             "tech_signal": tech_sig, "flow_signal": flow_sig, "peer_signal": str(peer_signal),
             "contradictions": contradictions, "bt_verdict": bt.get("verdict") if bt else None}
    return p.render(), stats


# ----------------------------------------------------------------------------
# حلقه اصلی
# ----------------------------------------------------------------------------

def classify(cat_details, symbol, in_nav, has_ticks, file_kind):
    if file_kind == "crypto" or symbol.upper() in ("BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "ADA", "TRX", "LTC", "LINK", "DOT", "AVAX", "SHIB", "UNI", "ATOM", "FIL", "XLM", "USDT", "USDC"):
        return "کریپتو"
    if file_kind in ("gold", "currency", "coin"):
        return "طلا/ارز/سکه"
    sector = str(cat_details.get("sector") or "")
    board = str(cat_details.get("board") or "")
    if in_nav or has_ticks or "صندوق" in sector or "صندوق" in board:
        return "صندوق/ETF"
    if sector:
        return "سهام بازار سرمایه ایران"
    return "سایر"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--no-ml", action="store_true")
    ap.add_argument("--no-backtest", action="store_true")
    ap.add_argument("--symbols", type=str, default="")
    ap.add_argument("--symbols-file", type=str, default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--stats-file", type=str, default="run_stats.jsonl")
    ap.add_argument("--no-detection", action="store_true", help="در اجرای موازی: رد کردن بازنویسی detection_log.csv")
    ap.add_argument("--no-summary", action="store_true", help="در اجرای موازی: رد کردن نوشتن گزارش خلاصه")
    args = ap.parse_args()

    t_start = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pages_dir = OUT_DIR / "pages"
    pages_dir.mkdir(exist_ok=True)
    conn = db_connect()
    print("[init] اتصال به دیتابیس برقرار شد؛ در حال فهرست‌گیری نمادهای هر جدول (یک‌بار) ...", flush=True)
    table_queries = {
        "candlesticks": "select distinct symbol from candlesticks",
        "quotes": "select distinct symbol from quotes",
        "snapshots": "select distinct symbol from brsapi_symbol_snapshots",
        "real_legal": "select distinct symbol from brsapi_historical_real_legal",
        "shareholders": "select distinct symbol from brsapi_shareholder_records",
        "announcements": "select distinct symbol from brsapi_codal_announcements",
        "nav": "select distinct symbol from brsapi_nav_records",
        "gold_daily": "select distinct symbol from brsapi_gold_currency_pro_daily_history",
        "crypto_daily": "select distinct symbol from brsapi_crypto_daily_history",
    }
    table_syms = {}
    t0 = time.time()
    for name, sql in table_queries.items():
        try:
            with conn.cursor() as c2:
                c2.execute(sql)
                table_syms[name] = set(r[0] for r in c2.fetchall() if r[0])
            print(f"[init] {name}: {len(table_syms[name])} نماد ({time.time()-t0:.0f}s)", flush=True)
        except Exception as e:
            table_syms[name] = set()
            print(f"[init] خطا {name}: {e}", flush=True)
    hub = DataHub(conn, table_syms)
    print(f"[init] details={len(hub.details_latest)} screener={len(hub.screener)} audit={len(hub.audit)} nav={len(hub.nav_all)}", flush=True)

    # --- تشخیص خودکار ستون‌ها (ثبت در detection_log) ---
    detection_rows = []
    detection_note = {}
    samples = [
        ("candlesticks (نوع ۳ - تعدیل‌شده)", "select gregorian_date, symbol, open, high, low, close, volume, candle_type from candlesticks where candle_type='3' limit 300", "سری روزانه تعدیل‌شده", "قیمت روزانه"),
        ("candlesticks (نوع ۲ - اسمی)", "select gregorian_date, symbol, open, high, low, close, volume, candle_type from candlesticks where candle_type='2' limit 200", "سری روزانه اسمی", "قیمت روزانه"),
        ("quotes", "select gregorian_date, time, symbol, price_open, price_high, price_low, price_close, price_last, volume, value, trade_count from quotes limit 300", "اسنپ‌شات‌های روزانه اخیر", "قیمت روزانه/درون‌روز"),
        ("brsapi_symbol_details", "select symbol, name, isin, sector, sub_sector, market, board, shares_count, eps, pe_ratio, price_close, free_float_pct, state, date from brsapi_symbol_details limit 300", "شناسنامه و آخرین وضعیت", "وضعیت نماد"),
        ("brsapi_historical_real_legal", "select date, symbol, buy_real_count, sell_real_count, buy_legal_count, sell_legal_count, buy_real_volume, sell_real_volume, buy_real_value, sell_real_value from brsapi_historical_real_legal limit 300", "تابلوی حقیقی/حقوقی روزانه", "حقیقی/حقوقی"),
        ("brsapi_shareholder_records", "select symbol, shareholder_name, volume, percent, change, date from brsapi_shareholder_records limit 300", "سهامداران", "سهامداران"),
        ("brsapi_codal_announcements", "select symbol, title, code, date_publish, date_send, time_publish from brsapi_codal_announcements limit 300", "اطلاعیه‌های کدال", "اخبار/اطلاعیه"),
        ("brsapi_nav_records", "select symbol, nav_issue, nav_redemption, date, time from brsapi_nav_records limit 300", "NAV صندوق‌ها", "NAV صندوق"),
        ("screener_profiles", "select symbol, industry, eps_current, registered_capital, industry_pe, current_price from screener_profiles limit 300", "پروفایل بنیادی", "بنیادی"),
        ("brsapi_symbol_snapshots", "select symbol, time, price_last, bid_price_1, ask_price_1, bid_volume_1, ask_volume_1 from brsapi_symbol_snapshots limit 200", "سفارش‌بوک لحظه‌ای", "درون‌روز"),
    ]
    for label, sql, desc, ctype in samples:
        try:
            df = pd.read_sql_query(sql, conn)
            mapping, rows = detect_columns(df, label, desc)
            for r in rows:
                r["نوع_محتوا_فایل"] = ctype
                detection_rows.append(r)
            paths = {r["مسیر_تشخیص"] for r in rows}
            confs = [r["درجه_اطمینان"] for r in rows]
            detection_note[label] = {"columns": ", ".join(f"{v}" for v in mapping.values()) or "—",
                                     "type": ctype,
                                     "path": ("ترکیبی (نام‌محور+آماری)" if len(paths) > 1 else (next(iter(paths)) if paths else "—")),
                                     "conf": (max(set(confs), key=confs.count) if confs else "—")}
        except Exception as e:
            print(f"[detect] خطا در {label}: {e}", flush=True)
    # فایل‌ها
    file_samples = [
        (HISTORY_DIR / "XAUUSD_history.json", "XAUUSD_history.json (سری روزانه OHLC)", "طلا/ارز/سکه"),
        (CRYPTO_HISTORY_DIR / "BTC_history.json", "BTC_history.json (سری روزانه OHLC)", "کریپتو"),
        (FUNDS_DIR / "آلتون.csv.gz", "آلتون.csv.gz (تیک درون‌روز صندوق)", "درون‌روز"),
        (CODAL_FILES_DIR / "اهرم_codal.json", "اهرم_codal.json (اطلاعیه‌های کدال)", "اخبار/اطلاعیه"),
    ]
    for path, label, ctype in file_samples:
        try:
            if path.suffix == ".gz":
                df = load_tick_file(path)
            else:
                with open(path, encoding="utf-8") as fh:
                    arr = json.load(fh)
                df = pd.DataFrame(arr[:300])
            mapping, rows = detect_columns(df, label, ctype)
            for r in rows:
                r["نوع_محتوا_فایل"] = ctype
                detection_rows.append(r)
            paths = {r["مسیر_تشخیص"] for r in rows}
            confs = [r["درجه_اطمینان"] for r in rows]
            detection_note[label] = {"columns": ", ".join(f"{v}" for v in mapping.values()) or "—", "type": ctype,
                                     "path": ("ترکیبی (نام‌محور+آماری)" if len(paths) > 1 else (next(iter(paths)) if paths else "—")),
                                     "conf": (max(set(confs), key=confs.count) if confs else "—")}
        except Exception as e:
            print(f"[detect] خطا در {label}: {e}", flush=True)
    if not args.no_detection:
        with open(OUT_DIR / "detection_log.csv", "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=["نام_فایل", "ستون_انتخابی", "نوع_محتوای_تشخیص_داده_شده", "مسیر_تشخیص", "درجه_اطمینان", "نوع_محتوا_فایل", "توضیح"])
            w.writeheader()
            for r in detection_rows:
                w.writerow(r)
        print(f"[detect] {len(detection_rows)} تصمیم تشخیص در detection_log.csv ثبت شد", flush=True)
    DET_SHORT = {
        "candlesticks": "candlesticks (نوع ۳ - تعدیل‌شده)",
        "quotes": "quotes",
        "real_legal": "brsapi_historical_real_legal",
        "details": "brsapi_symbol_details",
        "shareholders": "brsapi_shareholder_records",
        "announcements": "brsapi_codal_announcements",
        "nav": "brsapi_nav_records",
        "screener": "screener_profiles",
        "snapshots": "brsapi_symbol_snapshots",
        "file_history": "XAUUSD_history.json (سری روزانه OHLC)",
        "file_crypto": "BTC_history.json (سری روزانه OHLC)",
        "file_ticks": "آلتون.csv.gz (تیک درون‌روز صندوق)",
    }
    detection_note_short = {k: detection_note.get(v, {}) for k, v in DET_SHORT.items()}
    if not args.no_detection:
        with contextlib.suppress(Exception), open(OUT_DIR / "detection_note_short.json", "w", encoding="utf-8") as fh:
            json.dump(detection_note_short, fh, ensure_ascii=False)

    # --- ساخت فهرست نمادها ---
    cur = conn.cursor()
    variants = {}
    symbol_sources = {}

    def add_symbol(sym, source):
        key = norm_symbol(sym)
        if not key:
            return
        variants.setdefault(key, set()).add(sym)
        symbol_sources.setdefault(key, {})[source] = True

    def add_from_query(sql, source):
        try:
            cur.execute(sql)
            for (s,) in cur.fetchall():
                if s:
                    add_symbol(s, source)
        except Exception as e:
            print(f"[universe] خطا ({source}): {e}", flush=True)

    for name, src in [("candlesticks", "candlesticks"), ("quotes", "quotes"), ("snapshots", "snapshots"),
                      ("real_legal", "real_legal"), ("shareholders", "shareholders"),
                      ("announcements", "announcements"), ("nav", "nav")]:
        for s in table_syms.get(name, ()):
            add_symbol(s, src)
    for s in hub.details_latest["symbol"].tolist():
        add_symbol(s, "details")
    for s in hub.screener["symbol"].tolist():
        add_symbol(s, "screener")

    file_series = {}
    file_kind = {}
    for path in sorted(HISTORY_DIR.glob("*_history.json")):
        sym = path.name.replace("_history.json", "")
        key = norm_symbol(sym)
        add_symbol(sym, "file_history")
        symbol_sources[key]["file_history"] = path
        file_kind[key] = "gold" if sym.startswith(("IR_GOLD", "IR_COIN", "IR_PCOIN", "XAU")) else "currency"
    for path in sorted(CRYPTO_HISTORY_DIR.glob("*_history.json")):
        sym = path.name.replace("_history.json", "")
        key = norm_symbol(sym)
        add_symbol(sym, "file_crypto")
        symbol_sources[key]["file_crypto"] = path
        file_kind[key] = "crypto"
    tick_files = {}
    if FUNDS_DIR.exists():
        for path in sorted(FUNDS_DIR.glob("*.csv.gz")):
            sym = path.name.replace(".csv.gz", "")
            key = norm_symbol(sym)
            add_symbol(sym, "file_ticks")
            symbol_sources[key]["file_ticks"] = path
            tick_files[key] = path
    tick_dates = {}
    with contextlib.suppress(Exception):
        summ_path = ROOT / "data" / "top50_funds_intraday" / "summary.csv"
        summ = pd.read_csv(summ_path, encoding="utf-8")
        for _, r in summ.iterrows():
            if pd.notna(r.get("last_trade_date")):
                tick_dates[norm_symbol(r["symbol"])] = str(r["last_trade_date"])
    print(f"[universe] {len(variants)} نماد یکتا شناسایی شد از تمام جداول و فایل‌ها", flush=True)

    all_keys = sorted(variants.keys())
    details_syms = set(hub.details_latest["symbol"])

    def choose_canonical(key):
        for src_set in (details_syms, table_syms.get("candlesticks", set()), table_syms.get("quotes", set()),
                        table_syms.get("shareholders", set()), table_syms.get("announcements", set())):
            matches = [s for s in variants[key] if s in src_set]
            if matches:
                return sorted(matches, key=lambda s: (len(s), s))[0]
        return sorted(variants[key], key=lambda s: (len(s), s))[0]

    wanted = set()
    if args.symbols:
        wanted |= {norm_symbol(s) for s in args.symbols.split(",")}
    if args.symbols_file:
        try:
            with open(args.symbols_file, encoding="utf-8") as fh:
                wanted |= {norm_symbol(ln.strip()) for ln in fh if ln.strip()}
        except Exception as e:
            print(f"[warn] خواندن symbols-file ناموفق: {e}", flush=True)
    if wanted:
        all_keys = [k for k in all_keys if k in wanted]
    total = len(all_keys)
    selected = all_keys[args.start:]
    if args.limit:
        selected = selected[:args.limit]
    print(f"[run] پردازش {len(selected)} نماد از {total} (شروع از {args.start})", flush=True)

    stats_path = OUT_DIR / args.stats_file
    done = 0
    processed_names = []
    for idx, key in enumerate(selected, start=1):
        sym = choose_canonical(key)
        safe = safe_name(sym)
        page_path = pages_dir / f"{safe}.md"
        if page_path.exists() and not args.force:
            continue
        try:
            data = hub.fetch("core", sym, variants[key] | {v for v in variants[key]})
            details = hub.latest_details_row(sym)
            if not details:
                for v in variants[key]:
                    details = hub.latest_details_row(v)
                    if details:
                        break
            screener = hub.screener_row(sym) or next((hub.screener_row(v) for v in variants[key] if hub.screener_row(v)), {})
            audit = hub.audit_row(sym) or next((hub.audit_row(v) for v in variants[key] if hub.audit_row(v)), {})
            nav_rows = hub.nav_rows(sym)
            if len(nav_rows) == 0:
                for v in variants[key]:
                    nav_rows = hub.nav_rows(v)
                    if len(nav_rows):
                        break
            f_daily = file_series.get(key)
            if f_daily is None:
                fp = symbol_sources[key].get("file_history") or symbol_sources[key].get("file_crypto")
                f_daily = load_history_file(fp) if fp else None
                file_series[key] = f_daily
            ticks = None
            if key in tick_files:
                ticks = load_tick_file(tick_files[key])
            series, raw_series = merge_series(
                candles_adj=data.get("candles_adj"), candles_raw=data.get("candles_raw"),
                quotes=data.get("quotes"), file_daily=f_daily, extra_daily=data.get("extra_daily"))
            tech_df, zero_vol, n_const = halted_filter(series) if series is not None and len(series) else (pd.DataFrame(), 0, 0)
            technical = compute_technical(tech_df) if len(tech_df) else {}
            backtest = {} if args.no_backtest else (backtest_full(tech_df) if len(tech_df) else {})
            ml_res = {} if args.no_ml else (ml_train(tech_df) if len(tech_df) else {"status": "داده ناکافی", "n": len(tech_df)})
            has_ticks = key in tick_files
            in_nav = len(nav_rows) > 0
            category = classify(details, sym, in_nav, has_ticks, file_kind.get(key, ""))
            is_fund = category == "صندوق/ETF"
            is_bank = "بانک" in str(details.get("sector") or "") or "سرمایه‌گذاری" in str(details.get("sector") or "")
            if data.get("candles_adj") is not None and len(data["candles_adj"]):
                note = "candlesticks نوع ۳ (تعدیل‌شده) + الحاق quotes جدیدتر"
            elif f_daily is not None and len(f_daily):
                note = "فایل سری زمانی روزانه (history_data یا crypto_history) + الحاق دیتابیس"
            elif data.get("quotes") is not None and len(data["quotes"]):
                note = "quotes (تجمیع روزانه اسنپ‌شات‌ها)"
            else:
                note = NO_DATA
            user_row = hub.user_system_row(sym, variants[key])
            payload = dict(details=details, screener=screener, audit=audit, snapshot=data.get("snapshot") or {},
                           series=series, raw_series=raw_series, ticks=ticks, technical=technical,
                           backtest=backtest, ml=ml_res, real_legal=data.get("real_legal"),
                           shareholders=data.get("shareholders"), announcements=data.get("announcements"),
                           nav_rows=nav_rows, category=category, is_fund=is_fund, is_bank=is_bank,
                           price_note=note, user_row=user_row,
                           halt_note=(f"حجم صفر: {zero_vol} ردیف | قیمت ثابت طولانی‌مدت: {n_const} ردیف (حذف از محاسبات تکنیکال)"
                                      if (series is not None and len(series)) else UNKNOWN),
                           tick_date=tick_dates.get(key, ""))
            page_md, page_stats = compose_page(sym, hub, sorted(symbol_sources[key].keys()), payload, detection_note_short)
            with open(page_path, "w", encoding="utf-8") as fh:
                fh.write(page_md)
            shares = details.get("shares_count")
            pe = details.get("pe_ratio")
            ind_pe = screener.get("industry_pe")
            stat = dict(symbol=sym, category=category, rows=int(len(series)) if series is not None else 0,
                        unknown=page_stats["unknown"], fill_pct=round(page_stats["fill_pct"], 1),
                        has_technical=bool(technical), has_backtest=bool(backtest and backtest.get("status") != "داده ناکافی"),
                        has_ml=bool(ml_res and ml_res.get("status") == "ok"),
                        missing=page_stats["missing"][:12],
                        file=str(page_path.relative_to(OUT_DIR)),
                        name=details.get("name"), sector=details.get("sector") or screener.get("industry"),
                        sub_sector=details.get("sub_sector") or screener.get("sub_industry"),
                        market=details.get("market"), board=details.get("board"), state=details.get("state"),
                        shares=shares,
                        capital_btom=(round(float(shares) * 1000 / 1e10, 2) if shares else None),
                        price=technical.get("close") if technical else None,
                        daily_change_pct=technical.get("chg_pct") if technical else None,
                        pe=pe, industry_pe=ind_pe,
                        pe_vs_industry=((float(pe) / float(ind_pe) - 1) * 100 if (pe and ind_pe) else None),
                        net_profit_growth=audit.get("net_profit_growth"),
                        revenue_growth=audit.get("revenue_growth"),
                        net_margin=audit.get("net_margin"),
                        rsi14=technical.get("rsi14") if technical else None,
                        avg_val30=technical.get("avg_val30") if technical else None,
                        ret12=technical.get("ret_12m") if technical else None,
                        max_dd_hist=technical.get("max_dd_hist") if technical else None,
                        annual_vol=technical.get("annual_vol") if technical else None,
                        tech_signal=page_stats.get("tech_signal"), flow_signal=page_stats.get("flow_signal"),
                        peer_signal=page_stats.get("peer_signal"), contradictions=page_stats.get("contradictions"),
                        user_daily=jsonable(user_row.get("daily") or {}),
                        user_signal=jsonable(user_row.get("signal") or {}))
            with open(stats_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(jsonable(stat), ensure_ascii=False) + "\n")
            done += 1
            processed_names.append(sym)
        except Exception as e:
            print(f"[error] {sym}: {e}", flush=True)
            traceback.print_exc()
        if idx % 20 == 0 or idx == len(selected):
            elapsed = time.time() - t_start
            print(f"[batch] {idx}/{len(selected)} | ساخته‌شده این اجرا: {done} | آخرین: {sym} | {elapsed:.0f}s", flush=True)

    # --- گزارش خلاصه اجرا ---
    if args.no_summary:
        print(f"[done] این اجرا: {done} صفحه | زمان کل: {time.time()-t_start:.0f}s (گزارش خلاصه رد شد)", flush=True)
        return
    stats = []
    for sp in sorted(OUT_DIR.glob("run_stats*.jsonl")):
        with open(sp, encoding="utf-8") as fh:
            for line in fh:
                try:
                    stats.append(json.loads(line))
                except Exception:
                    continue
    by_key = {}
    for s in stats:
        by_key[s["symbol"]] = s
    stats = list(by_key.values())
    if stats:
        fills = [s["fill_pct"] for s in stats]
        low = [s for s in stats if s["fill_pct"] < 30]
        cats = {}
        for s in stats:
            cats[s["category"]] = cats.get(s["category"], 0) + 1
        lines = ["# گزارش خلاصه اجرا — صفحات اختصاصی نمادها", "",
                 f"- تعداد کل نمادهای پردازش‌شده: **{len(stats)}**",
                 f"- میانگین درصد فیلدهای پرشده (شاخص کامل‌بودن داده): **{sum(fills)/len(fills):.1f}٪**",
                 f"- تعداد صفحات با تکمیل کمتر از ۳۰٪: **{len(low)}**",
                 "- توزیع دسته‌ها: " + "، ".join(f"{k}: {v}" for k, v in sorted(cats.items(), key=lambda t: -t[1])),
                 f"- نمادهای دارای مدل ML موفق: **{sum(1 for s in stats if s.get('has_ml'))}**",
                 f"- نمادهای دارای بک‌تست کافی: **{sum(1 for s in stats if s.get('has_backtest'))}**", "",
                 "## نمادهای نیازمند بررسی دستی (کمترین کامل‌بودن داده)", ""]
        for s in sorted(low, key=lambda x: x["fill_pct"])[:80]:
            lines.append(f"- {s['symbol']} ({s['category']}): تکمیل {s['fill_pct']}٪ — ردیف روزانه {s['rows']}"
                         + (f" — موارد نامشخص: {'، '.join(s.get('missing', [])[:6])}" if s.get("missing") else ""))
        with open(OUT_DIR / "run_summary.md", "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        print(f"[summary] گزارش خلاصه در {OUT_DIR / 'run_summary.md'} نوشته شد ({len(stats)} نماد)", flush=True)
    print(f"[done] این اجرا: {done} صفحه | زمان کل: {time.time()-t_start:.0f}s", flush=True)


if __name__ == "__main__":
    main()
