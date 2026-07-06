#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🚀 Codal Robust Fetcher v2.0
برنامه خودکار و مقاوم برای دریافت اطلاعات از سایت https://www.codal.ir/

ویژگی‌ها:
 - پشتیبانی از ۵ روش مختلف با قابلیت Fallback خودکار
 - ذخیره‌سازی در PostgreSQL با ساختار JSONB
 - ایجاد لاگ کامل و گزارش نهایی
 - مدیریت خطا و تلاش مجدد هوشمند
"""

import sys
import os
import time
import json
import logging
import subprocess
import random
import traceback
import urllib3
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================
#  نصب خودکار کتابخانه‌های مورد نیاز (با چاپ امن)
# ============================================================
REQUIRED_PACKAGES = [
    "psycopg2-binary",
    "requests",
    "beautifulsoup4",
    "lxml",
    "python-dotenv",
    "codalpy",
]

# مپ کردن نام pip به نام ماژول import
PIP_TO_MODULE = {
    "psycopg2-binary": "psycopg2",
    "beautifulsoup4": "bs4",
}

for pkg in REQUIRED_PACKAGES:
    module_name = PIP_TO_MODULE.get(pkg, pkg.replace("-", "_"))
    try:
        __import__(module_name)
    except ImportError:
        try:
            sys.stdout.write(f"[install] Installing {pkg}...\n")
            sys.stdout.flush()
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg, "--quiet"]
            )
        except Exception as e:
            sys.stdout.write(f"[install] Warning: Could not install {pkg}: {e}\n")
            sys.stdout.flush()

# ============================================================
#  ایمپورت‌ها
# ============================================================
import requests
from bs4 import BeautifulSoup
import pandas as pd
from dotenv import load_dotenv

# ============================================================
#  تنظیمات مسیر
# ============================================================
BASE_DIR = Path(__file__).parent.resolve()
LOG_DIR = BASE_DIR

# ============================================================
#  بارگذاری تنظیمات از .env (از مسیر اصلی پروژه یا همین مسیر)
# ============================================================
env_loaded = load_dotenv(BASE_DIR.parent / ".env")
if not env_loaded:
    env_loaded = load_dotenv(BASE_DIR / ".env")

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "my_first_db"),
    "user": os.getenv("DB_USER", "hossein"),
    "password": os.getenv("DB_PASSWORD", "1343"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
}

# ============================================================
#  تنظیمات اصلی
# ============================================================
SYMBOL = "فولاد"
START_DATE = "1395/01/01"
END_DATE = "1405/12/29"
SLEEP_BETWEEN_REQUESTS = 1.5
REQUEST_TIMEOUT = 20
MAX_RETRIES_PER_METHOD = 2
LOG_FILE = BASE_DIR / f"test_{SYMBOL}.log"

# ============================================================
#  راه‌اندازی سیستم لاگ‌گیری
# ============================================================
logger = logging.getLogger("CodalRobust")
logger.setLevel(logging.DEBUG)

# فرمت لاگ
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# لاگ فایل
file_handler = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# لاگ کنسول (با پشتیبانی از یونیکد)
class UnicodeStreamHandler(logging.StreamHandler):
    """Handler that writes to stderr with utf-8 encoding."""

    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            stream.write(msg + "\n")
            stream.flush()
        except UnicodeEncodeError:
            # تلاش مجدد با حذف کاراکترهای غیرقابل نمایش
            try:
                msg = self.format(record).encode("utf-8", errors="replace").decode("utf-8")
                stream.write(msg + "\n")
                stream.flush()
            except Exception:
                self.handleError(record)
        except Exception:
            self.handleError(record)


console_handler = UnicodeStreamHandler(sys.stderr)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# ============================================================
#  توابع کمکی
# ============================================================

def safe_print(text: str):
    """چاپ امن با پشتیبانی از یونیکد - نوشتن مستقیم در stderr/buffer"""
    try:
        # روش ۱: تلاش با sys.stdout.buffer (باینری مستقیم)
        sys.stdout.buffer.write((text + "\n").encode("utf-8"))
        sys.stdout.buffer.flush()
    except Exception:
        try:
            # روش ۲: حذف ایموجی‌ها و کاراکترهای غیرقابل نمایش
            clean = text.encode("ascii", errors="replace").decode("ascii")
            print(clean)
        except Exception:
            pass


def get_connection():
    """ایجاد اتصال به PostgreSQL"""
    import psycopg2

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.set_client_encoding("UTF8")
        return conn
    except Exception as e:
        logger.error(f"❌ خطا در اتصال به PostgreSQL: {e}")
        logger.error(f"   کانفیگ: host={DB_CONFIG['host']} port={DB_CONFIG['port']} "
                      f"dbname={DB_CONFIG['dbname']} user={DB_CONFIG['user']}")
        return None


def init_database():
    """ایجاد جداول دیتابیس"""
    logger.info("🔄 ایجاد/بررسی ساختار دیتابیس...")
    conn = get_connection()
    if conn is None:
        logger.error("❌ اتصال به دیتابیس ممکن نیست. از ذخیره‌سازی فایل استفاده می‌شود.")
        return False

    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                symbol VARCHAR(20) PRIMARY KEY,
                company_name VARCHAR(200) NOT NULL,
                isin VARCHAR(20),
                stock_code VARCHAR(20),
                market_type VARCHAR(20),
                sector VARCHAR(100),
                sub_sector VARCHAR(100),
                board VARCHAR(50),
                first_trade_date DATE,
                registered_capital BIGINT,
                website VARCHAR(100),
                phone VARCHAR(20),
                address TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS raw_reports (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(20) NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
                report_type VARCHAR(50) NOT NULL,
                period_date DATE,
                data_json JSONB NOT NULL,
                fetched_at TIMESTAMP DEFAULT NOW(),
                method_used VARCHAR(50),
                UNIQUE(symbol, report_type, period_date)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS processed_symbols (
                symbol VARCHAR(20) PRIMARY KEY REFERENCES companies(symbol) ON DELETE CASCADE,
                last_fetched TIMESTAMP DEFAULT NOW(),
                status VARCHAR(20) CHECK (status IN ('success', 'failed', 'processing')),
                retry_count INTEGER DEFAULT 0,
                method_used VARCHAR(50),
                error_message TEXT
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_raw_symbol ON raw_reports (symbol);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_raw_report_type ON raw_reports (report_type);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_raw_period_date ON raw_reports (period_date);")
        conn.commit()
        cur.close()
        conn.close()
        logger.info("✅ ساختار دیتابیس ایجاد/تأیید شد.")
        return True
    except Exception as e:
        logger.error(f"❌ خطا در ایجاد جداول: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return False


def save_company_to_db(symbol: str, company_name: str = None) -> bool:
    """ذخیره اطلاعات شرکت در دیتابیس"""
    conn = get_connection()
    if conn is None:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO companies (symbol, company_name)
            VALUES (%s, %s)
            ON CONFLICT (symbol) DO UPDATE SET
                company_name = EXCLUDED.company_name,
                updated_at = NOW()
        """, (symbol, company_name or symbol))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"   ❌ خطا در ذخیره اطلاعات شرکت: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return False


def save_report_to_db(symbol: str, report_type: str, data_json: Any,
                       period_date: Optional[str] = None, method: str = "") -> bool:
    """ذخیره یک گزارش در دیتابیس با ON CONFLICT"""
    conn = get_connection()
    if conn is None:
        return False
    try:
        import psycopg2.extras
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO raw_reports (symbol, report_type, period_date, data_json, method_used)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (symbol, report_type, period_date) DO UPDATE SET
                data_json = EXCLUDED.data_json,
                fetched_at = NOW(),
                method_used = EXCLUDED.method_used
        """, (
            symbol,
            report_type,
            period_date,
            psycopg2.extras.Json(data_json),
            method,
        ))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"      ❌ خطا در ذخیره {report_type}: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return False


def update_status(symbol: str, status: str, method_used: str = "", error_msg: str = None):
    """بروزرسانی وضعیت پردازش نماد"""
    conn = get_connection()
    if conn is None:
        return
    try:
        cur = conn.cursor()
        if status == "processing":
            cur.execute("""
                INSERT INTO processed_symbols (symbol, status, method_used)
                VALUES (%s, %s, %s)
                ON CONFLICT (symbol) DO UPDATE SET
                    status = EXCLUDED.status,
                    method_used = EXCLUDED.method_used,
                    last_fetched = NOW()
            """, (symbol, status, method_used))
        else:
            cur.execute("""
                INSERT INTO processed_symbols (symbol, status, method_used, error_message)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (symbol) DO UPDATE SET
                    status = EXCLUDED.status,
                    method_used = EXCLUDED.method_used,
                    error_message = EXCLUDED.error_message,
                    last_fetched = NOW(),
                    retry_count = processed_symbols.retry_count + 1
            """, (symbol, status, method_used, error_msg))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"   ❌ خطا در بروزرسانی وضعیت: {e}")
        try:
            conn.close()
        except Exception:
            pass


def period_date_from_df(df: pd.DataFrame) -> Optional[str]:
    """استخراج تاریخ دوره از دیتافریم با تبدیل دقیق شمسی→میلادی"""
    try:
        import jdatetime
    except ImportError:
        jdatetime = None

    for col in ["period_end_date", "تاریخ", "PeriodEndDate", "report_date"]:
        if col in df.columns:
            try:
                val = df.iloc[-1].get(col)
                if val and str(val).strip():
                    parts = str(val).split("/")
                    if len(parts) == 3:
                        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                        if y > 1400 and jdatetime is not None:
                            # تبدیل دقیق شمسی به میلادی با jdatetime
                            g = jdatetime.date(y, m, d).togregorian()
                            return g.isoformat()
                        elif y > 1400:
                            # Fallback: تقریب ساده
                            return f"{y - 621:04d}-{m:02d}-{d:02d}"
                        else:
                            return f"{y:04d}-{m:02d}-{d:02d}"
                    return str(val)
            except Exception:
                continue
    return None


def save_reports_batch(symbol: str, reports: Dict[str, Any], method: str) -> int:
    """ذخیره دسته‌ای گزارش‌ها"""
    saved = 0
    for report_type, data in reports.items():
        period = data.get("period_date")
        json_data = data.get("data")
        rows = data.get("rows", 0)
        if rows > 0 and json_data:
            if save_report_to_db(symbol, report_type, json_data, period, method):
                saved += 1
    return saved


# ============================================================
#  روش ۱: کتابخانه codalpy
# ============================================================
def method_codalpy(symbol: str) -> Tuple[bool, Dict[str, Any], str]:
    """
    روش ۱: استفاده از کتابخانه تخصصی codalpy
    اگر متدها موجود نباشند، خطا ثبت می‌کند و به روش بعدی می‌رود.
    """
    logger.info(f"  ┌─ [Method 1/5] Trying codalpy library...")

    try:
        from codalpy import Codal
    except ImportError:
        logger.warning("  │  ⚠️  codalpy not installed. Trying to install...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "codalpy", "--quiet"],
                timeout=30,
            )
            from codalpy import Codal
        except Exception as e:
            logger.warning(f"  │  ❌ Failed to install codalpy: {e}")
            return (False, {}, "codalpy_not_available")

    try:
        # تلاش برای ایجاد Codal با پارامترهای مختلف
        codal = None
        for args in [
            lambda: Codal(query="", category=""),
            lambda: Codal(),
            lambda: Codal(query="فولاد", category="income_statement"),
        ]:
            try:
                codal = args()
                break
            except Exception:
                continue

        if codal is None:
            logger.warning("  │  ❌ Could not instantiate Codal")
            return (False, {}, "codalpy_init_failed")

        # کشف متدهای موجود
        available = set(
            m for m in dir(codal)
            if not m.startswith("_") and callable(getattr(codal, m))
        )
        logger.info(f"  │  Available methods: {sorted(available)}")

        reports = {}
        saved_any = False

        method_names = {
            "income_statement": ["income_statement", "income", "get_income_statement"],
            "balance_sheet": ["balance_sheet", "balance", "get_balance_sheet"],
            "cash_flow": ["cash_flow", "cashflow", "get_cash_flow"],
            "monthly_activity": ["monthly_activity", "monthly", "get_monthly_activity"],
            "shareholders": ["shareholders", "shareholder", "get_shareholders"],
            "management_report": ["management_report", "management", "get_management_report"],
        }

        for report_type, names in method_names.items():
            found = None
            for n in names:
                if n in available:
                    found = getattr(codal, n)
                    break
            if found is None:
                logger.debug(f"  │     ⚠️  No method for {report_type}")
                continue

            try:
                time.sleep(SLEEP_BETWEEN_REQUESTS)
                result = found(issuer=symbol, from_jdate=START_DATE, to_jdate=END_DATE)

                if result is None:
                    continue
                if isinstance(result, pd.DataFrame) and result.empty:
                    continue
                if not isinstance(result, pd.DataFrame):
                    result = pd.DataFrame(result)

                period = period_date_from_df(result)
                json_data = result.to_json(orient="records", force_ascii=False)
                reports[report_type] = {
                    "data": json_data,
                    "period_date": period,
                    "rows": len(result),
                }
                logger.info(f"  │     ✅ {report_type}: {len(result)} rows")
                saved_any = True
            except Exception as e:
                logger.debug(f"  │     ⚠️  {report_type}: {str(e)[:60]}")

        if saved_any:
            return (True, reports, "codalpy")
        else:
            logger.warning("  │  ⚠️  No data from codalpy")
            return (False, reports, "codalpy_no_data")

    except Exception as e:
        logger.warning(f"  │  ❌ codalpy error: {str(e)[:100]}")
        logger.debug(traceback.format_exc())
        return (False, {}, f"codalpy_error_{str(e)[:50]}")


# ============================================================
#  روش ۲: API مستقیم کدال
# ============================================================
def fetch_via_api(symbol: str, report_type: str, headers: dict,
                   timeout: int = REQUEST_TIMEOUT) -> Optional[pd.DataFrame]:
    """دریافت یک گزارش از API مستقیم کدال"""
    url = "https://codal.ir/api/FinancialReport/GetFinancialReport"
    params = {
        "symbol": symbol,
        "reportType": report_type,
        "fromDate": START_DATE.replace("/", "-"),
        "toDate": END_DATE.replace("/", "-"),
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                return pd.DataFrame(data)
        return None
    except requests.Timeout:
        logger.debug(f"      ⏱️  Timeout for {report_type}")
        return None
    except Exception as e:
        logger.debug(f"      ⚠️  {report_type}: {str(e)[:50]}")
        return None


def method_direct_api(symbol: str) -> Tuple[bool, Dict[str, Any], str]:
    """
    روش ۲: ارسال درخواست HTTP مستقیم به API کدال
    """
    logger.info(f"  ┌─ [Method 2/5] Trying direct Codal API...")

    headers_list = [
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9,fa;q=0.8",
            "Referer": "https://codal.ir/",
            "Origin": "https://codal.ir",
        },
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://codal.ir/",
        },
        {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Accept": "application/json",
        },
    ]

    report_types = [
        "income_statement",
        "balance_sheet",
        "cash_flow",
        "monthly_activity",
        "shareholders",
        "management_report",
    ]

    reports = {}
    saved_any = False

    for attempt in range(MAX_RETRIES_PER_METHOD):
        headers = headers_list[attempt % len(headers_list)]
        logger.info(f"  │  Attempt {attempt + 1} with {headers['User-Agent'][:40]}...")

        for rtype in report_types:
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            df = fetch_via_api(symbol, rtype, headers)
            if df is not None and not df.empty:
                period = period_date_from_df(df)
                json_data = df.to_json(orient="records", force_ascii=False)
                reports[rtype] = {
                    "data": json_data,
                    "period_date": period,
                    "rows": len(df),
                }
                logger.info(f"  │     ✅ {rtype}: {len(df)} rows")
                saved_any = True
            else:
                logger.debug(f"  │     ⚠️  {rtype}: no data")

        if saved_any:
            break
        if attempt < MAX_RETRIES_PER_METHOD - 1:
            time.sleep(3)

    if saved_any:
        return (True, reports, "direct_api")
    else:
        logger.warning("  │  ⚠️  Direct API returned no data")
        return (False, reports, "api_no_data")


# ============================================================
#  روش ۳: Scraping با requests + BeautifulSoup
# ============================================================
def method_beautifulsoup(symbol: str) -> Tuple[bool, Dict[str, Any], str]:
    """
    روش ۳: جستجوی نماد در کدال با Scraping و BeautifulSoup
    """
    logger.info(f"  ┌─ [Method 3/5] Trying BeautifulSoup scraping...")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,fa;q=0.8",
    }

    try:
        # جستجوی نماد در سایت کدال
        search_url = "https://codal.ir/ReportList.aspx"
        params = {
            "search": symbol,
            "auditor": "False",
            "isNotAudited": "False",
            "childs": "True",
        }

        logger.info(f"  │  Searching for '{symbol}' on codal.ir...")
        time.sleep(SLEEP_BETWEEN_REQUESTS)
        resp = requests.get(search_url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)

        if resp.status_code != 200:
            logger.warning(f"  │  ⚠️  Search page returned status {resp.status_code}")
            return (False, {}, f"scrape_status_{resp.status_code}")

        # بررسی محتوا
        soup = BeautifulSoup(resp.text, "lxml")
        logger.info(f"  │  Fetched page ({len(resp.text)} bytes)")

        # تلاش برای یافتن لینک‌های گزارش
        links = soup.find_all("a", href=True)
        report_links = [l for l in links if "Report" in l.get("href", "") or "FinancialReport" in l.get("href", "")]
        logger.info(f"  │  Found {len(report_links)} report links")

        # استخراج اطلاعات از جدول اگر موجود باشد
        tables = soup.find_all("table")
        logger.info(f"  │  Found {len(tables)} HTML tables")

        reports = {}
        saved_any = False
        row_count = 0

        # پردازش جداول
        for i, table in enumerate(tables):
            rows = table.find_all("tr")
            if len(rows) > 1:
                # سعی می‌کنیم داده‌های جدول را استخراج کنیم
                table_data = []
                headers_row = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
                for tr in rows[1:]:
                    cols = [td.get_text(strip=True) for td in tr.find_all("td")]
                    if cols:
                        table_data.append(cols)

                if table_data and headers_row:
                    df = pd.DataFrame(table_data, columns=headers_row[:len(table_data[0])])
                    rtype = f"scraped_table_{i}"
                    json_data = df.to_json(orient="records", force_ascii=False)
                    reports[rtype] = {
                        "data": json_data,
                        "period_date": None,
                        "rows": len(df),
                    }
                    row_count += len(df)
                    saved_any = True

        if saved_any:
            logger.info(f"  │  ✅ Extracted {row_count} rows from HTML tables")
            return (True, reports, "beautifulsoup")
        else:
            logger.warning("  │  ⚠️  No data extracted via BeautifulSoup")
            return (False, reports, "bs4_no_data")

    except requests.Timeout:
        logger.warning("  │  ⏱️  Timeout on BeautifulSoup request")
        return (False, {}, "bs4_timeout")
    except Exception as e:
        logger.warning(f"  │  ❌ BeautifulSoup error: {str(e)[:80]}")
        logger.debug(traceback.format_exc())
        return (False, {}, f"bs4_error_{str(e)[:40]}")


# ============================================================
#  روش ۴: Scraping با Selenium
# ============================================================
def method_selenium(symbol: str) -> Tuple[bool, Dict[str, Any], str]:
    """
    روش ۴: استفاده از Selenium برای محتوای داینامیک
    """
    logger.info(f"  ┌─ [Method 4/5] Trying Selenium...")

    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, WebDriverException
    except ImportError:
        logger.warning("  │  ⚠️  selenium not installed")
        return (False, {}, "selenium_not_installed")

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-logging"])

    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(REQUEST_TIMEOUT)
    except WebDriverException as e:
        # تلاش با Firefox یا Safari
        logger.warning(f"  │  ⚠️  Chrome not available: {str(e)[:50]}")
        try:
            from selenium.webdriver.firefox.options import Options as FirefoxOptions
            firefox_options = FirefoxOptions()
            firefox_options.add_argument("--headless")
            driver = webdriver.Firefox(options=firefox_options)
            driver.set_page_load_timeout(REQUEST_TIMEOUT)
        except Exception as e2:
            logger.warning(f"  │  ❌ Firefox also failed: {str(e2)[:50]}")
            return (False, {}, "selenium_no_driver")

    reports = {}
    saved_any = False

    try:
        # رفتن به صفحه جستجوی کدال
        search_url = f"https://codal.ir/ReportList.aspx?search={symbol}"
        logger.info(f"  │  Navigating to {search_url}...")
        driver.get(search_url)
        time.sleep(3)

        # گرفتن محتوای صفحه
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, "lxml")
        logger.info(f"  │  Page loaded ({len(page_source)} bytes)")

        # استخراج جداول
        tables = soup.find_all("table")
        row_count = 0

        for i, table in enumerate(tables):
            rows = table.find_all("tr")
            if len(rows) > 1:
                headers_row = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
                table_data = []
                for tr in rows[1:]:
                    cols = [td.get_text(strip=True) for td in tr.find_all("td")]
                    if cols:
                        table_data.append(cols)

                if table_data and headers_row:
                    df = pd.DataFrame(table_data, columns=headers_row[:len(table_data[0])])
                    rtype = f"selenium_table_{i}"
                    json_data = df.to_json(orient="records", force_ascii=False)
                    reports[rtype] = {
                        "data": json_data,
                        "period_date": None,
                        "rows": len(df),
                    }
                    row_count += len(df)
                    saved_any = True

        if saved_any:
            logger.info(f"  │  ✅ Extracted {row_count} rows via Selenium")
        else:
            logger.warning("  │  ⚠️  No data extracted via Selenium")

    except TimeoutException:
        logger.warning("  │  ⏱️  Selenium page load timeout")
    except Exception as e:
        logger.warning(f"  │  ❌ Selenium error: {str(e)[:80]}")
        logger.debug(traceback.format_exc())
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    return (saved_any, reports, "selenium" if saved_any else "selenium_no_data")


# ============================================================
#  روش ۵: درخواست با هدرهای مختلف + Proxy + curl_cffi
# ============================================================
def method_advanced_http(symbol: str) -> Tuple[bool, Dict[str, Any], str]:
    """
    روش ۵: استفاده از هدرهای متنوع، پروکسی و curl_cffi برای دور زدن محدودیت‌ها
    """
    logger.info(f"  ┌─ [Method 5/5] Trying advanced HTTP (proxies, curl_cffi)...")

    # ابتدا تلاش با curl_cffi که имитирует مرورگر واقعی
    try:
        logger.info("  │  Trying curl_cffi (browser fingerprint mimic)...")
        from curl_cffi import requests as curl_requests

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }

        url = "https://codal.ir/api/FinancialReport/GetFinancialReport"
        params = {
            "symbol": symbol,
            "reportType": "income_statement",
            "fromDate": START_DATE.replace("/", "-"),
            "toDate": END_DATE.replace("/", "-"),
        }

        # تلاش با different browser fingerprints
        for browser in ["chrome120", "chrome110", "safari16_5", "firefox110"]:
            try:
                time.sleep(SLEEP_BETWEEN_REQUESTS)
                resp = curl_requests.get(
                    url, params=params, headers=headers,
                    impersonate=browser, timeout=REQUEST_TIMEOUT
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        logger.info(f"  │  ✅ curl_cffi works with {browser}!")
                        df = pd.DataFrame(data)
                        period = period_date_from_df(df)
                        json_data = df.to_json(orient="records", force_ascii=False)
                        reports = {
                            "income_statement": {
                                "data": json_data,
                                "period_date": period,
                                "rows": len(df),
                            }
                        }
                        return (True, reports, "curl_cffi")
                else:
                    logger.debug(f"  │     {browser}: status {resp.status_code}")
            except Exception as e:
                logger.debug(f"  │     {browser}: {str(e)[:40]}")

    except ImportError:
        logger.info("  │  curl_cffi not available, trying regular requests with more options...")
    except Exception as e:
        logger.debug(f"  │  curl_cffi error: {str(e)[:50]}")

    # تلاش با proxy (لیست پروکسی‌های رایگان)
    logger.info("  │  Trying with different proxies...")

    proxies_list = [
        None,  # بدون پروکسی
    ]

    # اگر پروکسی در محیط تنظیم شده باشد
    env_proxy = os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")
    if env_proxy:
        proxies_list.append({"http": env_proxy, "https": env_proxy})

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://codal.ir/",
        "Origin": "https://codal.ir/",
        "DNT": "1",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
    }

    url = "https://codal.ir/api/FinancialReport/GetFinancialReport"
    report_types = [
        "income_statement",
        "balance_sheet",
        "cash_flow",
        "monthly_activity",
        "shareholders",
        "management_report",
    ]

    reports = {}
    saved_any = False

    for proxy in proxies_list:
        for rtype in report_types:
            params = {
                "symbol": symbol,
                "reportType": rtype,
                "fromDate": START_DATE.replace("/", "-"),
                "toDate": END_DATE.replace("/", "-"),
            }
            try:
                time.sleep(SLEEP_BETWEEN_REQUESTS)
                resp = requests.get(
                    url, params=params, headers=headers,
                    proxies=proxy, timeout=REQUEST_TIMEOUT + 10,
                    verify=False,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        df = pd.DataFrame(data)
                        period = period_date_from_df(df)
                        json_data = df.to_json(orient="records", force_ascii=False)
                        reports[rtype] = {
                            "data": json_data,
                            "period_date": period,
                            "rows": len(df),
                        }
                        saved_any = True
                        logger.info(f"  │     ✅ {rtype}: {len(df)} rows (proxy={proxy})")
            except Exception as e:
                logger.debug(f"  │     {rtype}: {str(e)[:40]}")

        if saved_any:
            break

    if saved_any:
        return (True, reports, "advanced_http")
    else:
        logger.warning("  │  ⚠️  All advanced HTTP methods failed")
        return (False, {}, "advanced_http_all_failed")


# ============================================================
#  ذخیره‌سازی فایل به عنوان پشتیبان (در صورت عدم دسترسی به دیتابیس)
# ============================================================
def save_reports_to_file(symbol: str, reports: Dict[str, Any], method: str):
    """ذخیره گزارش‌ها در فایل JSON به عنوان backup"""
    backup_file = BASE_DIR / f"reports_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    data = {
        "symbol": symbol,
        "method": method,
        "fetched_at": datetime.now().isoformat(),
        "reports": reports,
    }
    try:
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"  💾 Reports saved to {backup_file.name}")
        return str(backup_file)
    except Exception as e:
        logger.error(f"  ❌ Failed to save backup file: {e}")
        return None


# ============================================================
#  گزارش نهایی
# ============================================================
def print_summary(symbol: str, results: Dict[str, Any]):
    """نمایش خلاصه نتایج"""
    lines = []
    lines.append("\n" + "=" * 70)
    lines.append(f"  📊  REPORT SUMMARY for '{symbol}'")
    lines.append("=" * 70)

    total_rows = 0
    report_count = 0
    methods_tried = results.get("methods_tried", [])
    successful_method = results.get("successful_method", "N/A")

    lines.append(f"  • Successful method: {successful_method}")
    lines.append(f"  • Methods tried: {', '.join(methods_tried)}")
    lines.append("")

    if results.get("reports"):
        lines.append(f"  {'─' * 50}")
        lines.append(f"  {'Report Type':<25} {'Rows':<10} {'Period':<15}")
        lines.append(f"  {'─' * 50}")
        for rtype, data in results["reports"].items():
            rows = data.get("rows", 0)
            period = data.get("period_date") or "N/A"
            total_rows += rows
            report_count += 1
            lines.append(f"  {rtype:<25} {rows:<10} {str(period):<15}")
        lines.append(f"  {'─' * 50}")
        lines.append(f"  {'TOTAL':<25} {total_rows:<10}")
    else:
        lines.append(f"  ⚠️  No reports collected!")

    if results.get("error"):
        lines.append(f"\n  ❌ Error: {results['error']}")

    lines.append(f"\n  📝 Full log: {LOG_FILE}")
    lines.append("=" * 70)

    summary = "\n".join(lines)
    logger.info(summary)
    safe_print(summary)


# ============================================================
#  تابع اصلی
# ============================================================
def main(symbol: str = SYMBOL):
    """تابع اصلی اجرا"""
    start_time = datetime.now()

    safe_print("\n" + "=" * 70)
    safe_print(f"  🚀  CODAL ROBUST FETCHER v2.0")
    safe_print(f"  📡  Fetching data for symbol: {symbol}")
    safe_print(f"  ⏰  Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    safe_print("=" * 70 + "\n")

    logger.info("=" * 60)
    logger.info(f"START - Fetching data for '{symbol}'")
    logger.info(f"Date range: {START_DATE} to {END_DATE}")
    logger.info("=" * 60)

    # مرحله ۱: راه‌اندازی دیتابیس
    db_ok = init_database()

    # مرحله ۲: ذخیره اطلاعات شرکت (placeholder)
    if db_ok:
        save_company_to_db(symbol, symbol)
        update_status(symbol, "processing")

    # مرحله ۳: اجرای روش‌ها به ترتیب اولویت
    methods = [
        ("codalpy", method_codalpy),
        ("direct_api", method_direct_api),
        ("beautifulsoup", method_beautifulsoup),
        ("selenium", method_selenium),
        ("advanced_http", method_advanced_http),
    ]

    all_reports = {}
    successful_method = None
    methods_tried = []

    for method_name, method_func in methods:
        methods_tried.append(method_name)
        logger.info(f"\n  ┌{'─' * 50}┐")
        logger.info(f"  │  Method {methods_tried.index(method_name) + 1}: {method_name}")
        logger.info(f"  └{'─' * 50}┘")

        success = False
        last_error = None

        for attempt in range(1, MAX_RETRIES_PER_METHOD + 1):
            if attempt > 1:
                wait = attempt * 3
                logger.info(f"  Retry {attempt}/{MAX_RETRIES_PER_METHOD} after {wait}s...")
                time.sleep(wait)

            try:
                ok, reports, status = method_func(symbol)
                if ok and reports:
                    success = True
                    all_reports.update(reports)
                    successful_method = method_name
                    logger.info(f"  └─ ✅ Method '{method_name}' succeeded! "
                                  f"({sum(r['rows'] for r in reports.values())} total rows)")
                    break
                else:
                    last_error = status
                    logger.debug(f"     ↪ Status: {status}")
            except Exception as e:
                last_error = str(e)[:80]
                logger.debug(f"     ↪ Exception: {last_error}")
                logger.debug(traceback.format_exc())
            time.sleep(1)

        if success:
            if successful_method is None:
                successful_method = method_name
            # بعد از اولین روش موفق، از حلقه خارج می‌شویم
            logger.info(f"  └─ ✅ Success with method '{method_name}', stopping.")
            break
        else:
            logger.debug(f"  └─ ❌ Method '{method_name}' failed: {last_error}")

    # مرحله ۴: ذخیره‌سازی نتایج
    saved_count = 0
    backup_file = None

    if all_reports:
        if db_ok:
            saved_count = save_reports_batch(symbol, all_reports, successful_method or "unknown")
            if saved_count > 0:
                update_status(symbol, "success", successful_method or "unknown")
            else:
                update_status(symbol, "failed", successful_method or "unknown",
                              "Failed to save reports to DB")

        # پشتیبان فایل
        backup_file = save_reports_to_file(symbol, all_reports, successful_method or "unknown")
    else:
        error_msg = "All 5 methods failed to retrieve any data"
        logger.error(f"  ❌ {error_msg}")
        if db_ok:
            update_status(symbol, "failed", "all_methods_failed", error_msg)
        safe_print(f"\n  ❌ ALL 5 METHODS FAILED for '{symbol}'!")
        safe_print(f"  📝 Check log: {LOG_FILE}")

    # مرحله ۵: گزارش نهایی
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"\n⏱️  Total elapsed time: {elapsed:.1f} seconds")

    results = {
        "reports": all_reports,
        "successful_method": successful_method,
        "methods_tried": methods_tried,
        "saved_to_db": saved_count,
        "backup_file": str(backup_file) if backup_file else None,
        "elapsed_seconds": elapsed,
    }

    print_summary(symbol, results)

    if backup_file:
        safe_print(f"\n  💾 Backup saved to: {backup_file}")

    if db_ok and saved_count > 0:
        safe_print(f"  🗄️  {saved_count} reports saved to PostgreSQL database")
    else:
        safe_print(f"  ⚠️  Data saved to backup file only (DB unavailable or error)")

    return results


# ============================================================
#  اجرا
# ============================================================
if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else SYMBOL
    try:
        results = main(symbol)
        safe_print("\n" + "=" * 70)
        safe_print("  🏁  PROGRAM COMPLETED")
        safe_print("=" * 70)
    except KeyboardInterrupt:
        logger.info("⏹️  Interrupted by user")
        safe_print("\n⏹️  Program interrupted by user.")
    except Exception as e:
        logger.critical(f"💥 Unhandled exception: {e}")
        logger.debug(traceback.format_exc())
        safe_print(f"\n💥 CRITICAL ERROR: {e}")
        safe_print(f"📝 Check log: {LOG_FILE}")
        sys.exit(1)
