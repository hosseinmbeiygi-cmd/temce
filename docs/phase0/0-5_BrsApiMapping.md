# 0-5 — نقشه BrsApi → مدل داخلی — فاز صفر

> مالک: مالک داده | منبع: صفحه BrsApi + `brsapi/config.py` + `parsers/*`

## ۱. نگاشت سرویس به جدول

| سرویس BrsApi (endpoint) | دسته | جدول خام (`raw_store.source`) | جدول نرمال (`reference DB`) | کلید یکتایی |
|--------------------------|------|-------------------------------|------------------------------|--------------|
| `/Tsetmc/Option.php` | TSETMC | `brsapi.option` | `instruments` + `option_contracts` + `option_snapshots` | `symbol + fetched_at` |
| `/IME/Option.php` | IME | `brsapi.ime_option` | `ime_option_contracts` (جفتی call/put) | `strike + expiry + call_code` |
| `/IME/Future.php` | IME | `brsapi.ime_future` | `future_contracts` | `symbol + expiry` |
| `/IME/Fund.php` | IME | `brsapi.ime_fund` | `fund_nav` + `fund_snapshots` | `symbol + date` |
| `/IME/Certificate.php` | IME | `brsapi.ime_certificate` | `certificate_snapshots` | `symbol + date` |
| `/IME/Physical.php` | IME | `brsapi.ime_physical` | `physical_trades` | `symbol + date + trade_id` |

## ۲. نگاشت فیلد نمونه — آپشن TSETMC

| فیلد BrsApi | فیلد داخلی | نوع | توضیح |
|-------------|------------|-----|-------|
| `l18` | `symbol` | TEXT | نماد اختیار |
| `base_l18` | `underlying_symbol` | TEXT | نماد پایه |
| `price_strike` | `strike_price` | NUMERIC | اعمال |
| `interest_open` | `open_interest` | INT | |
| `date_end` | `expiry_date` | DATE | سررسید |
| `pmin/pmax/pf/pl/pc` | `price_*` | NUMERIC | OHLC |
| `tvol/tval` | `trade_volume/value` | BIGINT | |
| `qd/pd` (1-5) | `bid/ask levels` | JSONB | ۵ سطح |
| `day_remain` | `days_remaining` | INT | |
| `fetched_at` | `fetched_at` | TIMESTAMPTZ | زمان دریافت |

> همین نگاشت برای هر سرویس در `parsers/tsetmc.py` و `parsers/ime.py` مستند و تست می‌شود.

## ۳. تست سازگاری
- برای هر endpoint یک فایل نمونه `tests/fixtures/brsapi/{option,ime_option}_sample.json` نگهداری و در CI با schema مقاسیه می‌شود
- تغییر فیلد بدون bump `schema_version` → CI قرمز

## ۴. سهمیه (وابسته به runbook فاز ۱)
- TSETMC: 18 req/min (از config فعلی) — آینده در `brsapi/config.py` متمرکز
- IME: 12 req/min — هر ۵ دقیقه در ساعات بازار
