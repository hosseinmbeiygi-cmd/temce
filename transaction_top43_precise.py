import requests
import json
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import sys
from datetime import datetime, timedelta
import jdatetime
import logging

# ========== تنظیمات ==========
API_KEY = "Bk7JvdJZBHJ9DMhzeuTfWjwqYy1wMsif"
BASE_URL = "https://Api.BrsApi.ir/Tsetmc/Transaction.php"
OUTPUT_DIR = "transaction_all_symbols"
MAX_WORKERS = 4          # کاهش تردها برای پایداری بیشتر
RATE_LIMIT_5MIN = 500
RATE_WINDOW = 300
DAILY_LIMIT = 10000
DAYS_BACK = 30
# =============================

# ========== لیست کامل نمادها (بیش از ۴۰۰ نماد) ==========
SYMBOLS = [
    "وپارس", "لازما", "وگردش", "پارسيان", "وبملت", "حفاري", "آسيا", "ونفت",
    "ومدير", "شصفها", "شساخت", "داتام", "آواپارس", "وصنعت", "حآفرين", "وساپا",
    "وساغربي", "اتكام", "رايا", "واعتبار", "وسلرستا", "ولساپا", "وسكهبو",
    "وسبحان", "وسكرد", "البرز", "وفتخار", "وارس", "وتوصا", "وسيلام", "وتوكا",
    "مديريت", "وسكرمان", "وساشرقي", "رمپنا", "توسن", "وسپهر", "تنوين", "سمگا",
    "معين", "وتوشه", "بتيس", "اتكاي", "مهر", "پرديس", "ولبهمن", "ثاميد",
    "فاراك", "وآفري", "شتهران", "وسكرشا", "تملت", "فن افزار", "فتوسا", "وسهمدا",
    "داراب", "ختور", "تايرا", "شاوان", "قجام", "وشهر", "كوثر", "اسياتك",
    "وپويا", "وبهمن", "بنيرو", "دلقما", "ثبهساز", "وتجارت", "ما", "وبصادر",
    "پاسا", "تكيميا", "وسپه", "خكار", "كاما", "توريل", "تفارس", "الكتروماد",
    "فسوژ", "وسرمد", "شتران", "وتوسم", "وهامون", "تكاردان", "خزر", "وبوعلي",
    "بهپاك", "شكبير", "ودي", "وخاور", "كيميا", "وكار", "وصنا", "شتوكا",
    "فسبزوار", "غويتا", "بترانس", "فگستر", "خيمن", "خديزل", "وليز", "سرچشمه",
    "فسازان", "ختراك", "وپاسار", "لخزر", "رهياب", "وسينا", "پي پاد", "غبهار",
    "وكبهمن", "وسگلستا", "وسصفا", "پكوير", "اعتلا", "خموتور", "لوتوس", "اميد",
    "بفجر", "فجر", "ساروج", "تبرك", "كاذر", "كهمدا", "ثجنوب", "شبصير", "شملي",
    "فسپا", "همراه", "تماوند", "سامان", "ونوين", "وپست", "چافست", "سهگمت",
    "خودكفا", "والماس", "فافق", "پارس", "كنور", "غدشت", "كساوه", "نيان",
    "حكشتي", "دحاوي", "چدن", "وپايا", "قاروم", "كربن", "جم پيلن", "غزر",
    "خلنت", "سنوين", "وجامي", "كباده", "گدنا", "رافزا", "ملت", "بتهران",
    "سجام", "حتوكا", "واحيا", "شكربن", "ثپهران", "لبوتان", "بازرگام", "شنفت",
    "بموتو", "شجم", "مهرگان", "سقاين", "شسپا", "فزرين", "امين", "سخوز",
    "دشيري", "غشهد", "محتشم", "سفانو", "شپاكسا", "كپارس", "سصوفي", "ويسا",
    "ولاعتماد", "شبريز", "شدوص", "كلوند", "رانيز", "شبندر", "وسكاب", "ساروم",
    "ونيرو", "كمنگنز", "سبجنو", "شپارس", "شصدف", "فاما", "ريشمك", "پتاير",
    "اتكاسا", "سآبيك", "سيدكو", "شهر", "وكادو", "وآداك", "اردستان", "شپديس",
    "كحافظ", "حخزر", "شمواد", "جوين", "اخابر", "فرود", "سپيد", "ستران",
    "مرقام", "آريا", "سباقر", "آواك", "شكام", "قچار", "خريخت", "وايرا",
    "قمرو", "سبهان", "مارون", "دابور", "سمازن", "سهرمز", "سخزر", "انتخاب",
    "فافزا", "وپترو", "فنورد", "قلرست", "لكما", "گوهران", "بسويچ", "سشرق",
    "غشصفا", "فنفت", "جم", "صبا", "سكرد", "فجام", "پتوسعه", "غشهداب",
    "ثباغ", "وآوا", "سيسكو", "كوير", "فارس", "سخاش", "فولاد", "مبين",
    "ونيكي", "وسمازن", "شپاس", "بكابل", "سشمال", "سپاها", "عاليس", "شفام",
    "غديس", "فنر", "وبيمه", "ولصنم", "بشهاب", "اپال", "كگهر", "شسينا",
    "قشير", "سغرب", "زفجر", "كطبس", "غشاذر", "زفارس", "نتوس", "خبرنا",
    "بنو", "رنيك", "غگلستا", "غسالم", "كگاز", "بپويا", "وسفارس", "زكشت",
    "حتايد", "وثنو", "حپارسا", "شپنا", "فوكا", "ددانا", "پخش", "غپآذر",
    "ولراز", "شكلر", "حپرتو", "بانيان", "دبالك", "آردينه", "سكرما", "پيزد",
    "ددام", "كايزد", "كتوكا", "شگويا", "بجهرم", "ولكار", "حسينا", "كاوه",
    "دالبر", "غمينو", "ارفع", "كرازي", "حريل", "ساراب", "ناما", "غگلپا",
    "زمگسا", "ودانا", "رپويا", "خچرخش", "قاسم", "ومپنا", "خبازرس", "شبهرن",
    "كلر", "مهرمام", "سنير", "زشريف", "شغدير", "نان", "فخاس", "زبينا",
    "واميد", "زفكا", "قشهد", "غدانه", "كيسون", "فغدير", "سرود", "درهآور",
    "پكرمان", "وحافظ", "ساينا", "درازك", "ولنوين", "قزوين", "زهلال",
    "سغدير", "دفارا", "ذرت", "زشگزا", "وصندوق", "قپيرا", "شرانل", "ساربيل",
    "چاپ", "فروي", "فاذر", "فروسيل", "گنگين", "سمتاز", "شگل", "فخوز",
    "كرماشا", "داترا", "وغدير", "ثرود", "وبانك", "زدشت", "كوچين", "كيمازي",
    "غشان", "تليسه", "فايرا", "دتماد", "چكارن", "گشان", "كگل", "خمحور",
    "قرن", "دسينا", "زكوثر", "غچين", "فصبا", "سصفها", "غگل", "غپينو",
    "كچاد", "ساوه", "زقيام", "آلومينا", "خراسان", "كيمياتك", "چخزر",
    "ومهان", "شاراك", "خنور", "شيران", "سيمرغ", "وسيزد", "وهور", "فهامون",
    "بخاور", "نمرينو", "زملارد", "شيراز", "بيوتيك", "حبندر", "دماوند",
    "حگهر", "غفارس", "نيشكر", "دتوزيع", "بوعلي", "نيروترانسفو", "وسمركز",
    "غمايه", "حسير", "وسيستا", "فلوله", "بمولد", "فولاي", "پرداخت",
    "دكپسول", "شراز", "دپارس", "دسبحان", "ثمسكن", "دارو", "شفارا", "وسقم",
    "قصفها", "دلر", "گكوثر", "وخارزم", "دزهراوي", "پاكشو", "غصينو", "قيستو",
    "بپيوند", "هجرت", "فنوال", "هانيكو", "فباهنر", "وسزنجان", "شاملا",
    "زگلدشت", "غاذر", "وفيروزه", "وامين", "كتوسعه", "كپرور", "غمهرا",
    "خنصير", "كپرسپوليس", "كسرا", "سفارس", "كاسپين", "غشوكو", "سفاسي",
    "كفرآور", "دزاگرس", "مداران", "كانسار", "غانيزان", "شيفته", "پترول",
    "نوري", "نخريس", "واتي", "وآتوس", "ولپارس", "ثجوان", "شليا", "كاريز",
    "اخشان", "سفار", "داوه", "آريان", "فپنتا", "كپشير", "بكاب", "شفارس",
    "حگردش", "ومعادن", "شمس", "كالا", "سليم", "تپكو", "بگيلان", "ولقمان",
    "دقاضي", "باران", "وتوسكا", "دجابر", "قهكمت", "كفپارس", "فولاژ",
    "كدما", "استقلال", "شوينده", "غپونه", "اروند", "دشيمي", "رتاپ",
    "غبشهر", "كخاك", "فلامي", "كسعدي", "وحكمت", "تپمپي", "قتربت",
    "وساخت", "والبر", "وطوبي", "بمپنا", "بهير", "شفا", "ذوب", "كيانا",
    "شخارك", "فروس", "وبرق", "آ س پ", "سبزوا", "بزندگي", "افق", "پدرخش",
    "نطرين", "پشاهن", "شستا", "سيتا", "وملت", "لسرما", "وبشهر", "ولشرق",
    "سيستم", "خعمرا", "كولان", "خرينگ", "فبيرا", "خكاوه", "لطيف", "كصدف",
    "سدشت", "غكورش", "تكمبا", "ولتجار", "قنيشا", "بزاگرس", "زنگان",
    "كي بي سي", "تاپيكو", "فزر", "دفرا", "خكرمان", "ركيش", "فملي",
    "خشرق", "كماسه", "سپيدار", "لپارس", "دعبيد", "داسوه", "ماديرا",
    "ثشاهد", "غپاك", "شفن", "گلديرا", "وسرضوي", "خاور", "وكغدير",
    "شاروم", "ثاخت", "وآرين", "كمرجان", "پارسان", "شلعاب", "شگستر",
    "زاگرس", "لابسا", "كبافق", "بهامرز", "وتوس", "دسبحا", "پارتا",
    "بپرديس", "تيپيكو", "تاصيكو", "حآسا", "فرآور", "ثشرق", "كروميت",
    "ثپرديس", "غبهنوش", "ثغرب", "بپاس", "سپ", "سلار", "پسهند",
    "دكيمي", "حيات", "هرمز", "غگيلا", "خصدرا", "حپترو", "ورازي",
    "خفنر", "وامير", "فرابورس", "نوين", "بورس", "بالاس", "سيلام",
    "غناب", "رتكو", "گكيش", "قثابت", "نبابك", "آرمان", "معيار",
    "خپويش", "فن آوا", "ورنا", "زپارس", "فماك", "ولغدر", "كابگن",
    "بساما", "اپرداز", "دكوثر", "غمارگ", "وايران", "چنوپا", "ولملت",
    "ديران", "وپخش", "تاديكو", "فجهان", "آبين", "وآفر", "تاپكيش",
    "افرا", "خزاميا", "وتعاون", "شلرد", "كمينا", "حفارس", "ثامان",
    "خبهمن", "آبادا", "خگستر", "ثفارس", "پلوله", "كورز", "بالبر",
    "رانفور", "وسگيلا", "غنوش", "تاتمس", "كيا", "وساربيل", "حشكوه",
    "قشكر", "ثتوسا", "سكارون", "فسا", "انرژي", "رفاه", "خكمك",
    "فبستم", "وسخراج", "تجلي", "پاريز", "بايكا", "كساپا", "وفردا",
    "شپلي", "حرهشا", "دامين", "ثنور", "وسبوشهر", "خفناور", "ثالوند",
    "پلاست", "ثقزوي", "درپاد", "وملي", "تكنو", "خمحركه", "غگز",
    "شگامرن", "گپارس", "ميدكو", "شستان", "ثنوسا", "خفولا", "مفاخر",
    "فطلوع"
]

# حذف تکراری‌ها (اختیاری)
SYMBOLS = list(set(SYMBOLS))
print(f"تعداد نمادهای یکتا: {len(SYMBOLS)}")

# ============================================================

os.makedirs(OUTPUT_DIR, exist_ok=True)
file_lock = Lock()

# ========== راه‌اندازی لاگ ==========
logging.basicConfig(
    filename='fetch_errors.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

# ============================================================
# کلاس کنترل نرخ ۵ دقیقه‌ای (بدون قفل طولانی)
# ============================================================
class PreciseRateLimiter:
    def __init__(self, max_requests, window_seconds):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.window_start = time.time()
        self.request_count = 0
        self.lock = Lock()
    
    def wait_if_needed(self):
        with self.lock:
            now = time.time()
            elapsed = now - self.window_start
            
            if elapsed >= self.window_seconds:
                self.window_start = now
                self.request_count = 0
            
            if self.request_count >= self.max_requests:
                wait_time = self.window_seconds - elapsed + 0.1
                if wait_time > 0:
                    # آزاد کردن قفل قبل از sleep
                    self.lock.release()
                    print(f"\n⏳ محدودیت {self.max_requests} درخواست در {self.window_seconds//60} دقیقه! {wait_time:.1f} ثانیه صبر می‌کنم...", end="", flush=True)
                    time.sleep(wait_time)
                    self.lock.acquire()
                    self.window_start = time.time()
                    self.request_count = 0
            
            self.request_count += 1

rate_limiter = PreciseRateLimiter(RATE_LIMIT_5MIN, RATE_WINDOW)

# ============================================================
# کلاس کنترل محدودیت روزانه (با ذخیره در فایل)
# ============================================================
class DailyRateLimiter:
    def __init__(self, daily_limit, counter_file):
        self.daily_limit = daily_limit
        self.counter_file = counter_file
        self.lock = Lock()
        self.load_counter()
    
    def load_counter(self):
        if os.path.exists(self.counter_file):
            try:
                with open(self.counter_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    today = jdatetime.date.today().strftime('%Y-%m-%d')
                    if data.get('date') == today:
                        self.count = data.get('count', 0)
                        self.date = today
                        print(f"📊 شمارنده روزانه: {self.count}/{self.daily_limit} (امروز)")
                        return
            except:
                pass
        self.count = 0
        self.date = jdatetime.date.today().strftime('%Y-%m-%d')
        self.save_counter()
    
    def save_counter(self):
        with open(self.counter_file, 'w', encoding='utf-8') as f:
            json.dump({
                'date': self.date,
                'count': self.count,
                'daily_limit': self.daily_limit,
                'last_update': datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
    
    def wait_if_needed(self):
        with self.lock:
            today = jdatetime.date.today().strftime('%Y-%m-%d')
            if today != self.date:
                self.date = today
                self.count = 0
                self.save_counter()
                print(f"\n📅 روز جدید شروع شد. شمارنده ریست شد.")
            
            if self.count >= self.daily_limit:
                print(f"\n🚫 محدودیت روزانه {self.daily_limit} درخواست به پایان رسید!")
                print(f"   امروز {self.count} درخواست ارسال شده.")
                print("   برای ادامه، صبر کنید تا فردا (ساعت ۰۰:۰۰) یا کلید API خود را تغییر دهید.")
                print("   برنامه متوقف می‌شود...")
                sys.exit(0)
    
    def increment(self):
        with self.lock:
            self.count += 1
            self.save_counter()

daily_limiter = DailyRateLimiter(DAILY_LIMIT, f"{OUTPUT_DIR}/daily_counter.json")

# ============================================================
# توابع کمکی
# ============================================================
def get_trading_days():
    today = jdatetime.date.today()
    start = today - timedelta(days=DAYS_BACK)
    days = []
    current = start
    while current <= today:
        if current.weekday() < 5:
            days.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=1)
    return days

def fetch_transaction(symbol, date):
    daily_limiter.wait_if_needed()   # بررسی محدودیت روزانه
    
    url = f"{BASE_URL}?key={API_KEY}&l18={symbol}&date={date}"
    rate_limiter.wait_if_needed()
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            data = response.json()
            # فقط در صورت موفقیت شمارنده را افزایش بده
            daily_limiter.increment()
            return data
        else:
            logging.error(f"HTTP {response.status_code} for {symbol} on {date}")
            return None
    except Exception as e:
        logging.error(f"Error fetching {symbol} on {date}: {e}")
        return None

def save_transaction(symbol, date, data):
    if not data or not isinstance(data, list):
        return
    
    filename = f"{OUTPUT_DIR}/{symbol}.json"
    with file_lock:   # قفل برای نوشتن ایمن
        existing = []
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            except:
                pass
        
        new_entry = {
            'date': date,
            'count': len(data),
            'transactions': data
        }
        
        existing = [e for e in existing if e.get('date') != date]
        existing.append(new_entry)
        existing.sort(key=lambda x: x.get('date', ''))
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

def get_progress():
    progress_file = f"{OUTPUT_DIR}/progress.json"
    if os.path.exists(progress_file):
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {'processed': [], 'total_requests': 0}   # processed: list of "symbol-date"

def save_progress(processed_list, total_requests):
    progress_file = f"{OUTPUT_DIR}/progress.json"
    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump({
            'processed': processed_list,
            'total_requests': total_requests,
            'last_update': datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)

def main():
    print("=" * 70)
    print("🚀 دریافت ریزمعاملات یک ماه اخیر برای تمام نمادها")
    print("=" * 70)
    print(f"📊 تعداد نمادها: {len(SYMBOLS)}")
    
    days = get_trading_days()
    print(f"📅 تعداد روزهای معاملاتی یک ماه اخیر: {len(days)}")
    print(f"   از {days[0]} تا {days[-1]}")
    
    total_requests = len(SYMBOLS) * len(days)
    print(f"📊 تعداد کل درخواست‌ها: {total_requests:,}")
    print(f"⏱️ محدودیت‌ها:")
    print(f"   - {RATE_LIMIT_5MIN} درخواست در {RATE_WINDOW//60} دقیقه")
    print(f"   - {DAILY_LIMIT:,} درخواست در روز")
    
    minutes_5min = (total_requests / RATE_LIMIT_5MIN) * 5
    days_needed = total_requests / DAILY_LIMIT
    print(f"⏱️ زمان تقریبی (با محدودیت ۵ دقیقه‌ای): {minutes_5min:.1f} دقیقه")
    if days_needed > 1:
        print(f"⚠️ این تعداد درخواست ({total_requests}) از محدودیت روزانه {DAILY_LIMIT} بیشتر است.")
        print(f"   نیاز به {days_needed:.1f} روز برای تکمیل دارید.")
    
    # بارگذاری پیشرفت
    progress = get_progress()
    processed_set = set(progress.get('processed', []))
    total_requests_done = len(processed_set)
    print(f"\n📂 {total_requests_done} ترکیب (نماد-روز) قبلاً پردازش شده.")
    
    # ساخت لیست تمام ترکیب‌ها
    all_combinations = [(s, d) for s in SYMBOLS for d in days]
    remaining = [comb for comb in all_combinations if f"{comb[0]}-{comb[1]}" not in processed_set]
    print(f"📂 {len(remaining)} ترکیب باقی مانده.")
    
    if not remaining:
        print("✅ همه ترکیب‌ها پردازش شده‌اند.")
        return
    
    print(f"🚀 تعداد تردهای همزمان: {MAX_WORKERS}")
    print("=" * 70)
    
    start_time = time.time()
    total_successful = 0
    total_failed = 0
    
    # پردازش به صورت دسته‌های کوچک برای نمایش پیشرفت
    batch_size = MAX_WORKERS * 5
    total_batches = (len(remaining) + batch_size - 1) // batch_size
    
    for batch_idx in range(total_batches):
        batch = remaining[batch_idx * batch_size : (batch_idx+1) * batch_size]
        print(f"\n📦 دسته {batch_idx+1}/{total_batches} ({len(batch)} ترکیب)")
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_transaction, symbol, date): (symbol, date) for symbol, date in batch}
            
            for future in as_completed(futures):
                symbol, date = futures[future]
                data = future.result()
                comb_key = f"{symbol}-{date}"
                
                if data and isinstance(data, list) and len(data) > 0:
                    save_transaction(symbol, date, data)
                    total_successful += 1
                    status = f"✅ {len(data):,} رکورد"
                else:
                    total_failed += 1
                    status = "❌ بدون داده"
                
                # ثبت پیشرفت
                processed_set.add(comb_key)
                save_progress(list(processed_set), total_requests)
                
                done = len(processed_set)
                percent = (done / total_requests) * 100
                print(f"\r   🔄 {done:,}/{total_requests:,} ({percent:.1f}%) - {symbol} {date} {status}", end="", flush=True)
        
        time.sleep(0.2)
    
    elapsed = time.time() - start_time
    
    print("\n\n" + "=" * 70)
    print("📊 گزارش نهایی:")
    print(f"   📊 تعداد نمادها: {len(SYMBOLS)}")
    print(f"   📅 تعداد روزهای معاملاتی: {len(days)}")
    print(f"   📊 تعداد کل درخواست‌ها: {total_requests:,}")
    print(f"   ✅ موفق: {total_successful:,}")
    print(f"   ❌ ناموفق: {total_failed:,}")
    print(f"   ⏱️ زمان کل: {elapsed:.0f} ثانیه (~{elapsed/60:.1f} دقیقه)")
    print(f"   📁 داده‌ها در پوشه '{OUTPUT_DIR}' ذخیره شدند.")
    
    # نمایش خلاصه هر نماد (فقط ۲۰ تا اول)
    print("\n📊 خلاصه ۲۰ نماد اول:")
    print(f"{'نماد':<12} {'تعداد روزها':<12} {'تعداد کل رکوردها':<18}")
    print("-" * 45)
    count = 0
    for symbol in SYMBOLS[:20]:
        filename = f"{OUTPUT_DIR}/{symbol}.json"
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                days_count = len(data)
                total_records = sum(day.get('count', 0) for day in data)
                print(f"{symbol:<12} {days_count:<12} {total_records:>15,}")
            except:
                print(f"{symbol:<12} {'خطا':<12}")
        else:
            print(f"{symbol:<12} {'ندارد':<12}")
        count += 1
        if count >= 20:
            break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 متوقف شد توسط کاربر. پیشرفت ذخیره شد.")
        sys.exit(0)