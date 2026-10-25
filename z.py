import json
import logging
import os
import re
import sqlite3
import threading
import time
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from contextlib import contextmanager
from datetime import datetime, timedelta

import jdatetime
import psycopg2
import requests
from dotenv import load_dotenv
from psycopg2.extras import execute_values
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# متغیرهای .env (DB_HOST/DB_PASSWORD/...) را قبل از ساخت PG_CONFIG بارگذاری کن
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ============================ تنظیمات ============================
# کلید BrsApi فقط از محیط خوانده می‌شود (هرگز در کد هاردکد نمی‌شود).
# مقدار را در .env یا متغیر محیطی BRSAPI_KEY بگذارید.
API_KEY = (os.environ.get("BRSAPI_API_KEY") or os.environ.get("BRSAPI_KEY") or "").strip()
if not API_KEY:
    raise SystemExit(
        "BRSAPI_KEY تنظیم نشده است. کلید را در .env (یا متغیر محیطی) قرار دهید — "
        "هاردکد کردن کلید در سورس ممنوع است."
    )

DAILY_LIMIT = 10000          # سقف روزانه قطعی
# محدودیت نرخ: هدف ≈۱۰۰۰ ریکوئست در ۵ دقیقه (≈۳٫۳ ریکوئست/ثانیه).
# نرخ مؤثر = max(1/MIN_DELAY_PER_REQ , MAX_PER_BURST/BURST_WINDOW) ⇒ اینجا ۳٫۳۳/ثانیه.
MAX_PER_BURST = 40           # سقف ریکوئست در هر بازه ۱۰ ثانیه‌ای (سقف پشتیبان ۴/ثانیه)
BURST_WINDOW = 10            # بازه ۱۰ ثانیه‌ای
MIN_DELAY_PER_REQ = 0.3      # حداقل فاصله بین دو ریکوئست (ثانیه) — عامل تعیین‌کننده نرخ
MAX_WORKERS = 16             # تعداد ترد پایدار (نرخ را در صورت تأخیر بالای پاسخ حفظ می‌کند؛ خود محدودکننده فراتر نمی‌رود)

DATA_DIR = "transactions_data"
QUOTA_STATE_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "temce")
STATE_FILE = os.path.join(QUOTA_STATE_DIR, "crawler_state.json")
SYMBOLS_CACHE_FILE = "all_symbols.json"
DB_FILE = "transactions.db"     # پایگاه داده SQLite برای تحلیل (علاوه بر فایل JSON)

# ── مقصد اصلی ریز معاملات: پستگرس (همان جدولی که سرویس BrsApi می‌نویسد) ──
PG_CONFIG = {
    "host": os.environ.get("PG_HOST") or os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("PG_PORT") or os.environ.get("DB_PORT", "5432")),
    "dbname": os.environ.get("PG_DATABASE") or os.environ.get("DB_NAME", "my_first_db"),
    "user": os.environ.get("PG_USER") or os.environ.get("DB_USER", "hossein"),
    "password": os.environ.get("PG_PASSWORD") or os.environ.get("DB_PASSWORD", ""),
    "connect_timeout": 15,
}
TRADES_TABLE = "brsapi_intraday_trades"

START_DATE_SHAMSI = "1390-01-01"

# ── تقویم معاملاتی ──
# بورس تهران شنبه تا چهارشنبه باز است. تأیید تجربی: در ۳۲٫۷ میلیون ردیف دیتابیس
# (۳٬۵۲۸ تاریخ متمایز، ۱۳۹۰ تا ۱۴۰۵) هیچ معامله‌ای در پنجشنبه/جمعه ثبت نشده است.
# jdatetime: شنبه=0، یکشنبه=1، ... پنجشنبه=5، جمعه=6
WEEKLY_CLOSED_WEEKDAYS = (5, 6)

# تعطیلات رسمی با تاریخ شمسی ثابت (هر سال تکرار می‌شوند)
FIXED_SHAMSI_HOLIDAYS = (
    (1, 1), (1, 2), (1, 3), (1, 4),   # نوروز
    (1, 12),                          # روز جمهوری اسلامی
    (1, 13),                          # سیزده‌بدر
    (3, 14),                          # رحلت امام خمینی
    (3, 15),                          # قیام ۱۵ خرداد
    (11, 22),                         # پیروزی انقلاب اسلامی
    (12, 29),                         # ملی شدن صنعت نفت
)

# تعطیلات متغیر (قمری) خودکار از پاسخ صریح API یاد گرفته و برای همه نمادها کش می‌شوند
HOLIDAYS_FILE = "market_holidays.json"

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
@contextmanager
def _state_file_lock():
    os.makedirs(os.path.dirname(os.path.abspath(STATE_FILE)), exist_ok=True)
    with open(STATE_FILE + ".lock", "a+b") as lock_file:
        if os.name == "nt":
            import msvcrt

            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"\0")
                lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


class RateLimiter:
    def __init__(self, daily_limit=DAILY_LIMIT, burst_limit=MAX_PER_BURST, burst_window=BURST_WINDOW):
        self.daily_limit = daily_limit
        self.burst_limit = burst_limit
        self.burst_window = burst_window
        self.lock = threading.Lock()
        self.state = self.load_state()
        self.recent_requests = deque(self.state["recent_requests"])
        self.last_req_time = self.state["last_req_time"]

    @staticmethod
    def _default_state(today_str):
        return {
            "current_day": today_str,
            "requests_today": 0,
            "recent_requests": [],
            "last_req_time": 0,
        }

    def _read_state(self, today_str):
        if not os.path.exists(STATE_FILE):
            return self._default_state(today_str)
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            raise RuntimeError(f"خطا در بارگذاری فایل وضعیت سهمیه: {e}") from e
        if not isinstance(data, dict):
            raise RuntimeError("ساختار فایل وضعیت سهمیه نامعتبر است.")
        if data.get("current_day") != today_str:
            return self._default_state(today_str)
        count = data.get("requests_today")
        if not isinstance(count, int) or count < 0:
            raise RuntimeError("شمارنده درخواست روزانه در فایل وضعیت نامعتبر است.")
        state = self._default_state(today_str)
        state.update(data)
        if not isinstance(state["recent_requests"], list):
            raise RuntimeError("فهرست درخواست‌های اخیر در فایل وضعیت نامعتبر است.")
        try:
            state["recent_requests"] = [float(t) for t in state["recent_requests"]]
            state["last_req_time"] = float(state["last_req_time"])
        except (TypeError, ValueError) as e:
            raise RuntimeError(f"زمان درخواست‌ها در فایل وضعیت نامعتبر است: {e}") from e
        return state

    def load_state(self):
        today_str = datetime.now().strftime("%Y-%m-%d")
        with _state_file_lock():
            return self._read_state(today_str)

    def _save_state_unlocked(self):
        temp_path = f"{STATE_FILE}.{os.getpid()}.tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, STATE_FILE)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def save_state(self):
        with _state_file_lock():
            self._save_state_unlocked()

    def acquire_slot(self):
        while True:
            with self.lock:
                today_str = datetime.now().strftime("%Y-%m-%d")
                with _state_file_lock():
                    self.state = self._read_state(today_str)
                    now = time.time()
                    recent_requests = [
                        request_time
                        for request_time in self.state["recent_requests"]
                        if request_time > now - self.burst_window
                    ]

                    if self.state["requests_today"] >= self.daily_limit:
                        return False, "DAILY_LIMIT_EXCEEDED"

                    sleep_time = 0
                    if len(recent_requests) >= self.burst_limit:
                        sleep_time = max(
                            sleep_time,
                            recent_requests[0] + self.burst_window - now + 0.5,
                        )
                    elapsed = now - self.state["last_req_time"]
                    sleep_time = max(sleep_time, MIN_DELAY_PER_REQ - elapsed)

                    if sleep_time <= 0:
                        recent_requests.append(now)
                        self.state["recent_requests"] = recent_requests
                        self.state["last_req_time"] = now
                        self.state["requests_today"] += 1
                        current_count = self.state["requests_today"]
                        self.recent_requests = deque(recent_requests)
                        self.last_req_time = now
                        self._save_state_unlocked()
                        return True, current_count

            time.sleep(sleep_time)

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


# ── مدیریت تقویم تعطیلات بازار ──
_HOLIDAYS_LOCK = threading.Lock()
_HOLIDAYS = set()   # تاریخ‌های تعطیل رسمی شمسی (YYYY-MM-DD) که بازار در آن‌ها بسته بوده


def _load_holidays():
    """بارگذاری تعطیلات یادگرفته‌شده از فایل (در صورت وجود)"""
    if not os.path.exists(HOLIDAYS_FILE):
        return
    try:
        with open(HOLIDAYS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            _HOLIDAYS.update(str(x) for x in data)
        logging.info(f"تقویم تعطیلات: {len(_HOLIDAYS)} روز تعطیل رسمی بارگذاری شد.")
    except Exception as e:
        logging.error(f"بارگذاری تقویم تعطیلات ناموفق: {e}")


def _save_holidays():
    """ذخیره اتمیک تعطیلات یادگرفته‌شده"""
    tmp = HOLIDAYS_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(sorted(_HOLIDAYS), f, ensure_ascii=False, indent=2)
        os.replace(tmp, HOLIDAYS_FILE)
    except Exception as e:
        logging.error(f"ذخیره تقویم تعطیلات ناموفق: {e}")


def _mark_holiday(date_str):
    """ثبت یک تاریخ به‌عنوان تعطیل رسمی بازار (سراسری، نه مخصوص یک نماد)"""
    with _HOLIDAYS_LOCK:
        if not date_str or date_str in _HOLIDAYS:
            return
        _HOLIDAYS.add(date_str)
        _save_holidays()


def is_market_closed(jd) -> bool:
    """آیا بازار در این تاریخ (jdatetime.date) تعطیل است؟"""
    if jd.weekday() in WEEKLY_CLOSED_WEEKDAYS:
        return True
    if (jd.month, jd.day) in FIXED_SHAMSI_HOLIDAYS:
        return True
    return jd.strftime("%Y-%m-%d") in _HOLIDAYS


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


def extract_all_symbols(limiter):
    if os.path.exists(SYMBOLS_CACHE_FILE):
        try:
            with open(SYMBOLS_CACHE_FILE, encoding="utf-8") as f:
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
        allowed, count_or_reason = limiter.acquire_slot()
        if not allowed:
            raise RuntimeError("سقف روزانه پیش از دریافت فهرست نمادها تکمیل شده است.")
        url = f"{BASE_URL}/Tsetmc/AllSymbols.php"
        resp = requests.get(
            url,
            params={"key": API_KEY, "type": "1"},
            headers=HEADERS,
            timeout=20,
            allow_redirects=False,
        )
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
_DB_LOCAL = threading.local()


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


def _db_conn():
    """اتصال SQLite پایدار برای هر ترد (به‌جای باز/بسته کردن اتصال در هر تاریخ)."""
    conn = getattr(_DB_LOCAL, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DB_FILE, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA synchronous=NORMAL")
        _DB_LOCAL.conn = conn
    return conn


def _save_trades_db(symbol, date_str, rows):
    """ذخیره تراکنش‌ها در SQLite (INSERT OR IGNORE برای جلوگیری از تکراری)"""
    if not rows:
        return 0
    with _DB_LOCK:
        conn = _db_conn()
        conn.executemany(
            """INSERT OR IGNORE INTO transactions
               (symbol, trade_date, seq_no, time, volume, price, is_canceled)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [(symbol, date_str, r["seq_no"], r["time"], r["volume"], r["price"], r["is_canceled"]) for r in rows],
        )
        conn.commit()
        return len(rows)


# ============================ ذخیره در پستگرس (PostgreSQL) ============================
_DB_INSERT_SQL = (
    "INSERT INTO " + TRADES_TABLE +
    ' (symbol, "row", time, volume, price, canceled, trade_date, shamsi_date, gregorian_date, ins_id) VALUES %s'
)


def _jalali_to_gregorian(date_str):
    """تاریخ شمسی YYYY-MM-DD را به میلادی تبدیل می‌کند (نبودِ مقدار → None)"""
    try:
        y, m, d = map(int, str(date_str).split("-"))
        return jdatetime.date(y, m, d).togregorian()
    except Exception:
        return None


def _load_ins_id_map(cur):
    """{symbol: ins_id} از جدول نمادها — در صورت نبود جدول، دیکشنری خالی"""
    try:
        cur.execute("SELECT DISTINCT symbol, ins_id FROM brsapi_symbol_snapshots WHERE ins_id IS NOT NULL")
        return {s: str(i) for s, i in cur.fetchall() if s}
    except Exception:
        return {}


def _insert_batch_no_dup(cur, batch, ins_map):
    """درج دسته‌ای در جدول ریز معاملات با حذف ردیف‌های تکراری.

    کلید تکرار: (symbol, trade_date, row) — همان کلید منطقی پیشین در SQLite.
    هر ردیف ورودی: (symbol, trade_date, seq_no, time, volume, price, is_canceled)
    خروجی: (تعداد درج‌شده، تعداد رد‌شده)
    """
    batch = list(batch)
    if not batch:
        return (0, 0)

    existing = set()
    for sym, date_str in {(r[0], r[1]) for r in batch}:
        cur.execute(
            'SELECT "row" FROM ' + TRADES_TABLE + " WHERE symbol=%s AND trade_date=%s",
            (sym, date_str),
        )
        for (rn,) in cur.fetchall():
            existing.add((sym, date_str, rn))

    fresh = []
    seen = set()
    for r in batch:
        key = (r[0], r[1], r[2])
        if key in existing or key in seen:
            continue
        seen.add(key)
        fresh.append(r)
    if not fresh:
        return (0, len(batch))

    values = [
        (r[0], r[2], r[3], r[4], r[5], bool(r[6]), r[1], r[1], _jalali_to_gregorian(r[1]), ins_map.get(r[0]))
        for r in fresh
    ]
    execute_values(cur, _DB_INSERT_SQL, values, page_size=2000)
    return (len(fresh), len(batch) - len(fresh))


def _check_pg():
    """بررسی زودهنگام (fail-fast) دسترسی به پستگرس و جدول ریز معاملات"""
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM " + TRADES_TABLE + " LIMIT 1")
        conn.close()
    except Exception as e:
        raise RuntimeError(f"دسترسی به پستگرس یا جدول {TRADES_TABLE} برقرار نشد: {e}")
    logging.info(
        f"مقصد ذخیره ریز معاملات: {PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['dbname']} :: {TRADES_TABLE}"
    )


# ============================ دانلودر ============================
class SmartCollector:
    def __init__(self, symbols, limiter):
        self.symbols = symbols
        self.skipped_closed = 0   # تعداد روزهای تعطیلی که بدون ریکوئست رد شدند
        self.limiter = limiter
        self.stop_event = threading.Event()
        os.makedirs(DATA_DIR, exist_ok=True)
        _init_db()
        self.session = requests.Session()
        retries = Retry(total=0)
        adapter = HTTPAdapter(max_retries=retries, pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def fetch_transaction(self, task):
        symbol, date_str, out_path = task

        if self.stop_event.is_set():
            return "API_STOP"
        allowed, count_or_reason = self.limiter.acquire_slot()
        if not allowed:
            return "DAILY_STOP"
        if self.stop_event.is_set():
            return "API_STOP"

        url = f"{BASE_URL}/Tsetmc/Transaction.php"
        params = {
            "key": API_KEY,
            "l18": symbol,
            "date": date_str
        }

        try:
            resp = self.session.get(
                url,
                params=params,
                headers=HEADERS,
                timeout=15,
                allow_redirects=False,
            )

            if resp.status_code in (429, 403):
                self.stop_event.set()
                logging.error(
                    f"کد HTTP {resp.status_code} برای {symbol} در {date_str}; "
                    "دانلودگر برای جلوگیری از درخواست بیشتر متوقف شد."
                )
                return "API_STOP"

            if resp.status_code == 200:
                data = resp.json()
                # پاسخ خطا (پاکت {"error": ...} / {"success": false})
                if isinstance(data, dict) and (data.get("error") or data.get("successful") is False):
                    self.stop_event.set()
                    logging.error(f"پاسخ خطای API برای {symbol} در {date_str}; دانلودگر متوقف شد.")
                    return "API_STOP"
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
                        # این تاریخ برای کل بازار تعطیل است ⇒ برای نمادهای بعدی بدون ریکوئست رد شود
                        _mark_holiday(date_str)
                        with open(out_path, "w", encoding="utf-8") as f:
                            json.dump([], f)
                        logging.info(f"تعطیل (ثبت در تقویم تعطیلات): {symbol} | {date_str}")
                        return "EMPTY"
                self.stop_event.set()
                logging.error(
                    f"پاسخ HTTP {resp.status_code} برای {symbol} در {date_str}; "
                    "دانلودگر متوقف شد."
                )
                return "API_STOP"

        except Exception as e:
            self.stop_event.set()
            reason = str(e).replace(API_KEY, "[redacted]") if API_KEY else str(e)
            logging.error(
                f"خطا برای {symbol} در {date_str}: {type(e).__name__}: {reason}; "
                "دانلودگر متوقف شد و سهمیه پس‌گرفته نشد."
            )
            return "API_STOP"

    def _iter_tasks(self):
        """تولید تنبل (lazy) تسک‌های باقیمانده برای دانلود.

        تاریخ‌های موجود هر نماد با یک بار os.listdir خوانده می‌شود (به‌جای میلیون‌ها
        فراخوانی os.path.exists) و صف به‌صورت جریان تولید می‌شود تا کل میلیون‌ها تسک
        در حافظه نگه داشته نشود.
        """
        start_y, start_m, start_d = map(int, START_DATE_SHAMSI.split("-"))
        start_date = jdatetime.date(start_y, start_m, start_d)
        today = jdatetime.date.today()

        for sym in self.symbols:
            # جلوگیری مجدد از کاراکترهای غیرمجاز در نام فولدر ویندوز
            safe_sym = re.sub(r'[\\/*?:"<>|]', "", sym).strip()
            if not safe_sym:
                continue

            sym_dir = os.path.join(DATA_DIR, safe_sym)
            os.makedirs(sym_dir, exist_ok=True)
            try:
                existing = {n[:-5] for n in os.listdir(sym_dir) if n.endswith(".json")}
            except OSError as e:
                logging.warning(f"خواندن پوشه {safe_sym} ناموفق: {e}")
                existing = set()

            curr = start_date
            while curr <= today:
                # روزهای تعطیل (هفتگی/رسمی) اصلاً در صف قرار نمی‌گیرند تا سهمیه هدر نرود
                if is_market_closed(curr):
                    self.skipped_closed += 1
                    curr += timedelta(days=1)
                    continue

                date_str = curr.strftime("%Y-%m-%d")
                if date_str not in existing:
                    yield (sym, date_str, os.path.join(sym_dir, f"{date_str}.json"))

                curr += timedelta(days=1)

    def run(self):
        logging.info("آماده‌سازی صف کارها و تطبیق فایل‌های قبلی (Resume)...")
        max_pending = MAX_WORKERS * 8   # پنجره محدود ⇒ حافظه ثابت و شروع فوری دانلود
        queued = 0
        daily_stop = False
        api_stop = False

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            pending = set()
            for task in self._iter_tasks():
                pending.add(executor.submit(self.fetch_transaction, task))
                queued += 1
                if len(pending) < max_pending:
                    continue
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    result = future.result()
                    if result == "DAILY_STOP":
                        daily_stop = True
                    elif result == "API_STOP":
                        api_stop = True
                if daily_stop or api_stop:
                    break

            if daily_stop or api_stop:
                if daily_stop:
                    logging.info("سقف ۱۰,۰۰۰ ریکوئست امروز پر شد. کار تا فردا متوقف می‌شود.")
                else:
                    logging.error("دانلودگر پس از خطای API متوقف شد؛ اجرای مجدد خودکار انجام نمی‌شود.")
                executor.shutdown(wait=False, cancel_futures=True)
                return

            for future in as_completed(pending):
                if future.result() == "API_STOP":
                    api_stop = True
                    break

            if api_stop:
                self.stop_event.set()
                logging.error("دانلودگر پس از خطای API متوقف شد؛ اجرای مجدد خودکار انجام نمی‌شود.")
                executor.shutdown(wait=False, cancel_futures=True)
                return

        logging.info(
            f"صف تسک‌ها تمام شد (ارسال‌شده: {queued} | روز تعطیل رد‌شده: {self.skipped_closed})."
        )


if __name__ == "__main__":
    # اگر فایل کش قدیمی وجود دارد حذف شود تا دیتای خراب پاک شود
    if os.path.exists(SYMBOLS_CACHE_FILE):
        try:
            with open(SYMBOLS_CACHE_FILE, encoding="utf-8") as f:
                test_data = json.load(f)
                if any(any(c in s for c in r'/\:*?"<>|@;,') for s in test_data if isinstance(s, str)):
                    os.remove(SYMBOLS_CACHE_FILE)
        except Exception:
            pass

    _load_holidays()   # تقویم تعطیلات یادگرفته‌شده از اجراهای قبلی
    limiter = RateLimiter()
    symbols = extract_all_symbols(limiter)
    collector = SmartCollector(symbols, limiter)
    collector.run()
