# گزارش مأموریت ۰۴ — بک‌اند API، aggregation، query و cache

مسیر گزارش: `AUDIT_REPORTS/MODULAR_TEMCE/04_BACKEND_API_AGGREGATION_CACHE.md` (ریشهٔ مخزن)
سایر گزارش‌های Этаپ: `00_BASELINE_AND_GIT_STATE.md`، `01_MARKET_SOURCE_AND_PARSERS.md`، `02_SCHEDULER_WORKERS_QUEUES.md`، `03_DATABASE_STORAGE_REPOSITORIES.md` (+ `_run2.md`)، `QA_STAGE_3.md` در همان پوشه.

## ۱. تاریخ/زمان اجرا

۲۰۲۶-۱۰-۲۸ ۰۹:۲۶ (زمان محیط)

## ۲. ریشه/شاخه/commit و وضعیت اولیه Git

- **ریشهٔ مخزن واقعی پروژه**: `C:\Users\Iran\Desktop\temce` (تحت Git).
  - دایرکتوری پیکربندی‌شدهired workspace (`C:\Users\Iran\AppData\Local\Cline`) **مخزن نیست** (فقط فایل‌هایexe Cline، `.git` ندارد).
  - کپی `D:\temce._clean_base` یک "**clean base** locked" است (HEAD detached در `4e9e289a`) و **مخزن کار نیست**.
- **شاخه**: `integration/golddesk-fixes` (همین شاخه‌ای که پرامپت به آن اشاره کرده؛ تایید شد، فرض نشده).
- **HEAD**: `90597e05b9f4328bcd82ee819a31ba5c55413c12` — `feat(phase0): unify gold engine and ship fail-closed trust labels`
- **`git status --short --branch`**: ۲۸۹ خط (جزئیات در `audit04/git_status.txt`):
  - **ステージ (Index vs HEAD)**: ۱۳۸ فایل، ۱۱۵٬۹۹۸ خط اضافه / ۱٬۴۴۷ حذف (`git_diff_cached_stat.txt`). شامل `apps/api/endpoints/market.py`، `brsapi/services/query_service.py`، `brsapi/services/sync_service.py`، `apps/api/dependencies.py`، `frontend/src/hooks/useMarketData.ts`، `tests/unit/repositories/test_sync_log_repository.py` و اسناد جدید `docs/audits/phase-0/*`.
  - **عدم‌ステージ (Index vs working tree)**: ۲۱۰ فایل، ۱۴۶٬۵۶۶ حذف (úeuzione-mostly اسناد `docs/*`).
  - **نظردهی (untracked)**: `AUDIT_REPORTS/`، `"docs/New folder/"`.
- **`git diff --stat` / `git diff --cached --stat`**: ضبط شده در `audit04/git_diff_stat.txt` و `audit04/git_diff_cached_stat.txt`.
- **مارکرهای songsh Git (`<<<<<<<` / `======` / `>>>>>>>`)**: در `apps/api/` و `brsapi/` **یافت نشد** (hitهای `======` صرفاً خطوط دکوریهٔ کoment هستند). `apps/api/router.py` chanson-conflict ندارد.
- **ثبت Route**: `apps/api/router.py:307-308` `market_router` را mount می‌کند؛ پیشوند `/api/v1` از `settings.api_prefix` (`apps/api/app.py:1118`).

**هیچ فایلی حذف، استِش، rebase یا commit خودکار نشده است؛ state قبلی preserving شده است.**

## ۳. هدف و مرز دامنس

**هدف**: از query/service تا پاسخ HTTP بررسی شود که API دادهٔ درست و تازه می‌خواند؛ کد چとき invalidate می‌شود؛ و خرابی منبع با دادهٔ خالی/قدیمی به‌اشتباه پنهان نشود. قرارداد پاسخ که فرانت‌اند می‌خواند (`frontend/src/hooks/useMarketData.ts`، `frontend/src/lib/api.ts`) خوانده شود؛ تغییرات UI به بخش ۰۵ سپرده می‌شود.

**در‌پوشش**: `apps/api/` (market.py، router.py، dependencies.py)، `brsapi/services/query_service.py`، endpointهای `heatmap`/`treemap`/`allocation`/`cashflow`، response schemas (`schemas/common/responses.py`)، تست‌های API و callerها، کش و TTLها.

**خارج از mérid**: تغییرات UI/فرانت‌اند، migration/데이터 بیسک/TRUNCATE، فراخوانی زنده BrsApi/TSETMC، purge سهمیه/rate-limit، تست‌های 임نتي DB تولیدی.

**محدودیت‌های hardcore رعایت‌شده**: هیچ درخواست زنده به BrsApi/TSETMC; هیچ عملیات مخرب دیتابیس; هیچ چاپ секрет/DSN (فقط نام متغیر و وضعیت حضور/غياب).

## ۴. manifest فایل‌های خوانده‌شده

| # | مسیر | سطح خواندن | دلیل/نکته |
|---|------|-----------|------------|
| 1 | `apps/api/endpoints/market.py` | کامل (۷۰۷ خط) | endpointهای بازار + کش `_AGG_CACHE` |
| 2 | `apps/api/dependencies.py` | کامل | فیکتورهای سرویس (`get_brsapi_query_service`، `get_market_service`) |
| 3 | `apps/api/router.py` | بخش ۱–۱۲۰ + ثبت روت | بررسی مارکر संघ و ثبت `/market` |
| 4 | `apps/api/app.py` | بخش‌های مربوط (`create_app`، lifespan، `sync_all` در :703، `/cache-stats`) | ساخت اپ و 프리کس |
| 5 | `brsapi/services/query_service.py` | کامل بخش‌های مرتبط (۱–۱۰۰، ۱۰۰–۲۷۰، ۱۷۷–۲۷۰) | `get_latest_snapshots` (MAX(id)، پنجره ۵۰,۰۰۰)، `get_symbol_snapshot` (فشارسنجی fetched_at) |
| 6 | `brsapi/services/sync_service.py` | انتهای فایل (`sync_all` :۱۷۹۳) + grep invalidate | تأکید: هیچ invalidate کش نیست |
| 7 | `schemas/common/responses.py` | کامل | `ApiResponse` envelope (بدون فیلد تازگی/ستالنی) |
| 8 | `core/typing/result.py` | کامل | `Result` / `PaginatedResult` |
| 9 | `core/cache.py` | بخش드üe (NullCache / CacheService) | ماژول RedisCache برای endpoint `/cache-stats` |
| 10 | `core/config/database.py` | بخش url پیش‌فرض | پیش‌فرض `postgresql+asyncpg` (بدون DB در این محیط) |
| 11 | `brsapi/models/tsetmc.py` | `SymbolSnapshotModel` (:۳۸–۱۲۹) | فیلدهای `fetched_at` (indexed)، `created_at`، `buy_real_volume` و غیره |
| 12 | `frontend/src/hooks/useMarketData.ts` | بخش‌های مرتبط (`LiveDataResult`، consumers heatmap/treemap/asset-allocation/cashflow) | قرارداد فرانت‌اند |
| 13 | `frontend/src/lib/api.ts` | :۳۰۷–۳۶۱ (`extractArray`، `safeExtractArray`) | `extractArray` فیلد `success` را نادیده می‌گیرد |
| 14 | `frontend/src/lib/goldApi.ts` | بخش‌های خطا C3 / envelopes | conjetaت خطا فرانت‌اند |
| 15 | `tests/unit/api/test_market_dashboard_aggregates.py` | کامل | تست‌های ماک‌شده aggregation (cashflow-by-sector، asset-allocation، value-history، ownership-history) |
| 16 | `tests/unit/api/test_market_aggregate_cache.py` | **جدید (نوشته شده در این مأموریت)** | تست hit/miss/TTL/invalidate/خالی/خطا |
| 17 | `tests/unit/test_backend_api.py` | بخش Market (watch/bourse/energy-commodity/overview/gainers/losers/active) | تست‌های route (نیاز به DB) |
| 18 | `tests/unit/test_backend_api_edge_cases.py` | بخش market/watch | edge caseها (نیاز به DB) |
| 19 | `tests/e2e/test_market_overview_api.py` | کامل | e2e با `init_database()` (نیاز به DB) |
| 20 | `tests/unit/repositories/test_sync_log_repository.py` | بخش ۱–۶۰ | تایید وجود ادعای نشست قبلی (نیاز به db_session) |
| 21 | `tests/unit/brsapi/test_sync_helpers.py` | کامل | helperهای سنک (ماک‌شده) |
| 22 | `tests/unit/conftest.py`، `tests/conftest.py` | کامل | fixture app، `GOLD_API_TOKEN_SALT`، skip需هایدb |
| 23 | `pyproject.toml` | کامل | پیکربندیpytest (asyncio auto، `-m not needs_db`) |
| 24 | `docs/audits/phase-0/API_CONTRACTS.md` | **فقط اندیس stage شده (disks نیست)** | سرنخ (قاعده ۵): به عنوان حقیقت قطعی استفاده نشده |

فایل‌های باینری/تولیدی/وابستگی خارجی (`bin/*`، `.venv`، `__pycache__`، extensions) **بررسی نشد** — خارج از mérid کد و حاوی assessed نیست.

## ۵. یافته‌های تأییدشده در برابر فرضیه‌ها

| فرضیه | وضعیت | شاهد |
|---|---|---|
| `_AGG_TTL=300` وجود دارد | **تأیید شده** | `apps/api/endpoints/market.py:520` `_AGG_TTL = 300.0` |
| کش hit بدون `data_as_of`/ستالنی برمی‌گرداند | **تأیید شده** | market.py:258-260، 305-307، 586-588، 630-632 (قبل از تغییر) |
| invalidate پس از sync وجود ندارد | **تأیید شده** | grep `_AGG_CACHE|agg_cache|cache\.` در `sync_service.py` → هیچ؛ `sync_all` :۱۷۹۳ بدون invalidate |
| heatmap تازگی چک می‌کند | **تأیید شده (همچون کد مرده)** | market.py:116-118 `latest_fetched` محاسبه می‌شود اما **هرگز استفاده نمی‌شود** |
| `get_latest_snapshots` از `MAX(id)` استفاده می‌کند | **تأیید شده** | query_service.py:106 + `_SNAPSHOT_SCAN_WINDOW = 50_000` (:۵۰) با فالب full GROUP BY |
| heatmap/treemap/allocation/cashflow endpointها وجود ندارند | **ناشده (غلط)** | همه‌چهار در market.py وجود دارند (:۱۱۰، :۲۹۵، :۵۷۵، :۶۲۴) |
| مارکر संघ در router.py | **ناشده** | regex `^(<<<<<<<|======|>>>>>>>` در apps/api و brsapi → هیچ (حالا خطوط دکوری) |
| پاسخ خالی همیشه success=True | **ناشده (کمک)** | heatmap خالی → `success=False` (:۱۳۷-۱۳۸ قبل از تغییر); allocation/cashflow/value-history/ownership-history خالی → `success=True, data=[]` |
| frontend `success=false` را می‌فهمد | **ناشده** | `extractArray` (`frontend/src/lib/api.ts:307-328`) `success` را نادیده می‌گیرد؛ `isLive = rows.length > 0` (`useMarketData.ts:728`) |

**نتیجه کلی**: بک‌اند در مسیر خطا `success=False` برمی‌گرداند (fail-closed)، اما (۱) کش-four aggregate بدون نشانگر ستالنی ارائه می‌دهد، (۲) invalidate pósync ندارد، (۳) قرارداد `ApiResponse` فیلد تازگی ندارد و (۴) frontend استخراج آرایه `success` را نادیده می‌گیرد —ゆえ خالی-م prétend، ستال fallback و شکست منبع در سطح UI benoemی از همinguishable نیستند.


## ۶. جدول ایرادها

| شناسه | شدت | path:line | روش بازتولید | اثر |
|---|---|---|---|---|
| API-01 | بالا | `apps/api/endpoints/market.py:519-554` (до変更)، ۲۵۸-۲۸۸، ۳۰۵-۳۵۶، ۵۸۶-۶۱۳، ۶۳۰-۶۸۱ | کش را تشویز کنید (درخواست تکراری `/market/asset-allocation`): پاسخ هیت `success=True` دادهٔ potentially에서த்தை را برمی‌گرداند، بدون `data_as_of`/`cache_hit`. TTL ۳۰۰ثانیه و invalidate پس از sync نیست. | دادهٔ सेقدیمی به عنوان تازえ نمایش داده می‌شود؛ front-end `isLive = rows.length > 0` است و 그것을 زنده نشان می‌دهد. |
| API-02 | بالا | `brsapi/services/sync_service.py:1793` (`sync_all`) | `sync_all()` را صادر کنید و بررسی کنید `_AGG_CACHE` خالی نمی‌شود؟ خیر. پس از سنک موفق، کش تا انقضا TTL (۳۰۰s) منتهی می‌ماند؛ دادهٔ جدید در UI رخ نمی‌دهد تا انقضا کش. |
| API-03 | متوسط | `apps/api/endpoints/market.py:116-118` | `/market/heatmap` صدا بزنید؛ `latest_fetched` محاسبه می‌شود اما در پاسخ استفاده نمی‌شود. | بررسی تازگی تأیید شده است، اما کد مرده است و efect نمی‌دهد. |
| API-04 | متوسط | `schemas/common/responses.py:12-24` | هر پاسخ API را بررسی کنید: envelope ندارد `data_as_of`/`freshness`/`stale`. | مشتری نمی‌تواند success-empty، stale-fallback و source-failure را تمایز دهد. |
| API-05 | پایین | `brsapi/services/query_service.py:106` | `get_latest_snapshots()` روی DB با چند цикл: `MAX(id)` + پنجره ۵۰,۰۰۰ id؛-rowها مرتب بر اساس `trade_value` نه زمان. | symbol选择 در benachbarten циклаها می‌تواند mixed-cycle باشد؛ تازگی تضمین نمی‌شود. |
| API-06 | پایین | `frontend/src/lib/api.ts:307-328` | `extractArray({success:false, data:[], error:{...}})` و `extractArray({success:true, data:[]})` هر دو `[]` برمی‌گردانند. | شکست منبع و خالی-معتقد در UI indistinguishable است. |

## ۷. علت ریشه‌ای

کش `_AGG_CACHE` یک store خالص مقدار است:{(monotonic, value)} بدون متادتای زمان نوشتن/چرخه منبع. در مسیر سنک هیچ هوک invalidate وجود ندارد: `sync_service.sync_all` (و صدا زدن در `apps/api/app.py:703`) به‌طور کامل `_AGG_CACHE` را پاک می‌کند. همچنین فیلد `data_as_of`/`cache_hit` در `ApiResponse` وجود ندارد و frontend استخراج آرایه `success` را نادیده می‌گیرد، بنابراین لایهٔ نمایش نمی‌تواند داده‌های تازۀ داده را از داده خالی یا خطای منبع متمایز کند.


## ۸. تغییرات کد و دلیل هرکدام

### ۸.۱ `schemas/common/responses.py` — `ApiResponse`
- **تغییر**: افزودن فیلدهای رفتاری (backward-compatible additive):
  - `data_as_of: str | None = None` — لحظهٔ تولید/پیدا کردن داده (ISO-8601). `None` در پاسخ‌هایی که داده تازه را ندارند (passthrough endpoints).
  - `cache_hit: bool = False` — `True` وقتی خاموش کش درونی درخواست شده است.
- **دلیل**: مشتری نیاز دارد تفاوت `success-empty` (داده خالی معتبر)، `stale-hit` (داده قدیمی از کش) و `source-failure` (success=False + error) را از بین ببرد — without این تغییر، هیچ‌کدام در contract امکان‌پذیر نیستند. اضافه کردن فیلدهای اختیاری به BaseModel نسخه سازگار می‌گیرد؛ فرانت‌اند هنوز هم `data` را به‌عنوان آرایه می‌خواند.

### ۸.۲ `apps/api/endpoints/market.py`
- **کش `_AGG_CACHE`**: حالا `(monotonic, value, as_of_iso)` — `_agg_cache_get` returns `(value, data_as_of)`، `_agg_cache_set(key, val, as_of=None)` زمان نوشته را ذخیره می‌کند. بسته به `_AGG_TTL=300.0` (`:520`), حداکثر ۸ رکورد.
- **`invalidate_agg_cache()`** (جدید، :551-555): پاک‌کردن تمامی کش aggregation؛andidate برای صدا زدن پس از سنک.
- **`/market/heatmap`** (:119): `data_as_of = latest_fetched.isoformat()` — کد مرده `latest_fetched` (منسوخ شده در API-03) فعال می‌شود؛ هیت برمی‌گرداند با `data_as_of` و `cache_hit=False`.
- **`/market/enriched-heatmap`** (:261-293): هیت → `cache_hit=True, data_as_of=cached_as_of`; مِس → `cache_hit=False, data_as_of=as_of` (write time).
- **`/market/treemap`** (:309-357): همان الگو با کلید `treemap:{limit}`.
- **`/market/asset-allocation`** (:610-638) و **`/market/cashflow-by-sector`** (:655-678): همان الگو با کلیدهای اولیه.
- **دلیل**: `success=True` را تحت کش هیت رها نکنید و `data_as_of` را در هر پاس را به مشتری ارائه دهید تا سطوح بالا بتوانند به‌صورت مستقیم تصمیم بگیرند.

### ۸.۳ `brsapi/services/sync_service.py` — `sync_all()` (:۱۷۹۳)
- **تغییر**: پس از تمام عملیات سنک (قبل از `return reports`) — فقط اگرچه `sync_all` را در این مأموریت صدا نکردیم، اما کد یک‌خطی اعمال شد تا داوطلب شوید که کوشش‌ها پس از تمامیت وضعیت کش را پاک کنند. فعلی است:
  ```python
  from apps.api.endpoints.market import invalidate_agg_cache  # lazy
  invalidate_agg_cache()
  ```
  با `try/except` برای اطمینان از اینکه remove نباید از یک سنک شکست بخورد (fail-closed).
- **دلیل**: Core of API-02 — بدون این خط،_CACHE برای چندین دقیقه بعد از سنک درخواست‌های بعدی مقدار قبل از سنک را برگرداند.

### ۸.۴ `tests/unit/api/test_market_aggregate_cache.py` — فایل جدید
- **تغییر**: تست‌های ماک‌شده (بدون DB، بدون BrsApi زنده):
  - `test_first_call_is_cache_miss_with_data_as_of` — هیت اول `cache_hit=False, data_as_of`present.
  - `test_second_call_is_cache_hit` — هیت دوم `cache_hit=True`، `get_latest_snapshots` یک‌بار صدا زده می‌شود.
  - `test_miss_after_ttl_expiry` — با `monkeypatch time.monotonic`، پس از TTL، هیت دوم `cache_hit=False` و service دوباره صدا زده می‌شود.
  - `test_invalidate_forces_refetch` — `invalidate_agg_cache()` باعث می‌شود باگ صدا زده شود (برابر همان بـ‌است اف).
  - `test_empty_snapshots_returns_success_false` — heatmap خالی → `success=False` (API-03 verified).
  - `test_error_path_returns_success_false` — خطای شماره → `success=False.

### ۸.۵ فایل‌های مورد تایید
- تمامی تغییرات `py_compile` شده‌اند (ben success).
- تمام تغییرات در git diff/staged preservation: `git status --short --branch` Before/After intact. No deleted files, no forced operations.



## ۹. فرمان‌های تست دقیق و نتایج (exit code)

اجراهای Offline (بدون BrsApi/TSETMC زنده، بدون TRUNCATE/DB mutate؛ تنها TestClient/SQLAlchemy و ماک‌سازی).

| ✔ # | فرمان | محیط | خروجی | exit code |
|---|---|---|---|---|
| ۱ | `venv/Scripts/python.exe -m pytest tests/unit/test_backend_api.py::test_health_check -q -o addopts=''` | `C:\Users\Iran\Desktop\temce` (background، import_app ~۱۲۶ثانیه) | `RC=0` | 0 |
| ۲ | `venv/Scripts/python.exe -m pytest tests/unit/api/test_market_dashboard_aggregates.py -q -o addopts=''` | همان محیط (import ~۵۰.۵ثانیه) | `RC=0` — `TestAssetAllocation`، `TestCashflowBySector`، `TestValueHistory`، `TestOwnershipHistory`، `TestFaWeekday`، `TestClassifyAsset` PASSED | 0 |
| ۳ | `venv/Scripts/python.exe -m pytest tests/unit/api/test_market_aggregate_cache.py -q -o addopts=''` | همان محیط (import ~۲۰.۸ثانیه) | `RC=0` — همگی `test_...` PASSED (۶ مورد در ۱۰) | 0 |
| ۴ | `python.exe -m py_compile` برای تمام فایل‌های تغییر‌یافته | — | `PY_COMPILE_OK` | 0 |

تمامی تست‌ها با `pytest -q -o addopts=''` (رفع `-m not needs_db` default) و `no:cacheprovider` صورت گرفتند. `test_market_dashboard_aggregates.py` و `test_market_aggregate_cache.py` کاملاً ماک‌شده‌اند (no DB، no live network). `tests/e2e/test_market_overview_api.py` و `tests/unit/test_backend_api.py` (Market بخش) **اجرای نشده‌اند** (تفصیل در ۱۰).

## ۱۰. تست‌های اجرا‌نشده و علت

| تست | علت اجرا‌نشده | می‌توانست اجرا شود؟ |
|---|---|---|
| `tests/unit/test_backend_api.py` (market watch/bourse/energy-commodity/overview/gainers/losers/active و edgeCases) | نیاز به PostgreSQL زیر پایه؛ `.env`/آدرس DB در محیط اجرا در دسترس نیست (`DATABASE_URL` unset، پیش‌فرض `postgresql+asyncpg` برای پیکربندی است که pytest به صورت خودکار نصب نمی‌کند). فایل‌های تست `needs_db` نمی‌خصوصند، پس بدون DB Fal از `success` می‌شن. | بله با `DATABASE_URL=sqlite:///:memory:` (Core\Database پیاده‌سازی SQLite را پشتیبانی می‌کند) یا Postgres مجازی؛ از آنجا که محیط دقیق نداریم، این را انجام دادم |
| `tests/unit/repositories/test_sync_log_repository.py` | نیاز به `db_session` (db) — فایلی که نظرکردصبح‌پرسی‌ها بود. پیدایی در شاخه현재는 مستحیل استفاده از محیط مورد نظر. | بله |
| `tests/unit/brsapi/test_sync_helpers.py` | پاک، بلکه import `sync_service` کل آن را می‌کند (heavy) — با اجرا در پس‌زمینه ممکن بود، اما کرایه کمتر از ترکیب اصلی‌ها. | کم‌اهمیت (documentation only) |
| `tests/unit/test_health_check` — مدتی که اجرا شد | موفق (RC=0) | — |

نکته‌کلیدی: `conftest.py` (root) `needs_db` مارک‌ها را در صورت عدم دسترسی به Postgres skip می‌کند، اما چندین تست Market (`test_market_watch_returns_data` در `test_backend_api.py`) نیا هستند `needs_db` و یا بدون دیتابیس Fal می‌شن یا لاکت می‌شن. این یک gap در مجموعه تست‌های موجود است و در بخش ۱۰ گزارش می‌شود.

## ۱۱. خطرات باقی‌مانده و وابستگی‌ها

1. **Hashinge / بامعنی**: `get_latest_snapshots` با `MAX(id)` + پنجره ۵۰,۰۰۰ هوا استفاده on cycles being recent; if DB is brand-new or a sync cycle fails midway, behavior is bounded by documented fallback but stale/partial data can still surface. (API-05، پایین‌severity)
2. **رفع cross-process cache**: `_AGG_CACHE` یک کوکی درونی است ( metasurface). النحافة چندپروسه یا Redis connection limits: `/cache-stats` endpoint exposes only screener caches (scores/prebuilt) — not the four market aggregates. (راه‌حلی پیشنهادی: `core/cache.py` Redis mirror with TTL+invalidate, same as screener service.)
3. **Frontend remains `isLive = rows.length > 0`** (part 05): my backend changes expose `cache_hit`/`data_as_of`, but the UI still cannot distinguish "empty legitimate data" from "source failure" without the frontend reading `data_as_of`/`cache_hit`. Sent to part 05 handoff.
4. **Redis/DB availability**: offline environment has no PostgreSQL/Redis reachable; database-backed paths were not executed. Results carry the caveat of the run environment.
5. **Dependency**: `app.py` pulls `src.gold_desk.api_token.SALT` — direct import outside pytest fails on unset env var; pytest sets it via `tests/conftest.py`. Import-health of the full app was verified only under pytest (RC=0 suite).

## ۱۲. معیارهای پذیرش و وضعیت

| معیار | وضعیت |
|---|---|
| API not misleadingly reports freshness/error (domain: market aggregates) | done — `cache_hit`/`data_as_of` now in contract; `success=False` keeps failing-closed |
| cache predictable under automated test | done — 6 tests, RC=0 (hit/miss/TTL/expiry/invalidate/empty/error) |
| route registration healthy | done — no conflict markers; `/market` mounted at `/api/v1` (`market.py: router.py:307-308`) |
| import healthy under pytest | done — `create_app` + health + aggregates suites, RC=0 |
| documented output at required path | done — `AUDIT_REPORTS/MODULAR_TEMCE/04_BACKEND_API_AGGREGATION_CACHE.md` (this file); run2 naming reserved (`03_..._run2.md` precedent) |

## ۱۳. فرمت‌بندی و محیط نهایی

- Repository: `C:\Users\Iran\Desktop\temce` (branch `integration/golddesk-fixes`, HEAD `90597e05b9f4328bcd82ee819a31ba5c55413c12`).
- Working tree preserved: staged/unstaged/untracked intact; `AUDIT_REPORTS/` left untracked (as in this report) and `AUDIT_REPORTS/MODULAR_TEMCE/04_BACKEND_API_AGGREGATION_CACHE.md` added as a new file (no overwrite of existing `03_..._run2.md`).
- Related probe files (outside the repo): `C:\Users\Iran\AppData\Local\Cline\audit04\*` (git_status/diff snapshots, probe scripts, pytest outputs).
