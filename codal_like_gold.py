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
# 📋 لیست نمادها (مشابه لیست طلا و ارز)
# ============================================================
# 🔹 اینجا می‌توانید لیست نمادهای مورد نظر خود را وارد کنید
SYMBOLS = [
    "موج",
    "اهرم",
    # "وبملت",
    # "فولاد",
    # "خودرو",
    # "شستا",
    # ... هر نماد دیگری که می‌خواهید اضافه کنید
]

# ============================================================
# 📋 دسته‌بندی اطلاعیه‌ها (برای مرجع)
# ============================================================
CATEGORIES = {
    1: "اطلاعات و صورت مالی سالانه",
    2: "افشای اطلاعات بااهمیت و شفاف‌سازی",
    3: "گزارش عملکرد ماهانه",
    4: "اساسنامه / امیدنامه",
    5: "اطلاعات هیئت مدیره و کمیته حسابرسی",
    6: "آگهی دعوت به مجامع و تصمیمات",
    7: "افزایش سرمایه",
    8: "شفاف‌سازی مربوط به بورس / فرابورس",
    9: "شفاف‌سازی مربوط به سازمان",
    10: "سایر",
    11: "اوراق بدهی"
}

# ============================================================
# 📥 دریافت اطلاعیه‌های یک نماد (مشابه fetch_history در برنامه طلا)
# ============================================================
def fetch_announcements(
    l18,
    category=None,
    audited=True,
    unaudited=True,
    only_main_company=True,
    only_subsidiaries=True,
    date_start=None,
    date_end=None,
    page=1
):
    """
    دریافت اطلاعیه‌های یک نماد با پارامترهای دلخواه
    مشابه تابع fetch_history در برنامه طلا
    """
    params = {"key": API_KEY, "l18": l18}

    if category:
        params["category"] = category
    if audited is not None:
        params["audited"] = "true" if audited else "false"
    if unaudited is not None:
        params["unaudited"] = "true" if unaudited else "false"
    if only_main_company is not None:
        params["only_main_company"] = "true" if only_main_company else "false"
    if only_subsidiaries is not None:
        params["only_subsidiaries"] = "true" if only_subsidiaries else "false"
    if date_start:
        params["date_start"] = date_start
    if date_end:
        params["date_end"] = date_end
    params["page"] = page

    try:
        response = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=180)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        print(f"      ❌ خطا: {e}")
        return None

# ============================================================
# 🔍 دریافت تمام صفحات یک نماد (مشابه برنامه طلا)
# ============================================================
def get_all_announcements_for_symbol(symbol, date_start=None, date_end=None, max_pages=None):
    """
    دریافت تمام اطلاعیه‌های یک نماد (همه دسته‌بندی‌ها)
    مشابه تابع get_all_history_for_symbol در برنامه طلا
    """
    print(f"\n📊 دریافت اطلاعات {symbol} ...")

    all_announcements = []
    page = 1
    total_pages = None

    while True:
        # نمایش پیشرفت (مشابه برنامه طلا)
        if page == 1:
            print(f"   🔄 دریافت صفحه {page} ...")
        else:
            print(f"   🔄 صفحه {page} ...")

        data = fetch_announcements(
            l18=symbol,
            date_start=date_start,
            date_end=date_end,
            page=page
        )

        if not data:
            print("   ❌ داده‌ای دریافت نشد.")
            break

        # استخراج تعداد کل صفحات
        if total_pages is None:
            total_pages = data.get("count_page", 1)
            print(f"   📊 تعداد کل صفحات: {total_pages}")

        announcements = data.get("result", [])
        if not announcements:
            print(f"   ⚠️ صفحه {page} خالی است.")
            break

        all_announcements.extend(announcements)
        print(f"   ✅ {len(announcements)} اطلاعیه دریافت شد. (مجموع: {len(all_announcements)})")

        # بررسی پایان صفحات
        if page >= total_pages:
            print("   ✅ تمام صفحات دریافت شد.")
            break
        if max_pages and page >= max_pages:
            print(f"   ⏹️ به حداکثر صفحات ({max_pages}) رسیدیم.")
            break

        page += 1
        time.sleep(0.5)  # تاخیر بین درخواست‌ها

    return all_announcements

# ============================================================
# 💾 ذخیره‌سازی (مشابه برنامه طلا)
# ============================================================
def save_symbol_data(symbol, data):
    """ذخیره داده‌های یک نماد در فایل جداگانه"""
    if not data:
        return False

    filename = os.path.join(OUTPUT_DIR, f"{symbol}_codal.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"   💾 ذخیره شد: {filename} ({len(data)} اطلاعیه)")
    return True

# ============================================================
# 📋 نمایش خلاصه (مشابه برنامه طلا)
# ============================================================
def print_summary(symbol, data):
    """نمایش خلاصه اطلاعات یک نماد"""
    if not data:
        print(f"   ⚠️ هیچ اطلاعیه‌ای برای {symbol} یافت نشد.")
        return

    print(f"\n📊 خلاصه اطلاعیه‌های {symbol} ({len(data)} مورد):")
    print("=" * 60)

    for i, ann in enumerate(data[:5], 1):
        title = ann.get("title", "بدون عنوان")[:40]
        date_send = ann.get("date_send", "نامشخص")
        print(f"   {i}. {title}... ({date_send})")

    if len(data) > 5:
        print(f"   ... و {len(data) - 5} اطلاعیه دیگر")
    print("=" * 60)

# ============================================================
# 🚀 تابع اصلی (مشابه برنامه طلا)
# ============================================================
def main():
    print("=" * 70)
    print("🌟 دریافت اطلاعات کدال (مشابه برنامه طلا)")
    print("📅 سامانه انتشار گزارش‌های مالی شرکت‌های بورسی")
    print("=" * 70)

    # نمایش لیست نمادها
    print(f"\n📋 تعداد نمادها: {len(SYMBOLS)}")
    print(f"📌 نمادها: {', '.join(SYMBOLS)}")
    print("=" * 70)

    # تنظیمات تاریخ (اختیاری)
    print("\n🔍 تنظیمات تاریخ (اختیاری - Enter برای همه):")
    date_start = input("   تاریخ شروع (مثلاً 1400-01-01): ").strip() or None
    date_end = input("   تاریخ پایان (مثلاً 1405-05-01): ").strip() or None

    max_pages_input = input("\n📄 حداکثر تعداد صفحات (Enter برای همه): ").strip()
    max_pages = int(max_pages_input) if max_pages_input.isdigit() else None

    print("\n" + "=" * 70)
    print("🚀 شروع دریافت داده‌ها...")
    print("=" * 70)

    success_count = 0
    total_records = 0

    # حلقه روی نمادها (مشابه برنامه طلا)
    for idx, symbol in enumerate(SYMBOLS, 1):
        print(f"\n🔹 [{idx}/{len(SYMBOLS)}] دریافت اطلاعات {symbol} ...")

        data = get_all_announcements_for_symbol(
            symbol=symbol,
            date_start=date_start,
            date_end=date_end,
            max_pages=max_pages
        )

        if data:
            if save_symbol_data(symbol, data):
                success_count += 1
                total_records += len(data)
                print_summary(symbol, data)
        else:
            print(f"   ⚠️ هیچ اطلاعاتی برای {symbol} یافت نشد.")

        time.sleep(1)  # تاخیر بین نمادها

    # گزارش نهایی
    print("\n" + "=" * 70)
    print("📊 گزارش نهایی")
    print("=" * 70)
    print(f"✅ نمادهای موفق: {success_count} از {len(SYMBOLS)}")
    print(f"📈 کل اطلاعیه‌ها: {total_records}")
    print(f"📁 پوشه خروجی: {OUTPUT_DIR}")
    print("=" * 70)

# ============================================================
# 🧪 اجرای سریع (برای تست بدون ورودی)
# ============================================================
def quick_run():
    """اجرای سریع با تنظیمات پیش‌فرض"""
    print("🚀 اجرای سریع (بدون ورودی)...")
    date_start = "1400-01-01"
    date_end = "1405-05-01"

    for symbol in SYMBOLS:
        print(f"\n🔹 دریافت {symbol} ...")
        data = get_all_announcements_for_symbol(
            symbol=symbol,
            date_start=date_start,
            date_end=date_end,
            max_pages=2  # فقط ۲ صفحه برای تست
        )
        if data:
            save_symbol_data(symbol, data)
            print_summary(symbol, data)

if __name__ == "__main__":
    main()
    # برای اجرای سریع:
    # quick_run()
