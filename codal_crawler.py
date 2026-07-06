import subprocess
import json
import time
import os
import re

# ========== تنظیمات ==========
API_KEY = "Bk7JvdJZBHJ9DMhzeuTfWjwqYy1wMsif"
BASE_URL = "https://Api.BrsApi.ir/Codal/Announcement.php"
SYMBOLS_FILE = "all_symbols_data.json"
OUTPUT_DIR = "codal_data_db"
DELAY = 1.0
MAX_RETRIES = 3

# ========== فیلترها ==========
FILTERS = {
    "category": None,
    "period": None,
    "audited": None,
    "unaudited": None,
    "only_main_company": None,
    "only_subsidiaries": None,
    "date_start": None,
    "date_end": None,
}
# ===================================

def load_symbols(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if isinstance(data, list) and all(isinstance(item, dict) and 'l18' in item for item in data):
        return [item['l18'] for item in data]
    elif isinstance(data, list) and all(isinstance(item, str) for item in data):
        return data
    raise ValueError("فرمت فایل نمادها نامعتبر است.")

def clean_text(text):
    """پاکسازی متن برای ذخیره در دیتابیس"""
    if text is None:
        return None
    # حذف نقل قول‌های اضافی
    text = text.replace('"', '""')
    text = text.replace("'", "''")
    # حذف کاراکترهای کنترل
    text = re.sub(r'[\x00-\x1F\x7F]', '', text)
    return text.strip()

def build_params(symbol, page, filters):
    params = {'key': API_KEY, 'l18': symbol, 'page': page}
    for key, value in filters.items():
        if value is not None:
            if isinstance(value, bool):
                params[key] = 'true' if value else 'false'
            else:
                params[key] = str(value)
    return params

def fetch_announcements(symbol, page=1, filters=None):
    if filters is None:
        filters = {}
    params = build_params(symbol, page, filters)
    url = f"{BASE_URL}?key={API_KEY}"
    for key, value in params.items():
        if key != 'key':
            url += f"&{key}={value}"
    
    curl_path = "C:\\Windows\\System32\\curl.exe"
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    cmd = [curl_path, "-k", "--ssl-no-revoke", "-s", "-H", f"User-Agent: {user_agent}", "--max-time", "30", url]
    
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=35, text=False)
        stdout = result.stdout.decode('utf-8', errors='ignore')
        stderr = result.stderr.decode('utf-8', errors='ignore')
        if result.returncode != 0:
            raise Exception(f"curl خطا (کد {result.returncode}): {stderr}")
        if not stdout.strip():
            raise Exception("خروجی خالی از سرور")
        data = json.loads(stdout)
        if not data.get('successful', True) and data.get('status') == 'invalid_param':
            raise Exception(f"خطای پارامتر: {data.get('message_error')}")
        return data
    except json.JSONDecodeError as e:
        raise Exception(f"JSON نامعتبر: {e}\nخروجی: {stdout[:300]}")
    except subprocess.TimeoutExpired:
        raise Exception("زمان درخواست به پایان رسید")
    except FileNotFoundError:
        raise Exception("curl.exe پیدا نشد.")

def process_announcement(announcement):
    """پردازش اطلاعیه با حفظ تاریخ شمسی"""
    return {
        'symbol': clean_text(announcement.get('l18')),
        'company_name': clean_text(announcement.get('l30')),
        'title': clean_text(announcement.get('title')),
        'code': clean_text(announcement.get('code')),
        # تاریخ‌ها به همان صورت شمسی ذخیره می‌شوند (بدون تبدیل)
        'date_title': clean_text(announcement.get('date_title')),
        'date_send': clean_text(announcement.get('date_send')),
        'time_send': announcement.get('time_send'),
        'date_publish': clean_text(announcement.get('date_publish')),
        'time_publish': announcement.get('time_publish'),
        'link': clean_text(announcement.get('link')),
        'link_pdf': clean_text(announcement.get('link_pdf')),
        'link_excel': clean_text(announcement.get('link_excel')),
        'link_attachment': clean_text(announcement.get('link_attachment')),
    }

def fetch_all_pages(symbol, filters=None):
    all_announcements = []
    page = 1
    consecutive_errors = 0
    while True:
        try:
            print(f"دریافت صفحه {page} برای {symbol}...")
            data = fetch_announcements(symbol, page, filters)
            if 'announcement' not in data or not data['announcement']:
                break
            for ann in data['announcement']:
                all_announcements.append(process_announcement(ann))
            total_pages = data.get('count_page', 0)
            if page >= total_pages:
                break
            page += 1
            consecutive_errors = 0
            time.sleep(DELAY)
        except Exception as e:
            consecutive_errors += 1
            if consecutive_errors > MAX_RETRIES:
                print(f"❌ شکست پس از {MAX_RETRIES} تلاش برای {symbol}: {e}")
                break
            print(f"⚠️ خطا (تلاش {consecutive_errors}/{MAX_RETRIES}): {e}")
            time.sleep(DELAY * 2)
    return all_announcements

def save_as_json(symbol, announcements):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = f"{OUTPUT_DIR}/{symbol}.json"
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump({
            'symbol': symbol,
            'count': len(announcements),
            'announcements': announcements
        }, f, ensure_ascii=False, indent=2)
    print(f"✅ {symbol} با {len(announcements)} اطلاعیه ذخیره شد.")

def main():
    symbols = load_symbols(SYMBOLS_FILE)
    print(f"✅ {len(symbols)} نماد بارگذاری شد.")
    print(f"🔧 فیلترهای اعمال‌شده: {FILTERS}")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    existing_files = set(os.listdir(OUTPUT_DIR))
    existing_symbols = {f.replace('.json', '') for f in existing_files if f.endswith('.json')}
    print(f"📂 {len(existing_symbols)} نماد قبلاً پردازش شده‌اند.")
    
    for idx, symbol in enumerate(symbols, 1):
        if symbol in existing_symbols:
            print(f"\n⏭️ رد شدن {idx}/{len(symbols)}: {symbol} (قبلاً پردازش شده)")
            continue
        
        print(f"\n🔍 پردازش {idx}/{len(symbols)}: {symbol}")
        try:
            announcements = fetch_all_pages(symbol, FILTERS)
            if announcements:
                save_as_json(symbol, announcements)
                existing_symbols.add(symbol)
            else:
                print(f"⚠️ بدون اطلاعیه برای {symbol}")
                save_as_json(symbol, [])
                existing_symbols.add(symbol)
        except KeyboardInterrupt:
            print("\n🛑 متوقف شد توسط کاربر.")
            break
        except Exception as e:
            print(f"❌ شکست در {symbol}: {e}")
        time.sleep(DELAY * 1.5)

if __name__ == "__main__":
    main()