import json
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# تنظیمات
# ============================================================
API_KEY = os.environ.get("BRSAPI_API_KEY", "")
BASE_URL = "https://Api.BrsApi.ir/Codal/Announcement.php"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

OUTPUT_DIR = "codal_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# 📋 دریافت لیست نمادها (مشابه fetch_crypto_symbols)
# ============================================================
def fetch_symbols():
    """
    دریافت لیست نمادهای مورد نظر
    در اینجا می‌توانید لیست نمادهای خود را وارد کنید
    """
    # 🔹 لیست نمادهای پیش‌فرض (می‌توانید تغییر دهید)
    symbols = [
        "موج",
        "اهرم",
        # "وبملت",
        # "فولاد",
        # "خودرو",
        # "شستا",
        # "فارس",
    ]

    print("📡 دریافت لیست نمادها...")
    print(f"✅ {len(symbols)} نماد دریافت شد.")
    return sorted(symbols)

# ============================================================
# 🔍 دریافت اطلاعیه‌های یک نماد (مشابه fetch_history)
# ============================================================
def fetch_announcements(symbol, date_start=None, date_end=None, page=1):
    """
    دریافت اطلاعیه‌های یک نماد در یک صفحه مشخص
    مشابه fetch_history در برنامه رمزارزها
    """
    params = {
        "key": API_KEY,
        "l18": symbol,
        "page": page
    }

    if date_start:
        params["date_start"] = date_start
    if date_end:
        params["date_end"] = date_end

    # پارامترهای پیش‌فرض (همه موارد)
    params["audited"] = "true"
    params["unaudited"] = "true"
    params["only_main_company"] = "true"
    params["only_subsidiaries"] = "true"

    try:
        response = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=180)
        if response.status_code == 200:
            data = response.json()
            # ساختار پاسخ کدال شامل "result" و "count_page" است
            return data
        else:
            return None
    except Exception as e:
        print(f"   ❌ خطا: {e}")
        return None

def fetch_all_announcements(symbol, date_start=None, date_end=None):
    """
    دریافت تمام اطلاعیه‌های یک نماد (همه صفحات)
    مشابه fetch_history در برنامه رمزارزها که کل تاریخچه را دریافت می‌کند
    """
    all_announcements = []
    page = 1
    total_pages = None

    while True:
        data = fetch_announcements(symbol, date_start, date_end, page)
        if not data:
            break

        # استخراج تعداد کل صفحات
        if total_pages is None:
            total_pages = data.get("count_page", 1)

        announcements = data.get("result", [])
        if not announcements:
            break

        all_announcements.extend(announcements)

        # اگر به آخرین صفحه رسیدیم
        if page >= total_pages:
            break

        page += 1
        time.sleep(0.5)  # تاخیر بین صفحات

    return all_announcements

# ============================================================
# 💾 ذخیره‌سازی (مشابه save_history)
# ============================================================
def save_announcements(symbol, records):
    if not records:
        return False
    filename = os.path.join(OUTPUT_DIR, f"{symbol}_codal.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"   💾 ذخیره شد: {filename} ({len(records)} اطلاعیه)")
    return True

# ============================================================
# 🧪 تست یک نماد خاص (مشابه test_crypto)
# ============================================================
def test_symbol(symbol):
    print(f"\n🧪 تست {symbol} ...")
    records = fetch_all_announcements(symbol)
    if records:
        print(f"✅ {len(records)} اطلاعیه دریافت شد.")
        if records:
            print(f"📋 اولین اطلاعیه: {records[0].get('title', 'بدون عنوان')}")
        return records
    else:
        print(f"❌ داده‌ای برای {symbol} یافت نشد.")
        return None

# ============================================================
# 🚀 تابع اصلی (مشابه main برنامه رمزارزها)
# ============================================================
def main():
    print("=" * 70)
    print("🌟 دریافت اطلاعیه‌های کدال (Codal)")
    print("📅 سامانه انتشار گزارش‌های مالی شرکت‌های بورسی")
    print("=" * 70)

    symbols = fetch_symbols()
    if not symbols:
        return

    print(f"📊 تعداد نمادها: {len(symbols)}")
    print("=" * 70)

    # دریافت تاریخ از کاربر (اختیاری)
    date_start = input("\n🔍 تاریخ شروع (مثلاً 1400-01-01) یا Enter برای همه: ").strip() or None
    date_end = input("🔍 تاریخ پایان (مثلاً 1405-05-01) یا Enter برای همه: ").strip() or None

    print("\n" + "=" * 70)
    print("🚀 شروع دریافت داده‌ها...")
    print("=" * 70)

    success = 0
    total_records = 0

    for idx, symbol in enumerate(symbols, 1):
        print(f"\n🔹 [{idx}/{len(symbols)}] دریافت {symbol} ...")
        records = fetch_all_announcements(symbol, date_start, date_end)

        if records:
            if save_announcements(symbol, records):
                success += 1
                total_records += len(records)

                # نمایش خلاصه
                print(f"   📊 {len(records)} اطلاعیه دریافت شد.")
                if records:
                    print(f"   📋 نمونه: {records[0].get('title', 'بدون عنوان')[:50]}...")
        else:
            print(f"   ⚠️ داده‌ای برای {symbol} یافت نشد")

        time.sleep(0.5)

    print("\n" + "=" * 70)
    print("✅ پایان کار")
    print(f"📊 {success} نماد با داده دریافت شد.")
    print(f"📈 کل اطلاعیه‌ها: {total_records}")
    print(f"📁 پوشه خروجی: {OUTPUT_DIR}")
    print("=" * 70)

if __name__ == "__main__":
    # تست یک نماد خاص (اختیاری)
    # test_symbol("موج")

    # اجرای اصلی
    main()
