import os
import json
import time
import requests
from pathlib import Path
from urllib.parse import urlparse

# ========== تنظیمات ==========
JSON_DIR = "codal_data"        # پوشه حاوی فایل‌های JSON (خروجی کرالر)
PDF_DIR = "pdf_files"          # پوشه خروجی برای فایل‌های PDF
EXCEL_DIR = "excel_files"      # پوشه خروجی برای فایل‌های Excel
LOG_FILE = "download_log.txt"  # فایل لاگ

DELAY = 0.5                    # تاخیر بین هر دانلود (ثانیه)
TIMEOUT = 30                   # زمان انتظار برای هر درخواست
MAX_RETRIES = 3                # تعداد تلاش مجدد در صورت خطا
# ==============================

def ensure_directory(path):
    """ایجاد پوشه در صورت وجود نداشتن"""
    Path(path).mkdir(parents=True, exist_ok=True)

def sanitize_filename(name):
    """پاکسازی نام فایل از کاراکترهای غیرمجاز"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '_')
    # محدود کردن طول نام
    return name[:200]

def get_file_extension(url):
    """تشخیص پسوند فایل از URL"""
    if not url:
        return None
    # بررسی پارامترهای URL
    parsed = urlparse(url)
    path = parsed.path
    if 'excel' in path or 'Excel' in path:
        return '.xlsx'
    elif 'pdf' in path.lower():
        return '.pdf'
    # اگر از روی پسوند تشخیص داده نشد
    if path.endswith('.pdf'):
        return '.pdf'
    elif path.endswith('.xlsx') or path.endswith('.xls'):
        return '.xlsx'
    return None

def download_file(url, filepath):
    """دانلود یک فایل با مدیریت خطا و تلاش مجدد"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, timeout=TIMEOUT)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                return True
            else:
                print(f"    ⚠️ کد وضعیت {response.status_code} برای {url[:80]}...")
        except Exception as e:
            print(f"    ⚠️ تلاش {attempt}/{MAX_RETRIES} شکست: {e}")
            time.sleep(2)  # تاخیر قبل از تلاش مجدد
    return False

def log_message(message):
    """نوشتن پیام در فایل لاگ"""
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")

def process_json_file(json_path):
    """پردازش یک فایل JSON و دانلود PDF و Excel موجود در آن"""
    symbol = json_path.stem  # نام فایل بدون پسوند = نام نماد
    print(f"\n📂 پردازش نماد: {symbol}")

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        log_message(f"خطا در خواندن {json_path}: {e}")
        print(f"  ❌ خطا در خواندن فایل: {e}")
        return

    announcements = data.get('announcements', [])
    if not announcements:
        print(f"  ⚠️ بدون اطلاعیه")
        return

    pdf_count = 0
    excel_count = 0

    for idx, announcement in enumerate(announcements, 1):
        # --- دانلود PDF ---
        pdf_url = announcement.get('link_pdf')
        if pdf_url:
            ext = get_file_extension(pdf_url) or '.pdf'
            title = sanitize_filename(announcement.get('title', f'اطلاعیه_{idx}'))
            date_str = announcement.get('date_title', '').replace('/', '-')
            if date_str:
                filename = f"{symbol}_{date_str}_{title}{ext}"
            else:
                filename = f"{symbol}_{idx}_{title}{ext}"
            if len(filename) > 200:
                filename = filename[:200] + ext
            filepath = os.path.join(PDF_DIR, filename)

            if os.path.exists(filepath):
                print(f"  ⏭️ PDF رد شد (قبلاً دانلود شده): {filename[:60]}...")
            else:
                print(f"  ⬇️ دانلود PDF {idx}/{len(announcements)}: {title[:50]}...")
                if download_file(pdf_url, filepath):
                    pdf_count += 1
                    print(f"    ✅ PDF ذخیره شد: {filename[:60]}...")
                else:
                    log_message(f"شکست در دانلود PDF {symbol}: {pdf_url}")
                    print(f"    ❌ شکست در دانلود PDF")
                time.sleep(DELAY)

        # --- دانلود Excel ---
        excel_url = announcement.get('link_excel')
        if excel_url:
            ext = get_file_extension(excel_url) or '.xlsx'
            title = sanitize_filename(announcement.get('title', f'اطلاعیه_{idx}'))
            date_str = announcement.get('date_title', '').replace('/', '-')
            if date_str:
                filename = f"{symbol}_{date_str}_{title}{ext}"
            else:
                filename = f"{symbol}_{idx}_{title}{ext}"
            if len(filename) > 200:
                filename = filename[:200] + ext
            filepath = os.path.join(EXCEL_DIR, filename)

            if os.path.exists(filepath):
                print(f"  ⏭️ Excel رد شد (قبلاً دانلود شده): {filename[:60]}...")
            else:
                print(f"  ⬇️ دانلود Excel {idx}/{len(announcements)}: {title[:50]}...")
                if download_file(excel_url, filepath):
                    excel_count += 1
                    print(f"    ✅ Excel ذخیره شد: {filename[:60]}...")
                else:
                    log_message(f"شکست در دانلود Excel {symbol}: {excel_url}")
                    print(f"    ❌ شکست در دانلود Excel")
                time.sleep(DELAY)

    print(f"  📊 PDF دانلودشده: {pdf_count} | Excel دانلودشده: {excel_count}")

def main():
    # ایجاد پوشه‌های خروجی
    ensure_directory(PDF_DIR)
    ensure_directory(EXCEL_DIR)
    print(f"📁 پوشه PDF: {PDF_DIR}")
    print(f"📁 پوشه Excel: {EXCEL_DIR}")

    # پیدا کردن فایل‌های JSON
    json_files = list(Path(JSON_DIR).glob("*.json"))
    if not json_files:
        print(f"❌ هیچ فایل JSON در پوشه '{JSON_DIR}' یافت نشد.")
        return

    print(f"✅ {len(json_files)} فایل JSON یافت شد.")
    start_time = time.time()

    for json_file in json_files:
        process_json_file(json_file)
        # تاخیر بین نمادها
        time.sleep(DELAY * 2)

    elapsed = time.time() - start_time
    print(f"\n🎉 عملیات به پایان رسید. زمان کل: {elapsed:.2f} ثانیه")
    print(f"📄 لاگ خطاها در فایل '{LOG_FILE}' ذخیره شده است.")

if __name__ == "__main__":
    main()