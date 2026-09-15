#!/usr/bin/env python
"""
آماده‌سازی داده‌های اقتصادسنجی سالانه برای تحلیل عوامل موثر بر نرخ ارز.

این اسکریپت داده‌های خام را پردازش کرده و برای استفاده در آزمون‌های
ریشه واحد، همگرایی، و رگرسیون آماده می‌کند.

متغیرهای مورد استفاده (بر اساس مقاله شریف‌زاده و حقیقت):
  - NER: نرخ اسمی ارز (ریال/دلار)
  - RER: نرخ حقیقی ارز
  - M1: حجم پول در گردش
  - M2: حجم نقدینگی
  - DM: نرخ رشد پول
  - G: هزینه‌های دولت
  - GDP: تولید ناخالص داخلی
  - TOT: رابطه مبادله
  - Poil: قیمت نفت (دلار/بشکه)
  - Pgold: قیمت طلا (ریال/گرم)
  - P: نرخ تورم
  - BD: کسری بودجه دولت
  - OPN: درجه باز بودن اقتصاد
  - I: ارزش سرمایه‌گذاری
  - BR: نرخ سود بانکی
  - MR: نرخ بهره بازار آزاد
  - PROD: نرخ بهرهوری نیروی انسانی
  - IRAT: نسبت سرمایه‌گذاری به GDP
  - POP: نرخ رشد جمعیت
  - X: ارزش صادرات
  - M: ارزش واردات

Usage:
    python scripts/prepare_econometric_data.py
    python scripts/prepare_econometric_data.py --years 1340-1379
    python scripts/prepare_econometric_data.py --input-dir my_data/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ── setup project root ──
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

OUTPUT_DIR = _project_root / "exchange_rate_data"
OUTPUT_DIR.mkdir(exist_ok=True)


# ═══════════════════════════════════════════════════════════════
#  1. بارگذاری داده‌های خام
# ═══════════════════════════════════════════════════════════════


def load_raw_data(input_dir: Path) -> pd.DataFrame:
    """
    بارگذاری فایل‌های CSV/JSON خام و ترکیب آنها.
    """
    frames = []

    for ext in ("*.csv", "*.json"):
        for fp in sorted(input_dir.glob(ext)):
            try:
                if fp.suffix == ".csv":
                    df = pd.read_csv(fp, encoding="utf-8-sig")
                else:
                    df = pd.read_json(fp, encoding="utf-8")
                df["_source"] = fp.stem
                frames.append(df)
                print(f"    ✓ {fp.name}: {len(df)} ردیف")
            except Exception as e:
                print(f"    ✗ {fp.name}: {e}")

    if not frames:
        print("    ⚠ فایلی یافت نشد")
        return pd.DataFrame()

    return frames


# ═══════════════════════════════════════════════════════════════
#  2. پردازش متغیرها
# ═══════════════════════════════════════════════════════════════


def compute_derived_variables(df: pd.DataFrame) -> pd.DataFrame:
    """
    محاسبه متغیرهای مشتق از داده‌های خام.

    بر اساس تعاریف مقاله شریف‌زاده و حقیقت.
    """
    result = df.copy()

    # ── نرخ ارز ──
    if "usd_close" in result.columns:
        result["NER"] = result["usd_close"]

    # ── نرخ رشد پول (DM) ──
    # DM = ln(M1_t) - ln(M1_{t-1})
    if "m1" in result.columns:
        result["LM1"] = np.log(result["m1"])
        result["DM"] = result["LM1"].diff()

    # ── نرخ رشد نقدینگی ──
    if "m2" in result.columns:
        result["LM2"] = np.log(result["m2"])

    # ── لگاریتم متغیرها ──
    log_mapping = {
        "NER": "LNER",
        "GDP": "LGDP",
        "G": "LG",
        "P": "LP",
        "Poil": "LPOIL",
        "Pgold": "LPGOLD",
        "BD": "LBD",
    }
    for raw, log_name in log_mapping.items():
        if raw in result.columns:
            # Avoid log of zero/negative
            valid = result[raw] > 0
            result.loc[valid, log_name] = np.log(result.loc[valid, raw])

    # ── متغیرهای نسبی ──
    # OPN = (X + M) / GDP
    if all(c in result.columns for c in ("X", "M", "GDP")):
        result["OPN"] = (result["X"] + result["M"]) / result["GDP"]

    # IRAT = I / GDP
    if all(c in result.columns for c in ("I", "GDP")):
        result["IRAT"] = result["I"] / result["GDP"]

    # ── لگاریتم متغیرهای نسبی ──
    for col in ("OPN", "IRAT"):
        if col in result.columns:
            valid = result[col] > 0
            result.loc[valid, f"L{col}"] = np.log(result.loc[valid, col])

    return result


def compute_rer(df: pd.DataFrame) -> pd.DataFrame:
    """
    محاسبه نرخ حقیقی ارز (RER).

    فرمول ساده:
    RER = NER × (CPI_ایران / CPI_آمریکا)

    یا به صورت لگاریتمی:
    LRER = LNER + LP - LP*

    در صورت نبود CPI آمریکا، از تقریب زیر استفاده می‌شود:
    RER ≈ NER × (1 + π_ایران) / (1 + π_آمریکا)
    """
    result = df.copy()

    if "NER" in result.columns and "P" in result.columns:
        # استفاده از نرخ تورم داخلی به عنوان تقریب
        # (در صورت داشتن CPI آمریکا، باید اصلاح شود)
        result["RER_approx"] = result["NER"] * (1 + result["P"] / 100)

        # لگاریتمی
        valid = result["RER_approx"] > 0
        result.loc[valid, "LRER"] = np.log(result.loc[valid, "RER_approx"])

    return result


# ═══════════════════════════════════════════════════════════════
#  3. آزمون ریشه واحد (Unit Root Test)
# ═══════════════════════════════════════════════════════════════


def adf_test(series: pd.Series, name: str) -> dict:
    """
    آزمون دیکی-فولر تعمیم‌یافته (ADF).

    H₀: متغیر ریشه واحد دارد (غیرسکون)
    H₁: متغیر سکونی است

    اگر p-value < 0.05 → رد H₀ → متغیر سکونی است
    """
    try:
        from statsmodels.tsa.stattools import adfuller

        clean = series.dropna()
        if len(clean) < 10:
            return {"variable": name, "adf_stat": None, "p_value": None, "status": "insufficient_data"}

        result = adfuller(clean, autolag="AIC")

        return {
            "variable": name,
            "adf_stat": round(result[0], 4),
            "p_value": round(result[1], 6),
            "lags_used": result[2],
            "critical_1pct": round(result[4]["1%"], 4),
            "critical_5pct": round(result[4]["5%"], 4),
            "critical_10pct": round(result[4]["10%"], 4),
            "is_stationary": result[1] < 0.05,
            "status": "stationary" if result[1] < 0.05 else "unit_root",
        }
    except ImportError:
        return {"variable": name, "status": "statsmodels_not_installed"}
    except Exception as e:
        return {"variable": name, "status": f"error: {e}"}


def run_unit_root_tests(df: pd.DataFrame) -> pd.DataFrame:
    """
    اجرای آزمون ریشه واحد روی تمام متغیرها.
    """
    print("\n  [Unit Root] اجرای آزمون ADF روی متغیرها...")

    # متغیرهای مورد بررسی
    test_vars = [
        "NER",
        "RER_approx",
        "LM1",
        "DM",
        "LGDP",
        "LG",
        "LP",
        "LPOIL",
        "LPGOLD",
        "OPN",
        "IRAT",
    ]

    # فقط متغیرهای موجود را تست کن
    test_vars = [v for v in test_vars if v in df.columns]

    results = []
    for var in test_vars:
        res = adf_test(df[var], var)
        results.append(res)
        status = "✅ سکونی" if res.get("is_stationary") else "❌ ریشه واحد"
        print(f"    {var:15s}: ADF={res.get('adf_stat', 'N/A'):>10s}  p={res.get('p_value', 'N/A'):>10s}  {status}")

    return pd.DataFrame(results)


# ═══════════════════════════════════════════════════════════════
#  4. رگرسیون
# ═══════════════════════════════════════════════════════════════


def run_regression(df: pd.DataFrame, dependent: str, independents: list[str]) -> dict:
    """
    رگرسیون خطی چندگانه.
    """
    try:
        import statsmodels.api as sm

        # Filter available columns
        available = [v for v in independents if v in df.columns]
        if dependent not in df.columns or not available:
            return {"error": "missing variables"}

        # Drop rows with NaN
        subset = df[[dependent] + available].dropna()
        if len(subset) < len(available) + 2:
            return {"error": "insufficient data"}

        y = subset[dependent]
        X = sm.add_constant(subset[available])

        model = sm.OLS(y, X).fit()

        return {
            "dependent": dependent,
            "independents": available,
            "r_squared": round(model.rsquared, 4),
            "adj_r_squared": round(model.rsquared_adj, 4),
            "f_statistic": round(model.fvalue, 4),
            "f_p_value": round(model.f_pvalue, 6),
            "coefficients": {
                name: {
                    "value": round(float(model.params[name]), 6),
                    "std_err": round(float(model.bse[name]), 6),
                    "p_value": round(float(model.pvalues[name]), 6),
                    "significant_5pct": float(model.pvalues[name]) < 0.05,
                }
                for name in available
            },
            "nobs": int(model.nobs),
        }
    except ImportError:
        return {"error": "statsmodels not installed"}
    except Exception as e:
        return {"error": str(e)}


def run_all_regressions(df: pd.DataFrame) -> dict:
    """
    اجرای رگرسیون‌های اصلی مقاله.
    """
    print("\n  [Regression] اجرای رگرسیون‌ها...")

    regressions = {}

    # معادله NER
    if "NER" in df.columns:
        ner_vars = ["G", "GDP", "I", "TOT", "P", "Poil", "Pgold"]
        ner_vars = [v for v in ner_vars if v in df.columns]
        if ner_vars:
            print(f"    NER ~ {' + '.join(ner_vars)}")
            regressions["NER"] = run_regression(df, "NER", ner_vars)

    # معادله LNER
    if "LNER" in df.columns:
        lner_vars = ["DM", "LGDP", "LPGOLD", "BR"]
        lner_vars = [v for v in lner_vars if v in df.columns]
        if lner_vars:
            print(f"    LNER ~ {' + '.join(lner_vars)}")
            regressions["LNER"] = run_regression(df, "LNER", lner_vars)

    # معادله LRER
    if "LRER" in df.columns:
        lrer_vars = ["LG", "LPOIL", "BR", "LI", "LGDP"]
        lrer_vars = [v for v in lrer_vars if v in df.columns]
        if lrer_vars:
            print(f"    LRER ~ {' + '.join(lrer_vars)}")
            regressions["LRER"] = run_regression(df, "LRER", lrer_vars)

    return regressions


# ═══════════════════════════════════════════════════════════════
#  5. گزارش نهایی
# ═══════════════════════════════════════════════════════════════


def generate_report(
    df: pd.DataFrame,
    unit_root_results: pd.DataFrame,
    regression_results: dict,
) -> str:
    """تولید گزارش متنی خلاصه."""
    lines = [
        "=" * 70,
        "  گزارش تحلیل اقتصادسنجی",
        "  عوامل موثر بر نرخ ارز در ایران",
        "=" * 70,
        "",
        f"  تعداد مشاهدات: {len(df)}",
        f"  متغیرها: {len(df.columns)}",
        "",
    ]

    # Unit root
    lines.append("─" * 70)
    lines.append("  نتایج آزمون ریشه واحد (ADF)")
    lines.append("─" * 70)
    if not unit_root_results.empty:
        for _, row in unit_root_results.iterrows():
            status = "✅ سکونی" if row.get("is_stationary") else "❌ ریشه واحد"
            adf = row.get("adf_stat", "N/A")
            pval = row.get("p_value", "N/A")
            lines.append(f"  {row['variable']:15s}: ADF={adf}  p={pval}  {status}")
    lines.append("")

    # Regressions
    lines.append("─" * 70)
    lines.append("  نتایج رگرسیون")
    lines.append("─" * 70)
    for name, res in regression_results.items():
        if "error" in res:
            lines.append(f"  {name}: خطا — {res['error']}")
            continue
        lines.append(f"\n  معادله {name}:")
        lines.append(f"    R² = {res['r_squared']}  |  R² adjusted = {res['adj_r_squared']}")
        lines.append(f"    F-stat = {res['f_statistic']}  (p = {res['f_p_value']})")
        lines.append(f"    تعداد مشاهدات: {res['nobs']}")
        lines.append("    ضرایب:")
        for var, coeff in res["coefficients"].items():
            sig = "***" if coeff["significant_5pct"] else ""
            lines.append(
                f"      {var:10s}: β={coeff['value']:>10.4f}  "
                f"SE={coeff['std_err']:>10.4f}  "
                f"p={coeff['p_value']:>8.4f}  {sig}"
            )
    lines.append("")

    # Summary
    lines.append("─" * 70)
    lines.append("  خلاصه متغیرها")
    lines.append("─" * 70)
    desc = df.describe().round(4)
    lines.append(desc.to_string())

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
#  6. CLI
# ═══════════════════════════════════════════════════════════════


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="آماده‌سازی داده‌های اقتصادسنجی سالانه",
    )
    parser.add_argument(
        "--input-dir",
        "-i",
        type=str,
        default="exchange_rate_data",
        help="پوشه داده‌های خام",
    )
    parser.add_argument(
        "--years",
        "-y",
        type=str,
        default="1340-1379",
        help="بازه سال‌ها (شمسی)",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="رد شدن از آزمون‌ها (فقط آماده‌سازی)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="econometric_dataset.csv",
        help="نام فایل خروجی",
    )
    return parser.parse_args()


# ═══════════════════════════════════════════════════════════════
#  7. اجرای اصلی
# ═══════════════════════════════════════════════════════════════


def main():
    args = parse_args()
    input_dir = Path(args.input_dir)

    print("=" * 70)
    print("  آماده‌سازی داده‌های اقتصادسنجی")
    print(f"  پوشه ورودی: {input_dir}")
    print(f"  بازه سال‌ها: {args.years}")
    print("=" * 70)

    # ── Load data ──
    print("\n  [1/5] بارگذاری داده‌های خام...")
    raw_frames = load_raw_data(input_dir)

    if isinstance(raw_frames, list):
        if not raw_frames:
            print("\n  ⚠ داده‌ای یافت نشد!")
            print("  ابتدا اسکریپت fetch_exchange_rate_data.py را اجرا کنید.")
            sys.exit(1)
        # Merge all frames on date
        df = raw_frames[0]
        for frame in raw_frames[1:]:
            if "date" in df.columns and "date" in frame.columns:
                df = pd.merge(df, frame, on="date", how="outer", suffixes=("", "_dup"))
            else:
                df = pd.concat([df, frame], ignore_index=True)
        # Remove duplicate columns
        df = df.loc[:, ~df.columns.str.endswith("_dup")]
    else:
        df = raw_frames

    if df.empty:
        print("\n  ⚠ داده خالی!")
        sys.exit(1)

    print(f"    ✓ {len(df)} ردیف، {len(df.columns)} ستون")

    # ── Compute derived variables ──
    print("\n  [2/5] محاسبه متغیرهای مشتق...")
    df = compute_derived_variables(df)
    df = compute_rer(df)

    available = [
        c for c in ["NER", "RER_approx", "DM", "LGDP", "LG", "LP", "LPOIL", "LPGOLD", "OPN", "IRAT"] if c in df.columns
    ]
    print(f"    ✓ متغیرهای محاسبه‌شده: {', '.join(available)}")

    # ── Save processed data ──
    print("\n  [3/5] ذخیره داده‌های پردازش‌شده...")
    output_path = OUTPUT_DIR / args.output
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"    ✓ ذخیره شد: {output_path}")

    if not args.skip_tests:
        # ── Unit root tests ──
        print("\n  [4/5] آزمون ریشه واحد...")
        unit_root_df = run_unit_root_tests(df)
        if not unit_root_df.empty:
            ur_path = OUTPUT_DIR / "unit_root_results.csv"
            unit_root_df.to_csv(ur_path, index=False)
            print(f"    ✓ نتایج: {ur_path}")

        # ── Regressions ──
        print("\n  [5/5] رگرسیون‌ها...")
        reg_results = run_all_regressions(df)

        # Save regression results
        reg_path = OUTPUT_DIR / "regression_results.json"
        with open(reg_path, "w", encoding="utf-8") as f:
            json.dump(reg_results, f, ensure_ascii=False, indent=2, default=str)
        print(f"    ✓ نتایج: {reg_path}")

        # ── Report ──
        report = generate_report(df, unit_root_df, reg_results)
        report_path = OUTPUT_DIR / "analysis_report.txt"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n    📊 گزارش: {report_path}")
    else:
        print("\n  [4/5] رد شدن از آزمون‌ها...")
        print("  [5/5] رد شدن از رگرسیون‌ها...")

    print("\n" + "=" * 70)
    print("  ✅ تمام شد!")
    print("=" * 70)


if __name__ == "__main__":
    main()
