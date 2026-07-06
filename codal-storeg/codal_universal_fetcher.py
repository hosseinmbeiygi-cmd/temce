#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
برنامه جامع دریافت اطلاعات از سایت کدال (codal.ir)
با استفاده از تمام کتابخانه‌های موجود و روش‌های جایگزین
"""

import sys
import time
import logging
import pandas as pd
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# ============================================================
#  تنظیمات اولیه
# ============================================================
SYMBOL = "فولاد"           # نماد مورد نظر (قابل تغییر)
FROM_DATE = "1400/01/01"   # تاریخ شروع (شمسی)
TO_DATE = "1404/12/29"     # تاریخ پایان (شمسی)
REQUEST_TIMEOUT = 15       # زمان انتظار برای هر درخواست (ثانیه)
SLEEP_BETWEEN = 1          # تأخیر بین درخواست‌ها (ثانیه)

# ============================================================
#  تنظیمات لاگ‌گیری
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"codal_fetch_{SYMBOL}.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============================================================
#  روش ۱: دریافت با کتابخانه codalpy
# ============================================================
def fetch_with_codalpy(symbol, from_date, to_date):
    """دریافت داده با استفاده از کتابخانه codalpy"""
    try:
        from codalpy import Codal
        logger.info("📥 روش ۱: تلاش با 'codalpy'...")
        codal = Codal(issuer=symbol, from_jdate=from_date, to_jdate=to_date)
        
        # دریافت صورت سود و زیان
        data = codal.income_statement()
        if data is not None and not data.empty:
            logger.info(f"✅ 'codalpy' موفق شد. تعداد ردیف‌ها: {len(data)}")
            return data
        else:
            logger.warning("⚠️ 'codalpy' داده‌ای بازنگرداند.")
            return None
    except ImportError:
        logger.warning("❌ کتابخانه 'codalpy' نصب نیست. برای نصب: pip install codalpy")
    except Exception as e:
        logger.warning(f"⚠️ خطا در 'codalpy': {e}")
    return None

# ============================================================
#  روش ۲: دریافت با کتابخانه codal-tsetmc
# ============================================================
def fetch_with_codal_tsetmc(symbol, from_date, to_date):
    """دریافت داده با استفاده از کتابخانه codal-tsetmc"""
    try:
        from codal_tsetmc import CodalTsetmc
        logger.info("📥 روش ۲: تلاش با 'codal-tsetmc'...")
        client = CodalTsetmc()
        # این کتابخانه معمولاً برای جستجو استفاده می‌شود، اما می‌توان از آن برای دریافت داده نیز استفاده کرد
        data = client.search(symbol)  # ممکن است نیاز به تنظیم پارامترهای بیشتر داشته باشد
        if data is not None and not data.empty:
            logger.info(f"✅ 'codal-tsetmc' موفق شد. تعداد ردیف‌ها: {len(data)}")
            return data
        else:
            logger.warning("⚠️ 'codal-tsetmc' داده‌ای بازنگرداند.")
            return None
    except ImportError:
        logger.warning("❌ کتابخانه 'codal-tsetmc' نصب نیست. برای نصب: pip install codal-tsetmc")
    except Exception as e:
        logger.warning(f"⚠️ خطا در 'codal-tsetmc': {e}")
    return None

# ============================================================
#  روش ۳: دریافت با کتابخانه pytse-client
# ============================================================
def fetch_with_pytse_client(symbol, from_date, to_date):
    """دریافت داده با استفاده از کتابخانه pytse-client"""
    try:
        import pytse_client as tse
        logger.info("📥 روش ۳: تلاش با 'pytse-client'...")
        tickers = tse.download(symbols=symbol, write_to_csv=False)
        if symbol in tickers:
            data = tickers[symbol]
            if data is not None and not data.empty:
                logger.info(f"✅ 'pytse-client' موفق شد. تعداد ردیف‌ها: {len(data)}")
                return data
        logger.warning("⚠️ 'pytse-client' داده‌ای بازنگرداند.")
        return None
    except ImportError:
        logger.warning("❌ کتابخانه 'pytse-client' نصب نیست. برای نصب: pip install pytse-client")
    except Exception as e:
        logger.warning(f"⚠️ خطا در 'pytse-client': {e}")
    return None

# ============================================================
#  روش ۴: دریافت با API مستقیم کدال
# ============================================================
def fetch_with_direct_api(symbol, from_date, to_date):
    """دریافت داده با ارسال درخواست مستقیم به API کدال"""
    try:
        logger.info("📥 روش ۴: تلاش با 'API مستقیم'...")
        url = "https://search.codal.ir/api/search/v2/q"
        params = {
            "Audited": "true",
            "Category": "1",
            "Main": "true",
            "Symbol": symbol,
            "FromDate": from_date.replace('/', '-'),
            "ToDate": to_date.replace('/', '-')
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            if data and 'results' in data and len(data['results']) > 0:
                df = pd.DataFrame(data['results'])
                logger.info(f"✅ 'API مستقیم' موفق شد. تعداد ردیف‌ها: {len(df)}")
                return df
            else:
                logger.warning("⚠️ 'API مستقیم' داده‌ای بازنگرداند.")
        else:
            logger.warning(f"⚠️ 'API مستقیم' وضعیت: {response.status_code}")
        return None
    except Exception as e:
        logger.warning(f"⚠️ خطا در 'API مستقیم': {e}")
    return None

# ============================================================
#  روش ۵: دریافت با اسکرپینگ (BeautifulSoup)
# ============================================================
def fetch_with_scraping(symbol, from_date, to_date):
    """دریافت داده با استفاده از BeautifulSoup (اسکرپینگ)"""
    try:
        logger.info("📥 روش ۵: تلاش با 'اسکرپینگ (BeautifulSoup)'...")
        url = "https://www.codal.ir/"
        params = {"q": symbol}
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # پیدا کردن لینک‌های گزارش‌ها
            links = soup.find_all('a', href=True)
            report_links = [link['href'] for link in links if 'Report' in link.get('href', '')]
            if report_links:
                logger.info(f"✅ 'اسکرپینگ' موفق شد. تعداد لینک‌ها: {len(report_links)}")
                # می‌توانید ادامه دهید و هر لینک را پردازش کنید
                return pd.DataFrame({"links": report_links})
            else:
                logger.warning("⚠️ 'اسکرپینگ' هیچ لینکی پیدا نکرد.")
        else:
            logger.warning(f"⚠️ 'اسکرپینگ' وضعیت: {response.status_code}")
        return None
    except ImportError:
        logger.warning("❌ کتابخانه 'BeautifulSoup' نصب نیست. برای نصب: pip install beautifulsoup4")
    except Exception as e:
        logger.warning(f"⚠️ خطا در 'اسکرپینگ': {e}")
    return None

# ============================================================
#  روش ۶: دریافت با Selenium (برای محتوای داینامیک)
# ============================================================
def fetch_with_selenium(symbol, from_date, to_date):
    """دریافت داده با استفاده از Selenium (برای محتوای جاوااسکریپتی)"""
    try:
        logger.info("📥 روش ۶: تلاش با 'Selenium'...")
        options = Options()
        options.add_argument('--headless')  # اجرا بدون نمایش مرورگر
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        driver = webdriver.Chrome(options=options)
        
        url = f"https://www.codal.ir/?q={symbol}"
        driver.get(url)
        time.sleep(3)  # منتظر بارگذاری محتوای داینامیک
        
        # استخراج داده‌ها از صفحه
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        # پیدا کردن داده‌های مورد نظر (مثلاً جدول گزارش‌ها)
        tables = soup.find_all('table')
        if tables:
            logger.info(f"✅ 'Selenium' موفق شد. تعداد جداول: {len(tables)}")
            # می‌توانید جداول را به دیتافریم تبدیل کنید
            return pd.read_html(str(tables[0]))[0] if tables else None
        else:
            logger.warning("⚠️ 'Selenium' جدولی پیدا نکرد.")
        driver.quit()
        return None
    except ImportError:
        logger.warning("❌ کتابخانه 'selenium' نصب نیست. برای نصب: pip install selenium")
    except Exception as e:
        logger.warning(f"⚠️ خطا در 'Selenium': {e}")
    return None

# ============================================================
#  تابع اصلی: تلاش همه روش‌ها به ترتیب
# ============================================================
def main():
    print("="*70)
    print(f"🚀 برنامه جامع دریافت اطلاعات کدال برای نماد: {SYMBOL}")
    print("📋 استفاده از ۶ روش مختلف (به ترتیب اولویت)")
    print("="*70)
    logger.info(f"شروع دریافت اطلاعات برای {SYMBOL}")
    
    # لیست روش‌ها (به ترتیب اولویت)
    methods = [
        fetch_with_codalpy,
        fetch_with_codal_tsetmc,
        fetch_with_pytse_client,
        fetch_with_direct_api,
        fetch_with_scraping,
        fetch_with_selenium
    ]
    
    final_data = None
    for method in methods:
        try:
            data = method(SYMBOL, FROM_DATE, TO_DATE)
            if data is not None and not data.empty:
                final_data = data
                logger.info(f"✅ موفقیت با روش: {method.__name__}")
                break
        except Exception as e:
            logger.warning(f"⚠️ روش {method.__name__} با خطا مواجه شد: {e}")
        time.sleep(SLEEP_BETWEEN)
    
    # نمایش نتیجه نهایی
    if final_data is not None and not final_data.empty:
        print("\n" + "="*70)
        print("📊 خلاصه داده‌های دریافت‌شده:")
        print("="*70)
        print(f"✅ تعداد ردیف‌ها: {len(final_data)}")
        print(f"📋 ستون‌ها: {list(final_data.columns)}")
        print("\n📄 پیش‌نمایش داده‌ها (۵ ردیف اول):")
        print(final_data.head())
        print("\n" + "="*70)
        print(f"🏁 داده‌های {SYMBOL} با موفقیت دریافت شد.")
        # می‌توانید داده‌ها را در فایل CSV ذخیره کنید
        # final_data.to_csv(f"{SYMBOL}_data.csv", index=False, encoding='utf-8-sig')
        # logger.info(f"داده‌ها در فایل {SYMBOL}_data.csv ذخیره شد.")
    else:
        print("\n❌ هیچ داده‌ای دریافت نشد.")
        print("   لطفاً اتصال اینترنت، VPN و تنظیمات را بررسی کنید.")
        logger.error("❌ همه روش‌ها ناموفق بودند.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️ برنامه توسط کاربر متوقف شد.")
    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره: {e}")
        print(f"\n❌ خطای غیرمنتظره: {e}")
        sys.exit(1)