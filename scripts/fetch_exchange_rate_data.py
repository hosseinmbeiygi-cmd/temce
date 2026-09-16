#!/usr/bin/env python
"""
جمع‌آوری داده‌های نرخ ارز و متغیرهای کلان اقتصادی برای پروژه تحقیق
عوامل موثر بر نرخ ارز در ایران.

منابع داده:
  - BrsApi: نرخ ارز، سکه، طلا
  - Yahoo Finance: قیمت نفت خام (Brent), طلای جهانی
  - بانک مرکزی ایران: نرخ تورم (CPI)
  - World Bank / OPEC: متغیرهای کلان

Usage:
    python scripts/fetch_exchange_rate_data.py                      # همه داده‌ها
    python scripts/fetch_exchange_rate_data.py --only exchange      # فقط نرخ ارز
    python scripts/fetch_exchange_rate_data.py --only macro         # فقط متغیرهای کلان
    python scripts/fetch_exchange_rate_data.py --only gold          # فقط طلا
    python scripts/fetch_exchange_rate_data.py --only oil           # فقط نفت
    python scripts/fetch_exchange_rate_data.py --format csv         # خروجی CSV
    python scripts/fetch_exchange_rate_data.py --format excel       # خروجی Excel
    python scripts/fetch_exchange_rate_data.py --start 1397-01-01   # تاریخ شروع شمسی
    python scripts/fetch_exchange_rate_data.py --daily              # داده روزانه
    python scripts/fetch_exchange_rate_data.py --monthly            # داده ماهانه
    python scripts/fetch_exchange_rate_data.py --macro-yearly       # متغیرهای کلان سالانه
    python scripts/fetch_exchange_rate_data.py --all-in-one         # ترکیب همه در یک فایل
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ── setup project root ──
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv

from core.time import utc_now_naive

load_dotenv()

# ── constants ──
BRSAPI_KEY = os.environ.get("BRSAPI_API_KEY", "")
BRSAPI_BASE = "https://api.brsapi.ir/Market/Gold_Currency_Pro.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
}
OUTPUT_DIR = _project_root / "exchange_rate_data"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── BrsApi currency symbols ──
USD_SYMBOLS = ["USD", "usd", "دلار آمریکا", "Dollar"]
GOLD_SYMBOLS = ["سکه امامی", "Gold_Imami", "Gold18"]

# ── Yahoo Finance symbols ──
YAHOO_OIL = "BZ=F"  # Brent Crude Oil
YAHOO_GOLD = "GC=F"  # Gold Futures
YAHOO_DXY = "DX-Y.NYB"  # US Dollar Index


# ═══════════════════════════════════════════════════════════════
#  1. BrsApi — نرخ ارز و سکه
# ═══════════════════════════════════════════════════════════════


def brsapi_get_currencies() -> list[dict]:
    """دریافت لیست ارزها از BrsApi."""
    params = {"key": BRSAPI_KEY, "section": "currency"}
    resp = requests.get(BRSAPI_BASE, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("currency", [])


def brsapi_get_gold_coins() -> list[dict]:
    """دریافت لیست سکه و طلا از BrsApi."""
    params = {"key": BRSAPI_KEY, "section": "gold_coin"}
    resp = requests.get(BRSAPI_BASE, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("gold_coin", [])


def brsapi_get_current_price(symbol: str) -> dict | None:
    """دریافت قیمت لحظه‌ای یک نماد."""
    items = brsapi_get_currencies()
    items += brsapi_get_gold_coins()
    for item in items:
        if item.get("symbol") == symbol or item.get("name") == symbol:
            return item
    return None


def brsapi_get_history(
    symbol: str,
    date_start: str = "1390-01-01",
    date_end: str | None = None,
) -> list[dict]:
    """دریافت تاریخچه قیمت یک نماد از BrsApi."""
    if date_end is None:
        date_end = utc_now_naive().strftime("%Y-%m-%d")
    params = {
        "key": BRSAPI_KEY,
        "history": 2,
        "symbol": symbol,
        "date_start": date_start,
        "date_end": date_end,
    }
    resp = requests.get(BRSAPI_BASE, params=params, headers=HEADERS, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return data.get("history_daily") or data.get("result") or []


def fetch_usd_history(start_date: str = "1390-01-01") -> list[dict]:
    """دریافت تاریخچه نرخ دلار."""
    print("  [BrsApi] دریافت تاریخچه نرخ دلار...")
    for symbol in USD_SYMBOLS:
        try:
            records = brsapi_get_history(symbol, start_date)
            if records:
                print(f"    ✓ {len(records)} رکورد با نماد '{symbol}'")
                return records
        except Exception as e:
            print(f"    ✗ نماد '{symbol}': {e}")
    print("    ⚠ هیچ داده‌ای یافت نشد")
    return []


def fetch_scoin_history(start_date: str = "1390-01-01") -> list[dict]:
    """دریافت تاریخچه قیمت سکه امامی."""
    print("  [BrsApi] دریافت تاریخچه سکه امامی...")
    for symbol in GOLD_SYMBOLS:
        try:
            records = brsapi_get_history(symbol, start_date)
            if records:
                print(f"    ✓ {len(records)} رکورد با نماد '{symbol}'")
                return records
        except Exception as e:
            print(f"    ✗ نماد '{symbol}': {e}")
    print("    ⚠ هیچ داده‌ای یافت نشد")
    return []


def fetch_all_currencies_snapshot() -> list[dict]:
    """دریافت قیمت لحظه‌ای تمام ارزها."""
    print("  [BrsApi] دریافت قیمت لحظه‌ای تمام ارزها...")
    currencies = brsapi_get_currencies()
    print(f"    ✓ {len(currencies)} ارز یافت شد")
    return currencies


def fetch_all_gold_snapshot() -> list[dict]:
    """دریافت قیمت لحظه‌ای تمام طلا و سکه."""
    print("  [BrsApi] دریافت قیمت لحظه‌ای طلا و سکه...")
    gold = brsapi_get_gold_coins()
    print(f"    ✓ {len(gold)} قلم طلا/سکه یافت شد")
    return gold


# ═══════════════════════════════════════════════════════════════
#  2. Yahoo Finance — نفت خام، طلای جهانی، شاخص دلار
# ═══════════════════════════════════════════════════════════════


def yahoo_get_history(
    ticker: str,
    period1: str = "2010-01-01",
    period2: str | None = None,
    interval: str = "1d",
) -> list[dict]:
    """
    دریافت تاریخچه قیمت از Yahoo Finance (بدون نیاز به API key).

    Args:
        ticker: نماد (مثلاً "BZ=F" برای نفت برنت)
        period1: تاریخ شروع (YYYY-MM-DD)
        period2: تاریخ پایان (YYYY-MM-DD)
        interval: بازه زمانی ("1d", "1wk", "1mo")
    """
    if period2 is None:
        period2 = utc_now_naive().strftime("%Y-%m-%d")

    # Convert to timestamps
    p1 = int(datetime.strptime(period1, "%Y-%m-%d").timestamp())
    p2 = int(datetime.strptime(period2, "%Y-%m-%d").timestamp())

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {
        "period1": p1,
        "period2": p2,
        "interval": interval,
        "events": "history",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    resp = requests.get(url, params=params, headers=headers, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    result = data.get("chart", {}).get("result", [])
    if not result:
        return []

    timestamps = result[0].get("timestamp", [])
    indicators = result[0].get("indicators", {}).get("quote", [{}])[0]

    records = []
    for i, ts in enumerate(timestamps):
        dt = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
        record = {"date": dt}
        for key in ("open", "high", "low", "close", "volume"):
            values = indicators.get(key, [])
            record[key] = values[i] if i < len(values) else None
        records.append(record)

    return records


def fetch_oil_price(start_date: str = "2010-01-01") -> list[dict]:
    """دریافت تاریخچه قیمت نفت خام برنت."""
    print("  [Yahoo] دریافت تاریخچه قیمت نفت برنت...")
    try:
        records = yahoo_get_history(YAHOO_OIL, start_date, interval="1d")
        print(f"    ✓ {len(records)} رکورد دریافت شد")
        return records
    except Exception as e:
        print(f"    ✗ خطا: {e}")
        return []


def fetch_gold_intl(start_date: str = "2010-01-01") -> list[dict]:
    """دریافت تاریخچه قیمت طلای جهانی."""
    print("  [Yahoo] دریافت تاریخچه قیمت طلای جهانی...")
    try:
        records = yahoo_get_history(YAHOO_GOLD, start_date, interval="1d")
        print(f"    ✓ {len(records)} رکورد دریافت شد")
        return records
    except Exception as e:
        print(f"    ✗ خطا: {e}")
        return []


def fetch_dollar_index(start_date: str = "2010-01-01") -> list[dict]:
    """دریافت تاریخچه شاخص دلار."""
    print("  [Yahoo] دریافت تاریخچه شاخص دلار...")
    try:
        records = yahoo_get_history(YAHOO_DXY, start_date, interval="1d")
        print(f"    ✓ {len(records)} رکورد دریافت شد")
        return records
    except Exception as e:
        print(f"    ✗ خطا: {e}")
        return []


# ═══════════════════════════════════════════════════════════════
#  3. متغیرهای کلان اقتصادی (سالانه)
# ═══════════════════════════════════════════════════════════════


def fetch_macro_yearly() -> list[dict]:
    """
    متغیرهای کلان اقتصادی ایران (سالانه).
    این داده‌ها باید دستی یا از منابع رسمی (بانک مرکزی) تکمیل شوند.

    داده‌های زیر از مقاله شریف‌زاده و حقیقت استخراج شده‌اند
    و صرفاً ساختار نمونه هستند.
    """
    print("  [Macro] ساخت فایل نمونه متغیرهای کلان...")

    # ساختار نمونه — داده واقعی باید از بانک مرکزی تکمیل شود
    sample_data = [
        {"year": 1340, "gdp": None, "m1": None, "inflation": None, "oil_price": None, "gold_price": None},
        {"year": 1341, "gdp": None, "m1": None, "inflation": None, "oil_price": None, "gold_price": None},
        # ... تا 1379
        {"year": 1379, "gdp": None, "m1": None, "inflation": None, "oil_price": None, "gold_price": None},
    ]

    print(f"    ✓ ساختار {len(sample_data)} سال آماده شد")
    print("    ⚠ داده‌های واقعی باید از بانک مرکزی تکمیل شوند")
    return sample_data


# ═══════════════════════════════════════════════════════════════
#  4. ذخیره‌سازی
# ═══════════════════════════════════════════════════════════════


def save_json(data: list[dict], filename: str) -> Path:
    """ذخیره داده به فایل JSON."""
    filepath = OUTPUT_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"    💾 ذخیره شد: {filepath} ({len(data)} رکورد)")
    return filepath


def save_csv(data: list[dict], filename: str) -> Path:
    """ذخیره داده به فایل CSV."""
    import csv

    filepath = OUTPUT_DIR / filename
    if not data:
        print("    ⚠ داده‌ای برای ذخیره وجود ندارد")
        return filepath
    keys = data[0].keys()
    with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(data)
    print(f"    💾 ذخیره شد: {filepath} ({len(data)} رکورد)")
    return filepath


def save_excel(data: list[dict], filename: str) -> Path:
    """ذخیره داده به فایل Excel."""
    try:
        import pandas as pd

        filepath = OUTPUT_DIR / filename
        df = pd.DataFrame(data)
        df.to_excel(filepath, index=False, engine="openpyxl")
        print(f"    💾 ذخیره شد: {filepath} ({len(data)} رکورد)")
        return filepath
    except ImportError:
        print("    ⚠ pandas/openpyxl نصب نیست — ذخیره به CSV")
        return save_csv(data, filename.replace(".xlsx", ".csv"))


def save_data(data: list[dict], filename_base: str, fmt: str) -> Path:
    """ذخیره داده با فرمت مشخص."""
    if fmt == "json":
        return save_json(data, f"{filename_base}.json")
    elif fmt == "csv":
        return save_csv(data, f"{filename_base}.csv")
    elif fmt == "excel":
        return save_excel(data, f"{filename_base}.xlsx")
    else:
        return save_json(data, f"{filename_base}.json")


# ═══════════════════════════════════════════════════════════════
#  5. ترکیب داده‌ها (Merge)
# ═══════════════════════════════════════════════════════════════


def merge_daily_data(
    usd: list[dict],
    oil: list[dict],
    gold_intl: list[dict],
    dxy: list[dict],
) -> list[dict]:
    """ترکیب داده‌های روزانه بر اساس تاریخ میلادی."""
    print("\n  [Merge] ترکیب داده‌های روزانه...")

    # Build lookup dicts
    oil_map = {r["date"]: r.get("close") for r in oil if r.get("close")}
    gold_map = {r["date"]: r.get("close") for r in gold_intl if r.get("close")}
    dxy_map = {r["date"]: r.get("close") for r in dxy if r.get("close")}

    merged = []
    for rec in usd:
        date = rec.get("date", "")
        if not date:
            continue
        row = {
            "date": date,
            "usd_close": rec.get("close"),
            "usd_open": rec.get("open"),
            "usd_high": rec.get("high"),
            "usd_low": rec.get("low"),
            "oil_brent": oil_map.get(date),
            "gold_intl_usd": gold_map.get(date),
            "dollar_index": dxy_map.get(date),
        }
        merged.append(row)

    # Fill forward missing values
    for i in range(1, len(merged)):
        for field in ("oil_brent", "gold_intl_usd", "dollar_index"):
            if merged[i][field] is None:
                merged[i][field] = merged[i - 1][field]

    matched = sum(1 for r in merged if r.get("oil_brent") is not None)
    print(f"    ✓ {len(merged)} ردیف ترکیب شد ({matched} با نفت)")
    return merged


# ═══════════════════════════════════════════════════════════════
#  6. CLI
# ═══════════════════════════════════════════════════════════════


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="جمع‌آوری داده‌های نرخ ارز و متغیرهای کلان",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--only",
        "-o",
        choices=["exchange", "gold", "oil", "macro", "macro-yearly", "all-currencies", "all-gold"],
        default=None,
        help="فقط یک نوع داده جمع‌آوری شود",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["json", "csv", "excel"],
        default="csv",
        help="فرمت خروجی (پیش‌فرض: csv)",
    )
    parser.add_argument(
        "--start",
        "-s",
        type=str,
        default="1390-01-01",
        help="تاریخ شروع شمسی (پیش‌فرض: 1390-01-01)",
    )
    parser.add_argument(
        "--daily",
        action="store_true",
        default=True,
        help="داده روزانه (پیش‌فرض)",
    )
    parser.add_argument(
        "--monthly",
        action="store_true",
        help="داده ماهانه",
    )
    parser.add_argument(
        "--macro-yearly",
        action="store_true",
        help="متغیرهای کلان سالانه",
    )
    parser.add_argument(
        "--all-in-one",
        action="store_true",
        help="ترکیب همه داده‌ها در یک فایل",
    )
    parser.add_argument(
        "--output-dir",
        "-d",
        type=str,
        default=None,
        help="پوشه خروجی (پیش‌فرض: exchange_rate_data/)",
    )
    return parser.parse_args()


# ═══════════════════════════════════════════════════════════════
#  7. اجرای اصلی
# ═══════════════════════════════════════════════════════════════


def main():
    args = parse_args()

    global OUTPUT_DIR
    if args.output_dir:
        OUTPUT_DIR = Path(args.output_dir)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("  جمع‌آوری داده‌های نرخ ارز و متغیرهای کلان")
    print(f"  تاریخ شروع: {args.start}")
    print(f"  فرمت خروجی: {args.format}")
    print(f"  پوشه خروجی: {OUTPUT_DIR}")
    print("=" * 70)

    start_time = time.time()

    # ── Check API key ──
    if not BRSAPI_KEY:
        print("\n  ⚠ کلید BRSAPI_API_KEY تنظیم نشده!")
        print("  لطفاً کلید را در فایل .env قرار دهید.")
        print("  ادامه با داده‌های Yahoo Finance...\n")

    # ── Determine start date for Yahoo (Gregorian) ──
    # Rough conversion: start with Gregorian equivalent
    yahoo_start = "2010-01-01"

    # ── Fetch data ──
    usd_data = []
    oil_data = []
    gold_intl_data = []
    dxy_data = []
    scoin_data = []
    macro_data = []

    only = args.only

    if only in (None, "exchange", "gold"):
        usd_data = fetch_usd_history(args.start)
        scoin_data = fetch_scoin_history(args.start)
        time.sleep(0.5)

    if only in (None, "oil"):
        oil_data = fetch_oil_price(yahoo_start)
        time.sleep(0.5)

    if only in (None, "gold"):
        gold_intl_data = fetch_gold_intl(yahoo_start)
        time.sleep(0.5)

    if only in (None,):
        dxy_data = fetch_dollar_index(yahoo_start)
        time.sleep(0.5)

    if only in (None, "all-currencies"):
        currencies = fetch_all_currencies_snapshot()
        if currencies:
            save_data(currencies, "all_currencies_snapshot", args.format)

    if only in (None, "all-gold"):
        gold_items = fetch_all_gold_snapshot()
        if gold_items:
            save_data(gold_items, "all_gold_snapshot", args.format)

    if only in (None, "macro") or args.macro_yearly:
        macro_data = fetch_macro_yearly()

    # ── Save individual datasets ──
    print("\n" + "─" * 50)
    print("  ذخیره فایل‌ها:")
    print("─" * 50)

    if usd_data:
        save_data(usd_data, "usd_irr_daily", args.format)

    if scoin_data:
        save_data(scoin_data, "scoin_imami_daily", args.format)

    if oil_data:
        save_data(oil_data, "oil_brent_daily", args.format)

    if gold_intl_data:
        save_data(gold_intl_data, "gold_intl_daily", args.format)

    if dxy_data:
        save_data(dxy_data, "dollar_index_daily", args.format)

    if macro_data:
        save_data(macro_data, "macro_yearly", args.format)

    # ── Merge all-in-one ──
    if args.all_in_one and usd_data:
        merged = merge_daily_data(usd_data, oil_data, gold_intl_data, dxy_data)
        save_data(merged, "merged_daily_all", args.format)

    # ── Summary ──
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("  خلاصه:")
    print(f"  نرخ دلار:      {len(usd_data)} رکورد")
    print(f"  سکه امامی:     {len(scoin_data)} رکورد")
    print(f"  نفت برنت:      {len(oil_data)} رکورد")
    print(f"  طلای جهانی:    {len(gold_intl_data)} رکورد")
    print(f"  شاخص دلار:     {len(dxy_data)} رکورد")
    print(f"  متغیرهای کلان: {len(macro_data)} رکورد")
    print(f"  مدت زمان:      {elapsed:.1f} ثانیه")
    print(f"  پوشه خروجی:    {OUTPUT_DIR.resolve()}")
    print("=" * 70)


if __name__ == "__main__":
    main()
