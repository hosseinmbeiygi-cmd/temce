import requests
import json
import time
from datetime import datetime

# ======== تنظیمات اولیه ========
API_KEY = "Bk7JvdJZBHJ9DMhzeuTfWjwqYy1wMsif"  # کلید خود را از brsapi.ir دریافت کنید
SYMBOLS = ["شستا", "فملی", "خودرو", "کگل", "شپدیس"]  # لیست نمادها
START_DATE = "1400-01-01"  # تاریخ شروع (شمسی)

# هدرهای اجباری برای جلوگیری از مسدود شدن IP
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_codal_announcements(symbol, start_date, end_date=None):
    """دریافت اطلاعیه‌های کدال برای یک نماد با فیلتر حسابرسی‌شده"""
    base_url = "https://Api.BrsApi.ir/Codal/Announcement.php"
    
    # ساخت پارامترها
    params = {
        "key": API_KEY,
        "l18": symbol,
        "audited": "true",
        "date_start": start_date,
        "page": 1
    }
    if end_date:
        params["date_end"] = end_date
    
    try:
        # ارسال درخواست با تأخیر ۱ ثانیه برای رعایت محدودیت
        time.sleep(1)
        response = requests.get(base_url, params=params, headers=HEADERS, timeout=30)
        response.raise_for_status()  # بررسی وضعیت HTTP
        
        data = response.json()
        if data.get("status") == "error":
            print(f"❌ خطای API برای {symbol}: {data.get('message', 'خطای ناشناخته')}")
            return None
            
        count = data.get("count_announcement", 0)
        if count == 0:
            print(f"⚠️ هیچ اطلاعیه‌ای برای {symbol} یافت نشد")
            return None
            
        print(f"✅ {count} اطلاعیه برای {symbol} دریافت شد")
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ خطای شبکه برای {symbol}: {e}")
        return None
    except json.JSONDecodeError:
        print(f"❌ پاسخ نامعتبر JSON برای {symbol}")
        return None

def save_data(symbol, data):
    """ذخیره داده‌ها در فایل JSON با زمان‌بندی"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{symbol}_codal_{timestamp}.json"
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"💾 داده‌های {symbol} در {filename} ذخیره شد")
        return True
    except Exception as e:
        print(f"❌ خطا در ذخیره {symbol}: {e}")
        return False

def main():
    print("🚀 شروع دریافت اطلاعیه‌های کدال از BrsApi...")
    print(f"📅 از تاریخ {START_DATE} به بعد")
    print(f"📋 تعداد نمادها: {len(SYMBOLS)}")
    
    for i, symbol in enumerate(SYMBOLS, 1):
        print(f"\n🔹 [{i}/{len(SYMBOLS)}] پردازش {symbol}...")
        data = fetch_codal_announcements(symbol, START_DATE)
        if data:
            save_data(symbol, data)
        time.sleep(0.5)  # تأخیر بین نمادها برای رعایت محدودیت
    
    print("\n✅ کلیه نمادها پردازش شدند.")

if __name__ == "__main__":
    main()