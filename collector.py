"""
دانلود هوشمند ریزمعاملات بورس: فقط روزهایی که معامله واقعی داشته‌اند
"""

import json
import logging
import os

import requests

# کلید فقط از محیط (BRSAPI_KEY) خوانده می‌شود — مقادیر هاردکد شده در سورس
# از طریق git history لو می‌روند.
API_KEY = (os.environ.get("BRSAPI_API_KEY") or os.environ.get("BRSAPI_KEY") or "").strip()
if not API_KEY:
    raise SystemExit(
        "BRSAPI_KEY تنظیم نشده است. کلید را در .env (یا متغیر محیطی) قرار دهید."
    )
BASE_URL = "https://api.brsapi.ir"
HEADERS = {"User-Agent": "Mozilla/5.0"}
DATES_CACHE_DIR = "symbol_trade_days"
os.makedirs(DATES_CACHE_DIR, exist_ok=True)


def get_active_trade_dates(symbol: str) -> list:
    """
    دریافت لیست تاریخ‌هایی که سهم واقعاً در آن‌ها حجم معامله داشته است.
    با ۱ درخواست، کل تاریخچه روزهای معاملاتی استخراج و کش می‌شود.
    """
    cache_path = os.path.join(DATES_CACHE_DIR, f"{symbol}_days.json")

    # ۱. اگر قبلاً کش شده، از کش بخوانیم تا سهمیه مصرف نشود
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    logging.info(f"دریافت روزهای معاملاتی واقعی نماد {symbol}...")
    try:
        # فراخوانی سابقه قیمت سهم (کندل‌های روزانه)
        resp = requests.get(
            f"{BASE_URL}/Tsetmc/History.php",
            params={"key": API_KEY, "l18": symbol},
            headers=HEADERS,
            timeout=15
        )
        if resp.status_code != 200:
            logging.error(f"خطا در دریافت سابقه {symbol}: کد {resp.status_code}")
            return []

        data = resp.json()

        # استخراج روزهایی با حجم بیشتر از صفر
        active_dates = []

        # بسته به ساختار جیسون خروجی BrsApi (لیست سوابق)
        items = data.get("data", []) if isinstance(data, dict) else data
        if isinstance(items, list):
            for row in items:
                vol = int(row.get("volume") or row.get("qTitTran") or row.get("tvol") or 0)
                if vol > 0:
                    # تاریخ میلادی به شمسی یا فرمت استاندارد YYYY-MM-DD
                    raw_date = str(row.get("date") or row.get("dEven") or "")
                    if len(raw_date) == 8: # مثلا 14020512 یا 20230803
                        d_str = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
                        active_dates.append(d_str)
                    elif "-" in raw_date:
                        active_dates.append(raw_date)

        active_dates = sorted(list(set(active_dates)))

        # ذخیره در فایل کش
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(active_dates, f, ensure_ascii=False)

        logging.info(f"نماد {symbol} مجموعاً {len(active_dates)} روز معاملاتی واقعی دارد.")
        return active_dates

    except Exception as e:
        logging.error(f"خطا در پردازش تاریخ‌های {symbol}: {e}")
        return []
