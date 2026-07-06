import requests
import json
import time
import os
from datetime import datetime, timedelta
import jdatetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# ========== تنظیمات ==========
API_KEY = "Bk7JvdJZBHJ9DMhzeuTfWjwqYy1wMsif"  # کلید رایگان نمونه
BASE_URL = "https://Api.BrsApi.ir/Tsetmc/Nav.php"
OUTPUT_DIR = "etf_nav_history"
MAX_WORKERS = 4
RATE_LIMIT_5MIN = 500
RATE_WINDOW = 300
OUTPUT_DIR = "etf_nav_daily"  # یک سال (برای تاریخچه کامل، می‌توانید بیشتر کنید)
# =================================

os.makedirs(OUTPUT_DIR, exist_ok=True)
file_lock = Lock()

# ========== لیست نمادهای استخراج‌شده (همان لیست بالا) ==========
SYMBOLS = [
    "اهرم", "توان", "شتاب", "جهش", "موج", "نارنج اهرم", "بيدار", "دوايكس",
    "پيشران", "اطلس", "آساس", "كاريس", "الماس", "فيروزه", "كاردان", "ثروتم",
    "آگاس", "آتيمس", "افق ملت", "سرو", "بذر", "دارا يكم", "ارزش", "آوا",
    "مدير", "پالايش", "زرين", "وبازار", "فراز", "ثهام", "پادا", "داريوش",
    "ويستا", "اوج", "ثمين", "انار", "رماس", "پتروما", "تاراز", "مرواريد",
    "آرام", "سلام", "هم وزن", "درسا", "برليان", "عقيق", "هيوا", "ثنا",
    "ترمه", "دريا", "پرتو", "اكسيژن", "پتروآگاه", "استيل", "پتروداريوش",
    "صدف", "پتروصبا", "سمان", "هوشيار", "بهين رو", "تيام", "پيروز", "رويين",
    "فلزفارابي", "متال", "آذرين", "خليج", "جاودان", "هامون", "نارين",
    "پتروآبان", "فارما كيان", "تكپاد", "بازبيمه", "تخت گاز", "ثروت ساز",
    "سپينود", "خبرگان", "آبنوس", "رخش", "پتروفارس", "فرصت", "رسانا", "مانا",
    "پتروپاداش", "هومان", "سيمانيا", "رشدي كيان", "دي سهام", "جوانه كوچك",
    "عرش", "همتا", "فارماني", "آس", "ابتكار", "آميتيس", "پناه", "رونق",
    "فرا الگوريتم", "سهامدار", "هوشمند", "ديار", "پرتوسا", "رويش همراه",
    "بانكدار", "اعتبارسهام", "يلدا", "لذيذ", "هم تراز", "آلكان", "يكم",
    "سها", "كوانتوم", "بزرگ", "همسنگ", "هم ارز", "نبات", "جام سهند",
    "رادان", "پتروسورين", "ثروين", "امتياز", "ولتاژ", "بانكو", "ناوگان",
    "بانكيا", "آويد", "آوان", "آسام", "صنوين", "زيتون", "آفرين", "هيبريد",
    "شيلد", "مختلط", "تداوم", "اعتماد", "صايند", "سخند", "آكورد", "پارند",
    "كيان", "امين يكم", "كمند", "فيروزا", "اوصتا", "آساميد", "دارا",
    "ارمغان", "گنجينه", "تصميم", "افران", "گنجين", "ياقوت", "داريك", "سپر",
    "خاتم", "فردا", "كارين", "سپيدما", "كامياب", "سيناد", "هماي", "ماني",
    "ثبات", "كارا", "يارا", "هامرز", "رشد", "پاداش", "نشان", "آفاق", "آوند",
    "نخل", "ساحل", "لبخند", "كاج", "رايكا", "بازده", "اعتبار", "پايا",
    "ديبا", "رابين", "سام", "درين", "نيلي", "صنهال", "آكام", "آلا", "فاخر",
    "طلوع", "توسكا", "خورشيد", "اونيكس", "ثابت اكسيژن", "دامون", "ماهور",
    "بمان", "پايش", "اصيل", "كارما", "همگام", "نيك گستر", "آتيه ملت",
    "آرامش", "شميم", "ترنج ثابت", "اطمينان", "اركيده", "خزانه ملت",
    "كارآمد", "آسود", "زمرد كوروش", "ستاره", "سپنتارود", "پاسارگاد",
    "بلوط", "آسان", "اندوخته داريوش", "ماكان", "هدف", "آسا", "ثمر",
    "رايبد", "سيلور", "سيمين", "رويش", "آتي1", "آشناتك", "تهران1",
    "فنابا", "پارتين", "ونچر", "نوآور", "استارز", "ثروت", "كمان",
    "پيشرفت", "ديوان", "سپهر", "اكسير", "ديتا", "تهران2", "افق نگر",
    "تدبيريكم", "بامداد", "صنم", "تمشك", "خوشه", "ضمان", "گارانتي",
    "طلا", "زر", "گوهر", "عيار", "كهربا", "مثقال", "زرفام", "نفيس",
    "گنج", "ناب", "آلتون", "جواهر", "تابش", "ليان", "زروان", "درخشان",
    "آتش", "قيراط", "گلديس", "زمرد", "امرالد", "رز ترنج", "درنا", "زرگر",
    "ريتون", "گلدا", "رزگلد", "نگين فارس", "هميان", "ميراث", "دفينه"
]

# ========== توابع اصلی (همانند قبل) ==========
def get_trading_days(days_back=DAYS_BACK):
    today = jdatetime.date.today()
    start = today - timedelta(days=days_back)
    days = []
    current = start
    while current <= today:
        if current.weekday() < 5:
            days.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=1)
    return sorted(days)

def fetch_nav(symbol, date):
    url = f"{BASE_URL}?key={API_KEY}&l18={symbol}"
    try:
        response = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                for item in data:
                    if item.get('date') == date:
                        return {
                            'date': date,
                            'time': item.get('time', ''),
                            'psubtran': item.get('psubtran', 0),
                            'predtran': item.get('predtran', 0),
                        }
                return None
            if isinstance(data, dict) and data.get('date') == date:
                return {
                    'date': date,
                    'time': data.get('time', ''),
                    'psubtran': data.get('psubtran', 0),
                    'predtran': data.get('predtran', 0),
                }
        return None
    except:
        return None

def save_nav(symbol, date, data):
    filename = f"{OUTPUT_DIR}/{symbol}.json"
    with file_lock:
        existing = []
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            except:
                pass
        existing = [e for e in existing if e.get('date') != date]
        if data:
            existing.append(data)
        else:
            existing.append({
                'date': date,
                'time': '',
                'psubtran': 0,
                'predtran': 0,
                'no_data': True
            })
        existing.sort(key=lambda x: x.get('date', ''))
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

def load_progress():
    progress_file = f"{OUTPUT_DIR}/progress.json"
    if os.path.exists(progress_file):
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                return set(json.load(f).get('processed', []))
        except:
            pass
    return set()

def save_progress(processed):
    progress_file = f"{OUTPUT_DIR}/progress.json"
    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump({
            'processed': list(processed),
            'last_update': datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)

# ========== اجرای اصلی ==========
def main():
    print("=" * 70)
    print("🚀 دریافت تاریخچه NAV تمام صندوق‌های ETF (بر اساس لیست استخراج‌شده)")
    print("=" * 70)
    print(f"📊 تعداد نمادها: {len(SYMBOLS)}")
    
    days = get_trading_days()
    print(f"📅 تعداد روزهای معاملاتی: {len(days)}")
    print(f"   از {days[0]} تا {days[-1]}")
    
    total_requests = len(SYMBOLS) * len(days)
    print(f"📊 تعداد کل درخواست‌ها: {total_requests:,}")
    
    processed = load_progress()
    print(f"📂 {len(processed)} ترکیب قبلاً پردازش شده.")
    
    all_combinations = [(s, d) for s in SYMBOLS for d in days]
    remaining = [c for c in all_combinations if f"{c[0]}-{c[1]}" not in processed]
    
    if not remaining:
        print("✅ همه داده‌ها قبلاً دریافت شده‌اند.")
        return
    
    print(f"📂 {len(remaining)} ترکیب باقی مانده.")
    print("=" * 70)
    
    total_success = 0
    total_failed = 0
    start_time = time.time()
    
    batch_size = MAX_WORKERS * 5
    total_batches = (len(remaining) + batch_size - 1) // batch_size
    
    for batch_idx in range(total_batches):
        batch = remaining[batch_idx * batch_size : (batch_idx+1) * batch_size]
        print(f"\n📦 دسته {batch_idx+1}/{total_batches} ({len(batch)} ترکیب)")
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_nav, symbol, date): (symbol, date) 
                      for symbol, date in batch}
            
            for future in as_completed(futures):
                symbol, date = futures[future]
                data = future.result()
                comb_key = f"{symbol}-{date}"
                
                save_nav(symbol, date, data)
                
                if data:
                    total_success += 1
                    status = f"✅ NAV: {data.get('psubtran', 0):,}"
                else:
                    total_failed += 1
                    status = "❌ بدون داده"
                
                processed.add(comb_key)
                if len(processed) % 10 == 0:
                    save_progress(processed)
                
                done = len(processed)
                percent = (done / total_requests) * 100
                print(f"\r   🔄 {done:,}/{total_requests:,} ({percent:.1f}%) - {symbol} {date} {status}", 
                      end="", flush=True)
        
        time.sleep(0.5)
    
    save_progress(processed)
    elapsed = time.time() - start_time
    
    print("\n\n" + "=" * 70)
    print("📊 گزارش نهایی:")
    print(f"   ✅ موفق: {total_success:,}")
    print(f"   ❌ بدون داده: {total_failed:,}")
    print(f"   ⏱️ زمان کل: {elapsed:.0f} ثانیه (~{elapsed/60:.1f} دقیقه)")
    print(f"   📁 داده‌ها در پوشه '{OUTPUT_DIR}' ذخیره شدند.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 متوقف شد توسط کاربر.")