# ============================================
#  راهنمای تست دستی BrsApi
# ============================================

## ۱. تست سریع با cURL

### تست اتصال
```bash
curl -s "https://Api.BrsApi.ir/Market/Commodity.php?key=YOUR_BRSAPI_API_KEY" | python -m json.tool
```

### دریافت کامودیتی‌ها
```bash
curl -s "https://Api.BrsApi.ir/Market/Commodity.php?key=YOUR_BRSAPI_API_KEY" > commodity.json
```

### دریافت ارزهای دیجیتال
```bash
curl -s "https://Api.BrsApi.ir/Market/Cryptocurrency.php?key=YOUR_BRSAPI_API_KEY" > crypto.json
```

### دریافت طلا و سکه
```bash
curl -s "https://Api.BrsApi.ir/Market/Coin.php?key=YOUR_BRSAPI_API_KEY" > gold.json
```

### دریافت نرخ ارز
```bash
curl -s "https://Api.BrsApi.ir/Market/Currency.php?key=YOUR_BRSAPI_API_KEY" > currency.json
```

---

## ۲. استفاده از اسکریپت پایتون

### نصب پیش‌نیازها
```bash
pip install httpx python-dotenv psycopg2-binary
```

### اجرای اسکریپت
```bash
# تست اتصال
python test_brsapi_manual.py --test

# نمایش لیست API ها
python test_brsapi_manual.py --list

# دریافت یک بخش خاص
python test_brsapi_manual.py --section commodity
python test_brsapi_manual.py --section crypto
python test_brsapi_manual.py --section gold_coin
python test_brsapi_manual.py --section currency

# دریافت تمام داده‌ها
python test_brsapi_manual.py --all
```

---

## ۳. استفاده از فایل BAT (ویندوز)

```bash
# اجرای فایل
test_brsapi.bat

# سپس عدد مورد نظر را انتخاب کنید:
# 1 = تست اتصال
# 2 = کامودیتی‌ها
# 3 = ارزهای دیجیتال
# 4 = طلا و سکه
# 5 = نرخ ارز
# 6 = تمام داده‌ها
```

---

## ۴. API Endpoints موجود

| نام | آدرس |
|-----|------|
| کامودیتی‌ها | `/Market/Commodity.php` |
| ارزهای دیجیتال | `/Market/Cryptocurrency.php` |
| طلا و سکه | `/Market/Coin.php` |
| نرخ ارز | `/Market/Currency.php` |
| تغییرات ۲۴ ساعته طلا | `/Market/Gold24h.php` |
| تغییرات ۲۴ ساعته ارز | `/Market/Currency24h.php` |
| تمام نمادها | `/Tsetmc/AllSymbols.php` |
| شاخص‌ها | `/Tsetmc/Index.php` |

---

## ۵. ذخیره در پایگاه داده

اسکریپت `test_brsapi_manual.py` به صورت خودکار داده‌ها را در جداول زیر ذخیره می‌کند:

- `brsapi_commodities` - کامودیتی‌ها
- `brsapi_crypto` - ارزهای دیجیتال
- `brsapi_gold_coin` - طلا و سکه
- `brsapi_currency` - نرخ ارز

برای مشاهده داده‌های ذخیره شده:
```sql
SELECT * FROM brsapi_commodities ORDER BY created_at DESC LIMIT 10;
SELECT * FROM brsapi_crypto ORDER BY created_at DESC LIMIT 10;
SELECT * FROM brsapi_gold_coin ORDER BY created_at DESC LIMIT 10;
SELECT * FROM brsapi_currency ORDER BY created_at DESC LIMIT 10;
```

---

## ۶. عیب‌یابی مشکل عدم دریافت داده

### ۱. بررسی اتصال اینترنت
```bash
ping Api.BrsApi.ir
```

### ۲. بررسی API Key
مطمئن شوید API Key در فایل `.env` صحیح است:
```
BRSAPI_API_KEY=YOUR_BRSAPI_API_KEY
```

### ۳. بررسی پاسخ API
```bash
curl -v "https://Api.BrsApi.ir/Market/Commodity.php?key=YOUR_BRSAPI_API_KEY"
```

### ۴. بررسی خطاهای رایج
- `HTTP 429`: محدودیت تعداد درخواست‌ها - صبر کنید
- `HTTP 403`: API Key نامعتبر
- `HTTP 500`: خطای سرور BrsApi

---

## ۷. نکات مهم

1. **رعایت محدودیت‌ها**: بیش از ۳۰ درخواست در دقیقه ارسال نکنید
2. **User-Agent**: حتماً هدر User-Agent ارسال کنید
3. **ذخیره‌سازی**: داده‌ها را در فایل JSON ذخیره کنید تا درخواست تکراری ندهید
4. **تاخیر**: بین درخواست‌ها حداقل ۱ ثانیه تاخیر بگذارید
