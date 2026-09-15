#!/usr/bin/env python
"""
آزمون‌های ریشه واحد و همگرایی برای پروژه تحقیق عوامل موثر بر نرخ ارز.

شامل:
  ۱. آزمون ریشه واحد:
     - ADF تعمیم‌یافته (بدون روند و با روند)
     - پرون (شکست ساختاری)
     - تفاضل مرتبه اول

  ۲. آزمون همگرایی:
     - انگل-گرنجر تعمیم‌یافته (AEG)
     - دوربین-واتسون (CRDW)
     - یوهانسن (مدل بردار خودهمبستگی)

Usage:
    python scripts/unit_root_cointegration.py --input exchange_rate_data/econometric_dataset.csv
    python scripts/unit_root_cointegration.py --input data.csv --vars NER,GDP,M1,P
    python scripts/unit_root_cointegration.py --input data.csv --cointegration NER,GDP,M1,P,Oil
    python scripts/unit_root_cointegration.py --input data.csv --all
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

OUTPUT_DIR = _project_root / "exchange_rate_data"
OUTPUT_DIR.mkdir(exist_ok=True)


# ═══════════════════════════════════════════════════════════════
#  بخش ۱: آزمون ریشه واحد ADF
# ═══════════════════════════════════════════════════════════════


def adf_test_full(
    series: pd.Series,
    name: str,
    regression: str = "c",
    lags: int | None = None,
) -> dict:
    """
    آزمون دیکی-فولر تعمیم‌یافته (ADF) با جزئیات کامل.

    H₀: φ = 1 (متغیر ریشه واحد دارد / غیرسکون)
    H₁: φ < 1 (متغیر سکونی است)

    Args:
        series: سری زمانی
        name: نام متغیر
        regression: نوع رگرسیون
            - "c"  : فقط ثابت (بدون روند)
            - "ct" : ثابت + روند خطی
            - "n"  : بدون ثابت و بدون روند
        lags: تعداد وقایع (None = خودکار با AIC)

    Returns:
        دیکشنری با نتایج کامل آزمون
    """
    from statsmodels.tsa.stattools import adfuller

    clean = series.dropna()
    if len(clean) < 10:
        return {
            "variable": name,
            "regression": regression,
            "status": "insufficient_data",
            "nobs": len(clean),
        }

    max_lags = lags if lags is not None else min(int(np.floor(12 * (len(clean) / 100) ** 0.25)), len(clean) // 3)

    result = adfuller(
        clean,
        regression=regression,
        autolag="AIC" if lags is None else None,
        maxlag=max_lags,
    )

    # تصمیم‌گیری
    is_stationary_5 = result[1] < 0.05
    is_stationary_1 = result[1] < 0.01

    # مقایسه با مقادیر بحرانی
    adf_stat = result[0]
    criticals = result[4]
    reject_at_1pct = adf_stat < criticals["1%"]
    reject_at_5pct = adf_stat < criticals["5%"]
    reject_at_10pct = adf_stat < criticals["10%"]

    return {
        "variable": name,
        "regression": regression,
        "nobs": len(clean),
        "adf_statistic": round(adf_stat, 6),
        "p_value": round(result[1], 8),
        "lags_used": result[2],
        "critical_1pct": round(criticals["1%"], 4),
        "critical_5pct": round(criticals["5%"], 4),
        "critical_10pct": round(criticals["10%"], 4),
        "reject_1pct": reject_at_1pct,
        "reject_5pct": reject_at_5pct,
        "reject_10pct": reject_at_10pct,
        "is_stationary_5pct": is_stationary_5,
        "is_stationary_1pct": is_stationary_1,
        "conclusion": ("رد H₀ (سکونی)" if is_stationary_5 else " عدم رد H₀ (ریشه واحد)"),
    }


def run_adf_battery(df: pd.DataFrame, variables: list[str]) -> pd.DataFrame:
    """
    اجرای آزمون ADF روی تمام متغیرها با دو حالت (با و بدون روند).
    """
    print("\n" + "═" * 70)
    print("  بخش ۱: آزمون ریشه واحد ADF")
    print("═" * 70)

    results = []
    for var in variables:
        if var not in df.columns:
            print(f"  ⚠ متغیر '{var}' یافت نشد — رد شد")
            continue

        series = df[var].dropna()
        if len(series) < 10:
            print(f"  ⚠ متغیر '{var}': داده کافی نیست ({len(series)} مشاهده)")
            continue

        print(f"\n  ── {var} ({len(series)} مشاهده) ──")

        # حالت ۱: بدون روند (constant only)
        res_c = adf_test_full(series, var, regression="c")
        print(
            f"    بدون روند:  ADF={res_c['adf_statistic']:>10.4f}  "
            f"p={res_c['p_value']:>10.6f}  "
            f"CV(1%)={res_c['critical_1pct']:>8.4f}  "
            f"CV(5%)={res_c['critical_5pct']:>8.4f}  "
            f"→ {res_c['conclusion']}"
        )
        results.append(res_c)

        # حالت ۲: با روند (constant + trend)
        res_ct = adf_test_full(series, var, regression="ct")
        print(
            f"    با روند:    ADF={res_ct['adf_statistic']:>10.4f}  "
            f"p={res_ct['p_value']:>10.6f}  "
            f"CV(1%)={res_ct['critical_1pct']:>8.4f}  "
            f"CV(5%)={res_ct['critical_5pct']:>8.4f}  "
            f"→ {res_ct['conclusion']}"
        )
        results.append(res_ct)

    return pd.DataFrame(results)


# ═══════════════════════════════════════════════════════════════
#  بخش ۲: آزمون پرون (شکست ساختاری)
# ═══════════════════════════════════════════════════════════════


def perron_test_manual(
    series: pd.Series,
    name: str,
    break_point: int | None = None,
    model: int = 1,
) -> dict:
    """
    آزمون پرون برای ریشه واحد با شکست ساختاری.

    مدل‌ها:
      1: شکست در سطح (level shift)
      2: شکست در روند (trend shift)
      3: شکست در هر دو (level + trend)

    اگر break_point مشخص نشود، از نقطه میانی سری استفاده می‌شود.

    مقادیر بحرانی (از جداول مقاله):
      مدل ۱ (TB=0.5): 1%=-4.30, 5%=-3.76, 10%=-3.46
      مدل ۲ (TB=0.5): 1%=-4.56, 5%=-3.96, 10%=-3.68
      مدل ۳ (TB=0.5): 1%=-4.90, 5%=-4.24, 10%=-3.96
    """
    clean = series.dropna().values
    n = len(clean)
    if n < 20:
        return {"variable": name, "status": "insufficient_data"}

    if break_point is None:
        break_point = n // 2

    tb = break_point / n  # نسبت نقطه شکست

    # ساخت متغیرهای دامی
    du = np.zeros(n)  # dummy level
    dt = np.zeros(n)  # dummy trend
    for t in range(break_point, n):
        du[t] = 1.0
        dt[t] = t - break_point + 1

    # ساخت متغیرهای رگرسیون
    y = np.diff(clean)
    lag_y = clean[:-1]

    if model == 1:
        # y_t = μ + β·DU_t + φ·y_{t-1} + Σ ψ_i · Δy_{t-i} + ε_t
        X = np.column_stack(
            [
                np.ones(n - 1),
                du[1:],
                lag_y,
            ]
        )
    elif model == 2:
        # y_t = μ + β·DT_t + φ·y_{t-1} + Σ ψ_i · Δy_{t-i} + ε_t
        X = np.column_stack(
            [
                np.ones(n - 1),
                dt[1:],
                lag_y,
            ]
        )
    else:  # model == 3
        # y_t = μ + β·DU_t + γ·DT_t + φ·y_{t-1} + Σ ψ_i · Δy_{t-i} + ε_t
        X = np.column_stack(
            [
                np.ones(n - 1),
                du[1:],
                dt[1:],
                lag_y,
            ]
        )

    # رگرسیونOLS
    try:
        from numpy.linalg import lstsq

        beta, residuals, rank, sv = lstsq(X, y, rcond=None)
        fitted = X @ beta
        residuals_ols = y - fitted
        n_params = X.shape[1]
        sigma2 = np.sum(residuals_ols**2) / (n - 1 - n_params)

        # آماره t برای φ
        XtX_inv = np.linalg.inv(X.T @ X)
        se_phi = np.sqrt(sigma2 * XtX_inv[-1, -1])  # last param is φ
        phi_hat = beta[-1]
        t_stat = phi_hat / se_phi if se_phi > 0 else 0

        # مقادیر بحرانی پرون (تقریبی از جداول مقاله)
        # استفاده از λ = tb (نسبت نقطه شکست)
        critical_values = {
            1: {0.1: -3.46, 0.05: -3.76, 0.025: -4.03, 0.01: -4.30},
            2: {0.1: -3.68, 0.05: -3.96, 0.025: -4.20, 0.01: -4.56},
            3: {0.1: -3.96, 0.05: -4.24, 0.025: -4.48, 0.01: -4.90},
        }
        cvs = critical_values.get(model, critical_values[1])

        reject_5pct = t_stat < cvs[0.05]
        reject_1pct = t_stat < cvs[0.01]

        return {
            "variable": name,
            "model": model,
            "break_point": break_point,
            "break_ratio": round(tb, 2),
            "nobs": n,
            "phi_hat": round(phi_hat, 6),
            "t_statistic": round(t_stat, 4),
            "critical_1pct": cvs[0.01],
            "critical_5pct": cvs[0.05],
            "critical_10pct": cvs[0.1],
            "reject_5pct": reject_5pct,
            "reject_1pct": reject_1pct,
            "conclusion": "رد H₀ (شکست ساختاری)" if reject_5pct else "عدم رد H₀ (ریشه واحد)",
            "status": "completed",
        }
    except Exception as e:
        return {"variable": name, "status": f"error: {e}"}


def run_perron_battery(df: pd.DataFrame, variables: list[str]) -> pd.DataFrame:
    """اجرای آزمون پرون روی متغیرها."""
    print("\n" + "═" * 70)
    print("  بخش ۲: آزمون پرون (شکست ساختاری)")
    print("═" * 70)

    results = []
    for var in variables:
        if var not in df.columns:
            continue
        series = df[var].dropna()
        if len(series) < 20:
            continue

        print(f"\n  ── {var} ──")
        for model in (1, 2, 3):
            res = perron_test_manual(series, var, model=model)
            if res.get("status") == "completed":
                print(
                    f"    مدل {model}: t={res['t_statistic']:>8.4f}  "
                    f"CV(5%)={res['critical_5pct']:>8.4f}  → {res['conclusion']}"
                )
                results.append(res)

    return pd.DataFrame(results)


# ═══════════════════════════════════════════════════════════════
#  بخش ۳: آزمون همگرایی انگل-گرنجر (AEG)
# ═══════════════════════════════════════════════════════════════


def engle_granger_test(
    y: pd.Series,
    X: pd.DataFrame,
    y_name: str = "Y",
    regression: str = "c",
) -> dict:
    """
    آزمون انگل-گرنجر تعمیم‌یافته (AEG) برای همگرایی.

    مراحل:
      ۱. رگرسیون y روی X
      ۲. استخراج پسماند (residuals)
      ۳. اجرای ADF روی پسماند

    H₀: پسماند ریشه واحد دارد (متغیرها همگرا نیستند)
    H₁: پسماند سکونی است (متغیرها همگرا هستند)

    مقادیر بحرانی AEG (تقریبی، n=50):
      بدون روند: 1%=-3.58, 5%=-2.93, 10%=-2.60
      با روند:   1%=-4.15, 5%=-3.50, 10%=-3.18
    """
    import statsmodels.api as sm

    # حذف NaN مشترک
    combined = pd.concat([y, X], axis=1).dropna()
    y_clean = combined.iloc[:, 0]
    X_clean = combined.iloc[:, 1:]

    if len(X_clean) < len(X.columns) + 5:
        return {"status": "insufficient_data"}

    # مرحله ۱: رگرسیون
    X_const = sm.add_constant(X_clean)
    model = sm.OLS(y_clean, X_const).fit()
    residuals = model.resid

    # مرحله ۲: ADF روی پسماند
    adf_result = adf_test_full(residuals, f"resid({y_name})", regression=regression)

    # مقادیر بحرانی AEG (Phillips-Perron style)
    X_clean.shape[1]
    n = len(residuals)
    # تقریب تابعی از n و k
    cv = {0.01: -3.58, 0.05: -2.93, 0.1: -2.6} if regression == "c" else {0.01: -4.15, 0.05: -3.5, 0.1: -3.18}

    reject_5pct = adf_result["adf_statistic"] < cv[0.05]

    return {
        "y_variable": y_name,
        "X_variables": list(X.columns),
        "nobs": n,
        "r_squared": round(model.rsquared, 4),
        "adf_statistic": adf_result["adf_statistic"],
        "p_value": adf_result["p_value"],
        "critical_1pct_aeg": cv[0.01],
        "critical_5pct_aeg": cv[0.05],
        "critical_10pct_aeg": cv[0.10],
        "reject_5pct": reject_5pct,
        "conclusion": ("همگرایی تأیید شد ✅" if reject_5pct else "همگرایی رد شد ❌"),
    }


def run_engle_granger_battery(
    df: pd.DataFrame,
    dependent: str,
    independents: list[str],
) -> dict:
    """اجرای آزمون AEG روی یک مدل."""
    print("\n  [AEG] آزمون انگل-گرنجر...")
    print(f"    مدل: {dependent} ~ {' + '.join(independents)}")

    avail_y = dependent in df.columns
    avail_X = [v for v in independents if v in df.columns]

    if not avail_y or not avail_X:
        print("    ⚠ متغیرهای کافی موجود نیست")
        return {"status": "missing_variables"}

    result = engle_granger_test(
        y=df[dependent],
        X=df[avail_X],
        y_name=dependent,
    )

    if result.get("status") != "completed":
        print(f"    ⚠ {result.get('status', 'unknown error')}")
        return result

    print(
        f"    ADF پسماند = {result['adf_statistic']:.4f}  "
        f"CV(5%) = {result['critical_5pct_aeg']:.4f}  "
        f"→ {result['conclusion']}"
    )

    return result


# ═══════════════════════════════════════════════════════════════
#  بخش ۴: آزمون همگرایی دوربین-واتسون (CRDW)
# ═══════════════════════════════════════════════════════════════


def crdw_test(
    y: pd.Series,
    X: pd.DataFrame,
    y_name: str = "Y",
) -> dict:
    """
    آزمون همگرایی دوربین-واتسون (CRDW).

    مراحل:
      ۱. رگرسیون y روی X
      ۲. محاسبه آماره DW روی پسماند

    H₀: ρ = 1 (پسماند ریشه واحد دارد)
    H₁: ρ < 1 (پسماند سکونی است)

    مقدار بحرانی DW در سطح ۱٪ ≈ 0.511 (برای n بزرگ)
    اگر DW > 0.511 → رد H₀ → همگرایی تأیید
    """
    import statsmodels.api as sm

    # حذف NaN مشترک
    combined = pd.concat([y, X], axis=1).dropna()
    y_clean = combined.iloc[:, 0]
    X_clean = combined.iloc[:, 1:]

    if len(X_clean) < len(X.columns) + 5:
        return {"status": "insufficient_data"}

    # رگرسیون
    X_const = sm.add_constant(X_clean)
    model = sm.OLS(y_clean, X_const).fit()
    residuals = model.resid.values

    n = len(residuals)

    # محاسبه DW
    diff = np.diff(residuals)
    dw_stat = np.sum(diff**2) / np.sum(residuals**2)

    # مقدار بحرانی (تقریبی)
    # DW_crit ≈ 0.511 در سطح 1% برای n > 30
    # Savin-Wheatley critical values (approximate)
    X_clean.shape[1]  # number of regressors (excluding constant)
    cv_1pct = 0.511  # approximate for n >= 30
    cv_5pct = 0.800  # approximate

    reject_1pct = dw_stat > cv_1pct
    reject_5pct = dw_stat > cv_5pct

    return {
        "y_variable": y_name,
        "X_variables": list(X.columns),
        "nobs": n,
        "dw_statistic": round(dw_stat, 4),
        "critical_1pct_crdw": cv_1pct,
        "critical_5pct_crdw": cv_5pct,
        "reject_1pct": reject_1pct,
        "reject_5pct": reject_5pct,
        "conclusion": ("همگرایی تأیید شد ✅" if reject_5pct else "همگرایی رد شد ❌"),
    }


def run_crdw_battery(
    df: pd.DataFrame,
    dependent: str,
    independents: list[str],
) -> dict:
    """اجرای آزمون CRDW روی یک مدل."""
    print("\n  [CRDW] آزمون دوربین-واتسون...")
    print(f"    مدل: {dependent} ~ {' + '.join(independents)}")

    avail_y = dependent in df.columns
    avail_X = [v for v in independents if v in df.columns]

    if not avail_y or not avail_X:
        return {"status": "missing_variables"}

    result = crdw_test(
        y=df[dependent],
        X=df[avail_X],
        y_name=dependent,
    )

    if result.get("status") != "completed":
        return result

    print(
        f"    DW = {result['dw_statistic']:.4f}  CV(1%) = {result['critical_1pct_crdw']:.4f}  → {result['conclusion']}"
    )

    return result


# ═══════════════════════════════════════════════════════════════
#  بخش ۵: آزمون یوهانسن
# ═══════════════════════════════════════════════════════════════


def johansen_test(
    df: pd.DataFrame,
    variables: list[str],
    det_order: int = 0,
    k_ar_diff: int = 1,
) -> dict:
    """
    آزمون یوهانسن برای همگرایی (مدل بردار خودهمبستگی).

    مراحل:
      ۱. تعیین تعداد بهینه تاخیر (lag order selection)
      ۲. اجرای آزمون TRACE و λmax
      ۳. تعیین تعداد بردارهای همگرایی

    معیارها:
      - λTrace
      - λmax
      - AIC, SBC, HQC

    Args:
        df: دیتاست
        variables: لیست نام متغیرها
        det_order: ترتیب روند در مدل
            -1: بدون ثابت
             0: فقط ثابت در فرآیند
             1: ثابت + روند خطی در فرآیند
        k_ar_diff: تعداد وقایع در مدل VAR

    Returns:
        دیکشنری با نتایج کامل
    """
    from statsmodels.tsa.vector_ar.vecm import coint_johansen, select_coint_rank

    # آماده‌سازی داده
    avail = [v for v in variables if v in df.columns]
    data = df[avail].dropna()

    if len(data) < len(avail) * 3:
        return {"status": "insufficient_data", "variables": avail}

    print("\n  [Johansen] آزمون یوهانسن...")
    print(f"    متغیرها: {', '.join(avail)}")
    print(f"    مشاهدات: {len(data)}")
    print(f"    det_order: {det_order}, k_ar_diff: {k_ar_diff}")

    # ── مرحله ۱: انتخاب تعداد وقایع ──
    try:
        from statsmodels.tsa.vector_ar.var_model import VAR

        model_var = VAR(data)
        lag_order = model_var.select_order(maxlags=min(8, len(data) // 3))
        print(f"    تعداد وقایع بهینه: {lag_order.selected_orders}")
    except Exception:
        lag_order = None

    # ── مرحله ۲: اجرای آزمون یوهانسن ──
    try:
        result = coint_johansen(
            data,
            det_order=det_order,
            k_ar_diff=k_ar_diff,
        )
    except Exception as e:
        return {"status": f"johansen error: {e}", "variables": avail}

    n = len(data)
    k = len(avail)

    # ── نتایج TRACE ──
    trace_stat = result.lr1  # آماره‌های TRACE
    trace_crit = result.cvt  # مقادیر بحرانی TRACE (90%, 95%, 99%)

    # ── نتایج λmax ──
    max_stat = result.lr2  # آماره‌های λmax
    max_crit = result.cvm  # مقادیر بحرانی λmax

    # ── تعیین تعداد بردارهای همگرایی ──
    # با استفاده از معیار 5%
    n_coint_trace = 0
    for i in range(k):
        if trace_stat[i] > trace_crit[i, 1]:  # 95% column
            n_coint_trace += 1
        else:
            break

    n_coint_max = 0
    for i in range(k):
        if max_stat[i] > max_crit[i, 1]:  # 95% column
            n_coint_max += 1
        else:
            break

    # ── معیارهای اطلاعاتی ──
    with contextlib.suppress(Exception):
        select_coint_rank(data, det_order=det_order, k_ar_diff=k_ar_diff, method="trace")

    # ── ساخت جدول نتایج ──
    trace_table = []
    for i in range(k):
        trace_table.append(
            {
                "hypothesis": f"r ≤ {i}",
                "trace_stat": round(float(trace_stat[i]), 4),
                "critical_90pct": round(float(trace_crit[i, 0]), 4),
                "critical_95pct": round(float(trace_crit[i, 1]), 4),
                "critical_99pct": round(float(trace_crit[i, 2]), 4),
                "reject_95pct": bool(trace_stat[i] > trace_crit[i, 1]),
            }
        )

    max_table = []
    for i in range(k):
        max_table.append(
            {
                "hypothesis": f"r = {i}",
                "max_stat": round(float(max_stat[i]), 4),
                "critical_90pct": round(float(max_crit[i, 0]), 4),
                "critical_95pct": round(float(max_crit[i, 1]), 4),
                "critical_99pct": round(float(max_crit[i, 2]), 4),
                "reject_95pct": bool(max_stat[i] > max_crit[i, 1]),
            }
        )

    # ── چاپ نتایج ──
    print("\n    نتایج TRACE:")
    print(f"    {'فرضیه':>8s}  {'آماره':>10s}  {'CV(90%)':>10s}  {'CV(95%)':>10s}  {'CV(99%)':>10s}  {'نتیجه':>6s}")
    for row in trace_table:
        reject = "✅" if row["reject_95pct"] else "❌"
        print(
            f"    {row['hypothesis']:>8s}  {row['trace_stat']:>10.4f}  "
            f"{row['critical_90pct']:>10.4f}  {row['critical_95pct']:>10.4f}  "
            f"{row['critical_99pct']:>10.4f}  {reject}"
        )

    print("\n    نتایج λmax:")
    print(f"    {'فرضیه':>8s}  {'آماره':>10s}  {'CV(90%)':>10s}  {'CV(95%)':>10s}  {'CV(99%)':>10s}  {'نتیجه':>6s}")
    for row in max_table:
        reject = "✅" if row["reject_95pct"] else "❌"
        print(
            f"    {row['hypothesis']:>8s}  {row['max_stat']:>10.4f}  "
            f"{row['critical_90pct']:>10.4f}  {row['critical_95pct']:>10.4f}  "
            f"{row['critical_99pct']:>10.4f}  {reject}"
        )

    print("\n    تعداد بردار همگرایی:")
    print(f"      TRACE: {n_coint_trace}")
    print(f"      λmax:  {n_coint_max}")

    # ── استخراج بردارهای همگرایی ──
    evec = result.evec  # بردارهای ویژه
    # نرمال‌سازی: اولین متغیر = 1
    betas = []
    if n_coint_trace > 0:
        for r in range(min(n_coint_trace, evec.shape[1])):
            beta = evec[:, r]
            if abs(beta[0]) > 1e-10:
                beta = beta / beta[0]  # نرمال‌سازی نسبت به اولین متغیر
            beta_dict = {avail[i]: round(float(beta[i]), 6) for i in range(len(avail))}
            betas.append({"rank": r + 1, "coefficients": beta_dict})
            print(f"\n    بردار همگرایی #{r + 1}:")
            for var, coef in beta_dict.items():
                print(f"      {var:12s}: {coef:>12.6f}")

    return {
        "variables": avail,
        "nobs": n,
        "det_order": det_order,
        "k_ar_diff": k_ar_diff,
        "n_cointegration_trace": n_coint_trace,
        "n_cointegration_max": n_coint_max,
        "trace_test": trace_table,
        "max_test": max_table,
        "cointegrating_vectors": betas,
        "conclusion": (f"تعداد {n_coint_trace} بردار همگرایی تأیید شد" if n_coint_trace > 0 else "همگرایی تأیید نشد"),
    }


# ═══════════════════════════════════════════════════════════════
#  بخش ۶: تفاضل مرتبه اول
# ═══════════════════════════════════════════════════════════════


def run_first_diff_adf(df: pd.DataFrame, variables: list[str]) -> pd.DataFrame:
    """آزمون ADF روی تفاضل مرتبه اول (برای تأیید I(1) بودن)."""
    print("\n" + "═" * 70)
    print("  بخش ۶: آزمون ADF روی تفاضل مرتبه اول ΔX")
    print("═" * 70)

    results = []
    for var in variables:
        if var not in df.columns:
            continue
        series = df[var].diff().dropna()
        if len(series) < 10:
            continue

        res = adf_test_full(series, f"Δ{var}", regression="c")
        status = "✅ سکونی" if res.get("is_stationary_5pct") else "❌ ریشه واحد"
        print(f"    Δ{var:12s}: ADF={res['adf_statistic']:>10.4f}  p={res['p_value']:>10.6f}  → {status}")
        results.append(res)

    return pd.DataFrame(results)


# ═══════════════════════════════════════════════════════════════
#  بخش ۷: گزارش جامع
# ═══════════════════════════════════════════════════════════════


def generate_full_report(
    adf_results: pd.DataFrame,
    perron_results: pd.DataFrame,
    diff_adf_results: pd.DataFrame,
    aeg_results: dict,
    crdw_results: dict,
    johansen_results: dict,
) -> str:
    """تولید گزارش جامع متنی."""
    lines = [
        "═" * 70,
        "  گزارش جامع آزمون‌های ریشه واحد و همگرایی",
        "  پروژه: عوامل موثر بر نرخ ارز در ایران",
        "═" * 70,
        "",
    ]

    # ── ADF ──
    lines.append("─" * 70)
    lines.append("  ۱. آزمون ریشه واحد ADF (روی سطح)")
    lines.append("─" * 70)
    if not adf_results.empty:
        lines.append(
            f"  {'متغیر':>15s}  {'نوع':>5s}  {'ADF':>10s}  {'p-value':>10s}  "
            f"{'CV(1%)':>8s}  {'CV(5%)':>8s}  {'نتیجه':>20s}"
        )
        for _, row in adf_results.iterrows():
            reg = "c" if row.get("regression") == "c" else "ct"
            adf = row.get("adf_statistic", "N/A")
            pval = row.get("p_value", "N/A")
            cv1 = row.get("critical_1pct", "N/A")
            cv5 = row.get("critical_5pct", "N/A")
            concl = row.get("conclusion", "N/A")
            lines.append(
                f"  {row['variable']:>15s}  {reg:>5s}  {adf:>10.4f}  {pval:>10.6f}  {cv1:>8.4f}  {cv5:>8.4f}  {concl}"
            )
    lines.append("")

    # ── Perron ──
    if not perron_results.empty:
        lines.append("─" * 70)
        lines.append("  ۲. آزمون پرون (شکست ساختاری)")
        lines.append("─" * 70)
        for _, row in perron_results.iterrows():
            if row.get("status") != "completed":
                continue
            lines.append(
                f"  {row['variable']:>15s}  مدل {row['model']}: "
                f"t={row['t_statistic']:>8.4f}  "
                f"CV(5%)={row['critical_5pct']:>8.4f}  → {row['conclusion']}"
            )
        lines.append("")

    # ── ΔX ADF ──
    if not diff_adf_results.empty:
        lines.append("─" * 70)
        lines.append("  ۳. آزمون ADF روی تفاضل مرتبه اول (ΔX)")
        lines.append("─" * 70)
        for _, row in diff_adf_results.iterrows():
            status = "✅ سکونی" if row.get("is_stationary_5pct") else "❌ ریشه واحد"
            lines.append(
                f"  {row['variable']:>15s}: ADF={row['adf_statistic']:>10.4f}  p={row['p_value']:>10.6f}  → {status}"
            )
        lines.append("")

    # ── AEG ──
    if aeg_results and aeg_results.get("status") != "missing_variables":
        lines.append("─" * 70)
        lines.append("  ۴. آزمون انگل-گرنجر (AEG)")
        lines.append("─" * 70)
        if "y_variable" in aeg_results:
            lines.append(f"  مدل: {aeg_results['y_variable']} ~ {' + '.join(aeg_results['X_variables'])}")
            lines.append(f"  ADF پسماند: {aeg_results['adf_statistic']:.4f}")
            lines.append(f"  CV(5%) AEG: {aeg_results['critical_5pct_aeg']:.4f}")
            lines.append(f"  R²: {aeg_results['r_squared']:.4f}")
            lines.append(f"  نتیجه: {aeg_results['conclusion']}")
        lines.append("")

    # ── CRDW ──
    if crdw_results and crdw_results.get("status") != "missing_variables":
        lines.append("─" * 70)
        lines.append("  ۵. آزمون دوربین-واتسون (CRDW)")
        lines.append("─" * 70)
        if "dw_statistic" in crdw_results:
            lines.append(f"  مدل: {crdw_results['y_variable']} ~ {' + '.join(crdw_results['X_variables'])}")
            lines.append(f"  DW: {crdw_results['dw_statistic']:.4f}")
            lines.append(f"  CV(1%) CRDW: {crdw_results['critical_1pct_crdw']:.4f}")
            lines.append(f"  نتیجه: {crdw_results['conclusion']}")
        lines.append("")

    # ── Johansen ──
    if johansen_results and johansen_results.get("status") != "insufficient_data":
        lines.append("─" * 70)
        lines.append("  ۶. آزمون یوهانسن")
        lines.append("─" * 70)
        if "n_cointegration_trace" in johansen_results:
            lines.append(f"  متغیرها: {', '.join(johansen_results['variables'])}")
            lines.append(f"  تعداد بردار همگرایی (TRACE): {johansen_results['n_cointegration_trace']}")
            lines.append(f"  تعداد بردار همگرایی (λmax):  {johansen_results['n_cointegration_max']}")
            lines.append(f"  نتیجه: {johansen_results['conclusion']}")

            # بردارهای همگرایی
            if johansen_results.get("cointegrating_vectors"):
                lines.append("\n  بردارهای همگرایی (نرمال‌سازی‌شده):")
                for beta in johansen_results["cointegrating_vectors"]:
                    lines.append(f"    بردار #{beta['rank']}:")
                    for var, coef in beta["coefficients"].items():
                        lines.append(f"      {var:12s}: {coef:>12.6f}")
        lines.append("")

    # ── جمع‌بندی ──
    lines.append("═" * 70)
    lines.append("  جمع‌بندی")
    lines.append("═" * 70)
    lines.append("")
    lines.append("  خلاصه یافته‌ها:")
    lines.append("")

    if not adf_results.empty:
        stationary = adf_results[adf_results.get("is_stationary_5pct", False)]
        unit_root = adf_results[not adf_results.get("is_stationary_5pct", False)]
        lines.append(f"  • متغیرهای سکونی (I(0)): {len(stationary)}")
        lines.append(f"  • متغیرهای ریشه واحد (I(1)): {len(unit_root)}")

    if johansen_results and "n_cointegration_trace" in johansen_results:
        n_coint = johansen_results["n_cointegration_trace"]
        lines.append(f"  • تعداد بردارهای همگرایی: {n_coint}")

    lines.append("")
    lines.append("═" * 70)

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="آزمون‌های ریشه واحد و همگرایی",
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        required=True,
        help="مسیر فایل CSV داده‌ها",
    )
    parser.add_argument(
        "--vars",
        "-v",
        type=str,
        default=None,
        help="لیست متغیرها با کاما (مثلاً: NER,GDP,M1,P,Oil)",
    )
    parser.add_argument(
        "--cointegration",
        type=str,
        default=None,
        help="متغیرهای مدل همگرایی (مثلاً: NER,GDP,M1,P)",
    )
    parser.add_argument(
        "--dep",
        type=str,
        default="NER",
        help="متغیر وابسته در مدل همگرایی (پیش‌فرض: NER)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="اجرای تمام آزمون‌ها",
    )
    parser.add_argument(
        "--johansen-vars",
        type=str,
        default=None,
        help="متغیرهای آزمون یوهانسن (مثلاً: LNER,LGDP,LM1,LPOIL)",
    )
    parser.add_argument(
        "--skip-unit-root",
        action="store_true",
        help="رد شدن از آزمون ریشه واحد",
    )
    parser.add_argument(
        "--skip-cointegration",
        action="store_true",
        help="رد شدن از آزمون‌های همگرایی",
    )
    return parser.parse_args()


# ═══════════════════════════════════════════════════════════════
#  اجرای اصلی
# ═══════════════════════════════════════════════════════════════


def main():
    args = parse_args()

    print("=" * 70)
    print("  آزمون‌های ریشه واحد و همگرایی")
    print(f"  فایل ورودی: {args.input}")
    print("=" * 70)

    # ── بارگذاری داده ──
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"\n  ✗ فایل یافت نشد: {input_path}")
        sys.exit(1)

    df = pd.read_csv(input_path, encoding="utf-8-sig") if input_path.suffix == ".csv" else pd.read_json(input_path)

    print(f"\n  ✓ {len(df)} ردیف، {len(df.columns)} ستون")
    print(f"  ستون‌ها: {', '.join(df.columns[:20])}")

    # ── تعیین متغیرها ──
    default_vars = ["NER", "RER_approx", "LM1", "DM", "LGDP", "LG", "LP", "LPOIL", "LPGOLD", "OPN", "IRAT"]

    variables = [v.strip() for v in args.vars.split(",")] if args.vars else [v for v in default_vars if v in df.columns]

    print(f"  متغیرهای انتخابی: {', '.join(variables)}")

    # ── آزمون‌های ریشه واحد ──
    adf_df = pd.DataFrame()
    perron_df = pd.DataFrame()
    diff_adf_df = pd.DataFrame()

    if not args.skip_unit_root:
        adf_df = run_adf_battery(df, variables)
        perron_df = run_perron_battery(df, variables)
        diff_adf_df = run_first_diff_adf(df, variables)

        # ذخیره نتایج
        if not adf_df.empty:
            adf_path = OUTPUT_DIR / "adf_results.csv"
            adf_df.to_csv(adf_path, index=False)
            print(f"\n    💾 نتایج ADF: {adf_path}")

        if not perron_df.empty:
            perron_path = OUTPUT_DIR / "perron_results.csv"
            perron_df.to_csv(perron_path, index=False)
            print(f"    💾 نتایج پرون: {perron_path}")

        if not diff_adf_df.empty:
            diff_path = OUTPUT_DIR / "diff_adf_results.csv"
            diff_adf_df.to_csv(diff_path, index=False)
            print(f"    💾 نتایج ΔX ADF: {diff_path}")

    # ── آزمون‌های همگرایی ──
    aeg_result = {}
    crdw_result = {}
    johansen_result = {}

    if not args.skip_cointegration:
        # تعیین متغیرهای همگرایی
        if args.cointegration:
            coint_vars = [v.strip() for v in args.cointegration.split(",")]
        elif args.all:
            coint_vars = variables
        else:
            # استفاده از متغیرهای پیش‌فرض مقاله
            coint_vars = [v for v in ["NER", "G", "GDP", "I", "P", "Poil", "Pgold"] if v in df.columns]

        if len(coint_vars) >= 2:
            dep = args.dep if args.dep in df.columns else coint_vars[0]
            indep = [v for v in coint_vars if v != dep]

            # AEG
            aeg_result = run_engle_granger_battery(df, dep, indep)
            if "status" not in aeg_result or aeg_result["status"] == "completed":
                aeg_path = OUTPUT_DIR / "aeg_results.json"
                with open(aeg_path, "w", encoding="utf-8") as f:
                    json.dump(aeg_result, f, ensure_ascii=False, indent=2, default=str)
                print(f"    💾 نتایج AEG: {aeg_path}")

            # CRDW
            crdw_result = run_crdw_battery(df, dep, indep)
            if "status" not in crdw_result or crdw_result["status"] == "completed":
                crdw_path = OUTPUT_DIR / "crdw_results.json"
                with open(crdw_path, "w", encoding="utf-8") as f:
                    json.dump(crdw_result, f, ensure_ascii=False, indent=2, default=str)
                print(f"    💾 نتایج CRDW: {crdw_path}")

        # Johansen
        if args.johansen_vars:
            joh_vars = [v.strip() for v in args.johansen_vars.split(",")]
        elif args.all:
            joh_vars = [v for v in ["LNER", "LGDP", "LM1", "LPOIL", "LPGOLD"] if v in df.columns]
        else:
            joh_vars = [v for v in variables if v in df.columns]

        if len(joh_vars) >= 2:
            johansen_result = johansen_test(df, joh_vars)
            if johansen_result.get("status") != "insufficient_data":
                joh_path = OUTPUT_DIR / "johansen_results.json"
                with open(joh_path, "w", encoding="utf-8") as f:
                    json.dump(johansen_result, f, ensure_ascii=False, indent=2, default=str)
                print(f"    💾 نتایج یوهانسن: {joh_path}")

    # ── گزارش نهایی ──
    report = generate_full_report(
        adf_df,
        perron_df,
        diff_adf_df,
        aeg_result,
        crdw_result,
        johansen_result,
    )
    report_path = OUTPUT_DIR / "unit_root_cointegration_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print("\n" + report)
    print(f"\n  📊 گزارش کامل: {report_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
