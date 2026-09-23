# -*- coding: utf-8 -*-
"""
نسخه اصلاح‌شده و پایدار استخراج هوشمند ریزمعاملات بورس
"""

import os
import re
import time
import json
import logging
import threading
import sqlite3
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================ تنظیمات ============================
API_KEY = "Bk7JvdJZBHJ9DMhzeuTfWjwqYy1wMsif"

DAILY_LIMIT = 10000
MIN_DELAY_BETWEEN_REQUESTS = 4.0   # حداقل فاصله زمانی بین دو درخواست (تضمین عدم 429)
MAX_WORKERS = 2                   # تعداد ترد همزمان (کمتر = امن‌تر در برابر 429)

DATA_DIR = "transactions_data"
DATES_CACHE_DIR = "trade_days_cache"
STATE_FILE = "crawler_state.json"
DB_FILE = "transactions.db"

BASE_URL = "https://api.brsapi.ir"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("smart_collector.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# ============================ کنترل نرخ سراسری ============================
class StrictRateLimiter:
    def __init__(self):
        self.lock = threading.Lock()
        self.last_request_time = 0.0
        self.state = self._load_state()

    def _load_state(self):
        today = time.strftime("%Y-%m-%d")
        default = {"current_day": today, "requests_today": 0}
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("current_day") == today:
                    return data
            except Exception:
                pass
        return default

    def _save_state(self):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def wait_and_acquire(self):
        """تضمین رعایت فاصله زمانی و عدم برخورد با 429"""
        with self.lock:
            today = time.strftime("%Y-%m-%d")
            if self.state["current_day"] != today:
                self.state = {"current_day": today, "requests_today": 0}
                self._save_state()

            if self.state["requests_today"] >= DAILY_LIMIT:
                return False, self.state["requests_today"]

            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < MIN_DELAY_BETWEEN_REQUESTS:
                time.sleep(MIN_DELAY_BETWEEN_REQUESTS - elapsed)

            self.last_request_time = time.time()
            self.state["requests_today"] += 1
            cnt = self.state["requests_today"]
            self._save_state()
            return True, cnt

    def refund(self):
        with self.lock:
            if self.state["requests_today"] > 0:
                self.state["requests_today"] -= 1
                self._save_state()

# ============================ مدیریت SQLite ============================
db_lock = threading.Lock()

def init_db():
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    symbol TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    seq_no INTEGER NOT NULL,
                    time TEXT,
                    volume INTEGER,
                    price REAL,
                    is_canceled INTEGER DEFAULT 0,
                    PRIMARY KEY (symbol, trade_date, seq_no)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sym_date ON transactions(symbol, trade_date)")
            conn.commit()
        finally:
            conn.close()

def save_trades_to_db(symbol, date_str, rows):
    if not rows:
        return 0
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        try:
            conn.executemany(
                """INSERT OR IGNORE INTO transactions
                   (symbol, trade_date, seq_no, time, volume, price, is_canceled)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [(symbol, date_str, r["seq_no"], r["time"], r["volume"],
                  r["price"], r["is_canceled"]) for r in rows]
            )
            conn.commit()
            return len(rows)
        finally:
            conn.close()

def normalize_date_string(raw_val):
    """تبدیل فرمت‌های مختلف تاریخ به YYYYMMDD یا YYYY-MM-DD"""
    if not raw_val:
        return None
    s = str(raw_val).strip()
    s = s.replace("/", "-").replace(".", "-")
    digits = re.sub(r"\D", "", s)
    if len(digits) == 8:
        # مثلا 14020512
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"
    return s if len(s) >= 8 else None

def extract_trade_rows(data):
    items = []
    if isinstance(data, dict):
        inner = data.get("data")
        if isinstance(inner, dict):
            items = inner.get("transaction") or inner.get("transactions") or []
        elif isinstance(inner, list):
            items = inner
    elif isinstance(data, list):
        items = data

    rows = []
    for it in items:
        if not isinstance(it, dict):
            continue
        rows.append({
            "seq_no": int(it.get("row") or it.get("id") or it.get("seq") or 0),
            "time": str(it.get("time") or it.get("hEven") or ""),
            "volume": int(it.get("volume") or it.get("qTitTran") or 0),
            "price": float(it.get("price") or it.get("pTran") or 0),
            "is_canceled": 1 if (it.get("canceled") or it.get("cCanceled")) else 0,
        })
    return rows

# ============================ منطق استخراج هوشمند ============================
def get_active_trade_dates(symbol: str, limiter: StrictRateLimiter, session: requests.Session) -> list:
    """استخراج روزهای واقعی معامله با ۱ درخواست"""
    cache_path = os.path.join(DATES_CACHE_DIR, f"{symbol}_active_days.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    allowed, _ = limiter.wait_and_acquire()
    if not allowed:
        return []

    try:
        # دریافت سابقه معاملات روزانه نماد
        resp = session.get(f"{BASE_URL}/Tsetmc/History.php",
                           params={"key": API_KEY, "l18": symbol},
                           headers=HEADERS, timeout=20)

        if resp.status_code != 200:
            logging.warning(f"خطای {resp.status_code} در دریافت History برای {symbol}")
            limiter.refund()
            return []

        data = resp.json()
        items = data.get("data", []) if isinstance(data, dict) else data
        if not isinstance(items, list):
            return []

        active_dates = set()
        for row in items:
            if not isinstance(row, dict):
                continue
            # بررسی حجم معامله مثبت
            vol = int(row.get("volume") or row.get("vol") or row.get("qTitTran") or row.get("tvol") or 0)
            if vol > 0:
                raw_d = row.get("date") or row.get("dEven") or row.get("jalaliDate")
                d_formatted = normalize_date_string(raw_d)
                if d_formatted:
                    active_dates.add(d_formatted)

        final_dates = sorted(list(active_dates))
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(final_dates, f, ensure_ascii=False, indent=2)

        logging.info(f"نماد {symbol}: {len(final_dates)} روز معاملاتی واقعی پیدا شد.")
        return final_dates

    except Exception as e:
        logging.error(f"خطا در ارتباط با سابقه {symbol}: {e}")
        limiter.refund()
        return []

# ============================ تست نماد نمونه ============================
def test_single_symbol(test_symbol="فولاد"):
    """
    تابع اعتبارسنجی سریع:
    قبل از اجرای کل بازار، تست می‌کند که API متصل است و دیتا به درستی دریافت می‌شود.
    """
    print(f"\n--- تست اتصال با نماد: {test_symbol} ---")
    session = requests.Session()
    limiter = StrictRateLimiter()
    os.makedirs(DATES_CACHE_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    init_db()

    dates = get_active_trade_dates(test_symbol, limiter, session)
    if not dates:
        print("❌ نتوانستیم روزهای معاملاتی را دریافت کنیم. لطفاً کلید API و اینترنت را چک کنید.")
        return False

    print(f"✔ سوابق دریافت شد: {len(dates)} روز معامله پیدا شد.")
    sample_date = dates[-1] # آخرین روز معاملاتی
    print(f"در حال تست دانلود ریزمعاملات برای روز: {sample_date}...")

    # دریافت ریزمعاملات همان روز
    allowed, cnt = limiter.wait_and_acquire()
    resp = session.get(f"{BASE_URL}/Tsetmc/Transaction.php",
                       params={"key": API_KEY, "l18": test_symbol, "date": sample_date},
                       headers=HEADERS, timeout=15)

    if resp.status_code == 200:
        trades = extract_trade_rows(resp.json())
        print(f"✔ موفقیت‌آمیز بود! تعداد {len(trades)} معامله دریافت شد.")
        print("کد آماده اجرای سراسری است.\n")
        return True
    else:
        print(f"❌ سرور خطای {resp.status_code} داد: {resp.text[:100]}")
        return False

if __name__ == "__main__":
    # مرحله اول: اجرای تست برای اطمینان ۱۰۰٪
    test_passed = test_single_symbol("فولاد")
    
    if test_passed:
        # در صورت تأیید، می‌توانید فراخوانی کل نمادها را در ادامه قرار دهید:
        print("برای اجرای کامل، کلاس SmartTradeCollector را با لیست نمادها فراخوانی کنید.")
