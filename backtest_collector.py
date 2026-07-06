import subprocess
import json
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import sys
from datetime import datetime, timedelta
import jdatetime

# ========== تنظیمات ==========
API_KEY = "Bk7JvdJZBHJ9DMhzeuTfWjwqYy1wMsif"
BASE_URL = "https://Api.BrsApi.ir/Tsetmc/History.php"
SYMBOLS_FILE = "all_symbols_data.json"   # لیست کامل همه نمادها
OUTPUT_DIR = "backtest_data_all"         # پوشه خروجی جداگانه
MAX_WORKERS = 8
RATE_LIMIT = 500
RATE_WINDOW = 300
DAYS_BACK =  1200                  # تعداد روزهای گذشته
# ===================================

os.makedirs(OUTPUT_DIR, exist_ok=True)
file_lock = Lock()

# ========== کلاس کنترل نرخ ==========
class RateLimiter:
    def __init__(self, max_requests, window_seconds):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = []
        self.lock = Lock()
    
    def wait_if_needed(self):
        with self.lock:
            now = time.time()
            self.requests = [t for t in self.requests if now - t < self.window_seconds]
            if len(self.requests) >= self.max_requests:
                wait_time = self.window_seconds - (now - self.requests[0]) + 0.1
                if wait_time > 0:
                    print(f"\n⏳ محدودیت API! {wait_time:.1f} ثانیه صبر می‌کنم...", end="", flush=True)
                    time.sleep(wait_time)
                    self.wait_if_needed()
                    return
            self.requests.append(time.time())

rate_limiter = RateLimiter(RATE_LIMIT, RATE_WINDOW)

# ============================================================
# توابع کمکی
# ============================================================
def load_all_symbols():
    """بارگذاری لیست کامل همه نمادها از all_symbols_data.json"""
    try:
        with open(SYMBOLS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list) and all(isinstance(item, dict) and 'l18' in item for item in data):
            symbols = [item['l18'] for item in data]
        else:
            symbols = [item for item in data if isinstance(item, str)]
        print(f"✅ {len(symbols)} نماد از {SYMBOLS_FILE} بارگذاری شد.")
        return symbols
    except Exception as e:
        print(f"❌ خطا در خواندن {SYMBOLS_FILE}: {e}")
        return []

def fetch_history(symbol):
    """دریافت داده‌های تاریخی برای یک نماد"""
    url = f"{BASE_URL}?key={API_KEY}&type=0&l18={symbol}"
    rate_limiter.wait_if_needed()
    
    curl_path = "C:\\Windows\\System32\\curl.exe"
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    cmd = [curl_path, "-k", "--ssl-no-revoke", "-s", "-H", f"User-Agent: {user_agent}", "--max-time", "15", url]
    
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=20, text=False)
        stdout = result.stdout.decode('utf-8', errors='ignore')
        if result.returncode != 0 or not stdout.strip():
            return None
        data = json.loads(stdout)
        return data
    except:
        return None

def process_symbol(symbol):
    """پردازش یک نماد و فیلتر بر اساس روزهای اخیر"""
    try:
        data = fetch_history(symbol)
        if not data or not isinstance(data, list):
            return None
        
        today = jdatetime.date.today()
        cutoff = today - timedelta(days=DAYS_BACK)
        cutoff_str = cutoff.strftime('%Y-%m-%d')
        
        filtered = []
        for item in data:
            item_date = item.get('date')
            if item_date and item_date >= cutoff_str:
                filtered.append(item)
        
        return filtered
    except Exception as e:
        return None

def save_symbol_data(symbol, data):
    """ذخیره داده‌های یک نماد"""
    if not data:
        return
    
    filename = f"{OUTPUT_DIR}/{symbol}.json"
    
    existing = []
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except:
            pass
    
    all_data = existing + data
    seen = set()
    unique = []
    for item in all_data:
        date_key = item.get('date')
        if date_key and date_key not in seen:
            seen.add(date_key)
            unique.append(item)
    
    unique.sort(key=lambda x: x.get('date', ''))
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

def main():
    print("=" * 60)
    print("🚀 شروع دریافت تاریخچه قیمت‌ها برای همه نمادها")
    print("=" * 60)
    
    symbols = load_all_symbols()
    if not symbols:
        print("❌ هیچ نمادی یافت نشد.")
        return
    
    print(f"📅 دریافت {DAYS_BACK} روز گذشته")
    print(f"🚀 تعداد تردهای همزمان: {MAX_WORKERS}")
    print("=" * 60)
    
    start_time = time.time()
    successful = 0
    failed = 0
    
    batch_size = MAX_WORKERS * 5
    batches = [symbols[i:i+batch_size] for i in range(0, len(symbols), batch_size)]
    
    for batch_idx, batch in enumerate(batches):
        print(f"\n📦 دسته {batch_idx+1}/{len(batches)} ({len(batch)} نماد)")
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_symbol, symbol): symbol for symbol in batch}
            
            for future in as_completed(futures):
                symbol = futures[future]
                data = future.result()
                
                if data:
                    save_symbol_data(symbol, data)
                    successful += 1
                    print(f"   ✅ {symbol} - {len(data)} رکورد", flush=True)
                else:
                    failed += 1
                    print(f"   ❌ {symbol} - خطا", flush=True)
        
        print(f"💾 پیشرفت: {successful+failed}/{len(symbols)}")
        time.sleep(0.5)
    
    elapsed = time.time() - start_time
    
    print("\n" + "=" * 60)
    print("📊 گزارش نهایی:")
    print(f"   ✅ موفق: {successful} نماد")
    print(f"   ❌ ناموفق: {failed} نماد")
    print(f"   ⏱️ زمان کل: {elapsed:.0f} ثانیه (~{elapsed/60:.1f} دقیقه)")
    print(f"   📁 داده‌ها در پوشه '{OUTPUT_DIR}' ذخیره شدند.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 متوقف شد توسط کاربر.")
        sys.exit(0)