# Full `pytest tests/` run — evidence

- **Start (UTC):** 2026-10-29T14:08:42Z
- **End (UTC):** ~2026-10-29T14:45Z
- **HEAD at start:** `6e0ac36d` (my commit)
- **HEAD at end:** `46946947` — **۵ commit جدید از عامل هم‌زمان** در بازهٔ 14:15–14:39Z روی tree اضافه شد
- **Working tree:** برای فایل‌های `6e0ac36d` در شروع اجرا diff صفر بود؛ اما tree در طول اجرا تغییر کرد ⇒ نتایج یک snapshot واحد نیستند (ریسک اندازه‌گیری، نه لزوماً تغییر نتایج)
- **Python:** 3.11.9 (venv)، pytest 9.1.1
- **روش:** هر بخش در یک process جدا؛ سقف زمانی `timeout 540s` برای هر بخش

## ۱) exit code هر بخش

| بخش | فرمان | exit | passed | failed | skipped | errors | duration |
|---|---|---|---|---|---|---|---|
| root | `pytest tests/` (بدون زیرپوشه‌ها؛ دو اسکریپت DB و legacy مستثنی) | **1** | 95 | 30 | 1 | 1 | 307s |
| misc | `tests/comprehensive tests/fixtures tests/iran_market_data tests/performance` | **1** | 259 | 98 | 0 | 0 | 381s |
| e2e | `tests/e2e` | **1** | 10 | 18 | 1 | 13 | 114s |
| gold_integration | `tests/gold_desk tests/integration` | **1** | 484 | 8 | 5 | 2 | 131s |
| unit_services_a | نیمهٔ اول `tests/unit/services` (۶۲ فایل) | **1** | 1314 | 13 | 10 | 0 | 49s |
| unit_services_b | نیمهٔ دوم `tests/unit/services` (۶۲ فایل) | **0** | 1957 | 0 | 15 | 0 | 139s |
| unit_backtesting | `tests/unit/backtesting` | **0** | 395 | 0 | 1 | 0 | 10s |
| unit_jobs | `tests/unit/jobs` | **0** | 222 | 0 | 0 | 0 | 18s |
| unit_api_a | نیمهٔ اول `tests/unit/api` (۱۶ فایل) | **1** | 165 | 7 | 0 | 0 | 96s |
| unit_api_b | نیمهٔ دوم `tests/unit/api` (۱۵ فایل) | **0** | 149 | 0 | 5 | 0 | 64s |
| unit_core_options_ml_brsapi | `tests/unit/{core,options,ml,brsapi}` | **1** | 848 | 4 | 0 | 0 | 102s |
| unit_rest | `tests/unit/{repositories,providers,domain,ingestion,currency,scripts,gold_desk,parsers,orchestration,monitoring,observability,decision_engine_v5,apps,admin}` | **0** | 449 | 0 | 0 | 0 | 37s |
| **جمع** | — | — | **6347** | **178** | **38** | **16** | ~24 دقیقه |

بخش‌های اجرانشده به‌عمد:
- `tests/legacy/` — ۲۲ اسکریپت که در زمان import به شبکه/سرویس زنده وصل می‌شوند (`conftest.collect_ignore`)؛ اجرا = نقض ممنوعیت شبکهٔ زنده.
- `tests/load/` — فایل تست ندارد.
- `tests/test_screener_flow.py` و `tests/test_sync_2.py` — در زمان import `asyncio.run()` اجرا می‌کنند و به PostgreSQL وصل می‌شوند ⇒ collection error؛ اسکریپت‌اند نه تست.

## ۲) دسته‌بندی شکست‌ها

| علت | تعداد تقریبی | نمونه |
|---|---|---|
| PostgreSQL در دسترس نیست / اعتبار اشتباه | ~۱۵۵ | `Cannot connect to PostgreSQL … localhost:5432/market`، `asyncpg.InvalidPasswordError` |
| سرویس/سرور زنده لازم است (e2e/comprehensive/all_pages) | ~۳۰ | `assert resp.status_code == 200`، CORS، backtest API |
| شبکهٔ زنده | ۱ | `tests/test_raw.py` — `httpx.ConnectTimeout` |
| **منطق واقعی** | **۶** | `tests/unit/services/test_indicator_calculation.py` (Stochastic/Ichimoku) |
| **جمع** | **~۱۹۴** | — |

## ۳) تنها رگرسیون واقعی — NEW-01

`MarketService._compute_indicator` در مسیر `stochastic`/`ichimoku` بین `be8b4ff4` و `6e0ac36d` تغییر کرده و `d_line` را با تکرار مقدار اول به طول `k_line` می‌رساند:

```
# Align d_line to same length as k_line by padding with first value
if len(d_line) < len(k_line):
    d_line = d_line + [d_line[0]] * (len(k_line) - len(d_line))
```

- تست‌ها (`test_stochastic_lengths` و ۵ تست دیگر) انتظار دارند `%D = SMA(3)` از `%K` باشد (۷ مقدار در برابر ۹) و شکست می‌خورند (`assert 9 == 7`).
- این تغییر از کار uncommitted عامل دیگر وارد commit `6e0ac36d` شده بود (فایل مشترک `services/market_service.py`).
- اثر: نقاط نمایشی `%D` جعلی/تکرارشونده می‌شوند؛ قرارداد تست شکسته است.
- پیشنهاد: حذف این padding (بازگشت به طول واقعی) یا اگر UI به طول برابر نیاز دارد، هم‌ترازی باید در لایهٔ نمایش با `null` انجام شود، نه با تکرار مقدار.

## ۴) محدودیت‌های اجرا

- اجرا روی tree در حال حرکت انجام شد (۵ commit جدید در میانهٔ اجرا). برای release gate باید دوباره روی HEAD پایدار اجرا شود.
- هیچ تست وابسته به DB به‌دلیل نبودِ PostgreSQL/اعتبار، PASS محسوب نشده است؛ خروجی آن‌ها `FAILED` است نه skip (نقص marker `needs_db`).
