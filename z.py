import os
import re
import time
import json
import logging
import threading
import sqlite3
from datetime import datetime, timedelta
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
import jdatetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================ تنظیمات ============================
API_KEY = "Bk7JvdJZBHJ9DMhzeuTfWjwqYy1wMsif"  # کلید BrsApi خود را وارد کنید

DAILY_LIMIT = 10000          # سقف روزانه قطعی
MAX_PER_BURST = 2            # سقف ریکوئست در هر بازه (محدودیت رسمی BrsApi: Transaction = 2 ریکوئست/۱۰ ثانیه)
BURST_WINDOW = 10            # بازه ۱۰ ثانیه‌ای
MIN_DELAY_PER_REQ = 5.0      # تأخیر ۵ ثانیه بین ریکوئست‌ها (معادل 2 req/10s)
MAX_WORKERS = 4              # تعداد ترد پایدار در ویندوز

DATA_DIR = "transactions_data"
STATE_FILE = "crawler_state.json"
SYMBOLS_CACHE_FILE = "all_symbols.json"
DB_FILE = "transactions.db"     # پایگاه داده SQLite برای تحلیل (علاوه بر فایل JSON)

START_DATE_SHAMSI = "1390-01-01"

# User-Agent استاندارد مرورگر — BrsApi ریکوئست‌های با UA پیش‌فرض پایتون را 403 می‌کند
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": USER_AGENT}

BASE_URL = "https://api.brsapi.ir"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("collector.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# ============================ مدیریت سهمیه ============================
class RateLimiter:
    def __init__(self, daily_limit=DAILY_LIMIT, burst_limit=MAX_PER_BURST, burst_window=BURST_WINDOW):
        self.daily_limit = daily_limit
        self.burst_limit = burst_limit
        self.burst_window = burst_window
        self.lock = threading.Lock()
        self.recent_requests = deque()
        self.last_req_time = 0
        self.state = self.load_state()

    def load_state(self):
        today_str = datetime.now().strftime("%Y-%m-%d")
        default_state = {"current_day": today_str, "requests_today": 0}
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("current_day") == today_str:
                        return data
            except Exception as e:
                logging.error(f"خطا در بارگذاری فایل وضعیت: {e}")
        return default_state

    def save_state(self):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def acquire_slot(self):
        while True:
            with self.lock:
                now = time.time()
                today_str = datetime.now().strftime("%Y-%m-%d")

                if self.state["current_day"] != today_str:
                    self.state["current_day"] = today_str
                    self.state["requests_today"] = 0
                    self.recent_requests.clear()
                    self.save_state()

                if self.state["requests_today"] >= self.daily_limit:
                    return False, "DAILY_LIMIT_EXCEEDED"

                while self.recent_requests and self.recent_requests[0] <= now - self.burst_window:
                    self.recent_requests.popleft()

                sleep_time = 0
                if len(self.recent_requests) >= self.burst_limit:
                    sleep_time = (self.recent_requests[0] + self.burst_window) - now + 0.5
                else:
                    elapsed = now - self.last_req_time
                    if elapsed < MIN_DELAY_PER_REQ:
                        sleep_time = MIN_DELAY_PER_REQ - elapsed

                if sleep_time <= 0:
                    self.recent_requests.append(time.time())
                    self.last_req_time = time.time()
                    self.state["requests_today"] += 1
                    current_count = self.state["requests_today"]
                    self.save_state()
                    return True, current_count

            time.sleep(sleep_time)

    def refund_slot(self):
        with self.lock:
            if self.state["requests_today"] > 0:
                self.state["requests_today"] -= 1
                self.save_state()


# ============================ فیلتر و پالایش نام نمادها ============================
def is_valid_symbol_name(sym: str) -> bool:
    """بررسی اینکه آیا ورودی واقعاً یک نماد معتبر بورسی است یا خیر"""
    if not sym or not isinstance(sym, str):
        return False
    sym = sym.strip()
    # اگر تاریخ/ساعت یا کاراکترهای غیراستاندارد باشد رد شود
    if any(c in sym for c in r'/\:*?"<>|@;,'):
        return False
    # نماد نباید صرفاً عدد یا خیلی طولانی باشد
    if sym.isdigit() or len(sym) > 30 or len(sym) < 2:
        return False
    return True


# ── فیلتر بازار بر اساس پیشوند ISIN (استاندارد بورس ایران) ──
#   IRO1          = بورس تهران (سهام)        ~679 نماد
#   IRO3          = فرابورس (سهام)           ~343 نماد
#   IRO5 / IRO7   = سایر بازارهای سهام        ~160 نماد
#   IRT1/IRT3/IRTK/IRE9 = صندوق/ETF (حذف)     ~450 نماد
#   IRR*          = حق تقدم (حذف)             ~12 نماد
MARKET_FILTER = "tse"  # tse = فقط بورس | tse_ifb = بورس+فرابورس | stocks = همه سهام (بدون صندوق/حق تقدم)

_ISIN_PREFIXES = {
    "tse": ("IRO1",),
    "tse_ifb": ("IRO1", "IRO3"),
    "stocks": ("IRO1", "IRO3", "IRO5", "IRO7"),
}


def _isin_allowed(isin: str) -> bool:
    """بررسی اینکه آیا ISIN متعلق به بازار موردنظر است (فیلتر صندوق/ETF/حق تقدم)"""
    if not isin:
        return False
    prefixes = _ISIN_PREFIXES.get(MARKET_FILTER, _ISIN_PREFIXES["tse"])
    return any(isin.startswith(p) for p in prefixes)


def extract_all_symbols():
    if os.path.exists(SYMBOLS_CACHE_FILE):
        try:
            with open(SYMBOLS_CACHE_FILE, "r", encoding="utf-8") as f:
                syms = json.load(f)
                valid_syms = [s for s in syms if is_valid_symbol_name(s)]
                if len(valid_syms) > 10:
                    logging.info(f"تعداد {len(valid_syms)} نماد از کش لود شد.")
                    return valid_syms
        except Exception:
            pass

    logging.info("در حال استخراج دقیق لیست نمادها...")
    symbols = set()

    # ۱. اولویت اول: از وب‌سرویس خود BrsApi
    try:
        url = f"{BASE_URL}/Tsetmc/AllSymbols.php"
        resp = requests.get(url, params={"key": API_KEY, "type": "1"}, headers=HEADERS, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                for item in data:
                    sym = item.get("l18")
                    isin = item.get("isin") or ""
                    if not is_valid_symbol_name(sym):
                        continue
                    if not _isin_allowed(isin):
                        continue
                    symbols.add(sym.strip())
    except Exception as e:
        logging.warning(f"عدم دریافت از BrsApi: {e}")

    # ۲. فال‌بک دقیق و پالایش‌شده از TSETMC
    if not symbols:
        try:
            url = "http://old.tsetmc.com/tsev2/data/MarketWatchPlus.aspx"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
            if r.status_code == 200:
                parts = r.text.split(";")
                for row in parts:
                    cols = row.split(",")
                    # در دیتای بورس، سطر نماد باید حداقل ۲۳ ستون استاندارد داشته باشد
                    if len(cols) >= 10:
                        sym = cols[2].strip()
                        if is_valid_symbol_name(sym):
                            symbols.add(sym)
        except Exception as e:
            logging.error(f"خطا در ارتباط با TSETMC: {e}")

    clean_list = sorted(list(symbols))
    if clean_list:
        with open(SYMBOLS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(clean_list, f, ensure_ascii=False, indent=2)
        logging.info(f"مجموعاً {len(clean_list)} نماد استاندارد و معتبر استخراج شد.")
        return clean_list

    raise RuntimeError("هیچ نماد معتبری یافت نشد. اتصال اینترنت را چک کنید.")


# ============================ ذخیره در پایگاه داده (SQLite) ============================
_DB_LOCK = threading.Lock()


def _init_db():
    """ایجاد جدول تراکنش‌ها در SQLite (در صورت عدم وجود)"""
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                symbol      TEXT NOT NULL,
                trade_date  TEXT NOT NULL,   -- تاریخ شمسی YYYY-MM-DD
                seq_no      INTEGER NOT NULL,
                time        TEXT,
                volume      INTEGER,
                price       REAL,
                is_canceled INTEGER DEFAULT 0,
                PRIMARY KEY (symbol, trade_date, seq_no)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_symbol_date ON transactions(symbol, trade_date)")
        conn.commit()
    finally:
        conn.close()


def _extract_trade_rows(data):
    """تبدیل پاسخ Transaction.php به لیست ردیف‌های تراکنش (حالت تخت یا پاکت تودرتو)"""
    if isinstance(data, dict):
        inner = data.get("data")
        if isinstance(inner, dict) and isinstance(inner.get("transaction"), list):
            data = inner["transaction"]
        else:
            return []
    if not isinstance(data, list):
        return []
    rows = []
    for item in data:
        if not isinstance(item, dict):
            continue
        rows.append({
            "seq_no": int(item.get("row") or item.get("id") or 0),
            "time": item.get("time") or item.get("hEven") or "",
            "volume": int(item.get("volume") or item.get("qTitTran") or 0),
            "price": float(item.get("price") or item.get("pTran") or 0),
            "is_canceled": 1 if (item.get("canceled") or item.get("cCanceled")) else 0,
        })
    return rows


def _save_trades_db(symbol, date_str, rows):
    """ذخیره تراکنش‌ها در SQLite (INSERT OR IGNORE برای جلوگیری از تکراری)"""
    if not rows:
        return 0
    with _DB_LOCK:
        conn = sqlite3.connect(DB_FILE)
        try:
            conn.executemany(
                """INSERT OR IGNORE INTO transactions
                   (symbol, trade_date, seq_no, time, volume, price, is_canceled)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [(symbol, date_str, r["seq_no"], r["time"], r["volume"], r["price"], r["is_canceled"]) for r in rows],
            )
            conn.commit()
            return len(rows)
        finally:
            conn.close()


# ============================ دانلودر ============================
class SmartCollector:
    def __init__(self, symbols):
        self.symbols = symbols
        self.limiter = RateLimiter()
        os.makedirs(DATA_DIR, exist_ok=True)
        _init_db()
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=1)
        adapter = HTTPAdapter(max_retries=retries, pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def fetch_transaction(self, task):
        symbol, date_str, out_path = task

        allowed, count_or_reason = self.limiter.acquire_slot()
        if not allowed:
            return "DAILY_STOP"

        url = f"{BASE_URL}/Tsetmc/Transaction.php"
        params = {
            "key": API_KEY,
            "l18": symbol,
            "date": date_str
        }

        try:
            resp = self.session.get(url, params=params, headers=HEADERS, timeout=15)
            
            if resp.status_code in (429, 403):
                logging.warning(f"کد {resp.status_code} برای {symbol} در {date_str} - برگشت سهمیه و استراحت.")
                self.limiter.refund_slot()
                time.sleep(3)
                return "RETRY"

            if resp.status_code == 200:
                data = resp.json()
                # پاسخ خطا (پاکت {"error": ...} / {"success": false})
                if isinstance(data, dict) and (data.get("error") or data.get("successful") is False):
                    logging.warning(f"پاسخ خطا برای {symbol} در {date_str}: {str(data)[:120]}")
                    return "FAIL"
                # پاکت تودرتو {"data": {"transaction": [...]}} — اگر خالی بود ذخیره نکن
                if isinstance(data, dict) and isinstance(data.get("data"), dict):
                    if not data["data"].get("transaction"):
                        logging.info(f"بدون تراکنش: {symbol} | {date_str}")
                        return "EMPTY"
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
                # ذخیره همزمان در پایگاه داده SQLite (علاوه بر فایل JSON)
                _rows = _extract_trade_rows(data)
                _db_count = _save_trades_db(symbol, date_str, _rows) if _rows else 0
                logging.info(
                    f"[{count_or_reason}/{DAILY_LIMIT}] ذخیره شد: {symbol} | {date_str} | دیتابیس: {_db_count} ردیف"
                )
                return "OK"
            else:
                # تشخیص روز تعطیل/آخر هفته (بدون تراکنش) تا دوباره retry نشود و سهمیه هدر نرود
                try:
                    _err = resp.json()
                except Exception:
                    _err = None
                if isinstance(_err, dict) and isinstance(_err.get("message_error"), str):
                    _msg = _err["message_error"].lower()
                    if "holiday" in _msg or "weekend" in _msg or "تعطیل" in _msg:
                        with open(out_path, "w", encoding="utf-8") as f:
                            json.dump([], f)
                        logging.info(f"تعطیل (بدون تراکنش): {symbol} | {date_str}")
                        return "EMPTY"
                return "FAIL"

        except Exception as e:
            logging.error(f"خطای شبکه: {e}")
            self.limiter.refund_slot()
            return "RETRY"

    def run(self):
        start_y, start_m, start_d = map(int, START_DATE_SHAMSI.split("-"))
        start_date = jdatetime.date(start_y, start_m, start_d)
        today = jdatetime.date.today()

        tasks = []
        logging.info("آماده‌سازی صف کارها و تطبیق فایل‌های قبلی (Resume)...")

        for sym in self.symbols:
            # جلوگیری مجدد از کاراکترهای غیرمجاز در نام فولدر ویندوز
            safe_sym = re.sub(r'[\\/*?:"<>|]', "", sym).strip()
            if not safe_sym:
                continue

            sym_dir = os.path.join(DATA_DIR, safe_sym)
            os.makedirs(sym_dir, exist_ok=True)

            curr = start_date
            while curr <= today:
                date_str = curr.strftime("%Y-%m-%d")
                out_path = os.path.join(sym_dir, f"{date_str}.json")

                if not os.path.exists(out_path):
                    tasks.append((sym, date_str, out_path))

                curr += timedelta(days=1)

        logging.info(f"تعداد تسک‌های باقیمانده برای دانلود: {len(tasks)}")

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_task = {executor.submit(self.fetch_transaction, task): task for task in tasks}

            for future in as_completed(future_to_task):
                res = future.result()
                if res == "DAILY_STOP":
                    logging.info("سقف ۱۰,۰۰۰ ریکوئست امروز پر شد. کار تا فردا متوقف می‌شود.")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break


if __name__ == "__main__":
    # اگر فایل کش قدیمی وجود دارد حذف شود تا دیتای خراب پاک شود
    if os.path.exists(SYMBOLS_CACHE_FILE):
        try:
            with open(SYMBOLS_CACHE_FILE, "r", encoding="utf-8") as f:
                test_data = json.load(f)
                if any(any(c in s for c in r'/\:*?"<>|@;,') for s in test_data if isinstance(s, str)):
                    os.remove(SYMBOLS_CACHE_FILE)
        except Exception:
            pass

    symbols = extract_all_symbols()
    collector = SmartCollector(symbols)
    collector.run()
