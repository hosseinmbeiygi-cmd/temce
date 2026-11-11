# ممیزی مرحله ۴ — API بک‌اند، aggregation، query و cache (اجرای مستقل دوم)

**مسیر این گزارش:** `AUDIT_REPORTS/MODULAR_TEMCE/04_BACKEND_API_AGGREGATION_CACHE_run2.md`  
**گزارش قبلی همین مرحله:** `AUDIT_REPORTS/MODULAR_TEMCE/04_BACKEND_API_AGGREGATION_CACHE.md` (دست‌نخورده؛ فقط به‌عنوان سرنخ خوانده شد)  
**تاریخ/زمان:** 2026-10-28 — 10:19 به وقت محلی (UTC+03:30)، 06:49 UTC  
**ریشهٔ مخزن:** `C:/Users/Iran/Desktop/temce`  
**شاخه:** `integration/golddesk-fixes`  
**HEAD:** `90597e05b9f4328bcd82ee819a31ba5c55413c12` (بدون commit جدید)  
**نتیجهٔ نهایی:** **PARTIAL** — مسیرهای اصلاح‌شده و تست‌های آفلاین PASS هستند؛ اما invalidate کش بین‌پروسه‌ای، چند endpoint بدون متادیتای تازگی، و تأیید PostgreSQL/زنده BLOCKED باقی مانده‌اند.

---

## ۱. مسیر گزارش‌ها و وجود فایل

| گزارش | مسیر | وضعیت |
|---|---|---|
| گزارش قبلی مرحله ۴ | `AUDIT_REPORTS/MODULAR_TEMCE/04_BACKEND_API_AGGREGATION_CACHE.md` | ✅ موجود (۲۴٬۰۸۶ بایت)؛ overwrite نشد |
| گزارش این ممیزی | `AUDIT_REPORTS/MODULAR_TEMCE/04_BACKEND_API_AGGREGATION_CACHE_run2.md` | ✅ همین فایل؛ فایل قبلی حفظ شد |

---

## ۲. وضعیت Git و حفظ تغییرات

| مورد | شاهد/مقدار |
|---|---|
| HEAD ابتدا/انتها | `90597e05...` → `90597e05...` (بدون commit) |
| staged قبلی | ۱۳۸ فایل؛ `git diff --cached --stat` همچنان ۱۱۵٬۹۹۸ insert / ۱٬۴۴۷ delete |
| حذف فایل توسط این ممیزی | هیچ (`git status | grep '^ D'` = 0) |
| عملیات ممنوع | هیچ: بدون `reset --hard`، `clean`، `stash`، `checkout/restore` مخرب، rebase، force push یا commit |
| تغییرات هم‌زمان دیگران | `apps/api/endpoints/market.py` (MM)، `schemas/common/responses.py`، `apps/api/endpoints/market.py` و `tests/unit/api/test_market_aggregate_cache.py` قبل از این اجرا توسط عامل دیگری تغییر کرده بودند؛ همه حفظ شدند و فقط اصلاح/تکمیل شدند |

**فایل‌های تغییر‌یافته/ایجادشده در این ممیزی (روی unstaged موجود):**

- `apps/api/endpoints/market.py`
- `apps/api/endpoints/market_dashboard.py`
- `apps/api/endpoints/market_info.py`
- `apps/api/endpoints/market_watch.py`
- `brsapi/services/sync_service.py` (فقط بلوک invalidation)
- `tests/unit/api/test_market_aggregate_cache.py` (تقویت/تکمیل تست موجود)
- `tests/unit/api/test_market_endpoint_contracts.py` (جدید، ۱۳ تست)
- `tests/unit/test_sync_service_persistence_scope.py` (+۲ تست invalidation)
- همین گزارش

`schemas/common/responses.py` (فیلدهای `data_as_of`/`cache_hit`) توسط عامل هم‌زمان اضافه شده بود و تغییر نکرد.

---

## ۳. هدف و مرز دامنه

**هدف:** ردیابی HTTP route → handler → service/query → DB/cache → schema؛ بررسی TTL، cache key، invalidation، دادهٔ کهنه/خالی/خطا، limitهای ثابت، انتخاب snapshot از cycleهای متفاوت، و سلامت import/route.

**در دامنه:** `apps/api/` (market.py، market_dashboard.py، market_watch.py، market_info.py، router.py، dependencies.py، app.py/error_handlers.py)، `schemas/common/responses.py`، `brsapi/services/query_service.py`، `brsapi/services/sync_service.py` (فقط مسیر invalidation)، endpointهای heatmap/treemap/allocation/cashflow، تست‌های API/cache، و قرارداد مصرف فرانت‌اند.

**خارج از دامنه:** تغییر UI/فرانت‌اند (handoff به بخش ۰۵)، migration/DB عملیاتی، BrsApi/TSETMC زنده، Redis عملیاتی، و بازطراحی کل cache به Redis.

---

## ۴. Manifest فایل‌های خوانده‌شده

### کامل خوانده شد

| فایل | نکته |
|---|---|
| `apps/api/endpoints/market.py` | ۷۸۶+ خط؛ همهٔ endpointها، `_AGG_CACHE`، helperها |
| `apps/api/endpoints/market_dashboard.py` | کامل |
| `apps/api/endpoints/market_watch.py` | کامل |
| `apps/api/endpoints/market_info.py` | کامل |
| `schemas/common/responses.py` | کامل؛ `data_as_of`/`cache_hit` |
| `core/result.py` / `core/typing/result.py` | `Result`/`PaginatedResult` |
| `apps/api/router.py` | کامل؛ ۷۱۴ route، بدون conflict marker |
| `apps/api/error_handlers.py` | کامل؛ خطاهای unhandled → 500 |
| `apps/api/dependencies.py` | بخش `get_brsapi_query_service`/`get_market_service` |
| `tests/unit/api/test_market_aggregate_cache.py` | کامل (قبل/بعد از تقویت) |
| `tests/unit/api/test_market_dashboard_aggregates.py` | کامل (اجرا) |
| `tests/unit/api/test_market_endpoint_contracts.py` | کامل (جدید) |
| `tests/unit/test_sync_service_persistence_scope.py` | کامل (تست invalidation اضافه شد) |
| `frontend/src/lib/api.ts` | بخش `extractArray`/`safeExtractArray` |
| `frontend/src/hooks/useMarketData.ts` | بخش‌های heatmap/treemap/allocation/cashflow/overview |
| `brsapi/services/sync_service.py` | بخش `sync()` و `sync_all()`/invalidation |
| `brsapi/services/query_service.py` | توابع latest و `_latest_per_symbol` (مرحله ۳/۴) |
| `tests/unit/repositories/test_sync_log_repository.py` | ۱۵ تست (برای تأیید ادعای نشست قبل) |
| `AUDIT_REPORTS/MODULAR_TEMCE/04_BACKEND_API_AGGREGATION_CACHE.md` | کامل؛ فقط سرنخ |

### بخشی خوانده شد

| فایل | بخش |
|---|---|
| `apps/api/app.py` | `create_app`، prefix `/api/v1`، startup sync، `/cache-stats` |
| `apps/api/endpoints/brsapi.py` | بخش‌های cache/فرشنس مرتبط (نه کل ۳۳۵۰ خط) |
| `apps/api/endpoints/market_insights.py` | فقط الگوهای success/except |
| `services/market_service.py` | امضاهای `get_overview/get_top_gainers/...` و fallback |
| `brsapi/services/query_service.py` | توابع latest (کل فایل در مرحله ۳ خوانده شد؛ تغییرات جدید دوباره) |
| `brsapi/jobs/registry.py` | مسیر `sync_all_symbols` در jobها |

### بررسی نشد

| مورد | دلیل |
|---|---|
| BrsApi/TSETMC زنده | ممنوع/بدون دسترسی؛ هیچ درخواست زنده‌ای ارسال نشد |
| PostgreSQL/Redis عملیاتی، migration | عملیات روی DB عملیاتی ممنوع؛ DB تست اختصاصی در دسترس نبود |
| `tests/unit/test_backend_api.py` بخش‌های market (چند تست `needs_db`) | نیازمند DB؛ اجرا نشد |
| `tests/e2e/test_market_overview_api.py` | نیازمند DB و `init_database` |
| فرانت‌اند کامل | خارج از دامنه؛ فقط قرارداد مصرف بررسی شد |
| `venv/`، `node_modules/`، داده‌های حجیم | وابستگی/تولیدی/باینری |

هیچ ادعای «کل پروژه بررسی شد» وجود ندارد.

---

## ۵. یافته‌های تأییدشده در برابر فرضیه‌ها

| ادعا/فرضیه | نتیجه | شاهد |
|---|---|---|
| `/market/heatmap` تازگی را بررسی می‌کند | ❌ **کد قبلی خراب بود**: `select` import نشده و `brsapi.models` وجود ندارد؛ همیشه `success=False` | اجرای مستقیم: `NameError: name 'select' is not defined` در خط ۱۱۶–۱۱۸ نسخهٔ قبل |
| تست موجود heatmap این خرابی را می‌گیرد | ❌ **تست false-positive بود**: فقط `success is False` را برای snapshots خالی چک می‌کرد و خطای NameError هم همان نتیجه را می‌داد | `tests/unit/api/test_market_aggregate_cache.py` نسخهٔ قبل، `TestHeatmap.test_empty_snapshots_returns_success_false` |
| `_AGG_TTL=300` | ✅ تأیید | `market.py:534-535` |
| کش hit بدون data_as_of/stale | ✅ تأیید (قبل) | نسخهٔ قبل `market.py:258-260...` |
| invalidate بعد از sync همهٔ jobها را پوشش می‌دهد | ❌ فقط `sync_all()` بود؛ jobهای زمان‌بندی‌شده `sync_all_symbols` را مستقیم صدا می‌زنند | `brsapi/services/sync_service.py:1846-1855`؛ `brsapi/jobs/registry.py:832,1071,1335,1554` |
| cache key مستقل از `limit` | ❌ `asset-allocation` و `cashflow-by-sector` کلید ثابت داشتند | نسخهٔ قبل `market.py:610,655` |
| `data_as_of` زمان داده را نشان می‌دهد | ❌ `_now_iso()` زمان ساخت پاسخ بود | نسخهٔ قبل `market.py:291,351,635,676` |
| dashboard خطای منبع را پنهان نمی‌کند | ❌ `_fetch` فقط exception را می‌گرفت و `success=True` با `None` برمی‌گرداند؛ `Result.fail` هم تشخیص داده نمی‌شد | نسخهٔ قبل `market_dashboard.py:34-52` |
| `market_info` خطا را پنهان نمی‌کند | ❌ except به `success=True` خالی برمی‌گشت | نسخهٔ قبل `market_info.py:28-38,64-74` |
| `market_watch` بدون snapshot خطا می‌دهد | ❌ `success=True` خالی | نسخهٔ قبل `market_watch.py:26-31` |
| frontend `limit=120` برای enriched-heatmap را می‌فرستد | ✅ تأیید | `frontend/src/hooks/useMarketData.ts:268`؛ endpoint قبلاً پارامتر limit نداشت |
| route registration سالم است | ✅ ۷۱۴ route، ۰ duplicate (method,path)، بدون conflict marker | اسکریپت ایجاد app + `test_health_check` |
| `get_latest_snapshots` از MAX(id) استفاده می‌کند | ❌ منسوخ؛ در مرحله ۳ به `fetched_at` منتقل شد | `query_service.py:182-248` |
| ۱۵ تست sync log | ✅ ۱۵ تست، ۱۵ pass (در رگرسیون مرحله ۳) | `tests/unit/repositories/test_sync_log_repository.py` |

---

## ۶. جدول ایرادها

| # | شدت | عنوان | شاهد (path:line) | روش بازتولید | اثر | وضعیت |
|---|---|---|---|---|---|---|
| API-4-01 | **Critical** | `/market/heatmap` همیشه شکست می‌خورد | نسخهٔ قبل `apps/api/endpoints/market.py:115-118`؛ فعلی `:111-138` | فراخوانی `market_heatmap` با سرویس واقعی/fake دارای session | `NameError: select` / `AttributeError: brsapi.models`؛ heatmap در UI خالی | رفع شد |
| API-4-02 | بالا | cache key شامل `limit` نیست (asset/cashflow) | فعلی `market.py:625,671` | `asset-allocation?limit=100` سپس `?limit=2000` | پاسخ limit اول به درخواست limit دوم سرو می‌شود | رفع شد |
| API-4-03 | بالا | `data_as_of` زمان ساخت پاسخ بود نه زمان داده | فعلی `market.py:538-552` (helper) | کش hit یک snapshot قدیمی؛ `data_as_of` زمان حال را نشان می‌داد | داده کهنه «تازه» به‌نظر می‌رسید | رفع شد |
| API-4-04 | بالا | dashboard همهٔ خطاها را success=True پنهان می‌کرد | فعلی `market_dashboard.py:34-75` | همهٔ سرویس‌ها را fail کنید | قطعی کامل منبع به‌صورت ۲۰۰ موفق | رفع شد |
| API-4-05 | بالا | invalidate فقط در `sync_all` بود | فعلی `sync_service.py:501-509` و `1862-1865` | job زمان‌بندی‌شده `sync_all_symbols` را اجرا کنید | کش تا ۳۰۰ ثانیه کهنه می‌ماند | رفع شد (in-process) |
| API-4-06 | متوسط | `market_info` خطا را success=True خالی می‌کرد | فعلی `market_info.py:32-38,68-74` | exception در `get_commodity_categories`/`get_ime_funds` | خطای DB به‌صورت «لیست خالی موفق» | رفع شد |
| API-4-07 | متوسط | sparklines در خطا `data=[]` برای نوع dict برمی‌گرداند | فعلی `market.py:241-246` | `Result.fail` از `get_batch_sparklines` | نقض قرارداد نوع/سریال‌سازی | رفع شد (`{}`) |
| API-4-08 | متوسط | flow-summary بدون snapshot صفرهای موفق برمی‌گرداند | فعلی `market.py:385-395` | `get_latest_snapshots` خالی | جریان صفر جعلی به‌جای خطای منبع | رفع شد |
| API-4-09 | متوسط | `market_watch` بدون snapshot success=True | فعلی `market_watch.py:27-35` | snapshots خالی | بازار خالی جعلی | رفع شد |
| API-4-10 | متوسط | dedupe صندوق‌ها بر اساس ترتیب درج بود | فعلی `market_info.py:51-58` | دو رکورد با `fetched_at` متفاوت و ترتیب معکوس | NAV قدیمی به‌جای جدید | رفع شد |
| API-4-11 | متوسط | enriched-heatmap پارامتر `limit` را نادیده می‌گرفت | فعلی `market.py:253-260` | `?limit=120` (فرانت‌اند) | همیشه ۵۰۰ رکورد؛ ناسازگاری قرارداد | رفع شد |
| API-4-12 | متوسط (تست) | تست heatmap خرابی endpoint را نمی‌گرفت | `test_market_aggregate_cache.py` نسخهٔ قبل | اجرای تست‌ها روی endpoint خراب | اطمینان کاذب؛ ۲۶ تست PASS با endpoint شکسته | تست تقویت شد |
| API-4-13 | بالا (باقی) | کش درون‌پروسه‌ای است؛ sync در پروسهٔ دیگر آن را invalidate نمی‌کند | `market.py:534-578`؛ `sync_service.py:501-509` | API و Scheduler جدا | حداکثر ۳۰۰ ثانیه کهنگی (با `data_as_of` قابل‌تشخیص) | باز (handoff) |
| API-4-14 | متوسط (باقی) | `market_watch`/insights/`market_dashboard` متادیتای `data_as_of` ندارند | `market_watch.py`، `market_insights.py`، `market_dashboard.py` | پاسخ‌های aggregate | مصرف‌کننده فقط از `cache_hit`/timestampهای دیگر می‌فهمد | باز |
| API-4-15 | متوسط (باقی) | `get_latest_indices`/`market_index_history` بر `created_at` (زمان درج) | `query_service.py:382-412`؛ `market.py:477-488` | رکورد دیررس | انتخاب شاخص کهنه | باز |
| API-4-16 | پایین (باقی) | `_AGG_CACHE` سقف ۸ کلید و بدون observability در `/cache-stats` | `market.py:566-573`؛ `apps/api/app.py:1098` | limitهای متعدد | eviction و عدم دیده‌شدن hit-rate | باز |
| API-4-17 | پایین | فرانت‌اند `success`/`data_as_of`/`cache_hit` را نمی‌خواند | `frontend/src/lib/api.ts:307-328`؛ `useMarketData.ts:728` | پاسخ success=false | UI همچنان empty/stale را از error تشخیص نمی‌دهد | handoff بخش ۰۵ |

---

## ۷. علت ریشه‌ای

1. **تغییر نیمه‌کارهٔ هم‌زمان:** فیلدهای `data_as_of`/`cache_hit` به schema و market.py اضافه شده بود، اما کوئری heatmap با `select`/`brsapi.models` ناموجود نوشته شد و تست فقط `success=False` را برای حالت خالی چک می‌کرد؛ بنابراین خرابی واقعی پوشیده شد.
2. **کش value-only:** کلید فقط نام endpoint بود (بدون `limit`) و timestamp داخل کش زمان نوشتن بود، نه `fetched_at` داده؛ در نتیجه cache hit می‌توانست داده/برش اشتباه را با ظاهر تازه سرو کند.
3. **invalidation در لایهٔ orchestration اشتباه:** فقط `sync_all` پاک می‌کرد؛ jobهای دوره‌ای `sync_all_symbols` را مستقیم صدا می‌زنند.
4. **catch-all در dashboard/market_info:** خطاهای منبع به `success=True` با data خالی/None تبدیل می‌شدند و `Result.fail` (بدون exception) تشخیص داده نمی‌شد.
5. **کش درون‌پروسه‌ای:** API و Scheduler می‌توانند پروسهٔ جدا باشند؛ invalidate محلی کافی نیست.

---

## ۸. تغییرات کد و دلیل هرکدام

| # | فایل/خط | diff | دلیل | تست |
|---|---|---|---|---|
| C-1 | `apps/api/endpoints/market.py:111-138` | حذف کوئری خام `select(brsapi.models...)`؛ `snapshots = await get_latest_snapshots(...)` و `data_as_of = _rows_data_as_of(snapshots)` | رفع NameError/AttributeError و حذف کوئری تکراری خارج از query layer | `test_success_reports_snapshot_time_without_raw_query`، HTTP heatmap |
| C-2 | `market.py:538-552` | افزودن `_rows_data_as_of()`؛ max `fetched_at` ردیف‌ها | `data_as_of` باید زمان داده باشد، نه زمان ساخت پاسخ | تست cache/HTTP |
| C-3 | `market.py:565-578` | `_agg_cache_set` دیگر `None` را با `now` جایگزین نمی‌کند؛ `invalidate_agg_cache` | عدم جعل تازگی برای داده بدون timestamp | تست‌های cache |
| C-4 | `market.py:258,306,625,671` | کلید کش شامل `limit`؛ `enriched-heatmap:{limit}` و پارامتر `limit` در endpoint | جلوگیری از سرو دادهٔ limit دیگر | `test_different_limit_does_not_share_cache_entry`، `test_limit_is_part_of_cache_key` |
| C-5 | `market.py:289,349,632,678` | `as_of = _rows_data_as_of(enriched/snapshots)` در enriched/treemap/allocation/cashflow | کش/پاسخ timestamp داده را حمل کند | تست‌های cache |
| C-6 | `market.py:241-246` | خطای sparklines → `data={}` | حفظ قرارداد `dict[str, list[float]]` | `test_sparklines_failure_keeps_dict_contract` |
| C-7 | `market.py:385-420` | snapshots خالی → `success=False` + `data_as_of` در موفق | عدم نمایش جریان صفر جعلی | `test_flow_summary_without_snapshots_is_an_error` |
| C-8 | `market_dashboard.py:27-75` | `errors` map؛ تشخیص `Result.fail`؛ همه‌ناموفق → `success=False`؛ `_unwrap_indices` خطا می‌دهد؛ screener re-raise | خطای منبع پنهان نشود | `test_dashboard_all_sources_failed_is_success_false`، `...result_failures...`، HTTP dashboard |
| C-9 | `market_info.py:32-38,51-58,68-74` | خطا → `success=False` + error؛ dedupe صندوق‌ها با max `fetched_at` | عدم نمایش خطا به‌عنوان empty موفق؛ انتخاب NAV جدید | `test_market_info_*` |
| C-10 | `market_watch.py:27-35` | snapshots خالی → `success=False` | عدم نمایش بازار خالی جعلی | `test_market_watch_without_snapshots_is_not_success_empty` |
| C-11 | `sync_service.py:501-509` | بعد از commit snapshot، `invalidate_agg_cache()` (lazy import، fail-safe) | پوشش jobهای مستقیم + جلوگیری از کهنگی ۳۰۰ثانیه‌ای | `test_snapshot_sync_invalidates_market_aggregate_cache` |
| C-12 | `tests/unit/api/test_market_aggregate_cache.py` | تقویت تست heatmap (fetched_at)؛ حذف assertion ضعیف TTL؛ +۴ تست limit/موفق | تست واقعی، نه صرفاً `success=False` | ۱۰ تست |
| C-13 | `tests/unit/api/test_market_endpoint_contracts.py` | ۱۳ تست جدید برای error/freshness/dashboard/info/watch/HTTP | پوشش قرارداد API | ۱۳ تست |
| C-14 | `tests/unit/test_sync_service_persistence_scope.py` | +۲ تست invalidation (snapshot بله، non-snapshot خیر) | pin کردن رفتار cache | ۷ تست |

**نکته:** `schemas/common/responses.py` (فیلدهای `data_as_of`/`cache_hit`) توسط عامل هم‌زمان اضافه شده و در این ممیزی تغییر نکرد؛ فقط استفاده شد.

---

## ۹. فرمان‌های تست، نتیجه و exit code

> همه با `venv/Scripts/python.exe` (Python 3.11.9) و `PYTHONIOENCODING=utf-8`؛ بدون DB/BrsApi/Redis زنده.

| فرمان | Passed | Failed | Skipped/Deselected | Exit |
|---|---|---|---|---|
| **Baseline قبل از اصلاح:** `pytest tests/unit/api/test_market_aggregate_cache.py tests/unit/api/test_market_dashboard_aggregates.py -q ...` | **26** | 0 | 0 | 0 |
| **نهایی:** `pytest tests/unit/api/test_market_endpoint_contracts.py tests/unit/api/test_market_aggregate_cache.py tests/unit/api/test_market_dashboard_aggregates.py tests/unit/test_sync_service_persistence_scope.py tests/unit/test_backend_api.py::test_health_check -q ...` | **51** | **0** | 0 | **0** |
| رگرسیون مرحله ۳: ۹ فایل repository/worker/storage/sync-scope | **39** | 0 | 0 | **0** |
| `pytest tests/unit/test_backend_api.py::test_health_check` (app/import/route) | **1** | 0 | 0 | **0** |
| اسکریپت `create_app()` و شمارش route | — | — | **714 route، 0 duplicate** | 0 |
| `python -m py_compile` برای همه فایل‌های تغییر‌یافته | — | — | — | **0** |

جمع تست‌های نهایی Phase 4: ۵۱ = ۱۳ قرارداد + ۱۰ کش + ۲۰ dashboard aggregates + ۷ sync scope + ۱ health.  
تست‌های جدید این ممیزی: ۱۳ contracts + ۴ تست cache + ۲ تست invalidation = **۱۹** (به‌علاوه تقویت تست‌های قبلی).

### تست‌های اجرانشده و علت

| تست/بررسی | علت |
|---|---|
| `tests/unit/test_backend_api.py` بخش‌های market/watch/bourse (چند تست) | `needs_db`؛ PostgreSQL در دسترس نبود |
| `tests/e2e/test_market_overview_api.py` | نیازمند DB و `init_database` |
| E2E واقعی heatmap/treemap/dashboard با BrsApi/DB | BrsApi زنده ممنوع؛ DB عملیاتی در دسترس نبود |
| invalidate کش بین دو پروسه (API + Scheduler) | نیازمند Redis/چندپروسه؛ این محیط فراهم نبود |
| benchmark/EXPLAIN کوئری‌های newest-per-symbol | نیازمند DB با حجم واقعی |
| migration/DB destructive | ممنوع |

---

## ۱۰. خطرات باقی‌مانده و وابستگی‌ها

1. **کش درون‌پروسه‌ای:** `_AGG_CACHE` در حافظهٔ هر پروسه است. اگر Scheduler/Worker جدا از API اجرا شود، `invalidate_agg_cache()` در پروسهٔ API اجرا نمی‌شود؛ حداکثر ۳۰۰ ثانیه کهنگی باقی می‌ماند (با `data_as_of` قابل‌تشخیص). راه‌حل: Redis pub/sub یا shared cache + invalidate نسخه‌دار.
2. **فرانت‌اند:** `extractArray` مقدار `success` را نادیده می‌گیرد و `data_as_of`/`cache_hit` را نمی‌خواند؛ تا بخش ۰۵، UI همچنان empty/stale/error را یکسان می‌بیند (`frontend/src/lib/api.ts:307-328`، `useMarketData.ts:728`).
3. **endpointهای بدون `data_as_of`:** `market_watch`، `market_info`، `market_dashboard`، `flow-history`، `value-history`، `ownership-history`، `index-history` متادیتای تازگی کامل ندارند. `get_latest_indices`/`get_index_history` هنوز بر `created_at` (زمان درج) هستند.
4. **کش چندکلیدی/eviction:** `_AGG_CACHE` سقف ۸ کلید دارد؛ با limitهای متنوع ممکن است ورودی‌های دیگر evict شوند. `/cache-stats` این کش را گزارش نمی‌کند.
5. **`market_heatmap` limit ثابت ۱۰۰:** endpoint پارامتر limit ندارد؛ فرانت‌اند فقط ۱۰۰ نماد برتر را می‌بیند.
6. **`market_dashboard` هم‌زمانی/ترکیب منابع:** Result envelope حفظ شد اما `data_as_of` واحد ندارد؛ خطاها در `errors` و success=False فقط وقتی همه ناموفق‌اند.
7. **DB واقعی:** رفتار `get_latest_snapshots`/`_latest_per_symbol` روی PostgreSQL و حجم واقعی benchmark نشد؛ queryهای جدید می‌توانند پرهزینه باشند.
8. **BrsApi/Redis:** مسیرهای زنده و dedup/queue واقعی تأیید نشدند.

---

## ۱۱. معیارهای پذیرش و وضعیت

| معیار | وضعیت | شاهد |
|---|---|---|
| API وضعیت تازگی/خطا را گمراه‌کننده اعلام نکند (مسیرهای اصلاح‌شده) | ✅ PASS (offline) | heatmap/flow/dashboard/market_info/market_watch + `data_as_of` از `fetched_at` |
| cache با آزمون قابل‌پیش‌بینی باشد | ✅ PASS (offline) | hit/miss/TTL/invalidate/limit-key/empty/error؛ ۱۰ تست |
| import/route registration سالم | ✅ PASS | 714 route، 0 duplicate؛ `test_health_check` PASS |
| invalidate بعد از sync | ✅ PASS در همان پروسه | `sync()` snapshot + `sync_all()` |
| invalidate بین‌پروسه‌ای | ⛔ BLOCKED | نیازمند Redis/چندپروسه |
| تأیید DB/زنده | ⛔ BLOCKED | PostgreSQL/BrsApi در دسترس نبود |
| قرارداد فرانت‌اند (خواندن success/data_as_of) | ⚠️ handoff بخش ۰۵ | `extractArray` همچنان success را نادیده می‌گیرد |

**نتیجهٔ نهایی: PARTIAL** — اصلاحات و تست‌های آفلاین موفق و بدون failure هستند؛ اما invalidate بین‌پروسه‌ای، چند endpoint بدون تازگی، و تأیید PostgreSQL/زنده انجام نشده‌اند.

---

## ۱۲. تأیید ادعاهای نشست/گزارش قبلی

| ادعا | نتیجه |
|---|---|
| شاخه `integration/golddesk-fixes` روی `90597e05` | ✅ مستقل تأیید شد |
| ۱۵ تست `test_sync_log_repository.py` (۱۵/۱۵) | ✅ ۱۵ تست، ۱۵ pass در رگرسیون |
| گارد future-date در `useMarketData.ts` staged است | ✅ diff staged تأیید شد |
| گزارش `04...md` می‌گوید heatmap فعال و تست‌ها PASS | ❌ ناقص/گمراه‌کننده: endpoint با NameError شکست می‌خورد و تست فقط `success=False` را چک می‌کرد؛ در این ممیزی رفع و تست تقویت شد |
| گزارش `04...md` می‌گوید invalidate بعد از sync انجام شد | ⚠️ فقط `sync_all`؛ jobها `sync_all_symbols` را مستقیم صدا می‌زنند؛ در `sync()` هم اضافه شد |
| گزارش `04...md` می‌گوید `get_latest_snapshots` از MAX(id) استفاده می‌کند | ❌ منسوخ؛ مرحله ۳ به `fetched_at` منتقل شده |
| `AUDIT_BATCH_001..009_FA.md` و `ROOT_CAUSE_VERIFICATION_FA.md` | ❌ در worktree/index/history یافت نشدند؛ غیبت ثبت شد |

---

## ۱۳. فایل‌های ایجاد/تغییر‌یافته در این اجرا

**تغییر یافته:**
- `apps/api/endpoints/market.py`
- `apps/api/endpoints/market_dashboard.py`
- `apps/api/endpoints/market_info.py`
- `apps/api/endpoints/market_watch.py`
- `brsapi/services/sync_service.py`
- `tests/unit/api/test_market_aggregate_cache.py`
- `tests/unit/test_sync_service_persistence_scope.py`

**ایجاد شده:**
- `tests/unit/api/test_market_endpoint_contracts.py`
- `AUDIT_REPORTS/MODULAR_TEMCE/04_BACKEND_API_AGGREGATION_CACHE_run2.md` (همین گزارش)

**بدون commit؛ HEAD همچنان `90597e05`؛ staged/untracked قبلی حفظ شد.**
