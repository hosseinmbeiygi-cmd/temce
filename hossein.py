import requests
import json
import time
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================
# 🔧 تنظیمات اولیه
# ============================================
API_KEY = "Bk7JvdJZBHJ9DMhzeuTfWjwqYy1wMsif"  # 🔑 کلید خود را جایگزین کنید
HISTORY_URL = "https://Api.BrsApi.ir/Tsetmc/History.php"
INPUT_FILE = "all_symbols_data.json"  # فایل حاوی لیست نمادها
OUTPUT_DIR = "history_data"  # پوشه ذخیره تاریخچه هر نماد

# هدرهای شبیه‌سازی مرورگر
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# فیلدهای تاریخچه که استخراج می‌شوند
HISTORY_FIELDS = [
    'date', 'time', 'tno', 'tvol', 'tval',
    'pmin', 'pmax', 'py', 'pf', 'pl',
    'plc', 'plp', 'pc', 'pcc', 'pcp'
]


# ============================================
# 📥 تابع دریافت تاریخچه یک نماد
# ============================================
def fetch_symbol_history(symbol, retries=3, delay=2):
    """
    دریافت تاریخچه قیمت یک نماد از API
    :param symbol: نام نماد (مثل 'شتران')
    :param retries: تعداد تلاش مجدد در صورت خطا
    :param delay: فاصله بین تلاش‌ها (ثانیه)
    :return: لیست دیتای تاریخچه یا None در صورت خطا
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    # تنظیم خودکار retry
    retry_strategy = Retry(
        total=retries,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    params = {
        "key": API_KEY,
        "type": 0,  # 0 = دیتای معاملات و قیمت
        "l18": symbol
    }

    for attempt in range(1, retries + 1):
        try:
            print(f"   📥 دریافت تاریخچه {symbol} (تلاش {attempt}/{retries})...")
            resp = session.get(HISTORY_URL, params=params, timeout=30)
            resp.raise_for_status()

            data = resp.json()

            # بررسی اینکه داده به صورت لیست است
            if isinstance(data, list) and len(data) > 0:
                # فیلتر کردن فیلدهای مورد نظر
                filtered_data = []
                for item in data:
                    filtered_item = {field: item.get(field, 'N/A') for field in HISTORY_FIELDS}
                    filtered_item['symbol'] = symbol  # اضافه کردن نام نماد
                    filtered_data.append(filtered_item)

                print(f"   ✅ تاریخچه {symbol} با {len(filtered_data):,} رکورد دریافت شد.")
                return filtered_data
            else:
                print(f"   ⚠️ نماد {symbol} داده‌ای ندارد یا پاسخ نامعتبر است.")
                return None

        except requests.exceptions.Timeout:
            print(f"   ❌ زمان درخواست برای {symbol} تمام شد.")
        except requests.exceptions.ConnectionError as e:
            print(f"   ❌ خطای اتصال برای {symbol}: {e}")
        except requests.exceptions.HTTPError as e:
            print(f"   ❌ خطای HTTP برای {symbol}: {e}")
            break
        except json.JSONDecodeError:
            print(f"   ❌ پاسخ JSON نامعتبر برای {symbol}")
        except Exception as e:
            print(f"   ❌ خطای ناشناخته برای {symbol}: {e}")

        if attempt < retries:
            print(f"   ⏳ تلاش مجدد در {delay} ثانیه...")
            time.sleep(delay)

    return None


# ============================================
# 💾 تابع ذخیره تاریخچه در فایل
# ============================================
def save_history(symbol, data):
    """ذخیره تاریخچه یک نماد در فایل JSON"""
    if not data:
        return

    # ایجاد پوشه اگر وجود ندارد
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    filename = os.path.join(OUTPUT_DIR, f"{symbol}_history.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"   💾 تاریخچه {symbol} در {filename} ذخیره شد.")


# ============================================
# 📊 تابع اصلی - خواندن لیست و دریافت تاریخچه
# ============================================
def main():
    print("=" * 60)
    print("📊 دریافت تاریخچه تمام نمادها از فایل JSON")
    print("=" * 60)

    # 1️⃣ خواندن لیست نمادها از فایل JSON
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            all_data = json.load(f)
    except FileNotFoundError:
        print(f"❌ فایل '{INPUT_FILE}' پیدا نشد!")
        print("   لطفاً ابتدا کد دریافت لیست نمادها را اجرا کنید.")
        return
    except json.JSONDecodeError:
        print(f"❌ فایل '{INPUT_FILE}' فرمت JSON معتبری ندارد.")
        return

    if not isinstance(all_data, list):
        print("❌ داده‌های فایل به شکل لیست نیستند.")
        return

    # استخراج لیست نمادها (l18)
    symbols = [item.get('l18') for item in all_data if item.get('l18')]
    print(f"✅ تعداد کل نمادهای موجود در فایل: {len(symbols):,}")

    if not symbols:
        print("❌ هیچ نمادی در فایل پیدا نشد.")
        return

    # 2️⃣ دریافت تاریخچه برای هر نماد
    print("\n🔄 شروع دریافت تاریخچه نمادها...")
    print("-" * 60)

    successful = 0
    failed = 0
    failed_symbols = []

    for idx, symbol in enumerate(symbols, start=1):
        print(f"\n[{idx}/{len(symbols)}] 🔍 پردازش نماد: {symbol}")

        history = fetch_symbol_history(symbol)

        if history:
            save_history(symbol, history)
            successful += 1
        else:
            failed += 1
            failed_symbols.append(symbol)

        # تاخیر بین درخواست‌ها برای جلوگیری از مسدود شدن
        if idx < len(symbols):
            time.sleep(1)

    # 3️⃣ گزارش نهایی
    print("\n" + "=" * 60)
    print("📊 گزارش نهایی:")
    print(f"   ✅ دریافت موفق: {successful} نماد")
    print(f"   ❌ دریافت ناموفق: {failed} نماد")
    if failed_symbols:
        print(f"   ⚠️ نمادهای ناموفق: {', '.join(failed_symbols[:10])}")
        if len(failed_symbols) > 10:
            print(f"      ... و {len(failed_symbols) - 10} نماد دیگر")
    print(f"   📁 تاریخچه‌ها در پوشه '{OUTPUT_DIR}' ذخیره شدند.")


# ============================================
# 🚀 اجرای برنامه
# ============================================
if __name__ == "__main__":
    main()