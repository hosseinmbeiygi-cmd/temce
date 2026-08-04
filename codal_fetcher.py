import json
import os
import time
from datetime import datetime

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

# کلید API
API_KEY = os.environ.get("BRSAPI_API_KEY", "")
BASE_URL = "https://Api.BrsApi.ir/Codal/Announcement.php"

# پوشه خروجی
OUTPUT_DIR = "codal_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

FINAL_OUTPUT_FILE = os.path.join(OUTPUT_DIR, "all_codal_data.json")
PROGRESS_FILE = os.path.join(OUTPUT_DIR, "progress.json")
ERROR_LOG_FILE = os.path.join(OUTPUT_DIR, "errors.json")

def load_symbols_from_file(file_path="symbols.txt"):
    if not os.path.exists(file_path):
        print(f"❌ فایل {file_path} یافت نشد!")
        return []
    with open(file_path, encoding="utf-8") as f:
        symbols = [line.strip() for line in f if line.strip()]
    print(f"✅ {len(symbols)} نماد از فایل {file_path} بارگیری شد.")
    return symbols

def load_existing_data():
    if os.path.exists(FINAL_OUTPUT_FILE):
        try:
            with open(FINAL_OUTPUT_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception as e:
            print(f"⚠️ خطا در خواندن فایل قبلی: {e}")
    return []

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, encoding="utf-8") as f:
                progress = json.load(f)
            return progress.get("processed_symbols", [])
        except Exception as e:
            print(f"⚠️ خطا در خواندن فایل پیشرفت: {e}")
    return []

def save_progress(processed_symbols):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump({"processed_symbols": processed_symbols}, f, ensure_ascii=False, indent=2)

def save_all_data(all_data):
    with open(FINAL_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

def log_error(symbol, error_message):
    errors = []
    if os.path.exists(ERROR_LOG_FILE):
        try:
            with open(ERROR_LOG_FILE, encoding="utf-8") as f:
                errors = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    errors.append({
        "symbol": symbol,
        "error": error_message,
        "timestamp": datetime.now().isoformat()
    })
    with open(ERROR_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(errors, f, ensure_ascii=False, indent=2)

def create_session():
    """ایجاد نشست با تنظیمات Retry و Timeout"""
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=3,  # 3, 6, 12, 24, 48 ثانیه
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    return session

def fetch_announcements(symbol, page=1, max_retries=5):
    """
    دریافت اطلاعیه‌های یک نماد با تلاش مجدد و backoff
    """
    params = {
        "key": API_KEY,
        "l18": symbol,
        "audited": "false",      # ابتدا بدون audited برای کاهش بار
        "unaudited": "false",
        "only_main_company": "false",
        "only_subsidiaries": "false",
        "page": page
    }

    session = create_session()
    last_error = None

    for attempt in range(max_retries):
        try:
            response = session.get(BASE_URL, params=params, timeout=(10, 60))  # 10s اتصال، 60s خواندن
            if response.status_code == 200:
                data = response.json()
                if "count_announcement" in data:
                    return data
                else:
                    print(f"⚠️ پاسخ غیرمنتظره برای {symbol} (صفحه {page})")
                    return None
            elif response.status_code == 429:  # Too Many Requests
                wait = 30 * (attempt + 1)
                print(f"⏳ محدودیت درخواست، {wait} ثانیه صبر...")
                time.sleep(wait)
            else:
                print(f"❌ خطا در دریافت {symbol} (صفحه {page}): کد {response.status_code}")
                time.sleep(3 * (attempt + 1))
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.SSLError) as e:
            last_error = e
            wait = 5 * (2 ** attempt)  # 5, 10, 20, 40, 80 ثانیه
            print(f"❗ خطای اتصال برای {symbol} (تلاش {attempt+1}/{max_retries}): {e}")
            print(f"⏳ صبر {wait} ثانیه و تلاش مجدد...")
            time.sleep(wait)
        except Exception as e:
            last_error = e
            print(f"❗ خطای غیرمنتظره: {e}")
            time.sleep(5 * (attempt + 1))

    # اگر همه تلاش‌ها ناموفق بود
    print(f"❌ دریافت اطلاعات برای {symbol} پس از {max_retries} تلاش ناموفق بود.")
    log_error(symbol, f"Failed after {max_retries} attempts: {last_error}")
    return None

def fetch_all_pages(symbol):
    """تمام صفحات یک نماد را دریافت و ترکیب می‌کند"""
    all_data = []
    page = 1
    total_pages = None
    total_announcements = None

    while True:
        print(f"در حال دریافت {symbol} - صفحه {page} ...")
        result = fetch_announcements(symbol, page)
        if result is None:
            if page == 1:
                return None, 0, 0
            else:
                break

        if page == 1:
            total_pages = result.get("count_page", 0)
            total_announcements = result.get("count_announcement", 0)
            if total_announcements == 0:
                print(f"ℹ️ {symbol}: هیچ اطلاعیه‌ای وجود ندارد.")
                return [], 0, 0

        # پیدا کردن کلید اطلاعیه‌ها
        announcements = None
        for key in ["announcements", "data", "items", "list", "results"]:
            if key in result and isinstance(result[key], list):
                announcements = result[key]
                break

        if announcements is None:
            announcements = []

        if announcements:
            all_data.extend(announcements)

        # شرط پایان
        if total_pages is not None and page >= total_pages:
            break
        if not announcements:
            break

        page += 1
        time.sleep(2)  # تاخیر بیشتر بین صفحات

    return all_data, total_announcements, total_pages

def main():
    # بارگیری لیست نمادها
    all_symbols = load_symbols_from_file("symbols.txt")
    if not all_symbols:
        print("❌ هیچ نمادی برای پردازش وجود ندارد.")
        return

    # بارگیری داده‌های قبلی و وضعیت
    existing_data = load_existing_data()
    processed_symbols = load_progress()
    existing_symbols = [item["symbol"] for item in existing_data if "symbol" in item]
    all_processed = set(processed_symbols + existing_symbols)

    remaining_symbols = [s for s in all_symbols if s not in all_processed]

    if not remaining_symbols:
        print("✅ همه نمادها قبلاً پردازش شده‌اند.")
        return

    print(f"\n🔄 تعداد نمادهای باقیمانده: {len(remaining_symbols)} از {len(all_symbols)}")
    print(f"📌 از نماد '{remaining_symbols[0]}' شروع می‌شود...")

    total_remaining = len(remaining_symbols)
    for idx, symbol in enumerate(remaining_symbols, 1):
        print(f"\n--- ({idx}/{total_remaining}) پردازش نماد: {symbol} ---")

        try:
            announcements, total_count, total_pages = fetch_all_pages(symbol)

            if announcements is not None:
                record = {
                    "symbol": symbol,
                    "total_announcements": total_count if total_count is not None else 0,
                    "total_pages": total_pages if total_pages is not None else 0,
                    "fetched_count": len(announcements),
                    "fetched_at": datetime.now().isoformat(),
                    "announcements": announcements
                }
                existing_data.append(record)
                save_all_data(existing_data)
                print(f"✅ داده‌های {symbol} ذخیره شد (تعداد {len(announcements)} اطلاعیه).")
            else:
                error_msg = "دریافت اطلاعات ناموفق (همه تلاش‌ها ناموفق)"
                print(f"❌ {error_msg}")
                log_error(symbol, error_msg)
                # ثبت به عنوان پردازش‌شده با خطا (برای جلوگیری از تکرار)
                record = {
                    "symbol": symbol,
                    "total_announcements": 0,
                    "total_pages": 0,
                    "fetched_count": 0,
                    "fetched_at": datetime.now().isoformat(),
                    "announcements": [],
                    "error": error_msg
                }
                existing_data.append(record)
                save_all_data(existing_data)

            # به‌روزرسانی پردازش‌شده
            all_processed.add(symbol)
            save_progress(list(all_processed))

        except KeyboardInterrupt:
            print("\n⚠️ برنامه توسط کاربر متوقف شد. پیشرفت ذخیره شد.")
            return
        except Exception as e:
            error_msg = f"خطای غیرمنتظره: {str(e)}"
            print(f"❗ {error_msg}")
            log_error(symbol, error_msg)
            record = {
                "symbol": symbol,
                "total_announcements": 0,
                "total_pages": 0,
                "fetched_count": 0,
                "fetched_at": datetime.now().isoformat(),
                "announcements": [],
                "error": error_msg
            }
            existing_data.append(record)
            save_all_data(existing_data)
            all_processed.add(symbol)
            save_progress(list(all_processed))

        # تاخیر بین نمادها
        time.sleep(3)

    print("\n" + "="*50)
    print("✅ پردازش تمام نمادها به پایان رسید.")
    print(f"📁 فایل نهایی: {FINAL_OUTPUT_FILE}")
    print(f"📋 تعداد کل نمادهای پردازش‌شده: {len(existing_data)}")

    if os.path.exists(ERROR_LOG_FILE):
        with open(ERROR_LOG_FILE, encoding="utf-8") as f:
            errors = json.load(f)
        if errors:
            print(f"⚠️ تعداد خطاها: {len(errors)} (مشاهده در {ERROR_LOG_FILE})")
        else:
            print("✅ هیچ خطایی ثبت نشده است.")

if __name__ == "__main__":
    main()
