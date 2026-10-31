import argparse
import json
import logging
import os
import re
import threading
import time
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from logging.handlers import RotatingFileHandler

import jdatetime
import psycopg2
import requests
from dotenv import load_dotenv
from psycopg2.extras import execute_values
from requests.adapters import HTTPAdapter

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
MAX_ATTEMPTS = 3             # تلاش برای خطاهای گذرا (شبکه/5xx) — هر تلاش سهمیه می‌خورد
TRANSIENT_HTTP = (500, 502, 503, 504)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "transactions_data")
QUOTA_STATE_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "temce")
STATE_FILE = os.path.join(QUOTA_STATE_DIR, "crawler_state.json")
QUOTA_JOURNAL = os.path.join(QUOTA_STATE_DIR, "crawler_quota.jsonl")
SYMBOLS_CACHE_FILE = os.path.join(BASE_DIR, "all_symbols.json")

# ── مقصد اصلی ریز معاملات: پستگرس (همان جدولی که سرویس BrsApi می‌نویسد) ──
def _resolve_pg_config():
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if url:
        return {
            "dsn": re.sub(r"^postgresql\+[^:]+://", "postgresql://", url),
            "connect_timeout": 15,
        }
    dbname = os.environ.get("PG_DATABASE") or os.environ.get("DB_NAME")
    user = os.environ.get("PG_USER") or os.environ.get("DB_USER")
    if not dbname or not user:
        raise SystemExit(
            "تنظیمات پستگرس ناقص است. یکی از این دو را در .env بگذارید: "
            "DATABASE_URL، یا DB_NAME/DB_USER/DB_PASSWORD (DB_HOST/DB_PORT اختیاری)."
        )
    return {
        "host": os.environ.get("PG_HOST") or os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("PG_PORT") or os.environ.get("DB_PORT", "5432")),
        "dbname": dbname,
        "user": user,
        "password": os.environ.get("PG_PASSWORD") or os.environ.get("DB_PASSWORD", ""),
        "connect_timeout": 15,
    }


PG_CONFIG = _resolve_pg_config()
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
HOLIDAYS_FILE = os.path.join(BASE_DIR, "market_holidays.json")

# User-Agent استاندارد مرورگر — BrsApi ریکوئست‌های با UA پیش‌فرض پایتون را 403 می‌کند
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": USER_AGENT}

BASE_URL = "https://api.brsapi.ir"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        RotatingFileHandler(
            os.path.join(BASE_DIR, "collector.log"),
            maxBytes=20 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        ),
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


QUOTA_WINDOW = 24 * 60 * 60          # پنجره غلتان سهمیه (ثانیه)
CLOCK_SKEW_TOLERANCE = 60            # عقب‌رفتن مجاز ساعت سیستم (ثانیه)
JOURNAL_RELOAD_EVERY = 200           # هر چند درخواست، ژورنال دوباره خوانده شود
JOURNAL_COMPACT_MIN_LINES = 15000    # آستانه فشرده‌سازی ژورنال


def _journal_key(entry):
    return (round(entry["ts"], 3), round(entry["mono"], 3), entry["day"])


def _read_journal():
    """خواندن ژورنال پیوسته؛ خط خراب ⇒ توقف (fail-closed) تا شمارش تحریف نشود."""
    if not os.path.exists(QUOTA_JOURNAL):
        return []
    entries = []
    try:
        with open(QUOTA_JOURNAL, encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    entries.append({
                        "ts": float(rec["ts"]),
                        "mono": float(rec["mono"]),
                        "day": str(rec["day"]),
                    })
                except (KeyError, TypeError, ValueError) as e:
                    raise RuntimeError(
                        f"ژورنال سهمیه معتبر نیست (خط {lineno}): {e} — "
                        "برای جلوگیری از عبور از سقف اجرا متوقف شد."
                    ) from e
    except OSError as e:
        raise RuntimeError(f"خواندن ژورنال سهمیه ناموفق: {e}") from e
    return entries


def _write_journal(entries):
    tmp = f"{QUOTA_JOURNAL}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, QUOTA_JOURNAL)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _append_journal(entry):
    with open(QUOTA_JOURNAL, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def _entry_age(entry, now, mono):
    """سن ورودی؛ تا وقتی مونوتونیک جلوتر رفته، min(دیواری، مونوتونیک) ملاک است.

    جلو بردن ساعت سیستم نمی‌تواند ورودی‌های پنجره ۲۴ ساعته را زودتر حذف کند؛
    فقط وقتی مونوتونیک ری‌ست شده باشد (ری‌استارت) از ساعت دیواری استفاده می‌شود.
    """
    if entry["mono"] <= mono:
        return min(now - entry["ts"], mono - entry["mono"])
    return now - entry["ts"]


class RateLimiter:
    """سهمیه سخت‌گیرانه با ژورنال پیوسته (ضد ری‌استارت/ساعت/چندپروسه).

    قیدهای هم‌زمان:
      * سقف DAILY_LIMIT درخواست در هر روز تقویمی
      * سقف DAILY_LIMIT درخواست در هر پنجره غلتان ۲۴ ساعته
        (قید روزانه در چندپروسه دقیق است؛ پنجره غلتان هر JOURNAL_RELOAD_EVERY
        درخواست با ژورنال سایر پروسه‌ها هم‌تراز می‌شود)
      * عقب‌رفتن ساعت سیستم ⇒ توقف کامل (جلوگیری از ریست شمارنده)
    شمارنده روز از «حداکثرِ» فایل state و ژورنال بازسازی می‌شود؛ حذف یکی
    از دو فایل شمارنده را صفر نمی‌کند.
    """

    def __init__(self, daily_limit=DAILY_LIMIT, burst_limit=MAX_PER_BURST, burst_window=BURST_WINDOW,
                 now_fn=time.time, mono_fn=time.monotonic):
        self.daily_limit = daily_limit
        self.burst_limit = burst_limit
        self.burst_window = burst_window
        self._now_fn = now_fn
        self._mono_fn = mono_fn
        self.lock = threading.Lock()
        self._window = deque()
        self._day_counts = {}
        self._since_reload = 0
        with self.lock, _state_file_lock():
            self.state = self._bootstrap_unlocked()

    def _times(self):
        return self._now_fn(), self._mono_fn()

    @staticmethod
    def _today(now):
        return datetime.fromtimestamp(now).strftime("%Y-%m-%d")

    def _read_state(self, today):
        """Counter و last_req_time امروز؛ None یعنی فایل نیست یا مال روز دیگری است."""
        if not os.path.exists(STATE_FILE):
            return None
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            raise RuntimeError(f"خطا در بارگذاری فایل وضعیت سهمیه: {e}") from e
        if not isinstance(data, dict):
            raise RuntimeError("ساختار فایل وضعیت سهمیه نامعتبر است.")
        if data.get("current_day") != today:
            return None
        count = data.get("requests_today")
        if not isinstance(count, int) or count < 0:
            raise RuntimeError("شمارنده درخواست روزانه در فایل وضعیت نامعتبر است.")
        try:
            last_req_time = float(data.get("last_req_time", 0))
        except (TypeError, ValueError) as e:
            raise RuntimeError("زمان آخرین درخواست در فایل وضعیت نامعتبر است.") from e
        return {"requests_today": count, "last_req_time": last_req_time}

    def _write_state_unlocked(self, state):
        temp_path = f"{STATE_FILE}.{os.getpid()}.tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, STATE_FILE)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    @staticmethod
    def _prune(entries, now, mono):
        return [e for e in entries if _entry_age(e, now, mono) < QUOTA_WINDOW]

    def _reset_window_locked(self, entries, now, mono, today):
        live = self._prune(entries, now, mono)
        live.sort(key=lambda e: e["ts"])
        self._window = deque(live)
        self._day_counts = {}
        for entry in self._window:
            day = entry["day"]
            self._day_counts[day] = self._day_counts.get(day, 0) + 1
        return self._day_counts.get(today, 0)

    def _expire_locked(self, now, mono):
        while self._window:
            entry = self._window[0]
            if _entry_age(entry, now, mono) < QUOTA_WINDOW:
                break
            self._window.popleft()
            day = entry["day"]
            remaining = self._day_counts.get(day, 0) - 1
            if remaining > 0:
                self._day_counts[day] = remaining
            else:
                self._day_counts.pop(day, None)

    def _bootstrap_unlocked(self):
        now, mono = self._times()
        today = self._today(now)
        journal_day = self._reset_window_locked(_read_journal(), now, mono, today)
        state = self._read_state(today)
        journal_last = self._window[-1]["ts"] if self._window else 0.0
        if state is None:
            count = journal_day
            last_req = journal_last
        else:
            count = max(state["requests_today"], journal_day)
            last_req = max(state["last_req_time"], journal_last)
        return {"current_day": today, "requests_today": count, "last_req_time": last_req}

    def _reload_unlocked(self, now, mono):
        self._since_reload = 0
        raw = _read_journal()
        merged = {_journal_key(e): e for e in raw}
        for entry in self._window:
            merged.setdefault(_journal_key(entry), entry)
        entries = list(merged.values())
        if len(raw) > JOURNAL_COMPACT_MIN_LINES:
            _write_journal(self._prune(entries, now, mono))
        self._reset_window_locked(entries, now, mono, self._today(now))

    def acquire_slot(self):
        while True:
            sleep_time = 0.0
            with self.lock, _state_file_lock():
                now, mono = self._times()
                self._since_reload += 1
                if self._since_reload >= JOURNAL_RELOAD_EVERY:
                    self._reload_unlocked(now, mono)

                self._expire_locked(now, mono)
                today = self._today(now)
                state = self._read_state(today)
                last_ts = self._window[-1]["ts"] if self._window else 0.0
                if state is not None:
                    last_ts = max(last_ts, state["last_req_time"])

                if now < last_ts - CLOCK_SKEW_TOLERANCE:
                    logging.error(
                        "ساعت سیستم به عقب برگشته است؛ برای جلوگیری از عبور از سهمیه متوقف شد."
                    )
                    return False, "CLOCK_ROLLBACK"

                journal_day = self._day_counts.get(today, 0)
                requests_today = max(state["requests_today"] if state else 0, journal_day)
                if requests_today >= self.daily_limit:
                    return False, "DAILY_LIMIT_EXCEEDED"
                if len(self._window) >= self.daily_limit:
                    return False, "ROLLING_LIMIT_EXCEEDED"

                recent = []
                for entry in reversed(self._window):
                    if entry["ts"] <= now - self.burst_window:
                        break
                    recent.append(entry["ts"])
                if len(recent) >= self.burst_limit:
                    sleep_time = max(
                        sleep_time,
                        min(recent) + self.burst_window - now + 0.5,
                    )
                sleep_time = max(sleep_time, MIN_DELAY_PER_REQ - (now - last_ts))

                if sleep_time <= 0:
                    entry = {"ts": now, "mono": mono, "day": today}
                    _append_journal(entry)
                    self._window.append(entry)
                    self._day_counts[today] = journal_day + 1
                    self.state = {
                        "current_day": today,
                        "requests_today": requests_today + 1,
                        "last_req_time": now,
                    }
                    self._write_state_unlocked(self.state)
                    return True, requests_today + 1

            time.sleep(max(sleep_time, 0.05))

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
    return not (sym.isdigit() or len(sym) > 30 or len(sym) < 2)


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
    allowed, count_or_reason = limiter.acquire_slot()
    if not allowed:
        raise RuntimeError(f"سقف درخواست پیش از دریافت فهرست نمادها تکمیل شده است ({count_or_reason}).")
    try:
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

    # ۲. فال‌بک دقیق و پالایش‌شده از TSETMC (این درخواست هم از سقف کم می‌شود تا
    # جمع درخواست‌های HTTP از سقف روزانه عبور نکند)
    if not symbols:
        allowed, count_or_reason = limiter.acquire_slot()
        if not allowed:
            raise RuntimeError(f"سقف درخواست پیش از دریافت فهرست نمادها تکمیل شده است ({count_or_reason}).")
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

    clean_list = sorted(symbols)
    if clean_list:
        with open(SYMBOLS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(clean_list, f, ensure_ascii=False, indent=2)
        logging.info(f"مجموعاً {len(clean_list)} نماد استاندارد و معتبر استخراج شد.")
        return clean_list

    raise RuntimeError("هیچ نماد معتبری یافت نشد. اتصال اینترنت را چک کنید.")


# ============================ آرشیو خام JSON (منبع Resume) ============================
def _write_json_atomic(path, payload):
    """نوشتن اتمیک آرشیو خام؛ فایل نیمه‌کاره نباید «انجام‌شده» تلقی شود."""
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _as_int(value, default=0):
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def _as_float(value, default=0.0):
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def _as_bool(value):
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes")
    return bool(value)


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
            "seq_no": _as_int(item.get("row") if item.get("row") is not None else item.get("id")),
            "time": str(item.get("time") or item.get("hEven") or ""),
            "volume": _as_int(item.get("volume") if item.get("volume") is not None else item.get("qTitTran")),
            "price": _as_float(item.get("price") if item.get("price") is not None else item.get("pTran")),
            "is_canceled": 1 if _as_bool(item.get("canceled") if item.get("canceled") is not None else item.get("cCanceled")) else 0,
        })
    return rows


# ============================ ذخیره در پستگرس (PostgreSQL) ============================
_PG_LOCAL = threading.local()
_PG_INSERT_SQL = None

REQUIRED_TRADE_COLUMNS = ("symbol", "row", "time", "volume", "price", "canceled", "trade_date")
OPTIONAL_TRADE_COLUMNS = ("ins_id", "shamsi_date", "gregorian_date", "trade_date_utc")


def _pg_target():
    if "dsn" in PG_CONFIG:
        return re.sub(r"//[^@/]+@", "//***@", PG_CONFIG["dsn"])
    return f"{PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['dbname']}"


def _pg_conn():
    """اتصال پستگرس پایدار برای هر ترد؛ Commit/Rollback صریح است."""
    conn = getattr(_PG_LOCAL, "conn", None)
    if conn is not None and conn.closed == 0:
        return conn
    conn = psycopg2.connect(**PG_CONFIG)
    conn.autocommit = False
    _PG_LOCAL.conn = conn
    return conn


def _pg_columns(cur):
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
        (TRADES_TABLE,),
    )
    return {r[0] for r in cur.fetchall()}


def _shamsi_to_gregorian(date_str):
    """تاریخ شمسی YYYY-MM-DD → date میلادی (نبودِ مقدار → None)"""
    try:
        y, m, d = map(int, str(date_str).split("-"))
        return jdatetime.date(y, m, d).togregorian()
    except Exception:
        return None


def _shamsi_to_utc(date_str):
    """تاریخ شمسی YYYY-MM-DD → datetime آگاه از UTC (برای ستون trade_date_utc)"""
    gregorian = _shamsi_to_gregorian(date_str)
    if gregorian is None:
        return None
    return datetime(gregorian.year, gregorian.month, gregorian.day, tzinfo=UTC)


def _parse_jalali(value):
    y, m, d = map(int, str(value).split("-"))
    return jdatetime.date(y, m, d)


def _insert_sql(cols):
    """ستون‌های INSERT از اسکیمای واقعی جدول ساخته می‌شود تا drift جدول را نشکند."""
    missing = [c for c in REQUIRED_TRADE_COLUMNS if c not in cols]
    if missing:
        raise RuntimeError(f"ستون‌های لازم در {TRADES_TABLE} نیست: {', '.join(missing)}")
    optional = [c for c in OPTIONAL_TRADE_COLUMNS if c in cols]
    names = ['symbol', '"row"', 'time', 'volume', 'price', 'canceled', 'trade_date', *optional]
    return (
        f"INSERT INTO {TRADES_TABLE} ({', '.join(names)}) VALUES %s "
        "ON CONFLICT DO NOTHING RETURNING 1",
        tuple(optional),
    )


def _load_ins_id_map(symbols):
    """{symbol: ins_id} فقط برای نمادهای هدف (بدون اسکن کل جدول snapshots)."""
    conn = None
    try:
        conn = _pg_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT ON (symbol) symbol, ins_id "
                "FROM brsapi_symbol_snapshots "
                "WHERE symbol = ANY(%s) AND ins_id IS NOT NULL "
                "ORDER BY symbol, fetched_at DESC",
                (list(symbols),),
            )
            mapping = {s: str(i) for s, i in cur.fetchall() if s and i}
        conn.commit()
        return mapping
    except Exception as e:
        if conn is not None:
            conn.rollback()
        logging.warning(f"نگاشت ins_id در دسترس نیست: {e}")
        return {}


def _load_existing_dates(symbol):
    """تاریخ‌هایی که ریز معاملاتشان از قبل در PG هست (برای دانلود فقط باقی‌مانده)."""
    conn = _pg_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT trade_date FROM " + TRADES_TABLE + " WHERE symbol=%s",
                (symbol,),
            )
            dates = {row[0] for row in cur.fetchall() if row[0]}
        conn.commit()
        return dates
    except Exception:
        conn.rollback()
        raise


def _insert_trades(symbol, date_str, rows, ins_map):
    """درج دسته‌ای ریز معاملات در PG. خروجی: (تعداد درج‌شده، تعداد تکراری)"""
    global _PG_INSERT_SQL
    if not rows:
        return (0, 0)

    conn = _pg_conn()
    try:
        with conn.cursor() as cur:
            if _PG_INSERT_SQL is None:
                _PG_INSERT_SQL = _insert_sql(_pg_columns(cur))

            sql, optional = _PG_INSERT_SQL
            cur.execute(
                'SELECT "row" FROM ' + TRADES_TABLE + " WHERE symbol=%s AND trade_date=%s",
                (symbol, date_str),
            )
            existing = {rn for (rn,) in cur.fetchall()}

            fresh, seen = [], set()
            for r in rows:
                seq_no = r["seq_no"]
                if seq_no in existing or seq_no in seen:
                    continue
                seen.add(seq_no)
                fresh.append(r)
            if not fresh:
                conn.commit()
                return (0, len(rows))

            gregorian = _shamsi_to_gregorian(date_str)
            utc = _shamsi_to_utc(date_str)
            values = []
            for r in fresh:
                value = [
                    symbol, r["seq_no"], r["time"], r["volume"],
                    r["price"], bool(r["is_canceled"]), date_str,
                ]
                for column in optional:
                    if column == "ins_id":
                        value.append(ins_map.get(symbol))
                    elif column == "shamsi_date":
                        value.append(date_str)
                    elif column == "gregorian_date":
                        value.append(gregorian)
                    else:
                        value.append(utc)
                values.append(tuple(value))

            inserted = len(execute_values(cur, sql, values, page_size=2000, fetch=True))
        conn.commit()
        return (inserted, len(rows) - len(fresh))
    except Exception:
        conn.rollback()
        raise


def _check_pg():
    """بررسی زودهنگام (fail-fast) اتصال و اسکیمای جدول ریز معاملات"""
    try:
        conn = psycopg2.connect(**PG_CONFIG)
    except Exception as e:
        raise RuntimeError(f"اتصال به پستگرس ({_pg_target()}) برقرار نشد: {e}")
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM " + TRADES_TABLE + " LIMIT 1")
            _insert_sql(_pg_columns(cur))
    except Exception as e:
        raise RuntimeError(f"جدول {TRADES_TABLE} در {_pg_target()} آماده نیست: {e}")
    finally:
        conn.close()

    logging.info(f"مقصد ذخیره ریز معاملات: {_pg_target()} :: {TRADES_TABLE}")
    logging.info(
        "یادآوری: یکتایی (symbol, trade_date, row) به ایندکس یکتای جدول وابسته است؛ "
        "بدون آن درج هم‌زمان می‌تواند ردیف تکراری بسازد."
    )


# ============================ دانلودر ============================
class SmartCollector:
    def __init__(self, symbols, limiter, start_date=None, end_date=None,
                 db_resume=False, run_limit=None):
        self.symbols = symbols
        self.skipped_closed = 0   # تعداد روزهای تعطیلی که بدون ریکوئست رد شدند
        self.limiter = limiter
        self.stop_event = threading.Event()
        self._http_local = threading.local()
        self.start_date = start_date or _parse_jalali(START_DATE_SHAMSI)
        self.end_date = end_date or jdatetime.date.today()
        self.db_resume = db_resume
        self.run_limit = run_limit
        os.makedirs(DATA_DIR, exist_ok=True)
        self.ins_map = _load_ins_id_map(symbols)
        if self.ins_map:
            logging.info(f"نگاشت ins_id: {len(self.ins_map)} نماد")

    def _session(self):
        """Session مستقل برای هر ترد (requests.Session اشتراکی thread-safe نیست)."""
        session = getattr(self._http_local, "session", None)
        if session is None:
            session = requests.Session()
            adapter = HTTPAdapter(pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS)
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            self._http_local.session = session
        return session

    def fetch_transaction(self, task):
        symbol, date_str, out_path = task

        if self.stop_event.is_set():
            return "API_STOP"

        resp = None
        count_or_reason = 0
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                allowed, count_or_reason = self.limiter.acquire_slot()
            except Exception as e:
                self.stop_event.set()
                logging.error(f"خطای سامانه سهمیه: {type(e).__name__}: {e}; دانلودگر متوقف شد.")
                return "API_STOP"
            if not allowed:
                if count_or_reason in ("DAILY_LIMIT_EXCEEDED", "ROLLING_LIMIT_EXCEEDED"):
                    return "DAILY_STOP"
                logging.error(f"سهمیه متوقف شد: {count_or_reason}")
                return "API_STOP"
            if self.stop_event.is_set():
                return "API_STOP"

            try:
                resp = self._session().get(
                    f"{BASE_URL}/Tsetmc/Transaction.php",
                    params={"key": API_KEY, "l18": symbol, "date": date_str},
                    headers=HEADERS,
                    timeout=15,
                    allow_redirects=False,
                )
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt == MAX_ATTEMPTS:
                    self.stop_event.set()
                    logging.error(
                        f"خطای شبکه برای {symbol} در {date_str} پس از {attempt} تلاش: "
                        f"{type(e).__name__}; دانلودگر متوقف شد."
                    )
                    return "API_STOP"
                time.sleep(2 ** attempt)
                continue

            if resp.status_code == 429:
                if attempt < MAX_ATTEMPTS:
                    retry_after = _as_int(getattr(resp, "headers", {}).get("Retry-After"), 0)
                    wait_seconds = max(retry_after, 30 * attempt)
                    logging.warning(
                        f"محدودیت نرخ (429) برای {symbol} در {date_str}; "
                        f"{wait_seconds} ثانیه صبر و تلاش {attempt + 1}/{MAX_ATTEMPTS}."
                    )
                    time.sleep(wait_seconds)
                    continue
                break

            if resp.status_code == 403:
                break

            if resp.status_code == 424 and attempt < MAX_ATTEMPTS:
                # منبع برای این (نماد، تاریخ) داده ندارد؛ یک تلاش دوباره قبل از ثبت خالی
                time.sleep(2 ** attempt)
                continue

            if resp.status_code in TRANSIENT_HTTP and attempt < MAX_ATTEMPTS:
                time.sleep(2 ** attempt)
                continue
            break

        if resp is None:
            return "API_STOP"

        if resp.status_code == 429:
            self.stop_event.set()
            logging.error(f"محدودیت نرخ (429) برای {symbol} در {date_str}; دانلودگر متوقف شد.")
            return "API_STOP"

        if resp.status_code == 403:
            self.stop_event.set()
            logging.error(
                f"کد HTTP 403 برای {symbol} در {date_str}; "
                "دانلودگر برای جلوگیری از درخواست بیشتر متوقف شد."
            )
            return "API_STOP"

        if resp.status_code == 424:
            # منبع برای این (نماد، تاریخ) ریز معامله‌ای ندارد (نماد در آن روز معامله نشده)
            _write_json_atomic(out_path, {"status": "no_data", "http": 424, "symbol": symbol, "date": date_str})
            logging.info(f"بدون داده (424): {symbol} | {date_str}")
            return "EMPTY"

        if resp.status_code != 200:
            # تشخیص روز تعطیل/آخر هفته (بدون تراکنش) تا دوباره retry نشود و سهمیه هدر نرود
            try:
                _err = resp.json()
            except Exception:
                _err = None
            detail = ""
            if isinstance(_err, dict) and isinstance(_err.get("message_error"), str):
                _msg = _err["message_error"].lower()
                detail = _err["message_error"][:160]
                if "holiday" in _msg or "weekend" in _msg or "تعطیل" in _msg:
                    # این تاریخ برای کل بازار تعطیل است ⇒ برای نمادهای بعدی بدون ریکوئست رد شود
                    _mark_holiday(date_str)
                    _write_json_atomic(out_path, [])
                    logging.info(f"تعطیل (ثبت در تقویم تعطیلات): {symbol} | {date_str}")
                    return "EMPTY"
            self.stop_event.set()
            logging.error(
                f"پاسخ HTTP {resp.status_code} برای {symbol} در {date_str}: {detail}; دانلودگر متوقف شد."
            )
            return "API_STOP"

        try:
            data = resp.json()
        except ValueError:
            self.stop_event.set()
            logging.error(f"پاسخ غیر-JSON برای {symbol} در {date_str}; دانلودگر متوقف شد.")
            return "API_STOP"

        # پاکت خطا با HTTP 200 (هم success و هم successful بررسی می‌شوند)
        if isinstance(data, dict) and (
            data.get("error") or data.get("success") is False or data.get("successful") is False
        ):
            self.stop_event.set()
            logging.error(f"پاسخ خطای API برای {symbol} در {date_str}; دانلودگر متوقف شد.")
            return "API_STOP"

        # پاکت تودرتو {"data": {"transaction": [...]}} — آرشیو خام نوشته می‌شود تا
        # این (نماد، تاریخ) در اجراهای بعدی دوباره درخواست نشود.
        inner = data.get("data") if isinstance(data, dict) else None
        if isinstance(data, dict) and not isinstance(inner, dict):
            self.stop_event.set()
            logging.error(f"پاکت ناشناخته برای {symbol} در {date_str}; دانلودگر متوقف شد.")
            return "API_STOP"
        if isinstance(inner, dict) and not inner.get("transaction"):
            _write_json_atomic(out_path, data)
            logging.info(f"بدون تراکنش: {symbol} | {date_str}")
            return "EMPTY"

        rows = _extract_trade_rows(data)
        inserted = skipped = 0
        if rows:
            try:
                inserted, skipped = _insert_trades(symbol, date_str, rows, self.ins_map)
            except Exception as e:
                self.stop_event.set()
                logging.error(
                    f"درج در پستگرس ناموفق ({symbol} | {date_str}): "
                    f"{type(e).__name__}: {e}; دانلودگر متوقف شد."
                )
                return "API_STOP"

        try:
            _write_json_atomic(out_path, data)
        except OSError as e:
            self.stop_event.set()
            logging.error(f"نوشتن آرشیو {symbol} | {date_str} ناموفق: {e}; دانلودگر متوقف شد.")
            return "API_STOP"

        logging.info(
            f"[{count_or_reason}/{DAILY_LIMIT}] ذخیره شد: {symbol} | {date_str} | "
            f"PG: {inserted} ردیف (+{skipped} تکراری)"
        )
        return "OK"

    def _iter_tasks(self):
        """تولید تنبل (lazy) تسک‌های باقیمانده برای دانلود.

        تاریخ‌های موجود هر نماد با یک بار os.listdir خوانده می‌شود (به‌جای میلیون‌ها
        فراخوانی os.path.exists) و صف به‌صورت جریان تولید می‌شود تا کل میلیون‌ها تسک
        در حافظه نگه داشته نشود.
        """
        start_date = self.start_date
        today = self.end_date

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
            if self.db_resume:
                existing |= _load_existing_dates(sym)

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
        logging.info(
            f"آماده‌سازی صف کارها: {len(self.symbols)} نماد | "
            f"{self.start_date.strftime('%Y-%m-%d')} تا {self.end_date.strftime('%Y-%m-%d')} | "
            f"db_resume={self.db_resume} | run_limit={self.run_limit or 'بدون سقف جدا'}"
        )
        max_pending = MAX_WORKERS * 8   # پنجره محدود ⇒ حافظه ثابت و شروع فوری دانلود
        queued = 0
        daily_stop = False
        api_stop = False
        run_capped = False

        def _classify(futures):
            nonlocal daily_stop, api_stop
            for future in futures:
                try:
                    result = future.result()
                except Exception as e:
                    logging.error(f"خطای اجرای تسک: {type(e).__name__}: {e}")
                    api_stop = True
                    continue
                if result == "DAILY_STOP":
                    daily_stop = True
                elif result == "API_STOP":
                    api_stop = True
                    self.stop_event.set()

        def _finish(message, level):
            logging.log(level, message)
            executor.shutdown(wait=False, cancel_futures=True)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            pending = set()
            for task in self._iter_tasks():
                if self.run_limit is not None and queued >= self.run_limit:
                    run_capped = True
                    break
                pending.add(executor.submit(self.fetch_transaction, task))
                queued += 1
                if len(pending) < max_pending:
                    continue
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                _classify(done)
                if daily_stop or api_stop:
                    break

            if daily_stop or api_stop or run_capped:
                if run_capped and not (daily_stop or api_stop):
                    _finish(f"سقف این اجرا ({self.run_limit} درخواست) تکمیل شد.", logging.INFO)
                elif daily_stop:
                    _finish("سقف ۱۰,۰۰۰ درخواست (روزانه/۲۴ ساعته) پر شد. کار تا آزادشدن ظرفیت متوقف می‌شود.", logging.INFO)
                else:
                    _finish("دانلودگر پس از خطای API متوقف شد؛ اجرای مجدد خودکار انجام نمی‌شود.", logging.ERROR)
                return

            _classify(as_completed(pending))

            if api_stop:
                self.stop_event.set()
                _finish("دانلودگر پس از خطای API متوقف شد؛ اجرای مجدد خودکار انجام نمی‌شود.", logging.ERROR)
                return
            if daily_stop:
                _finish("سقف ۱۰,۰۰۰ درخواست (روزانه/۲۴ ساعته) پر شد. کار تا آزادشدن ظرفیت متوقف می‌شود.", logging.INFO)
                return

        logging.info(
            f"صف تسک‌ها تمام شد (ارسال‌شده: {queued} | روز تعطیل رد‌شده: {self.skipped_closed})."
        )


if __name__ == "__main__":
    def _jalali_arg(value):
        try:
            return _parse_jalali(value)
        except Exception as exc:
            raise argparse.ArgumentTypeError(f"تاریخ شمسی نامعتبر: {value}") from exc

    parser = argparse.ArgumentParser(description="دانلود ریز معاملات BrsApi و ذخیره مستقیم در پستگرس")
    parser.add_argument("--symbols", help="نمادها با کاما (پیش‌فرض: کش/کشف خودکار)")
    parser.add_argument("--start", type=_jalali_arg, default=_parse_jalali(START_DATE_SHAMSI),
                        help=f"تاریخ شروع شمسی (پیش‌فرض {START_DATE_SHAMSI})")
    parser.add_argument("--end", type=_jalali_arg, default=None, help="تاریخ پایان شمسی (پیش‌فرض: امروز)")
    parser.add_argument("--db-resume", action="store_true",
                        help="تاریخ‌هایی که از قبل در جدول ریز معاملات هستند دوباره دانلود نشوند")
    parser.add_argument("--max-requests", type=int, default=None,
                        help=f"سقف درخواست این اجرا (حداکثر {DAILY_LIMIT})")
    args = parser.parse_args()

    try:
        run_limit = min(args.max_requests, DAILY_LIMIT) if args.max_requests else None
        if run_limit is not None and run_limit < 1:
            raise ValueError("--max-requests باید حداقل ۱ باشد.")

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
        _check_pg()        # fail-fast پیش از مصرف سهمیه
        limiter = RateLimiter()
        if args.symbols:
            symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
        else:
            symbols = extract_all_symbols(limiter)
        collector = SmartCollector(
            symbols,
            limiter,
            start_date=args.start,
            end_date=args.end,
            db_resume=args.db_resume,
            run_limit=run_limit,
        )
        collector.run()
    except (RuntimeError, ValueError) as e:
        raise SystemExit(str(e))
