# ممیزی مستقل تکمیل مرحله ۴ — API بک‌اند، aggregation، query و cache

**مسیر این گزارش:** `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_4.md`  
**گزارش مرحله (مرجع اجرا):** `AUDIT_REPORTS/MODULAR_TEMCE/04_BACKEND_API_AGGREGATION_CACHE_run2.md`  
**گزارش قبلی مرحله:** `AUDIT_REPORTS/MODULAR_TEMCE/04_BACKEND_API_AGGREGATION_CACHE.md` (دست‌نخورده)  
**تاریخ/زمان ممیزی:** 2026-10-28 — حدود 10:23 به وقت محلی (UTC+03:30)  
**ریشهٔ مخزن:** `C:/Users/Iran/Desktop/temce`  
**شاخه:** `integration/golddesk-fixes`  
**HEAD:** `90597e05b9f4328bcd82ee819a31ba5c55413c12` (بدون commit جدید)  
**نتیجهٔ نهایی: PARTIAL** — اصلاحات و تست‌های آفلاین PASS هستند؛ اما invalidate کش بین‌پروسه‌ای/چند worker، چند endpoint بدون متادیتای تازگی کامل، و تأیید PostgreSQL/BrsApi/Redis زنده BLOCKED باقی مانده‌اند.

> این گزارش بر اساس بازخوانی کد فعلی، diff، Git و اجرای مجدد تست‌ها نوشته شده است، نه اتکا به گزارش قبلی. خروجی‌های تست در بخش ۶ عیناً ثبت شده‌اند.

---

## ۱. مسیر گزارش‌ها و وجود فایل

| گزارش | مسیر | وضعیت |
|---|---|---|
| گزارش مرحله (اجرای دوم) | `AUDIT_REPORTS/MODULAR_TEMCE/04_BACKEND_API_AGGREGATION_CACHE_run2.md` | ✅ موجود؛ ۲۷٬۲۵۷ بایت / ۲۷۵ خط |
| گزارش قبلی مرحله | `AUDIT_REPORTS/MODULAR_TEMCE/04_BACKEND_API_AGGREGATION_CACHE.md` | ✅ موجود؛ overwrite نشد |
| گزارش ممیزی این اجرا | `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_4.md` | ✅ همین فایل؛ overwrite روی `QA_STAGE_3*.md` انجام نشد |

---

## ۲. وضعیت Git و حفظ تغییرات

| مورد | مقدار/شاهد |
|---|---|
| HEAD ابتدا/انتها | `90597e05...` → `90597e05...` (بدون commit) |
| staged قبلی | ۱۳۸ فایل؛ `git diff --cached --stat` = ۱۱۵٬۹۹۸ insert / ۱٬۴۴۷ delete |
| فایل حذف‌شده توسط این ممیزی | هیچ (`git status | grep '^ D'` = 0) |
| عملیات ممنوع انجام‌شده | هیچ: بدون reset --hard، clean، stash، checkout/restore مخرب، rebase، force push یا commit |
| تغییرات هم‌زمان دیگران | `apps/api/endpoints/market.py` (MM)، `schemas/common/responses.py`، `apps/api/endpoints/market_watch.py` و testهای untracked از قبل وجود داشتند؛ همه حفظ شدند |
| فایل‌های تغییر‌یافته این ممیزی | ۵ فایل کد + ۲ فایل تست + گزارش `QA_STAGE_4.md` (بخش ۱۱) |

---

## ۳. فایل‌های بررسی‌شده و بررسی‌نشده

### کامل خوانده شد

| فایل | نکته |
|---|---|
| `apps/api/endpoints/market.py` | ۷۸۶+ خط؛ heatmap، sparklines، enriched/treemap، flow، allocation، cashflow، cache helpers |
| `apps/api/endpoints/market_dashboard.py` | کل؛ `_fetch`، Result، aggregate errors |
| `apps/api/endpoints/market_info.py` | کل؛ industries/funds/error paths |
| `apps/api/endpoints/market_watch.py` | کل؛ empty/error paths |
| `schemas/common/responses.py` | `ApiResponse` و فیلدهای `data_as_of`/`cache_hit` |
| `core/result.py` / `core/typing/result.py` | `Result`/`PaginatedResult` |
| `apps/api/router.py` | کل؛ mountها و ۷۱۴ route |
| `apps/api/error_handlers.py` | unhandled exception → 500 |
| `apps/api/dependencies.py` | بخش `get_brsapi_query_service`/`get_market_service` |
| `tests/unit/api/test_market_endpoint_contracts.py` | کل (۱۳ تست) |
| `tests/unit/api/test_market_aggregate_cache.py` | کل (۱۰ تست) |
| `tests/unit/api/test_market_dashboard_aggregates.py` | کل (۲۰ تست، اجرا) |
| `tests/unit/test_sync_service_persistence_scope.py` | کل (۷ تست) |
| `tests/unit/repositories/test_sync_log_repository.py` | کل (۱۵ تست) |
| `brsapi/services/sync_service.py` | بخش `sync()` و `sync_all()`/invalidation |
| `frontend/src/lib/api.ts` | بخش `extractArray`/`safeExtractArray` |
| `frontend/src/hooks/useMarketData.ts` | بخش‌های heatmap/treemap/allocation/cashflow/overview |
| `AUDIT_REPORTS/MODULAR_TEMCE/04_BACKEND_API_AGGREGATION_CACHE_run2.md` | کل؛ فقط به‌عنوان ادعای قابل‌بررسی |

### بخشی خوانده شد

| فایل | بخش |
|---|---|
| `apps/api/app.py` | `create_app`، prefix `/api/v1`، startup sync، `/cache-stats` |
| `apps/api/endpoints/brsapi.py` | بخش‌های cache/freshness مرتبط (نه کل ۳۳۵۰ خط) |
| `apps/api/endpoints/market_insights.py` | فقط الگوهای success/except |
| `services/market_service.py` | امضاها و fallbackهای overview/top gainers/… |
| `brsapi/jobs/registry.py` | مسیرهای `sync_all_symbols` |
| `brsapi/services/query_service.py` | توابع latest (کل فایل در مرحله ۳ خوانده شد؛ تغییرات مرتبط دوباره) |
| `migrations/*` | فقط migrationهای مرتبط با latest/index (برای context) |

### بررسی نشد

| مورد | دلیل |
|---|---|
| BrsApi/TSETMC زنده | ممنوع/بدون دسترسی؛ هیچ درخواست زنده‌ای ارسال نشد |
| PostgreSQL/Redis عملیاتی و اجرای migration | عملیات روی DB عملیاتی ممنوع؛ DB تست اختصاصی در دسترس نبود |
| `tests/unit/test_backend_api.py` بخش‌های market (تعدادی `needs_db`) | نیازمند PostgreSQL |
| `tests/e2e/test_market_overview_api.py` | نیازمند DB و `init_database` |
| فرانت‌اند کامل (UI/کامپوننت‌ها) | خارج از دامنه؛ فقط قرارداد مصرف بررسی شد |
| `venv/`، `node_modules/`، داده‌های حجیم | وابستگی/تولیدی/باینری |

هیچ ادعای «کل پروژه بررسی شد» مطرح نمی‌شود.

---

## ۴. جدول الزام‌های پرامپت

| # | الزام | شاهد | نتیجه | کار باقی‌مانده |
|---|---|---|---|---|
| 1 | شناسایی ریشه/شاخه/HEAD/status/diff | `pwd`، `git rev-parse`، `git status --short --branch`، `git diff --cached --stat` | **PASS** | — |
| 2 | حفظ staged/unstaged/untracked؛ عدم عملیات مخرب Git | HEAD ثابت `90597e05`؛ ۱۳۸ فایل staged دست‌نخورده؛ بدون حذف/reset/clean/stash/commit | **PASS** | — |
| 3 | عدم درخواست زنده BrsApi/TSETMC و عدم دست‌کاری cooldown/rate limit | هیچ کلاینت BrsApi اجرا نشد؛ تست‌ها fake/SQLite | **PASS (compliance)** | E2E زنده **BLOCKED** |
| 4 | عدم TRUNCATE/DELETE/reset و عدم چاپ secret/DSN | هیچ اتصال DB اجرا نشد؛ هیچ secret چاپ نشد | **PASS** | — |
| 5 | گزارش‌های قدیمی به‌عنوان سرنخ؛ تأیید مستقل ادعاهای قبلی | `git ls-files` برای `AUDIT_BATCH_*`/`ROOT_CAUSE_VERIFICATION` خالی؛ ۱۵ تست sync-log مستقل ۱۵/۱۵؛ `useMarketData.ts` staged؛ شاخه/HEAD تأیید شد | **PASS** | گزارش‌های قدیمی در دسترس نبودند (ثبت شد) |
| 6 | خواندن کامل فایل‌های دامنه و manifest | بخش ۳ | **PARTIAL** | `brsapi.py`/`market_insights.py`/`market_service.py` کامل خوانده نشدند |
| 7 | تغییر کوچک/هدفمند، بدون formatter سراسری | ۵ فایل کد + ۲ فایل تست؛ بدون `ruff --fix` سراسری | **PASS** | — |
| 8 | گزارش در فایل و بدون overwrite | `04..._run2.md` و `QA_STAGE_4.md` | **PASS** | — |
| 9 | ساختار کامل گزارش (تاریخ، Git، manifest، یافته‌ها، جدول ایراد، ریشه، تست، ریسک، پذیرش) | گزارش run2 + همین گزارش | **PASS** | — |
| 10 | انجام واقعی مأموریت نه چک‌لیست | کد تغییر کرد، تست‌ها اجرا شدند، diff/Git بررسی شد | **PASS** | — |
| 11 | ردیابی HTTP route → handler → service → DB/cache → schema و ثبت timestamp/source/status | heatmap، sparklines، enriched/treemap، allocation/cashflow، dashboard، watch، info | **PARTIAL** | برخی helperها/endpointهای جانبی فقط سطحی بررسی شدند |
| 12 | TTL، cache key، انقضا، invalidation بعد از sync، تفاوت hit/miss | `_AGG_TTL=300`، کلیدها شامل limit، تست‌های hit/miss/TTL/invalidate | **PASS (offline)** | invalidate بین‌پروسه‌ای **BLOCKED** |
| 13 | cache دادهٔ کهنه را بدون data_as_of/freshness/stale سرو نکند | `_rows_data_as_of` از `fetched_at`؛ `cache_hit`؛ HTTP test | **PASS (مسیرهای اصلاح‌شده)** | چند endpoint جانبی بدون data_as_of |
| 14 | limitهای ثابت، snapshot از دوره‌های مختلف، fallbackهای نامعتبر، MAX(id)، ترکیب cycleها | مرحله ۳ latest به `fetched_at`؛ cache key limit؛ heatmap limit 100 | **PARTIAL** | `get_latest_indices`/index-history هنوز `created_at`؛ heatmap limit ثابت |
| 15 | خطاها به 200 empty تبدیل نشوند؛ empty واقعی پشتیبانی شود | heatmap/flow/watch/info/dashboard اصلاح شدند؛ empty فیلترشده معتبر | **PARTIAL** | overview/indices/gainers/... بدون `error`؛ برخی endpointها data_as_of ندارند |
| 16 | بررسی conflict marker و حل حداقلی router | هیچ marker در `apps/api/router.py`/market؛ ۷۱۴ route، ۰ duplicate | **PASS** | — |
| 17 | اجرا/افزودن تست route/schema/cache | ۵۱ تست Phase 4؛ ۳۹ رگرسیون مرحله ۳ | **PASS (offline)** | تست‌های `needs_db`/e2e اجرا نشدند |
| 18 | معیار پذیرش: API غیرگمراه‌کننده، cache قابل‌پیش‌بینی، import/route سالم | بخش ۱۰ | **PARTIAL** | cross-process/live تأیید نشده |

---

## ۵. اصلاحات: مسیر، diff، دلیل، تست

diff محتوایی فعلی (شامل تغییرات هم‌زمان قبلی که حفظ شدند):

```
apps/api/endpoints/market.py             | 75 + / 32 -
apps/api/endpoints/market_dashboard.py   | 29 + /  4 -
apps/api/endpoints/market_info.py        | 16 + / 11 -
apps/api/endpoints/market_watch.py       |  7 + /  1 -
brsapi/services/sync_service.py          | 57 + /  4 -
```

| # | مسیر/خط | diff (خلاصه) | دلیل | تست مرتبط |
|---|---|---|---|---|
| F-1 | `apps/api/endpoints/market.py:111-138` | حذف `select(brsapi.models...)`؛ `data_as_of = _rows_data_as_of(snapshots)` | `select` import نشده و `brsapi.models` وجود ندارد؛ endpoint همیشه `success=False` | `test_success_reports_snapshot_time_without_raw_query`، `test_heatmap_http_serializes_data_as_of` |
| F-2 | `market.py:538-552` | افزودن `_rows_data_as_of()` | `data_as_of` باید زمان `fetched_at` داده باشد، نه زمان ساخت پاسخ | تست‌های cache + HTTP |
| F-3 | `market.py:258,306,625,671` | کلید کش شامل `limit`؛ افزودن پارامتر `limit` به enriched-heatmap | کش دادهٔ limit دیگر را سرو می‌کرد؛ فرانت‌اند `?limit=120` می‌فرستد | `test_different_limit_does_not_share_cache_entry`، `test_limit_is_part_of_cache_key` |
| F-4 | `market.py:289,349,632,678` | `as_of = _rows_data_as_of(enriched/snapshots)` | cache hit نباید دادهٔ کهنه را تازه نشان دهد | تست‌های cache |
| F-5 | `market.py:241-246` | خطای sparklines → `data={}` | حفظ قرارداد `dict[str, list[float]]` | `test_sparklines_failure_keeps_dict_contract` |
| F-6 | `market.py:385-420` | snapshots خالی → `success=False` + `data_as_of` در موفق | جلوگیری از جریان صفر جعلی | `test_flow_summary_without_snapshots_is_an_error` |
| F-7 | `market_dashboard.py:27-83` | `errors` map، تشخیص `Result.fail`، all-failed → `success=False`، `_unwrap_indices` raise، screener re-raise | خطای منبع نباید success=True شود | `test_dashboard_all_sources_failed_is_success_false`، `...result_failures...`، HTTP dashboard |
| F-8 | `market_info.py:32-38,51-58,68-74` | خطا → `success=False` + error؛ dedupe با max `fetched_at` | خطا به empty موفق تبدیل می‌شد؛ NAV قدیمی انتخاب می‌شد | `test_market_info_*` |
| F-9 | `market_watch.py:29-36` | snapshots خالی → `success=False` | بازار خالی جعلی | `test_market_watch_without_snapshots_is_not_success_empty` |
| F-10 | `sync_service.py:500-510` | `invalidate_agg_cache()` پس از commit snapshot (lazy، fail-safe) | jobهای مستقیم `sync_all_symbols` کش را پاک نمی‌کردند | `test_snapshot_sync_invalidates_market_aggregate_cache`، `test_non_snapshot...` |
| F-11 | `tests/unit/api/test_market_aggregate_cache.py` | تقویت تست heatmap؛ افزودن limit/موفق | تست قبلی خرابی NameError را نمی‌گرفت | ۱۰ تست |
| F-12 | `tests/unit/api/test_market_endpoint_contracts.py` | ۱۳ تست جدید قرارداد | پوشش خطا/تازگی/dashboard/info/watch/HTTP | ۱۳ تست |

**نکته:** `schemas/common/responses.py` و بخشی از diff `market.py` از تغییر هم‌زمان قبلی هستند و توسط این ممیزی حذف/بازنویسی نشدند.

---

## ۶. فرمان‌های تست و نتیجهٔ واقعی

> همه با `venv/Scripts/python.exe` (Python 3.11.9) و `PYTHONIOENCODING=utf-8`؛ بدون DB/BrsApi/Redis زنده.

| فرمان | Passed | Failed | Skipped/Deselected | Exit |
|---|---|---|---|---|
| `pytest tests/unit/api/test_market_endpoint_contracts.py tests/unit/api/test_market_aggregate_cache.py tests/unit/api/test_market_dashboard_aggregates.py tests/unit/test_sync_service_persistence_scope.py tests/unit/test_backend_api.py::test_health_check -q ...` | **51** | **0** | 0 | **0** |
| رگرسیون مرحله ۳ (۹ فایل repository/worker/storage/sync-scope) | **39** | **0** | 0 | **0** |
| `pytest tests/unit/repositories/test_sync_log_repository.py -q ...` | **15** | 0 | 0 | **0** |
| اسکریپت `create_app()` + شمارش route | — | — | **714 route، 0 duplicate** | 0 |
| `python -m py_compile` فایل‌های تغییر‌یافته | — | — | — | **0** |
| `git diff --check --ignore-cr-at-eol` | — | — | — | **0** |

- جمع ۵۱ = ۱۳ contracts + ۱۰ cache + ۲۰ dashboard aggregates + ۷ sync-scope + ۱ health.
- **Baseline ۲۶** که در گزارش قبلی ذکر شده، مربوط به قبل از اصلاح است و در این ممیزی بازتولید نشد؛ به‌عنوان نتیجهٔ تست فعلی محسوب نمی‌شود.

### تست‌های اجرانشده و علت

| تست/بررسی | علت |
|---|---|
| `tests/unit/test_backend_api.py` بخش‌های market (تعدادی) | `needs_db`؛ PostgreSQL در دسترس نبود |
| `tests/e2e/test_market_overview_api.py` | نیازمند DB و `init_database` |
| E2E زنده heatmap/treemap/dashboard با BrsApi/DB | BrsApi زنده ممنوع؛ DB عملیاتی در دسترس نبود |
| invalidate بین دو پروسه (API + Scheduler) | نیازمند Redis/چندپروسه؛ محیط فراهم نبود |
| benchmark/EXPLAIN کوئری‌های newest-per-symbol | نیازمند DB با حجم واقعی |
| migration/DB destructive | ممنوع |

---

## ۷. موارد BLOCKED

| مورد | مانع | اثر بر پذیرش |
|---|---|---|
| invalidate کش بین‌پروسه‌ای/چند worker | کش `_AGG_CACHE` درون‌حافظه‌ای است؛ Redis/pubsub یا shared cache لازم است | حداکثر ۳۰۰ ثانیه کهنگی در پروسه‌های دیگر؛ **BLOCKED** |
| تأیید PostgreSQL واقعی (کیفیت/پلن/cycle) | DB تست/مجاز در دسترس نیست | تأیید latest/aggregation روی داده واقعی **BLOCKED** |
| BrsApi/TSETMC زنده | ممنوع/بدون دسترسی | E2E زنده **BLOCKED** |
| Redis/queue و رفتار dedup واقعی | سرویس تست در دسترس نیست | **BLOCKED** |
| تست‌های `needs_db`/e2e | نیازمند DB | اجرا نشدند |

---

## ۸. کارهای باقی‌مانده (دقیق)

1. **invalidate کش بین‌پروسه‌ای:** انتقال `_AGG_CACHE` به Redis یا invalidate با pub/sub/versioned key؛ پوشش `SymbolSnapshotWarmSink` در ingestion و همهٔ workerها.
2. **تازگی در endpointهای باقی‌مانده:** افزودن `data_as_of`/`stale` به `market_watch`، `market_dashboard`، `market_info`، `market_insights`، `flow-history`، `value-history`، `ownership-history`، `index-history` و تعیین آستانهٔ stale.
3. **انتخاب شاخص:** `get_latest_indices` و `get_index_history` از `created_at` به `fetched_at` (یا قرارداد مستند) منتقل شوند.
4. **قرارداد خطا:** `market_overview/indices/gainers/losers/active/bourse/energy-commodity` در failure فیلد `error` و پیام امن برگردانند.
5. **امنیت پیام خطا:** `str(exc)` در پاسخ‌های endpointها با `safe_error_message`/پیام عمومی جایگزین شود.
6. **کش:** سیاست eviction (سقف ۸ کلید) و نمایش `_AGG_CACHE` در `/cache-stats` یا metrics.
7. **heatmap limit:** پارامتر `limit` (یا مستندسازی ثابت ۱۰۰) و تست قرارداد فرانت‌اند.
8. **فرانت‌اند:** مصرف `success`/`data_as_of`/`cache_hit` و نمایش stale/error در بخش ۰۵.
9. **تست واقعی DB:** اجرای `needs_db`/e2e و EXPLAIN برای `get_latest_snapshots`/`_latest_per_symbol`.
10. **تست زنده:** BrsApi/Redis و invalidate cross-process.
11. **تست Result.fail در HTTP dashboard:** اطمینان از سریال‌سازی `Result.fail` و `errors` در پاسخ واقعی.
12. **فرمت timestamp:** `_rows_data_as_of` برای ترکیب datetime/string با فرمت‌های متفاوت (ISO با `T`/فاصله) مقاوم شود.
13. **سیاست partial failure در dashboard:** تصمیم بگیرید خطای منابع حیاتی (overview/indices) همیشه `success=False` کند یا فقط `errors` گزارش شود.

---

## ۹. معیارهای پذیرش و نتیجه

| معیار پذیرش | وضعیت | شاهد |
|---|---|---|
| API وضعیت تازگی/خطا را گمراه‌کننده اعلام نکند (مسیرهای اصلی) | ✅ PASS (offline) | heatmap/dashboard/info/watch/flow + `data_as_of` از `fetched_at` |
| cache با آزمون قابل‌پیش‌بینی باشد | ✅ PASS (offline) | hit/miss/TTL/invalidate/limit/empty/error؛ ۱۰ تست |
| import و route registration سالم باشد | ✅ PASS | ۷۱۴ route، ۰ duplicate؛ health PASS |
| invalidate بعد از sync | ✅ PASS در همان پروسه | `sync()` snapshot + `sync_all()` |
| invalidate بین‌پروسه‌ای | ⛔ BLOCKED | نیازمند Redis/چندپروسه |
| تأیید DB/زنده | ⛔ BLOCKED | PostgreSQL/BrsApi/Redis در دسترس نبود |
| قرارداد فرانت‌اند (خواندن success/data_as_of) | ⚠️ handoff بخش ۰۵ | `extractArray` هنوز success را نادیده می‌گیرد |

### نتیجهٔ نهایی: **PARTIAL**

اصلاحات کد و ۵۱ تست آفلاین بدون failure هستند، اما معیارهای وابسته به PostgreSQL/BrsApi/Redis و invalidate بین‌پروسه‌ای تأیید نشده‌اند و چند endpoint جانبی هنوز متادیتای تازگی/خطای کامل ندارند. بنابراین مرحله «کامل/PASS» اعلام نمی‌شود.

---

## ۱۰. تأیید ادعاهای گزارش `run2`

| ادعا | نتیجهٔ ممیزی مستقل |
|---|---|
| ۵۱ تست Phase 4 pass | ✅ ۵۱ pass، ۰ failed، exit 0 |
| ۳۹ تست رگرسیون مرحله ۳ pass | ✅ ۳۹ pass، ۰ failed، exit 0 |
| ۷۱۴ route، ۰ duplicate | ✅ تأیید |
| heatmap خراب بود و رفع شد | ✅ کد فعلی فاقد `select`/`brsapi.models` است؛ تست HTTP موفق |
| `data_as_of` از `fetched_at` | ✅ `_rows_data_as_of` در market.py:538 |
| cache key شامل limit | ✅ خطوط 258/306/625/671 |
| dashboard خطا را پنهان نمی‌کند | ✅ `errors`/all-failed در market_dashboard.py:32-75 |
| invalidation بعد از snapshot sync | ✅ sync_service.py:500-510 |
| invalidate بین‌پروسه‌ای BLOCKED | ✅ همان محدودیت تأیید شد |
| بدون commit؛ staged حفظ شد | ✅ HEAD ثابت `90597e05`؛ ۱۳۸ staged؛ ۰ فایل حذفی |
| ۱۵ تست sync-log | ✅ ۱۵/۱۵ pass |
| گزارش‌های `AUDIT_BATCH_*`/`ROOT_CAUSE_VERIFICATION` | ❌ در worktree/index/history یافت نشدند؛ غیبت ثبت شد |
| Baseline ۲۶ | ⚠️ در این ممیزی بازتولید نشد؛ به‌عنوان نتیجهٔ فعلی محسوب نمی‌شود |

---

## ۱۱. فایل‌های ایجاد/تغییر‌یافته

**تغییر یافته (unstaged، روی تغییرات قبلی):**
- `apps/api/endpoints/market.py`
- `apps/api/endpoints/market_dashboard.py`
- `apps/api/endpoints/market_info.py`
- `apps/api/endpoints/market_watch.py`
- `brsapi/services/sync_service.py`
- `tests/unit/api/test_market_aggregate_cache.py`
- `tests/unit/test_sync_service_persistence_scope.py`

**ایجاد شده:**
- `tests/unit/api/test_market_endpoint_contracts.py`
- `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_4.md` (همین گزارش)

**بدون commit؛ HEAD `90597e05`؛ staged/untracked قبلی حفظ شد.**
