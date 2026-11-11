# QA_STAGE_04 — ممیزی مالکیت بک‌اند API، aggregation، query و cache

**مسیر فایل**: `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_04.md`
**زمان اجرا**: ۲۰۲۶-۱۰-۲۸ (زمان محیط)
**نتیجهِ مرحله**: **PARTIAL** — بخش سالم و با شواهد تأیید شده، بخش‌های وابسته به DB و UI (بخش ۰۵) هنوز اجرا/پیاده‌سازی نشده‌اند.

## ۱. حالت جیت (اثبات‌شده در این مرحله)

- شاخه: `integration/golddesk-fixes`، HEAD: `90597e05b9f4328bcd82ee819a31ba5c55413c12`
- فایل‌های stage‌شده: **۱۳۸ فایل** (۱۰۲ اضافه `+`, ۳۲ تغییر `M`, ۴ `MM`) — شامل اسناد بررسی (`docs/audits/phase-0/*`), کد (`apps/api/endpoints/market.py`, `brsapi/services/query_service.py`, `sync_service.py`, `responses.py`, `app.py`), فونت‌اند (`useMarketData.ts`) و تست‌هایrepositories
- تغییرات ناهم‌استیج (unstaged): **۴ فایل**
- نظردهی (untracked): **۸ فایل** شامل `AUDIT_REPORTS/`, `docs/New folder/`, `tests/unit/api/test_market_aggregate_cache.py` (من نوشته شده) و ۵ فایل تست جدید از_SESSION قبلی
- هیچ commit/reset/clean/checkout/restore یا stash بدون اجازه انجام نشد؛ تمام تغییرات کاربر حفظ می‌شوند.
- مقدار جداگانه `D:\temce._clean_base` یک کپی `locked clean-base` (HEAD detached 4e9e289a) است؛ مخزن فعالیت در `C:\Users\Iran\Desktop\temce` است.

## ۲. فهرست فایل‌های بررسی‌شده و بررسی‌نشده

| # | فایل | سطح | دلیل |
|---|---|---|---|
| 1 | `apps/api/endpoints/market.py` (۷۰۷ خط) | کامل | endpoint + کش `_AGG_CACHE` |
| 2 | `apps/api/dependencies.py` | کامل | فیکتورهای سرویس |
| 3 | `apps/api/router.py` | بخش ۱–۱۲۰ + ثبت روت | مارکر conflict (یافت نشد) |
| 4 | `apps/api/app.py` | بخش مربوط | create_app، /cache-stats، sync_all :۷۰۳ |
| 5 | `brsapi/services/query_service.py` | کامل بخش‌های کلیدی | `get_latest_snapshots` (MAX(id)), `get_symbol_snapshot` |
| 6 | `brsapi/services/sync_service.py` | انتهای فایل + grep invalidate | تایید: هیچ invalidate کش در این فایل وجود ندارد |
| 7 | `schemas/common/responses.py` | کامل | `ApiResponse` بدون کیفیت تازگی |

## ۳. جدول معیارهای پذیرش

| الزام | شاهد | نتیجه | کار باقی‌مانده |
|---|---|---|---|
| API تغییر تازگی/خطا را گمراه‌کننده نکند | تغییرات `ApiResponse`, `_AGG_CACHE`, تست‌های ۲۵۲۹ | انجام‌شده | — |
| کش با تست قابل‌پیش‌بینی باشد | `test_market_aggregate_cache.py` (۶ تست، RC=0) | انجام‌شده | — |
| import/register سالم باشد | `git status`، py_compile OK، سکن بوت `create_app` RC=0 | انجام‌شده | — |
| تازگی و لایه query/`MAX(id)` در چرخه‌ها بررسی شود | `query_service.py:106`، `get_symbol_snapshot` | تأیید‌شده | گزارش در ۱۱ |
| فایل گزارش دقیق در مخزن باشد | `AUDIT_REPORTS/MODULAR_TEMCE/04_BACKEND_API_AGGREGATION_CACHE.md` (۱۸۸ خط، ۲۴KB) | انجام‌شده | — |
| تغییرات UI (فرانت‌اند) | چه‌طور که شامل بخش ۰۵ می‌شود | به اجرارسیده به بخش ۰۵ | بخش ۰۵ حلقه |
| DB-dependent suites (market/watch و غیره) اجرا شوند | `tests/unit/test_backend_api.py` و همسر، بدون PostgreSQL | اجرا نشده | DB محلی/آفلاین یا CI |
| تست‌های ریپازیتوری جدید (bulk_upsert، query_latest_snapshot، ingestion_worker_persistence، storage_layer_params، sync_service_persistence_scope) | فایل‌های نظردهی کاربر | سایر بررسی نشده | کاهش / بررسی |

## ۴. لیست هر اصلاح: فایل، diff، دلیل، تست مرتبط

| اصلاح | فایل | diff (خلاصه) | دلیل | تست مرتبط |
|---|---|---|---|---|
| `ApiResponse.data_as_of` + `cache_hit` | `schemas/common/responses.py` | افزودن دو فیلد اختیاری (backward-compatible) | مصرف‌کننده باید تفاوت `success-empty`، `stale-hit` و `source-failure` را بدهد. | `test_market_aggregate_cache.py` (۶ تست) |
| کش `_AGG_CACHE` زمان نگهداری و `invalidate_agg_cache` | `apps/api/endpoints/market.py` (~:~۵۲۰–۵۵۵) | `tuple[float, value, as_of]`, `_agg_cache_set(key, val, as_of)`, نسل تابع | کش هیت بدون نشانگر staleness؛ زمان افزودن/removing شفاف می‌گردد. | ۶ تست کش (ها، مِس، TTL، invalidate، خالی، خطا) |
| `heatmap` از `latest_fetched` برای `data_as_of` استفاده | `apps/api/endpoints/market.py` (~:۱۱۹) | فعال کردن کد مرده فعلی | کد مرده قبلاً محاسبه می‌شد اما استفاده نمی‌شد. | `test_empty_snapshots_returns_success_false` |
| هیت/مِس endpoints (enriched-heatmap, treemap, asset-allocation, cashflow-by-sector) | `market.py` (~:۲۶۱–۳۵۷، :۶۱۰–۶۳۸، :۶۵۵–۶۷۸) | `cached, cached_as_of = _agg_cache_get(...)` و `cache_hit=True/False`, `data_as_of` | مقادیر کشی می‌توانند به‌هم برسند بدون الگوریتم. | آن‌ها در مجموعه ۶ تست پوشش داده شد |
| invalidate پس از sync | `brsapi/services/sync_service.py` (`sync_all`) | فراخوانی `invalidate_agg_cache()` در انتهای `sync_all` با try/except | دونش از cache‌ها پس از sync، داده‌های قدیمی در UI می‌ماند. | سعی‌های سیستم‌ها (محدود به محیط offline) |
| فایل تست جدید | `tests/unit/api/test_market_aggregate_cache.py` | ۶ تست، تمام ماک‌شده (بدون DB/live net) | پیکربندی خودکار کش را شفاف می‌کند. | اجرای مستقیم: RC=0 در ۲۰.۸s |

| 8 | `core/typing/result.py` | کامل | `Result` / `PaginatedResult` |
| 9 | `core/cache.py` | بخشده | NullCache / CacheService |
| 10 | `brsapi/models/tsetmc.py` | `SymbolSnapshotModel` | `fetched_at`, `created_at`, volumes |
| 11 | `frontend/src/hooks/useMarketData.ts` | مربوط | LiveDataResult, extractArray, consumers |
| 12 | `frontend/src/lib/api.ts` | :۳۰۷–۳۶۱ | extractArray نمی‌چکد success |
| 13 | `frontend/src/lib/goldApi.ts` | مربوط | C3 / GoldAPIError |
| 14 | `tests/unit/api/test_market_dashboard_aggregates.py` | کامل | تست‌های ماک‌شده aggregate |
| 15 | `tests/unit/api/test_market_aggregate_cache.py` | جدید | هیت/مِس/TTL/invalidate/خالی/خطا |

## ۵. فرمان‌های تست و نتایج واقعی

| # | فرمان | خروجی | موفق/ناموفق/نCleanpa |
|---|---|---|---|
| ۱ | `venv/Scripts/python.exe -m pytest tests/unit/test_backend_api.py::test_health_check -q -o addopts=''` | `RC=0` (import clinic ~۱۲۶s) | موفق |
| ۲ | `venv/Scripts/python.exe -m pytest tests/unit/api/test_market_dashboard_aggregates.py -q -o addopts=''` | `RC=0` (۵۰.۵s، تمام ۶ کلاس تست‌ها PASS) | موفق |
| ۳ | `venv/Scripts/python.exe -m pytest tests/unit/api/test_market_aggregate_cache.py -q -o addopts=''` | `RC=0` (۲۰.۸s، ۶ تست PASS) | موفق |
| ۴ | `python.exe -m py_compile` برای تمام فایل‌های تغییر‌یافته | `PY_COMPILE_OK` | موفق |
| ۵ | تست‌های `test_backend_api.py` (market/watch، bourse، energy-commodity، overview، gainers، losers، active، edgeCases) | **اجرایش نشده** (PostgreSQL غیرقابل دسترسی در این محیط؛ `DATABASE_URL` unset؛ فایل‌های تست `needs_db` ندارند) | اجرای نشده — به دلایل زیر بازگردانده می‌شود |
| ۶ | تست‌های ریپازیتوری جدید (`test_query_latest_snapshot`, `test_bulk_upsert_repository`, `test_storage_layer_params`, `test_ingestion_worker_persistence`, `test_sync_service_persistence_scope`) | **اجرایش نشده** (فایل‌های نظردهی/نمونه‌ای هستند و بدون تست‌های خود در محیط QA نباید اجرا شده باشند؛ بدون دسترسی فایل کامل/مک‌تن) | اجرا نشده |

> ⚠️ **چه را به عنوان موفق اعلام نکنم**: آزمون‌های DB-dependent و فایل‌های نظردهیukan واقعاً اجرا نشده‌اند. خروجی `RC=0` یک‌بار برای ۳ سند خودم بکار رفته است که توسط pytest اجرا شده‌اند.

## ۶. نکات خطر و وابستگی‌ها

1. **DB-dependent suites** (test_backend_api.py watch/bourse/... & edgeCases، test_market_overview_api e2e): فیض‌زدایی DB/DATABASE_URL در محیط QA باعث می‌شود بدون پیکربندی، فایل‌های تست‌ای که `needs_db` ندارند، فیلد `success` را نادیده بگیرند یا دامین نمی‌گیرند. افزونه بازیابی: `DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db` یا WSL/CI با Postgres.
2. **بخش ۰۵ UI / فرانت‌اند تغییرات** (useMarketData.ts و سایر فایل‌ها stage شد) — تغییر فقط به مرحله ۰۵ می‌رسد؛ QA این بخش را جلد می‌کند.
3. **کش چندپروسه**: `_AGG_CACHE` یک کوکی درونی است؛ `core/cache.py` (Redis) برای CacheStats/Prometheus موجود است اما ۴ endpointهای aggregate هنوز از آن استفاده نمی‌کنند.
4. **فایل‌های نظردهی کاربر** (۵ فایل ریپازیتوری جدید) بدون بررسی توسط خودم — باید در مرحلهٔ بعد با تست‌های خود شناسایی شوند.
5. **GITState** (stage ۱۳۸ فایل، ۴ تغییر، ۸ نظردهی): محفوظ است به‌طور خودکار؛ هیچ کدام حذف/commit نشده‌اند.

## ۷. فهرست کارهای باقی‌مانده (آخرینcreditor)

1. اجرا و تأیید مجموعه تست‌های DB-dependent در `tests/unit/test_backend_api.py` (market/watch، bourse، energy-commodity، overview، gainers، losers، active، edgeCases) و `tests/e2e/test_market_overview_api.py` — نیازمند `PostgreSQL`/`DATABASE_URL` قابل دسترسی.
2. بررسی و تایید ۵ فایل تست ریپازیتوری جدید (bulk_upsert_repository، query_latest_snapshot، ingestion_worker_persistence، storage_layer_params، sync_service_persistence_scope) — یا اضافه کردنِ تست‌های خودشان و اجرای آن‌ها.
3. تکمیل بخش ۰۵ (فرانت‌اند): استفاده از `data_as_of`/`cache_hit` در `useMarketData.ts` تا `LiveDataBanner` در صورت `cache_hit=true` یا `data_as_of` قدیمی، برطرف کند.
4. (اختیاری) پخش `_AGG_CACHE` به Redis `core/cache.py` با TTL+invalidation snapshot را برای چندپروسه.
5. بسته‌بندی دوباره: `git add` + commit فقط با مراجعه صریح، اقدام به حفظ تغییرات stage‌شده را ادامه نده.

## ۸. بسته‌بندی و نتیجه‌ی مرحله

- فایل گزارش این مرحله: **`AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_04.md`** (مخزن واقعی: `C:\Users\Iran\Desktop\temce`)
- مرحله‌ای که این گزارش رسم می‌کند، نیست. تمام معیارهای اولیه (مدیریت API، کش، روت، import، گزارش در مسیر) با شواهد کد/تست تأیید شده‌اند؛ بخش‌های باقی‌مانده (DB-dependent tests، ریپازیتوری نظردهی، بخش ۰۵ UI) به مراحل بعدی تعلق دارند.
- وضعیت نهایی: **PARTIAL** (تأیید شده با شواهد؛ بیهوش‌متر شدن بررسی‌ها جهتِ محدودیت‌های محیطی/خارجی).

| 16 | `tests/unit/test_backend_api.py` | بخش Market | (DB-dependent، اجرا نشده) |
| 17 | `tests/unit/test_backend_api_edge_cases.py` | بخش market | (DB-dependent، اجرا نشده) |
| 18 | `tests/e2e/test_market_overview_api.py` | کامل | (DB-dependent، اجرا نشده) |
| 19 | `tests/unit/repositories/test_sync_log_repository.py` | بخش ۱–۶۰ | تایید وجود ادعای نشست قبلی |
| 20 | `tests/unit/brsapi/test_sync_helpers.py` | کامل | helperهای pure |
| 21 | `tests/unit/conftest.py`، `tests/conftest.py` | کامل | fixture، ENV fix |
| 22 | `pyproject.toml` | کامل | pytest config |
| 23 | `services/` (market_service، sync، query-service لایه‌ها) | کامل | لایه query / sync |

**فایل‌های بررسی‌نشده (کنترل‌کننده، در ترکیب خودِ «تأیید» نیستند چرا که بدون تست‌های آن‌ها یا دسترسی فایل ندارند):**
`tests/unit/repositories/test_bulk_upsert_repository.py`، `tests/unit/repositories/test_query_latest_commodity.py`، `tests/unit/repositories/test_query_latest_snapshot.py`، `tests/unit/test_ingestion_worker_persistence.py`، `tests/unit/test_storage_layer_params.py`، `tests/unit/repositories/test_instrument_repository_finglish.py`، `tests/unit/repositories/test_lazy_import.py`.
