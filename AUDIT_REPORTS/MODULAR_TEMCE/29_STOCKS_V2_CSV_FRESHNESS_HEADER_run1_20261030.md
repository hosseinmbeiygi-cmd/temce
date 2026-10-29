# ۲۹ — API-05 تکمیلی ۲: هدر `X-Data-As-Of` برای CSV تاریخچه

**تاریخ:** 2026-10-30
**دامنه:** `apps/api/endpoints/stocks_v2.py::export_history_csv` + تست
**وضعیت:** DONE (اصلاح + تست RED→GREEN)
**نسخه:** run1 — گزارش‌های قبلی بازنویسی نشدند.

---

## ۱. Git و وضعیت محیط

| فیلد | مقدار |
|---|---|
| شاخه | `integration/golddesk-fixes` |
| HEAD (شروع این مرحله) | `6383b6a93ce4fb85848768cffff17872fd6f74ef` |
| `staged` (مجموعهٔ عامل هم‌زمان) | ۱۳۰ فایل — دست‌نخورده ماند |
| snapshot | `AUDIT_REPORTS/MODULAR_TEMCE/_snapshots/t23-post-commit.txt` |
| PostgreSQL / Redis / Docker | در دسترس نیست → موارد وابسته BLOCKED |

---

## ۲. یافته (پایان‌بخش API-05)

در گزارش ۲۸ همهٔ مسیرهای `/stocks/v2` پاکت `data_as_of` گرفتند، به‌جز یک مسیر:

`GET /stocks/v2/{symbol}/history/export.csv` یک `StreamingResponse` است و اصلاً پاکت JSON ندارد؛
پس قرارداد تازگی روی آن حتی قابل بیان نبود. کلاینت (دکمهٔ دانلود در
`frontend/src/components/StockIntelligencePanel.tsx`) فایلی می‌گرفت که هیچ جای آن مشخص نبود
داده مربوط به کدام تاریخ معاملاتی است.

**شدت:** P3 (بدهی قرارداد؛ داده درست بود، انتساب زمانی فایل نامعلوم).

---

## ۳. علت ریشه‌ای

مکانیزم envelope برای پاسخ‌های باینری/جریانی کار نمی‌کند؛ الگوی صحیح، انتقال متادیتای
تازگی در هدر پاسخ است — که در این ماژول پیاده نشده بود.

---

## ۴. اصلاح (کمینه)

در `export_history_csv`، پیش از ساخت `StreamingResponse`:

```python
headers = {"Content-Disposition": f"attachment; filename={symbol}_history.csv"}
data_as_of = _newest_ts(c.get("date") for c in candles)
if data_as_of is not None:
    headers["X-Data-As-Of"] = data_as_of
```

- مقدار از `date` آخرین کندلِ **سروشده** مشتق می‌شود (نه زمان درخواست).
- اگر کندلی وجود نداشته باشد هدر **حذف** می‌شود (نه رشتهٔ خالی) تا «نامعلوم» با «تاریخ واقعی» قاطی نشود.
- هیچ تغییری در بدنهٔ CSV، فیلتر تعدیل یا `Content-Disposition` ایجاد نشد.

---

## ۵. تست (RED → GREEN)

دو تست جدید در `tests/unit/api/test_stocks_v2_freshness_envelope.py`:

- `test_history_csv_exports_the_data_as_of_header` → هدر برابر آخرین `date` کندل + صحت سرصفحهٔ CSV.
- `test_history_csv_omits_the_header_when_there_is_no_data` → نبود هدر وقتی داده نیست.

| مرحله | فرمان | نتیجه |
|---|---|---|
| RED | `python -m pytest tests/unit/api/test_stocks_v2_freshness_envelope.py -q -p no:cacheprovider --no-header` | `1 failed, 12 passed` — `KeyError: 'x-data-as-of'` |
| GREEN | همان فرمان | `13 passed, 1 warning in 72.10s` |
| lint | `python -m ruff check apps/api/endpoints/stocks_v2.py tests/unit/api/test_stocks_v2_freshness_envelope.py` | `All checks passed!` (exit 0) |

---

## ۶. رگرسیون

| فرمان | نتیجه |
|---|---|
| `python -m pytest tests/unit/api/test_market_freshness_envelope.py tests/unit/api/test_market_endpoint_contracts.py tests/unit/api/test_market_aggregate_cache.py tests/unit/api/test_market_dashboard_aggregates.py tests/unit/api/test_stocks_v2_freshness_envelope.py -q -p no:cacheprovider --no-header` | `60 passed` در ۷۷.۳۶s |

(رگرسیون کامل `tests/unit/api` در گزارش ۲۸ اجرا شد: `325 passed` و ۷ خطای
`Cannot connect to PostgreSQL database` از `core/database.py:180` که وابسته به محیط و
خارج از دامنهٔ این تغییر است.)

---

## ۷. محدودیت‌ها

- تست‌ها DB-free هستند؛ محتوای واقعی CSV روی PostgreSQL verify نشد (BLOCKED).
- مصرف‌کنندهٔ فرانت‌اند (لینک دانلود) هنوز هدر را نمی‌خواند؛ استفاده از آن یک گام UI است و
  در این مرحله انجام نشد تا دامنهٔ تغییر کوچک بماند.

---

## ۸. فایل‌های تغییرکرده (این مرحله)

| فایل | نوع |
|---|---|
| `apps/api/endpoints/stocks_v2.py` | اصلاح (هدر + ۴ خط) |
| `tests/unit/api/test_stocks_v2_freshness_envelope.py` | +۲ تست (۱۳ کل) |
| `AUDIT_REPORTS/MODULAR_TEMCE/29_STOCKS_V2_CSV_FRESHNESS_HEADER_run1_20261030.md` | این گزارش |

**معیار پذیرش این مرحله (محقق‌شده):** تنها مسیر باقی‌ماندهٔ بدون سیگنال تازگی در `/stocks/v2`
حالا `X-Data-As-Of` را از دادهٔ سروشده منتشر می‌کند؛ در نبود داده هدر حذف می‌شود؛ ۲ تست جدید
RED→GREEN و ruff پاک.

---

## ۹. وضعیت تجمیعی `/stocks/v2` (پایان زنجیرهٔ API-05)

| مسیر | تازگی |
|---|---|
| tape / signal | `quoted_at` |
| indicators | `computed_at` |
| codal | جدیدترین `publish_date` |
| news | جدیدترین `published_at` |
| history | آخرین `date` کندل |
| history/export.csv | هدر `X-Data-As-Of` |
| market-pulse | `indicator_date` |
| peers / dossier / volume-profile / monitoring | `data_as_of: null` صریح |

**باقی‌ماندهٔ باز (خارج از این مرحله):** `tests/unit/jobs` regression در این نشست اجرا نشد؛
موارد نیازمند PostgreSQL/Redis/Docker همچنان BLOCKED هستند.
