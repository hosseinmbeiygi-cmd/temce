#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
برنامه کامل دریافت اطلاعات کدال برای تمام نمادها
نسخه نهایی ۵.۰ - بدون وابستگی به TSETMC
"""

import psycopg2
from psycopg2.extras import Json
import requests
import json
import time
import logging
import sys
import os
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

# ============================================================
#  تنظیمات
# ============================================================
START_DATE = "1395/01/01"
END_DATE = "1405/12/29"
REQUEST_TIMEOUT = 10
SLEEP_BETWEEN_REQUESTS = 1
SLEEP_BETWEEN_SYMBOLS = 2
MAX_RETRY_PER_SYMBOL = 2

# ============================================================
#  لیست کامل نمادها (بدون نیاز به TSETMC)
# ============================================================
SYMBOLS_LIST = [
    "فولاد", "شپنا", "خودرو", "وبملت", "کگل", "جم", "فملی", "پارس",
    "حکشتی", "غاذر", "کچاد", "فایرا", "دماوند", "سپید", "پترول",
    "شستا", "ملی", "گلگهر", "چادرملو", "کیمیا",
    "آتیه", "دی", "پارس خودرو", "سایپا", "ایران خودرو",
    "شپديس", "فارس", "خگستر", "خساپا",
    "باما", "پکویر", "نیرو", "برکت", "صدرا",
    "خاور", "ذوب", "معدنی", "صنعتی", "شیمیایی",
    "پتروشیمی", "پالایش", "آسپ", "آریا", "آسیا",
    "آتی", "آذر", "آپ", "آبت", "آبید",
    "آتک", "آجین", "آدر", "آرین", "آسان",
    "آسمان", "آفاق", "آلوم", "آهن",
    "سها", "سهام", "سهند", "سیرنگ", "سیمان",
    "وبصادر", "وتجارت", "وبانک", "وبشهر",
    "وملی", "وسینا", "وپاسار", "وپارس", "وپترو"
]

# ============================================================
#  تنظیمات لاگ‌گیری
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("codal_complete.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============================================================
#  توابع دیتابیس
# ============================================================
def get_connection():
    try:
        return psycopg2.connect(**DB_CONFIG)
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
#  دریافت لیست نمادها (فقط از لیست داخلی)
# ============================================================
def get_all_symbols() -> List[str]:
    logger.info(f"📋 استفاده از لیست داخلی با {len(SYMBOLS_LIST)} نماد")
    return SYMBOLS_LIST.copy()

# ============================================================
#  ۱. ذخیره اطلاعات شرکت (بدون وابستگی به TSETMC)
# ============================================================
def save_company(symbol: str):
    """ذخیره اطلاعات شرکت در دیتابیس (فقط placeholder)"""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # ابتدا سعی می‌کنیم با codalpy اطلاعات کامل بگیریم (اگر متد موجود باشد)
        company_name = symbol
        try:
            from codalpy import Codal
            codal = Codal(query="", category="")
            if hasattr(codal, "company_info"):
                df = codal.company_info(issuer=symbol, from_jdate=START_DATE, to_jdate=END_DATE)
                if df is not None and not df.empty:
                    row = df.iloc[0]
                    company_name = row.get("نام شرکت", symbol)
        except:
            pass
        
        # ذخیره placeholder
        cur.execute("""
            INSERT INTO companies (symbol, company_name)
            VALUES (%s, %s)
            ON CONFLICT (symbol) DO UPDATE SET
                company_name = EXCLUDED.company_name,
                updated_at = NOW()
        """, (symbol, company_name))
        conn.commit()
        logger.debug(f"   ✅ اطلاعات شرکت {symbol} ذخیره شد.")
        return True
    except Exception as e:
        logger.warning(f"   ⚠️ خطا در ذخیره اطلاعات شرکت: {e}")
        return False
    finally:
        cur.close()
        conn.close()

# ============================================================
#  ۲. دریافت گزارش‌ها با codalpy
# ============================================================
def fetch_with_codalpy(symbol: str) -> Dict[str, Any]:
    reports = {}
    try:
        from codalpy import Codal
        codal = Codal(query="", category="")
        
        available_methods = [m for m in dir(codal) if not m.startswith('_') and callable(getattr(codal, m))]
        
        method_map = {
            "income_statement": ["income_statement", "income"],
            "balance_sheet": ["balance_sheet", "balance"],
            "cash_flow": ["cash_flow", "cashflow"],
            "monthly_activity": ["monthly_activity", "monthly"],
            "shareholders": ["shareholders", "shareholder"],
            "management_report": ["management_report", "management"]
        }
        
        for report_type, possible_names in method_map.items():
            found_method = None
            for name in possible_names:
                if name in available_methods:
                    found_method = name
                    break
            
            if found_method is None:
                continue
            
            try:
                method = getattr(codal, found_method)
                time.sleep(SLEEP_BETWEEN_REQUESTS)
                df = method(issuer=symbol, from_jdate=START_DATE, to_jdate=END_DATE)
                
                if df is not None and not (isinstance(df, pd.DataFrame) and df.empty):
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
                    logger.debug(f"      ✅ {report_type}: {len(df)} ردیف (codalpy)")
            except Exception as e:
                logger.debug(f"      ⚠️ {report_type} با codalpy: {str(e)[:30]}")
    
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"   ⚠️ خطا در codalpy: {str(e)[:30]}")
    
    return reports

# ============================================================
#  ۳. دریافت گزارش‌ها با API مستقیم
# ============================================================
def fetch_with_api(symbol: str) -> Dict[str, Any]:
    reports = {}
    
    report_types = [
        "income_statement",
        "balance_sheet",
        "cash_flow",
        "monthly_activity",
        "shareholders",
        "management_report"
    ]
    
    url = "https://codal.ir/api/FinancialReport/GetFinancialReport"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    for report_type in report_types:
        params = {
            "symbol": symbol,
            "reportType": report_type,
            "fromDate": START_DATE.replace('/', '-'),
            "toDate": END_DATE.replace('/', '-')
        }
        
        try:
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            response = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    df = pd.DataFrame(data)
                    
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
                    logger.debug(f"      ✅ {report_type}: {len(df)} ردیف (API)")
            else:
                logger.debug(f"      ⚠️ {report_type}: وضعیت {response.status_code}")
                
        except requests.Timeout:
            logger.debug(f"      ⚠️ {report_type}: Timeout")
        except Exception as e:
            logger.debug(f"      ⚠️ {report_type}: {str(e)[:30]}")
    
    return reports

# ============================================================
#  ۴. دریافت تمام گزارش‌ها (ترکیبی)
# ============================================================
def fetch_all_reports(symbol: str) -> Dict[str, Any]:
    all_reports = {}
    
    reports1 = fetch_with_codalpy(symbol)
    all_reports.update(reports1)
    
    reports2 = fetch_with_api(symbol)
    for key, value in reports2.items():
        if key not in all_reports:
            all_reports[key] = value
    
    return all_reports

# ============================================================
#  ۵. ذخیره گزارش‌ها
# ============================================================
def save_reports(symbol: str, reports: Dict[str, Any]) -> int:
    if not reports:
        return 0
    
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
#  ۶. مدیریت وضعیت پردازش
# ============================================================
def get_processed_symbols() -> Set[str]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT symbol FROM processed_symbols WHERE status = 'success'")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {row[0] for row in rows}

def update_status(symbol: str, status: str, error_msg: Optional[str] = None):
    conn = get_connection()
    cur = conn.cursor()
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
    cur.close()
    conn.close()

# ============================================================
#  ۷. پردازش یک نماد
# ============================================================
def process_symbol(symbol: str) -> bool:
    logger.info(f"⏳ پردازش {symbol}...")
    
    try:
        # مرحله ۱: اطلاعات شرکت (placeholder)
        save_company(symbol)
        
        # مرحله ۲: دریافت تمام گزارش‌ها
        reports = fetch_all_reports(symbol)
        
        # مرحله ۳: ذخیره در دیتابیس
        saved = 0
        if reports:
            saved = save_reports(symbol, reports)
        
        # مرحله ۴: ثبت وضعیت
        if saved > 0:
            update_status(symbol, "success")
            logger.info(f"   ✅ {saved} گزارش ذخیره شد.")
            return True
        else:
            update_status(symbol, "failed", "هیچ داده‌ای دریافت نشد")
            logger.warning(f"   ⚠️ هیچ داده‌ای دریافت نشد.")
            return False
            
    except Exception as e:
        error_msg = str(e)[:200]
        logger.error(f"   ❌ خطا: {error_msg}")
        update_status(symbol, "failed", error_msg)
        return False

# ============================================================
#  ۸. اجرای اصلی
# ============================================================
def main():
    print("="*70)
    print("🚀 برنامه کامل دریافت اطلاعات کدال (بدون وابستگی به TSETMC)")
    print("📋 تعداد نمادها: " + str(len(SYMBOLS_LIST)))
    print("="*70)
    logger.info("شروع برنامه (نسخه بدون TSETMC)")
    
    init_database()
    
    all_symbols = get_all_symbols()
    if not all_symbols:
        logger.error("❌ هیچ نمادی یافت نشد.")
        return
    
    processed = get_processed_symbols()
    pending = [s for s in all_symbols if s not in processed]
    
    logger.info(f"📊 کل نمادها: {len(all_symbols)}")
    logger.info(f"✅ قبلاً پردازش‌شده: {len(processed)}")
    logger.info(f"⏳ باقی‌مانده: {len(pending)}")
    
    if not pending:
        logger.info("🎉 همه نمادها پردازش شده‌اند.")
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
        print(f"⚠️ {fail_count} نماد با خطا مواجه شدند.")

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