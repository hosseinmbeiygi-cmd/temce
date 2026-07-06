import subprocess
import json
import time
import os
import re

# ========== تنظیمات ==========
API_KEY = "Bk7JvdJZBHJ9DMhzeuTfWjwqYy1wMsif"
BASE_URL = "https://Api.BrsApi.ir/Tsetmc/Candlestick.php"
SYMBOLS_FILE = "all_symbols_data.json"
OUTPUT_DIR = "candlestick_data"
DELAY = 0.7  # تاخیر بین هر درخواست (ثانیه) - با 0.7 حدود 428 درخواست در 5 دقیقه
MAX_RETRIES = 3

# نوع داده‌های مورد نظر
# 1 = لحظه‌ای روز جاری
# 2 = تعدیل نشده روزانه
# 3 = تعدیل شده روزانه
TYPES = [1, 2, 3]  # هر سه نوع
# TYPES = [3]  # فقط تعدیل شده
# TYPES = [1]  # فقط لحظه‌ای
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
    if text is None:
        return None
    return str(text).strip()

def fetch_candlestick(symbol, type_code):
    """دریافت داده‌های کندل‌استیک برای یک نماد و نوع مشخص"""
    url = f"{BASE_URL}?key={API_KEY}&type={type_code}&l18={symbol}"
    
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
        return data
    except json.JSONDecodeError as e:
        raise Exception(f"JSON نامعتبر: {e}\nخروجی: {stdout[:300]}")
    except subprocess.TimeoutExpired:
        raise Exception("زمان درخواست به پایان رسید")
    except FileNotFoundError:
        raise Exception("curl.exe پیدا نشد.")

def process_candle(candle):
    """پردازش یک کندل برای ذخیره‌سازی (تبدیل اعداد به عدد)"""
    return {
        'date': clean_text(candle.get('date')),
        'time': clean_text(candle.get('time')),
        'open': int(candle.get('open', 0)),
        'high': int(candle.get('high', 0)),
        'low': int(candle.get('low', 0)),
        'close': int(candle.get('close', 0)),
        'volume': int(candle.get('volume', 0)),
    }

def fetch_and_save(symbol, type_code):
    """دریافت و ذخیره داده‌های کندل برای یک نماد و نوع"""
    type_name = {1: 'live', 2: 'unadjusted', 3: 'adjusted'}.get(type_code, str(type_code))
    print(f"  📊 دریافت نوع {type_name}...")
    
    try:
        raw_data = fetch_candlestick(symbol, type_code)
        if not raw_data:
            print(f"    ⚠️ داده‌ای برای {symbol} نوع {type_name} یافت نشد.")
            return False
        
        # پردازش کندل‌ها
        processed = [process_candle(c) for c in raw_data]
        
        # ذخیره در فایل
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        filename = f"{symbol}_type{type_code}.json"
        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                'symbol': symbol,
                'type': type_code,
                'type_name': type_name,
                'count': len(processed),
                'data': processed
            }, f, ensure_ascii=False, indent=2)
        print(f"    ✅ {len(processed)} کندل برای {symbol} نوع {type_name} ذخیره شد.")
        return True
    except Exception as e:
        print(f"    ❌ خطا در دریافت {symbol} نوع {type_name}: {e}")
        return False

def main():
    # بارگذاری نمادها
    symbols = load_symbols(SYMBOLS_FILE)
    print(f"✅ {len(symbols)} نماد بارگذاری شد.")
    print(f"📊 دریافت برای نوع‌های: {TYPES}")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # بررسی فایل‌های موجود (Resume)
    existing_files = set(os.listdir(OUTPUT_DIR))
    processed = set()
    for f in existing_files:
        if f.endswith('.json'):
            # استخراج نماد و نوع از نام فایل
            parts = f.replace('.json', '').split('_type')
            if len(parts) == 2:
                symbol = parts[0]
                type_code = int(parts[1])
                processed.add((symbol, type_code))
    
    print(f"📂 {len(processed)} ترکیب (نماد+نوع) قبلاً پردازش شده‌اند.")
    
    total_requests = len(symbols) * len(TYPES)
    completed = len(processed)
    print(f"📊 {completed} از {total_requests} درخواست قبلاً انجام شده.")
    
    for idx, symbol in enumerate(symbols, 1):
        for type_code in TYPES:
            if (symbol, type_code) in processed:
                continue
            
            print(f"\n🔍 پردازش {idx}/{len(symbols)}: {symbol} (نوع {type_code})")
            
            success = fetch_and_save(symbol, type_code)
            if success:
                processed.add((symbol, type_code))
            time.sleep(DELAY)

if __name__ == "__main__":
    main()