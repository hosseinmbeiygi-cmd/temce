#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
برنامه دریافت اطلاعات کدال - نسخه مقاوم (سازگار با نسخه‌های مختلف codalpy)
با امتحان نام‌های مختلف متدها
"""

import psycopg2
from psycopg2.extras import Json
import json
import time
import logging
import sys
import os
import random
from datetime import datetime
import pandas as pd
from codalpy import Codal
from dotenv import load_dotenv
from typing import Dict, Any, Optional, List, Set

# ============================================================
#  بارگذاری تنظیمات از .env
# ============================================================
load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "my_first_db"),
    "user": os.getenv("DB_USER", "hossein"),
    "password": os.getenv("DB_PASSWORD", "1343"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}

START_DATE = "1395/01/01"
END_DATE = "1405/12/29"
SLEEP_BETWEEN_SYMBOLS = 2
SLEEP_BETWEEN_REQUESTS = 1
MAX_RETRY_PER_SYMBOL = 2

# ============================================================
#  لیست کامل نمادها (بورس + فرابورس)
# ============================================================
SYMBOLS_LIST = [
    "فولاد", "شپنا", "خودرو", "وبملت", "کگل", "جم", "فملی", "پارس",
    "حکشتی", "غاذر", "کچاد", "فایرا", "دماوند", "سپید", "پترول",
    "شستا", "ملی", "گلگهر", "چادرملو", "کیمیا", "سرمایه‌گذاری",
    "آتیه", "دی", "پارس خودرو", "سایپا", "ایران خودرو",
    "شپديس", "فارس", "خگستر", "خساپا", "سرمایه",
    "باما", "پکویر", "نیرو", "برکت", "صدرا",
    "خاور", "خودروسازی", "سایپا دیزل", "ایران خودرو دیزل",
    "پارس سوییچ", "سپاهان", "ذوب", "فولاد مبارکه",
    "معدنی", "صنعتی", "شیمیایی", "پتروشیمی", "پالایش",
    "آسپ", "آریا", "آسیا", "آتی", "آذر",
    "آپ", "آبت", "آبید", "آتک", "آجین",
    "آدر", "آذر", "آرین", "آسان", "آسمان",
    "آفاق", "آلوم", "آهن", "آهن و فولاد", "آینده",
    "سها", "سهام", "سهند", "سیرنگ", "سیمان",
    "وبصادر", "وبملت", "وتجارت", "وبانک", "وبشهر",
    "وملی", "وسینا", "وپاسار", "وپارس", "وپترو",
    "خودرو", "سایپا", "پارس خودرو", "خگستر", "خساپا",
    "خاور", "خدیزل", "خپارس", "ختراک", "خزر",
    "شپنا", "شتران", "شبندر", "شبصیر", "شراز",
    "شپديس", "شپاس", "شسپا", "شگستر", "شمواد",
    "فولاد", "کگل", "فملی", "کچاد", "گلگهر",
    "چادرملو", "کیمیا", "ذوب", "فسنگ", "فخاس",
    "سپاس", "سپید", "سرمایه", "سیمان", "سفارس",
    "دماوند", "دپارس", "دتولید", "دارو", "دشیمی",
    "غاذر", "غشاذر", "غپینو", "غدام", "غصینو",
    "سرمایه", "سهام", "سهند", "سیرنگ", "سها",
    "وتجارت", "وبصادر", "وبملت", "وپاسار", "وپترو"
]

# ============================================================
#  تنظیمات لاگ‌گیری
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("codal_robust.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============================================================
#  توابع دیتابیس
# ============================================================
def get_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"❌ خطا در اتصال به PostgreSQL: {e}")
        sys.exit(1)

def init_database():
    logger.info("🔄 ایجاد ساختار دیتابیس...")
    conn = get_connection()
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
            UNIQUE(symbol, report_type, period_date)
        );
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS processed_symbols (
            symbol VARCHAR(20) PRIMARY KEY REFERENCES companies(symbol) ON DELETE CASCADE,
            last_fetched TIMESTAMP DEFAULT NOW(),
            status VARCHAR(20) CHECK (status IN ('success', 'failed', 'processing')),
            retry_count INTEGER DEFAULT 0,
            error_message TEXT
        );
    """)
    
    cur.execute("CREATE INDEX IF NOT EXISTS idx_raw_symbol ON raw_reports (symbol);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_raw_report_type ON raw_reports (report_type);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_raw_period_date ON raw_reports (period_date);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_companies_sector ON companies (sector);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_companies_market ON companies (market_type);")
    
    conn.commit()
    cur.close()
    conn.close()
    logger.info("✅ ساختار دیتابیس ایجاد شد.")

# ============================================================
#  ابزار دریافت با نام‌های مختلف
# ============================================================
def get_method(obj, possible_names):
    """تلاش برای یافتن متد با نام‌های مختلف"""
    for name in possible_names:
        try:
            method = getattr(obj, name)
            if callable(method):
                return method
        except AttributeError:
            continue
    return None

# ============================================================
#  ذخیره اطلاعات شرکت (با تلاش برای نام‌های مختلف)
# ============================================================
def get_company_info(codal, symbol):
    """دریافت اطلاعات شرکت با استفاده از نام‌های مختلف متد"""
    possible_methods = [
        "company_info",
        "get_company_info",
        "company_information",
        "get_company_information",
        "company"
    ]
    method = get_method(codal, possible_methods)
    if method is None:
        logger.warning(f"   ⚠️ متد اطلاعات شرکت برای {symbol} یافت نشد.")
        return None
    try:
        return method(issuer=symbol, from_jdate=START_DATE, to_jdate=END_DATE)
    except Exception as e:
        logger.warning(f"   ⚠️ خطا در دریافت اطلاعات شرکت {symbol}: {e}")
        return None

def get_report(codal, symbol, report_type, possible_methods):
    """دریافت یک گزارش خاص با امتحان نام‌های مختلف"""
    method = get_method(codal, possible_methods)
    if method is None:
        logger.debug(f"   ⚠️ متد {report_type} یافت نشد.")
        return None
    try:
        return method(issuer=symbol, from_jdate=START_DATE, to_jdate=END_DATE)
    except Exception as e:
        logger.debug(f"   ⚠️ خطا در {report_type} برای {symbol}: {e}")
        return None

def save_company_info(symbol: str, company_df: pd.DataFrame) -> bool:
    """ذخیره اطلاعات شرکت (با placeholder در صورت نبود)"""
    conn = get_connection()
    cur = conn.cursor()
    
    if company_df is None or company_df.empty:
        try:
            cur.execute("""
                INSERT INTO companies (symbol, company_name)
                VALUES (%s, %s)
                ON CONFLICT (symbol) DO NOTHING
            """, (symbol, symbol))
            conn.commit()
            cur.close()
            conn.close()
            logger.debug(f"   ✅ رکورد placeholder برای {symbol} ایجاد شد.")
            return True
        except Exception as e:
            logger.error(f"   ❌ خطا در ایجاد placeholder: {e}")
            return False
    
    row = company_df.iloc[0]
    col_map = {
        "نام شرکت": "company_name",
        "کد ISIN": "isin",
        "کد بورس": "stock_code",
        "نوع بازار": "market_type",
        "گروه صنعت": "sector",
        "زیرگروه": "sub_sector",
        "تابلو": "board",
        "تاریخ پذیرش": "first_trade_date",
        "سرمایه ثبتی": "registered_capital",
        "وب‌سایت": "website",
        "تلفن": "phone",
        "آدرس": "address"
    }
    
    data = {}
    for persian_col, db_col in col_map.items():
        if persian_col in row:
            val = row[persian_col]
            if pd.isna(val):
                val = None
            if db_col == "first_trade_date" and val:
                try:
                    parts = str(val).split('/')
                    if len(parts) == 3:
                        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                        val = f"{y-621}-{m:02d}-{d:02d}"
                except:
                    val = None
            elif db_col == "registered_capital" and val:
                try:
                    val = int(str(val).replace(',', '').strip())
                except:
                    val = 0
            data[db_col] = val
    
    if "company_name" not in data or not data["company_name"]:
        data["company_name"] = symbol
    
    try:
        cur.execute("""
            INSERT INTO companies (
                symbol, company_name, isin, stock_code, market_type,
                sector, sub_sector, board, first_trade_date,
                registered_capital, website, phone, address, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (symbol) DO UPDATE SET
                company_name = EXCLUDED.company_name,
                isin = EXCLUDED.isin,
                stock_code = EXCLUDED.stock_code,
                market_type = EXCLUDED.market_type,
                sector = EXCLUDED.sector,
                sub_sector = EXCLUDED.sub_sector,
                board = EXCLUDED.board,
                first_trade_date = EXCLUDED.first_trade_date,
                registered_capital = EXCLUDED.registered_capital,
                website = EXCLUDED.website,
                phone = EXCLUDED.phone,
                address = EXCLUDED.address,
                updated_at = NOW()
        """, (
            symbol,
            data.get("company_name"),
            data.get("isin"),
            data.get("stock_code"),
            data.get("market_type"),
            data.get("sector"),
            data.get("sub_sector"),
            data.get("board"),
            data.get("first_trade_date"),
            data.get("registered_capital", 0),
            data.get("website"),
            data.get("phone"),
            data.get("address")
        ))
        conn.commit()
        logger.info(f"   ✅ اطلاعات شرکت {symbol} ذخیره شد.")
        return True
    except Exception as e:
        logger.error(f"   ❌ خطا در ذخیره اطلاعات شرکت {symbol}: {e}")
        return False
    finally:
        cur.close()
        conn.close()

# ============================================================
#  دریافت گزارش‌ها با امتحان نام‌های مختلف
# ============================================================
def fetch_symbol_reports(symbol: str) -> Dict[str, Any]:
    """دریافت همه گزارش‌ها با امتحان نام‌های مختلف متدها"""
    try:
        try:
            codal = Codal(query="", category="")
        except:
            codal = Codal()
    except Exception as e:
        logger.error(f"   ❌ خطا در ایجاد Codal: {e}")
        return {}
    
    reports = {}
    
    # دیکشنری نگاشت گزارش به لیستی از نام‌های احتمالی متد
    method_names = {
        "income_statement": [
            "income_statement",
            "get_income_statement",
            "income",
            "get_income",
            "profit_loss"
        ],
        "balance_sheet": [
            "balance_sheet",
            "get_balance_sheet",
            "balance",
            "get_balance"
        ],
        "cash_flow": [
            "cash_flow",
            "get_cash_flow",
            "cashflow",
            "cash_flow_statement"
        ],
        "monthly_activity": [
            "monthly_activity",
            "get_monthly_activity",
            "monthly",
            "get_monthly"
        ],
        "shareholders": [
            "shareholders",
            "get_shareholders",
            "shareholder",
            "get_shareholder"
        ],
        "company_info": [
            "company_info",
            "get_company_info",
            "company_information",
            "get_company_information",
            "company"
        ],
        "management_report": [
            "management_report",
            "get_management_report",
            "report",
            "get_management"
        ]
    }
    
    for report_type, possible_names in method_names.items():
        df = get_report(codal, symbol, report_type, possible_names)
        if df is None:
            continue
        if isinstance(df, pd.DataFrame) and df.empty:
            continue
        if not isinstance(df, pd.DataFrame):
            df = pd.DataFrame(df)
        
        period_date = None
        if "period_end_date" in df.columns:
            period_date = df.iloc[-1].get("period_end_date")
        elif "تاریخ" in df.columns:
            period_date = df.iloc[-1].get("تاریخ")
        
        if period_date:
            try:
                parts = str(period_date).split('/')
                if len(parts) == 3:
                    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                    period_date = f"{y-621}-{m:02d}-{d:02d}"
            except:
                period_date = None
        
        reports[report_type] = {
            "data": df.to_json(orient="records", force_ascii=False),
            "period_date": period_date,
            "rows": len(df)
        }
        logger.debug(f"      ✅ {report_type}: {len(df)} ردیف")
        time.sleep(SLEEP_BETWEEN_REQUESTS)
    
    return reports

# ============================================================
#  ذخیره گزارش‌ها
# ============================================================
def save_reports_to_db(symbol: str, reports: Dict[str, Any]) -> int:
    conn = get_connection()
    cur = conn.cursor()
    saved_count = 0
    
    for report_type, report_data in reports.items():
        try:
            cur.execute("""
                INSERT INTO raw_reports (symbol, report_type, period_date, data_json)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (symbol, report_type, period_date) DO NOTHING
            """, (
                symbol,
                report_type,
                report_data.get("period_date"),
                Json(report_data.get("data"))
            ))
            if cur.rowcount > 0:
                saved_count += 1
        except Exception as e:
            logger.error(f"      ❌ خطا در ذخیره {report_type}: {e}")
    
    conn.commit()
    cur.close()
    conn.close()
    return saved_count

# ============================================================
#  مدیریت وضعیت پردازش
# ============================================================
def get_processed_symbols() -> Set[str]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT symbol FROM processed_symbols WHERE status = 'success'")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {row[0] for row in rows}

def update_processed_status(symbol: str, status: str, error_msg: Optional[str] = None):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO processed_symbols (symbol, status, error_message)
            VALUES (%s, %s, %s)
            ON CONFLICT (symbol) DO UPDATE SET
                status = EXCLUDED.status,
                error_message = EXCLUDED.error_message,
                last_fetched = NOW(),
                retry_count = processed_symbols.retry_count + 1
        """, (symbol, status, error_msg))
        conn.commit()
    except Exception as e:
        logger.error(f"   ❌ خطا در به‌روزرسانی وضعیت {symbol}: {e}")
    finally:
        cur.close()
        conn.close()

# ============================================================
#  پردازش یک نماد
# ============================================================
def process_symbol(symbol: str) -> bool:
    logger.info(f"⏳ پردازش {symbol}...")
    
    # مرحله ۱: اطلاعات شرکت
    try:
        try:
            codal = Codal(query="", category="")
        except:
            codal = Codal()
        company_df = get_company_info(codal, symbol)
        save_company_info(symbol, company_df)
    except Exception as e:
        logger.warning(f"   ⚠️ خطا در اطلاعات شرکت {symbol}: {e}")
        save_company_info(symbol, None)
    
    # مرحله ۲: دریافت گزارش‌ها (با استفاده از codal مشابه)
    reports = fetch_symbol_reports(symbol)
    saved_count = 0
    if reports:
        saved_count = save_reports_to_db(symbol, reports)
    
    # مرحله ۳: ثبت وضعیت
    if saved_count > 0:
        update_processed_status(symbol, "success")
        logger.info(f"   ✅ {saved_count} گزارش برای {symbol} ذخیره شد.")
        return True
    else:
        update_processed_status(symbol, "failed", "هیچ داده‌ای دریافت نشد")
        logger.warning(f"   ⚠️ هیچ داده‌ای برای {symbol} دریافت نشد.")
        return False

# ============================================================
#  تابع اصلی
# ============================================================
def main():
    print("="*70)
    print("🚀 برنامه دریافت اطلاعات کدال (نسخه مقاوم)")
    print(f"📋 تعداد نمادهای لیست: {len(SYMBOLS_LIST)}")
    print("="*70)
    logger.info("شروع برنامه (نسخه مقاوم)")
    
    init_database()
    
    # حذف تکراری‌ها و تصادفی‌سازی
    symbols = list(set(SYMBOLS_LIST))
    random.shuffle(symbols)
    
    processed = get_processed_symbols()
    pending = [s for s in symbols if s not in processed]
    
    logger.info(f"📊 کل نمادها: {len(symbols)}")
    logger.info(f"✅ قبلاً پردازش شده: {len(processed)}")
    logger.info(f"⏳ باقی‌مانده: {len(pending)}")
    
    if not pending:
        logger.info("🎉 همه نمادها قبلاً پردازش شده‌اند.")
        return
    
    success_count = 0
    fail_count = 0
    
    for i, symbol in enumerate(pending, 1):
        logger.info(f"\n[{i}/{len(pending)}] شروع پردازش {symbol}")
        
        for attempt in range(MAX_RETRY_PER_SYMBOL):
            if process_symbol(symbol):
                success_count += 1
                break
            else:
                if attempt < MAX_RETRY_PER_SYMBOL - 1:
                    wait_time = 10 * (attempt + 1)
                    logger.info(f"   🔄 تلاش مجدد {attempt+2} بعد از {wait_time} ثانیه...")
                    time.sleep(wait_time)
                else:
                    fail_count += 1
        
        if i < len(pending):
            logger.info(f"   💤 مکث {SLEEP_BETWEEN_SYMBOLS} ثانیه...")
            time.sleep(SLEEP_BETWEEN_SYMBOLS)
    
    logger.info("\n" + "="*70)
    logger.info("🏁 عملیات به پایان رسید.")
    logger.info(f"✅ موفق: {success_count}")
    logger.info(f"❌ ناموفق: {fail_count}")
    logger.info("="*70)
    
    print(f"\n✅ عملیات تکمیل شد. {success_count} نماد با موفقیت پردازش شد.")
    if fail_count > 0:
        print(f"⚠️ {fail_count} نماد با خطا مواجه شدند. برای جزئیات به فایل لاگ مراجعه کنید.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("⏹️ برنامه توسط کاربر متوقف شد.")
        print("\n⏹️ برنامه متوقف شد.")
    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره: {e}")
        print(f"\n❌ خطای غیرمنتظره: {e}")
        sys.exit(1)