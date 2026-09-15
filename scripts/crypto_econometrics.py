#!/usr/bin/env python
"""
تحلیل اقتصادسنجی رمزارزها (بیتکوین و اتریوم).

بر اساس مقاله: «تحلیل عوامل موثر در قیمت ارزهای مجازی»
ابوالحسنی و صمدی (۱۳۹۹)

شامل:
  ۱. آزمون ایستایی ADF
  ۲. آزمون همانباشتگی یوهانسن
  ۳. رگرسیون OLS (کوتاه‌مدت)
  ۴. مدل VECM (بلندمدت)
  ۵. ارزیابی فرضیه‌ها

Usage:
    python scripts/crypto_econometrics.py --input data.csv --crypto bitcoin
    python scripts/crypto_econometrics.py --input data.csv --crypto ethereum
    python scripts/crypto_econometrics.py --input data.csv --all
    python scripts/crypto_econometrics.py --fetch --crypto bitcoin
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

OUTPUT_DIR = _project_root / "exchange_rate_data" / "crypto_econometrics"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════
#  بخش ۱: جمع‌آوری داده
# ═══════════════════════════════════════════════════════════════


def fetch_crypto_data(coin: str = "bitcoin") -> pd.DataFrame:
    """
    دریافت داده‌های روزانه رمزارز از CoinGecko (رایگان).
    """
    import requests

    print(f"\n  [CoinGecko] دریافت داده‌های {coin}...")

    url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart"
    params = {
        "vs_currency": "usd",
        "days": "max",
        "interval": "daily",
    }
    headers = {"accept": "application/json"}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        prices = data.get("prices", [])
        volumes = data.get("total_volumes", [])

        df_prices = pd.DataFrame(prices, columns=["timestamp", "price"])
        df_volumes = pd.DataFrame(volumes, columns=["timestamp", "volume"])

        df_prices["date"] = pd.to_datetime(df_prices["timestamp"], unit="ms").dt.date
        df_volumes["date"] = pd.to_datetime(df_volumes["timestamp"], unit="ms").dt.date

        df = pd.merge(df_prices[["date", "price"]], df_volumes[["date", "volume"]], on="date")
        df = df.sort_values("date").reset_index(drop=True)

        print(f"    ✓ {len(df)} رکورد دریافت شد ({df['date'].min()} تا {df['date'].max()})")
        return df

    except Exception as e:
        print(f"    ✗ خطا: {e}")
        return pd.DataFrame()


def fetch_gold_data() -> pd.DataFrame:
    """دریافت قیمت طلا از Yahoo Finance."""
    print("  [Yahoo] دریافت قیمت طلا...")
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F"
        params = {"period1": 1262304000, "period2": int(time.time()), "interval": "1d"}
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        quotes = result["indicators"]["quote"][0]
        df = pd.DataFrame(
            {
                "date": [pd.Timestamp(t, unit="s").date() for t in timestamps],
                "gold": quotes["close"],
            }
        )
        print(f"    ✓ {len(df)} رکورد")
        return df
    except Exception as e:
        print(f"    ✗ خطا: {e}")
        return pd.DataFrame()


def fetch_sp500_data() -> pd.DataFrame:
    """دریافت شاخص S&P 500."""
    print("  [Yahoo] دریافت شاخص S&P 500...")
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC"
        params = {"period1": 1262304000, "period2": int(time.time()), "interval": "1d"}
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        quotes = result["indicators"]["quote"][0]
        df = pd.DataFrame(
            {
                "date": [pd.Timestamp(t, unit="s").date() for t in timestamps],
                "sp500": quotes["close"],
            }
        )
        print(f"    ✓ {len(df)} رکورد")
        return df
    except Exception as e:
        print(f"    ✗ خطا: {e}")
        return pd.DataFrame()


def fetch_dxy_data() -> pd.DataFrame:
    """دریافت شاخص دلار (DXY)."""
    print("  [Yahoo] دریافت شاخص دلار...")
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB"
        params = {"period1": 1262304000, "period2": int(time.time()), "interval": "1d"}
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        quotes = result["indicators"]["quote"][0]
        df = pd.DataFrame(
            {
                "date": [pd.Timestamp(t, unit="s").date() for t in timestamps],
                "dxy": quotes["close"],
            }
        )
        print(f"    ✓ {len(df)} رکورد")
        return df
    except Exception as e:
        print(f"    ✗ خطا: {e}")
        return pd.DataFrame()


def fetch_all_data(coin: str = "bitcoin") -> pd.DataFrame:
    """دریافت تمام داده‌ها و ترکیب آنها."""
    print("\n" + "═" * 70)
    print(f"  جمع‌آوری داده‌ها برای {coin.upper()}")
    print("═" * 70)

    crypto = fetch_crypto_data(coin)
    gold = fetch_gold_data()
    sp500 = fetch_sp500_data()
    dxy = fetch_dxy_data()

    # ترکیب
    df = crypto.copy()
    for other in [gold, sp500, dxy]:
        if not other.empty:
            df = pd.merge(df, other, on="date", how="left")

    # پر کردن NaN
    df = df.ffill().dropna()

    # ساخت متغیرهای مشتق
    if "price" in df.columns:
        df["log_price"] = np.log(df["price"])
        df["returns"] = df["price"].pct_change()

    if "gold" in df.columns:
        df["log_gold"] = np.log(df["gold"])

    if "sp500" in df.columns:
        df["log_sp500"] = np.log(df["sp500"])

    if "dxy" in df.columns:
        df["log_dxy"] = np.log(df["dxy"])

    if "volume" in df.columns:
        df["log_volume"] = np.log(df["volume"])

    df = df.dropna()

    print(f"\n  ✓ نهایی: {len(df)} ردیف، {len(df.columns)} ستون")
    print(f"  ستون‌ها: {', '.join(df.columns)}")

    return df


# ═══════════════════════════════════════════════════════════════
#  بخش ۲: آزمون ایستایی ADF
# ═══════════════════════════════════════════════════════════════


def adf_test(series: pd.Series, name: str, regression: str = "c") -> dict:
    """
    آزمون دیکی-فولر تعمیم‌یافته (ADF).

    H₀: φ = 1 (ریشه واحد / غیرسکون)
    H₁: φ < 1 (سکونی)
    """
    from statsmodels.tsa.stattools import adfuller

    clean = series.dropna()
    if len(clean) < 20:
        return {"variable": name, "status": "insufficient_data"}

    result = adfuller(clean, regression=regression, autolag="AIC")
    is_stationary = result[1] < 0.05

    return {
        "variable": name,
        "regression": regression,
        "nobs": len(clean),
        "adf_stat": round(result[0], 4),
        "p_value": round(result[1], 6),
        "lags": result[2],
        "cv_1pct": round(result[4]["1%"], 4),
        "cv_5pct": round(result[4]["5%"], 4),
        "cv_10pct": round(result[4]["10%"], 4),
        "is_stationary_5pct": is_stationary,
        "conclusion": "مانا ✅" if is_stationary else "نامانا ❌",
    }


def run_adf_battery(df: pd.DataFrame, variables: list[str]) -> pd.DataFrame:
    """اجرای ADF روی تمام متغیرها."""
    print("\n" + "═" * 70)
    print("  ۱. آزمون ایستایی ADF")
    print("═" * 70)

    results = []
    for var in variables:
        if var not in df.columns:
            continue
        print(f"\n  ── {var} ──")
        for reg, label in [("c", "فقط ثابت"), ("ct", "ثابت + روند")]:
            res = adf_test(df[var], var, regression=reg)
            print(
                f"    {label:15s}: ADF={res['adf_stat']:>10.4f}  "
                f"p={res['p_value']:>10.6f}  CV(5%)={res['cv_5pct']:>8.4f}  → {res['conclusion']}"
            )
            results.append(res)

    return pd.DataFrame(results)


def run_diff_adf(df: pd.DataFrame, variables: list[str]) -> pd.DataFrame:
    """اجرای ADF روی تفاضل مرتبه اول."""
    print("\n" + "═" * 70)
    print("  ۲. آزمون ADF روی ΔX (تفاضل مرتبه اول)")
    print("═" * 70)

    results = []
    for var in variables:
        if var not in df.columns:
            continue
        diff_series = df[var].diff().dropna()
        res = adf_test(diff_series, f"Δ{var}", regression="c")
        print(f"    Δ{var:15s}: ADF={res['adf_stat']:>10.4f}  p={res['p_value']:>10.6f}  → {res['conclusion']}")
        results.append(res)

    return pd.DataFrame(results)


# ═══════════════════════════════════════════════════════════════
#  بخش ۳: آزمون همانباشتگی یوهانسن
# ═══════════════════════════════════════════════════════════════


def run_johansen(df: pd.DataFrame, variables: list[str], k_ar_diff: int = 3) -> dict:
    """
    آزمون یوهانسن برای همانباشتگی.
    """
    from statsmodels.tsa.vector_ar.vecm import coint_johansen

    print("\n" + "═" * 70)
    print("  ۳. آزمون همانباشتگی یوهانسن")
    print("═" * 70)

    avail = [v for v in variables if v in df.columns]
    data = df[avail].dropna()

    print(f"  متغیرها: {', '.join(avail)}")
    print(f"  مشاهدات: {len(data)}")

    # اجرای یوهانسن
    result = coint_johansen(data, det_order=0, k_ar_diff=k_ar_diff)
    n = len(avail)

    # TRACE
    trace_stat = result.lr1
    trace_crit = result.cvt

    # λmax
    max_stat = result.lr2
    max_crit = result.cvm

    # تعیین تعداد بردار همگرایی
    n_coint_trace = 0
    for i in range(n):
        if trace_stat[i] > trace_crit[i, 1]:  # 95%
            n_coint_trace += 1
        else:
            break

    n_coint_max = 0
    for i in range(n):
        if max_stat[i] > max_crit[i, 1]:
            n_coint_max += 1
        else:
            break

    # چاپ نتایج TRACE
    print("\n  ── نتایج TRACE ──")
    print(f"  {'فرضیه':>10s}  {'آماره':>10s}  {'CV(90%)':>10s}  {'CV(95%)':>10s}  {'CV(99%)':>10s}  {'نتیجه':>6s}")
    for i in range(n):
        reject = "✅" if trace_stat[i] > trace_crit[i, 1] else "❌"
        print(
            f"  {'r ≤ ' + str(i):>10s}  {trace_stat[i]:>10.4f}  "
            f"{trace_crit[i, 0]:>10.4f}  {trace_crit[i, 1]:>10.4f}  "
            f"{trace_crit[i, 2]:>10.4f}  {reject}"
        )

    # چاپ نتایج λmax
    print("\n  ── نتایج λmax ──")
    print(f"  {'فرضیه':>10s}  {'آماره':>10s}  {'CV(90%)':>10s}  {'CV(95%)':>10s}  {'CV(99%)':>10s}  {'نتیجه':>6s}")
    for i in range(n):
        reject = "✅" if max_stat[i] > max_crit[i, 1] else "❌"
        print(
            f"  {'r = ' + str(i):>10s}  {max_stat[i]:>10.4f}  "
            f"{max_crit[i, 0]:>10.4f}  {max_crit[i, 1]:>10.4f}  "
            f"{max_crit[i, 2]:>10.4f}  {reject}"
        )

    print(f"\n  تعداد بردار همگرایی: TRACE={n_coint_trace}, λmax={n_coint_max}")

    return {
        "variables": avail,
        "nobs": len(data),
        "n_coint_trace": n_coint_trace,
        "n_coint_max": n_coint_max,
        "trace_test": [
            {
                "hypothesis": f"r ≤ {i}",
                "stat": round(float(trace_stat[i]), 4),
                "cv_95": round(float(trace_crit[i, 1]), 4),
                "reject": bool(trace_stat[i] > trace_crit[i, 1]),
            }
            for i in range(n)
        ],
        "max_test": [
            {
                "hypothesis": f"r = {i}",
                "stat": round(float(max_stat[i]), 4),
                "cv_95": round(float(max_crit[i, 1]), 4),
                "reject": bool(max_stat[i] > max_crit[i, 1]),
            }
            for i in range(n)
        ],
    }


# ═══════════════════════════════════════════════════════════════
#  بخش ۴: رگرسیون OLS
# ═══════════════════════════════════════════════════════════════


def run_ols(df: pd.DataFrame, dependent: str, independents: list[str], name: str = "") -> dict:
    """
    رگرسیون OLS.
    """
    import statsmodels.api as sm

    print(f"\n  [OLS] {name}: {dependent} ~ {' + '.join(independents)}")

    avail_y = dependent in df.columns
    avail_X = [v for v in independents if v in df.columns]

    if not avail_y or not avail_X:
        print("    ⚠ متغیرهای کافی موجود نیست")
        return {"status": "missing_variables"}

    subset = df[[dependent] + avail_X].dropna()
    if len(subset) < len(avail_X) + 5:
        print("    ⚠ داده کافی نیست")
        return {"status": "insufficient_data"}

    y = subset[dependent]
    X = sm.add_constant(subset[avail_X])

    model = sm.OLS(y, X).fit()

    # چاپ نتایج
    print(f"    R² = {model.rsquared:.4f}  |  R² adj = {model.rsquared_adj:.4f}")
    print(f"    F = {model.fvalue:.4f}  (p = {model.f_pvalue:.6f})")
    print(f"    {'متغیر':>15s}  {'ضریب':>10s}  {'SE':>10s}  {'t':>10s}  {'p':>10s}  {'نتیجه':>10s}")
    for var in avail_X:
        sig = "***" if model.pvalues[var] < 0.05 else ""
        print(
            f"    {var:>15s}  {model.params[var]:>10.4f}  "
            f"{model.bse[var]:>10.4f}  {model.tvalues[var]:>10.4f}  "
            f"{model.pvalues[var]:>10.6f}  {sig}"
        )

    return {
        "name": name,
        "dependent": dependent,
        "independents": avail_X,
        "r_squared": round(model.rsquared, 4),
        "r_squared_adj": round(model.rsquared_adj, 4),
        "f_stat": round(model.fvalue, 4),
        "f_pvalue": round(model.f_pvalue, 6),
        "nobs": int(model.nobs),
        "coefficients": {
            var: {
                "coef": round(float(model.params[var]), 6),
                "se": round(float(model.bse[var]), 6),
                "t": round(float(model.tvalues[var]), 4),
                "p": round(float(model.pvalues[var]), 6),
                "significant": bool(model.pvalues[var] < 0.05),
            }
            for var in avail_X
        },
    }


# ═══════════════════════════════════════════════════════════════
#  بخش ۵: مدل VECM
# ═══════════════════════════════════════════════════════════════


def run_vecm(
    df: pd.DataFrame, dependent: str, independents: list[str], k_ar_diff: int = 3, coint_rank: int = 1
) -> dict:
    """
    مدل تصحیح خطای برداری (VECM).
    """
    from statsmodels.tsa.vector_ar.vecm import VECM

    print(f"\n  [VECM] {dependent} ~ {' + '.join(independents)}")

    avail = [dependent] + [v for v in independents if v in df.columns]
    data = df[avail].dropna()

    if len(data) < len(avail) * 5:
        return {"status": "insufficient_data"}

    print(f"    متغیرها: {', '.join(avail)}")
    print(f"    مشاهدات: {len(data)}")

    try:
        model = VECM(data, k_ar_diff=k_ar_diff, coint_rank=coint_rank, deterministic="ci")
        result = model.fit()

        print(f"    LR = {result.summary()}")

        return {
            "dependent": dependent,
            "independents": avail[1:],
            "k_ar_diff": k_ar_diff,
            "coint_rank": coint_rank,
            "nobs": len(data),
            "status": "completed",
        }
    except Exception as e:
        print(f"    ✗ خطا: {e}")
        return {"status": f"error: {e}"}


# ═══════════════════════════════════════════════════════════════
#  بخش ۶: ارزیابی فرضیه‌ها
# ═══════════════════════════════════════════════════════════════


def evaluate_hypotheses(ols_results: dict, vecm_results: dict, crypto_name: str) -> dict:
    """
    ارزیابی فرضیه‌های مقاله.
    """
    print("\n" + "═" * 70)
    print(f"  ارزیابی فرضیه‌ها — {crypto_name}")
    print("═" * 70)

    hypotheses = {
        "short_run": [
            {
                "name": "تعداد معاملات با قیمت مثبت",
                "expected": "positive",
                "variable": "log_volume" if "log_volume" in (ols_results.get("coefficients") or {}) else "volume",
            },
            {
                "name": "سختی استخراج با قیمت مثبت",
                "expected": "positive",
                "variable": "difficulty",
            },
            {
                "name": "حجم در گردش با قیمت مثبت",
                "expected": "positive",
                "variable": "log_volume",
            },
            {
                "name": "قیمت طلا با قیمت مثبت",
                "expected": "positive",
                "variable": "log_gold",
            },
            {
                "name": "S&P 500 با قیمت منفی",
                "expected": "negative",
                "variable": "log_sp500",
            },
            {
                "name": "نرخ ارز با قیمت منفی",
                "expected": "negative",
                "variable": "log_dxy",
            },
        ],
    }

    # بررسی فرضیه‌ها
    coeffs = ols_results.get("coefficients", {})
    results_short = []

    for h in hypotheses["short_run"]:
        var = h["variable"]
        if var in coeffs:
            coef = coeffs[var]["coef"]
            sig = coeffs[var]["significant"]
            supported = coef > 0 and sig if h["expected"] == "positive" else coef < 0 and sig
            status = "تأیید ✅" if supported else "رد ❌"
        else:
            coef = 0
            sig = False
            status = "— (متغیر موجود نیست)"

        result = {
            "hypothesis": h["name"],
            "expected": h["expected"],
            "coefficient": round(coef, 6),
            "significant": sig,
            "status": status,
        }
        results_short.append(result)
        print(f"  {h['name']:>40s}: β={coef:>10.4f}  sig={sig}  → {status}")

    return {"short_run": results_short}


# ═══════════════════════════════════════════════════════════════
#  بخش ۷: CLI
# ═══════════════════════════════════════════════════════════════


def parse_args():
    p = argparse.ArgumentParser(description="تحلیل اقتصادسنجی رمزارزها")
    p.add_argument("--input", "-i", type=str, default=None, help="فایل CSV")
    p.add_argument("--fetch", action="store_true", help="دانلود داده از اینترنت")
    p.add_argument("--crypto", type=str, default="bitcoin", help="نام رمزارز")
    p.add_argument("--all", action="store_true", help="اجرای تمام آزمون‌ها")
    p.add_argument("--save", type=str, default=None, help="ذخیره داده در فایل")
    return p.parse_args()


# ═══════════════════════════════════════════════════════════════
#  بخش ۸: اجرا
# ═══════════════════════════════════════════════════════════════


def main():
    args = parse_args()

    print("=" * 70)
    print("  تحلیل اقتصادسنجی رمزارزها")
    print(f"  رمزارز: {args.crypto.upper()}")
    print("=" * 70)

    # ── بارگذاری/دانلود داده ──
    if args.fetch or args.input is None:
        df = fetch_all_data(args.crypto)
        if df.empty:
            print("\n  ✗ داده‌ای دریافت نشد")
            sys.exit(1)
    else:
        fp = Path(args.input)
        if not fp.exists():
            print(f"\n  ✗ فایل یافت نشد: {fp}")
            sys.exit(1)
        df = pd.read_csv(fp, encoding="utf-8-sig")
        print(f"\n  ✓ {len(df)} ردیف از فایل بارگذاری شد")

    # ── ذخیره ──
    if args.save:
        save_path = Path(args.save)
        df.to_csv(save_path, index=False)
        print(f"  💾 ذخیره شد: {save_path}")

    # ── تعیین متغیرها ──
    log_vars = ["log_price", "log_gold", "log_sp500", "log_dxy", "log_volume"]
    log_vars = [v for v in log_vars if v in df.columns]

    print(f"\n  متغیرهای لگاریتمی: {', '.join(log_vars)}")

    # ── ۱. آزمون ADF ──
    adf_df = run_adf_battery(df, log_vars)
    if not adf_df.empty:
        adf_df.to_csv(OUTPUT_DIR / "adf_results.csv", index=False)

    # ── ۲. ADF روی تفاضل ──
    diff_df = run_diff_adf(df, log_vars)
    if not diff_df.empty:
        diff_df.to_csv(OUTPUT_DIR / "diff_adf_results.csv", index=False)

    # ── ۳. یوهانسن ──
    joh_result = {}
    if len(log_vars) >= 2:
        joh_result = run_johansen(df, log_vars, k_ar_diff=3)
        with open(OUTPUT_DIR / "johansen_results.json", "w", encoding="utf-8") as f:
            json.dump(joh_result, f, ensure_ascii=False, indent=2, default=float)

    # ── ۴. OLS ──
    ols_results = {}
    if "log_price" in df.columns:
        indep_vars = [v for v in log_vars if v != "log_price"]
        if indep_vars:
            ols_results = run_ols(df, "log_price", indep_vars, name=f"OLS-{args.crypto}")
            with open(OUTPUT_DIR / "ols_results.json", "w", encoding="utf-8") as f:
                json.dump(ols_results, f, ensure_ascii=False, indent=2)

    # ── ۵. ارزیابی فرضیه‌ها ──
    hyp_results = evaluate_hypotheses(ols_results, joh_result, args.crypto)
    with open(OUTPUT_DIR / "hypothesis_results.json", "w", encoding="utf-8") as f:
        json.dump(hyp_results, f, ensure_ascii=False, indent=2)

    # ── خلاصه ──
    print("\n" + "=" * 70)
    print("  خلاصه نتایج")
    print("=" * 70)

    if not adf_df.empty:
        stationary = adf_df[adf_df.get("is_stationary_5pct", False)]
        unit_root = adf_df[not adf_df.get("is_stationary_5pct", False)]
        print(f"  ADF: {len(stationary)} مانا، {len(unit_root)} نامانا")

    if joh_result.get("n_coint_trace", 0) > 0:
        print(f"  یوهانسن: {joh_result['n_coint_trace']} بردار همگرایی تأیید شد")

    if ols_results.get("r_squared"):
        print(f"  OLS: R² = {ols_results['r_squared']}")

    print(f"\n  خروجی‌ها: {OUTPUT_DIR.resolve()}")
    print("=" * 70)


if __name__ == "__main__":
    main()
