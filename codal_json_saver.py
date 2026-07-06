import subprocess
import json
import time
import os

# ========== تنظیمات ==========
API_KEY = "Bk7JvdJZBHJ9DMhzeuTfWjwqYy1wMsif"
BASE_URL = "https://Api.BrsApi.ir/Codal/Announcement.php"
SYMBOLS_FILE = "all_symbols_data.json"
OUTPUT_FILE = "symbols_with_codal.json"
DELAY = 0.6  # 0.6 ثانیه = 500 درخواست در 5 دقیقه
MAX_RETRIES = 2
# ===================================

def load_symbols(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if isinstance(data, list) and all(isinstance(item, dict) and 'l18' in item for item in data):
        return [item['l18'] for item in data]
    elif isinstance(data, list) and all(isinstance(item, str) for item in data):
        return data
    raise ValueError("فرمت فایل نمادها نامعتبر است.")

def check_symbol_has_codal(symbol):
    url = f"{BASE_URL}?key={API_KEY}&l18={symbol}&page=1"
    curl_path = "C:\\Windows\\System32\\curl.exe"
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    cmd = [curl_path, "-k", "--ssl-no-revoke", "-s", "-H", f"User-Agent: {user_agent}", "--max-time", "20", url]
    
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=25, text=False)
        stdout = result.stdout.decode('utf-8', errors='ignore')
        if result.returncode != 0 or not stdout.strip():
            return None
        data = json.loads(stdout)
        if not data.get('successful', True) and data.get('status') == 'invalid_param':
            return None
        return data.get('count_announcement', 0) > 0
    except:
        return None

def load_previous_results():
    """بارگذاری نتایج قبلی برای ادامه از نقطه قطع"""
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return (
                set(data.get('symbols_with_codal', [])),
                set(data.get('symbols_without_codal', [])),
                set(data.get('error_symbols', []))
            )
    return set(), set(), set()

def save_results(symbols, has_codal, no_codal, errors):
    """ذخیره نتایج در فایل JSON"""
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            'total_symbols': len(symbols),
            'has_codal': len(has_codal),
            'no_codal': len(no_codal),
            'errors': len(errors),
            'symbols_with_codal': sorted(has_codal),
            'symbols_without_codal': sorted(no_codal),
            'error_symbols': sorted(errors)
        }, f, ensure_ascii=False, indent=2)

def main():
    # بارگذاری لیست کامل نمادها
    all_symbols = load_symbols(SYMBOLS_FILE)
    print(f"✅ {len(all_symbols)} نماد بارگذاری شد.")
    
    # بارگذاری نتایج قبلی (Resume)
    has_codal, no_codal, errors = load_previous_results()
    checked = has_codal | no_codal | errors
    print(f"📂 {len(checked)} نماد قبلاً بررسی شده‌اند.")
    
    # باقیمانده نمادها
    remaining = [s for s in all_symbols if s not in checked]
    print(f"📊 {len(remaining)} نماد باقی مانده برای بررسی.")
    
    if not remaining:
        print("✅ همه نمادها قبلاً بررسی شده‌اند.")
        return
    
    print("\n🔍 شروع بررسی نمادها...")
    print("=" * 50)
    
    start_time = time.time()
    
    for idx, symbol in enumerate(remaining, 1):
        print(f"{idx}/{len(remaining)}: {symbol} ... ", end="", flush=True)
        
        result = check_symbol_has_codal(symbol)
        
        if result is True:
            has_codal.add(symbol)
            print("✅ دارد")
        elif result is False:
            no_codal.add(symbol)
            print("❌ ندارد")
        else:
            errors.add(symbol)
            print("⚠️ خطا")
        
        # ذخیره هر ۱۰۰ رکورد یکبار (برای جلوگیری از از دست رفتن داده)
        if idx % 100 == 0:
            save_results(all_symbols, has_codal, no_codal, errors)
            print(f"💾 ذخیره شد (تا {idx})")
        
        # تاخیر 0.6 ثانیه برای رعایت محدودیت 500 درخواست در 5 دقیقه
        time.sleep(DELAY)
    
    # ذخیره نهایی
    save_results(all_symbols, has_codal, no_codal, errors)
    
    elapsed = time.time() - start_time
    print(f"\n✅ نتایج نهایی در '{OUTPUT_FILE}' ذخیره شد.")
    print(f"⏱️ زمان کل: {elapsed:.0f} ثانیه (~{elapsed/60:.1f} دقیقه)")
    
    # آمار نهایی
    print("\n📊 آمار نهایی:")
    print(f"   مجموع نمادها: {len(all_symbols)}")
    print(f"   ✅ دارای اطلاعیه کدال: {len(has_codal)}")
    print(f"   ❌ بدون اطلاعیه کدال: {len(no_codal)}")
    print(f"   ⚠️ خطا در بررسی: {len(errors)}")

if __name__ == "__main__":
    main()