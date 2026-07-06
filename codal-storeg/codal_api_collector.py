#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
برنامه دریافت اطلاعات کامل از کدال از طریق API عمومی
(بدون نیاز به کتابخانه‌ی codalpy)
"""

import psycopg2
from psycopg2.extras import Json
import requests
import json
import time
import logging
import sys
import os
import random
from datetime import datetime
import pandas as pd
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
#  لیست نمادها (می‌توانید اضافه کنید)
# ============================================================
SYMBOLS_LIST = [
    "فولاد", "شپنا", "خودرو", "وبملت", "کگل", "جم", "فملی", "پارس",
    "حکشتی", "غاذر", "کچاد", "فایرا", "دماوند", "سپید", "پترول",
    "شستا", "ملی", "گلگهر", "چادرملو", "کیمیا",
    "آتیه", "دی", "پارس خودرو", "سایپا", "ایران خودرو",
    "شپديس", "فارس", "خگستر", "خساپا",
    "باما", "پکویر", "نیرو", "برکت", "صدرا",
    "خاور", "ذوب", "فولاد مبارکه",
    "معدنی", "صنعتی", "شیمیایی", "پتروشیمی", "پالایش",
    "آسپ", "آریا", "آسیا", "آتی", "آذر",
    "آپ", "آبت", "آبید", "آتک", "آجین",
    "آدر", "آرین", "آسان", "آسمان",
    "آفاق", "آلوم", "آهن",
    "سها", "سهام", "سهند", "سیرنگ", "سیمان",
    "وبصادر", "وتجارت", "وبانک", "وبشهر",
    "وملی", "وسینا", "وپاسار", "وپارس", "وپترو",
    "خدیزل", "خپارس", "خزر",
    "شتران", "شبندر", "شبصیر", "شراز",
    "شپاس", "شسپا", "شگستر", "شمواد",
    "فسنگ", "فخاس",
    "سپاس", "سفارس",
    "دپارس", "دتولید", "دارو", "دشیمی",
    "غشاذر", "غپینو", "غدام", "غصینو"
]

# ============================================================
#  تنظیمات لاگ‌گیری
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("codal_api.log", encoding="utf-8"),
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
#  توابع دریافت از API کدال
# ============================================================
def fetch_report_from_api(symbol: str, report_type: str) -> Optional[pd.DataFrame]:
    """
    دریافت یک گزارش خاص از API کدال
    report_type: income_statement, balance_sheet, cash_flow, monthly_activity, shareholders, management_report
    """
    # API غیررسمی کدال
    url = f"https://codal.ir/api/FinancialReport/GetFinancialReport"
    
    params = {
        "symbol": symbol,
        "reportType": report_type,
        # برخی API‌ها ممکن است به سال نیاز داشته باشند، اما ما از همه دوره‌ها استفاده می‌کنیم
        "fromDate": START_DATE.replace('/', '-'),
        "toDate": END_DATE.replace('/', '-')
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, list) and len(data) > 0:
                df = pd.DataFrame(data)
                return df
            else:
                logger.debug(f"   ⚠️ داده‌ای برای {report_type} یافت نشد.")
                return None
        else:
            logger.debug(f"   ⚠️ خطا در API: {response.status_code}")
            return None
    except Exception as e:
        logger.debug(f"   ⚠️ خطا در {report_type}: {str(e)[:50]}")
        return None

def save_company_info(symbol: str) -> bool:
    """اطلاعات شرکت را از API دریافت و ذخیره می‌کند (در صورت وجود)"""
    # در این نسخه، فقط placeholder ذخیره می‌کنیم
    # می‌توانیم از API شرکت‌ها نیز استفاده کنیم اما فعلاً ساده می‌گیریم
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO companies (symbol, company_name)
            VALUES (%s, %s)
            ON CONFLICT (symbol) DO NOTHING
        """, (symbol, symbol))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"   ❌ خطا در ایجاد placeholder: {e}")
        return False

# ============================================================
#  دریافت همه‌ی گزارش‌ها برای یک نماد
# ============================================================
def fetch_all_reports(symbol: str) -> Dict[str, Any]:
    """دریافت همه‌ی گزارش‌های موجود برای یک نماد با استفاده از API"""
    reports = {}
    
    # لیست انواع گزارش‌هایی که می‌خواهیم دریافت کنیم
    report_types = [
        "income_statement",
        "balance_sheet",
        "cash_flow",
        "monthly_activity",
        "shareholders",
        "management_report"
    ]
    
    for report_type in report_types:
        time.sleep(SLEEP_BETWEEN_REQUESTS)
        df = fetch_report_from_api(symbol, report_type)
        if df is not None and not df.empty:
            # استخراج تاریخ (اگر موجود باشد)
            period_date = None
            if "period_end_date" in df.columns:
                period_date = df.iloc[-1].get("period_end_date")
            elif "تاریخ" in df.columns:
                period_date = df.iloc[-1].get("تاریخ")
            
            # تبدیل تاریخ به میلادی
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
            logger.debug(f"   ✅ {report_type}: {len(df)} ردیف")
    
    return reports

# ============================================================
#  ذخیره گزارش‌ها در دیتابیس
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
    
    # اطلاعات شرکت (placeholder)
    save_company_info(symbol)
    
    # دریافت گزارش‌ها
    reports = fetch_all_reports(symbol)
    saved_count = 0
    if reports:
        saved_count = save_reports_to_db(symbol, reports)
    
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
    print("🚀 برنامه دریافت اطلاعات کدال از طریق API عمومی")
    print("📋 شامل همه‌ی گزارش‌های مالی")
    print("="*70)
    logger.info("شروع برنامه (API عمومی)")
    
    init_database()
    
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