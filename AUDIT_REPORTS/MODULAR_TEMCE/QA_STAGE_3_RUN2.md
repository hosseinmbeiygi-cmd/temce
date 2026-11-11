# ممیزی مستقل تکمیل مرحله ۳ — دیتابیس، Schema، Repository و صحت ذخیره‌سازی

**مسیر این گزارش (ممیزی):** `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_3_RUN2.md`  
**گزارش مرحله (مرجع اجرا):** `AUDIT_REPORTS/MODULAR_TEMCE/03_DATABASE_STORAGE_REPOSITORIES_run3.md`  
**تاریخ/زمان ممیزی:** 2026-10-28 — حدود 09:55 به وقت محلی میزبان (UTC+03:30)  
**ریشهٔ مخزن:** `C:/Users/Iran/Desktop/temce`  
**شاخه:** `integration/golddesk-fixes`  
**HEAD:** `90597e05b9f4328bcd82ee819a31ba5c55413c12` (بدون commit جدید)  
**نتیجهٔ نهایی این ممیزی: PARTIAL** — اصلاحات کد و تست‌های آفلاین انجام شده‌اند؛ بخشی از تأییدها به PostgreSQL/BrsApi زنده نیاز دارد و BLOCKED است؛ چند ریسک schema/view/retention نیز باز مانده است.

> این گزارش بر اساس بازخوانی کد واقعی، diff، وضعیت Git و اجرای مجدد تست‌ها نوشته شده است، نه بر اساس ادعای گزارش قبلی. در جریان ممیزی دو نقص جدید پیدا و رفع شد؛ بنابراین آمار تست و دامنهٔ تغییرات، گزارش `run3` را به‌روزرسانی می‌کند.

---

## 1. مسیر گزارش‌ها و وجود فایل

| گزارش | مسیر | وضعیت |
|---|---|---|
| گزارش مرحله (اجرای سوم) | `AUDIT_REPORTS/MODULAR_TEMCE/03_DATABASE_STORAGE_REPOSITORIES_run3.md` | ✅ موجود؛ ۴۰۰ خط (بررسی شد) |
| گزارش ممیزی این اجرا | `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_3_RUN2.md` | ✅ همین فایل؛ overwrite روی `QA_STAGE_3.md` انجام نشد |
| گزارش ممیزی قبلی | `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_3.md` | ✅ موجود؛ دست‌نخورده |

---

## 2. وضعیت Git و حفظ تغییرات

| مورد | مقدار/شاهد |
|---|---|
| HEAD قبل و بعد | `90597e05...` → `90597e05...` (بدون commit) |
| staged قبلی | ۱۳۸ فایل؛ `git diff --cached --stat` همچنان همان حجم قبلی را نشان می‌دهد |
| تغییرات unstaged این مرحله | ۶ فایل کد + ۸ فایل تست جدید (بخش ۶) |
| فایل حذف‌شده توسط این ممیزی | هیچ (`git status | grep '^ D'` = 0) |
| عملیات ممنوع انجام‌شده | هیچ: بدون `reset --hard`، `clean`، `stash`، `checkout/restore` مخرب، rebase، force push یا commit |
| تغییرات هم‌زمان دیگران | فایل‌های خارج از دامنه مثل `apps/api/endpoints/market.py` و گزارش `04_BACKEND_API_AGGREGATION_CACHE.md` توسط فرآیندهای دیگر تغییر کرده‌اند؛ این ممیزی آن‌ها را نه حذف و نه بازنویسی کرد |

**نتیجه:** الزام حفظ تغییرات کاربر/staged رعایت شد. تنها فایل‌های داخل دامنه و تست‌های جدید ویرایش/ایجاد شدند.

---

## 3. فایل‌های بررسی‌شده و بررسی‌نشده

### ۳.۱ بررسی‌شده (کامل یا بخش مرتبط، با بازخوانی مستقل)

| فایل | نوع بررسی | دلیل/بخش |
|---|---|---|
| `brsapi/models/base.py` | کامل | `RawPayloadModel`، `SyncLogModel` و تغییر UTC |
| `brsapi/models/tsetmc.py` | کامل (قبلاً) + بخش `SymbolSnapshotModel` دوباره | کلید یکتا، `fetched_at`، ایندکس‌ها |
| `brsapi/models/commodity.py` + `brsapi/models/crypto.py` | بخش مدل‌های Gold/Currency/Crypto | نبود unique، نوع `fetched_at` رشته‌ای |
| `brsapi/repositories/base.py` | کامل | `SyncLogRepository`، `RawPayloadRepository`، `BulkUpsertRepository`، `delete_where` |
| `brsapi/services/query_service.py` | کامل (۸۶۰+ خط) | همهٔ مسیرهای «آخرین» و تغییرات جدید |
| `brsapi/services/sync_service.py` | بخش‌های ۳۲۰–۵۴۰، ۱۲۴۰–۱۵۵۰ | `sync()`، Gold/Currency و Gold Pro، commit/rollback |
| `brsapi/parsers/tsetmc.py` | بخش `parse_all_symbols` | `fetched_at` مشترک و second-truncated |
| `brsapi/parsers/commodity.py` | بخش GoldCurrency/Pro/GoldCoin/Currency/Crypto | فرمت ISO رشته‌ای `fetched_at` |
| `brsapi/parsers/crypto.py` | بخش `CryptoParser.parse` | همان فرمت timestamp |
| `brsapi/migrations/001_create_brsapi_tables.py` | کامل | DDL اولیه و تناقض `String(30)` |
| `migrations/versions/0020_brsapi_snapshots_unique.py` | کامل | unique constraint و DELETE dedupe |
| `migrations/versions/0103_ingestion_source_timestamp.py` | کامل | `source_timestamp` و ادعای `_source_time` |
| `migrations/versions/0048_materialized_latest_views.py` | کامل | `DISTINCT ON ... id DESC` |
| `migrations/versions/0104_fund_market_views.py` | کامل | `created_at DESC, id DESC` |
| `migrations/versions/0105_alert_eval_indexes.py` | کامل | ایندکس `(symbol, fetched_at DESC)` |
| `ingestion/worker.py` | کامل | dedup، write failure، counters |
| `ingestion/storage/__init__.py` | کامل | `StorageLayer` و چهار writer |
| `ingestion/storage/dedup.py` | کامل | `is_duplicate/mark_seen` |
| `ingestion/storage/layered_pipeline.py` | کامل | dedup دقیقه‌ای و counters |
| `ingestion/layered_store.py` | کامل | WarmSink روی snapshot |
| `ingestion/db/models.py`، `ingestion/db/session.py` | کامل | schema جداول ingestion و asyncpg |
| `core/time/__init__.py` | کامل | `utc_now_naive`، `IRAN_TZ` |
| `tests/unit/repositories/test_sync_log_repository.py` | کامل | ۱۵ تست |
| `tests/unit/repositories/conftest.py`، `tests/conftest.py`، `tests/unit/conftest.py` | کامل | SQLite fixture و `needs_db` |
| `tests/unit/test_brsapi_sync_fixes.py`، `ingestion/tests/test_layered_store.py`، `tests/unit/test_brsapi_codal_sync.py` | کامل | تست‌های مرتبط upsert/لایه‌ها |
| `tests/unit/api/test_market_aggregate_cache.py`، `test_market_dashboard_aggregates.py`، `test_deep_confirmed_fixes.py` | کامل (اجرا) | تست‌های مجاور |
| ۸ فایل تست جدید این مرحله/ممیزی | کامل | ۲۲ تست (بخش ۵) |
| `scripts/brsapi_full_update.py` | بخش ۳۰۰–۳۳۵ و ۵۰۰–۵۴۸ | `create_all` و `truncate_first=True` |
| `brsapi/jobs/registry.py` | بخش ۶۴۰–۷۲۰ و ۱۷۵۰–۱۸۰۵ | حلقهٔ Gold Pro و نگاشت مدل‌ها |
| `apps/api/endpoints/brsapi.py` | بخش ۱۰۸–۱۶۵ | مصرف `get_crypto_prices/get_gold_coin_prices` |
| `jobs/definitions/alert_jobs.py`، `sync_jobs.py`، `apps/api/endpoints/funds.py` | بخش کوئری‌های latest | مقایسهٔ رفتار `fetched_at` |

### ۳.۲ بررسی‌نشده (عمداً)

| مورد | دلیل | آیا «بررسی‌شده» حساب شد؟ |
|---|---|---|
| کل ۱۸۱۹+ خط `sync_service.py` | فقط بخش‌های مرتبط با persistence خوانده شد | ❌ خیر |
| فرانت‌اند (به‌جز existence/diff `useMarketData.ts`) | خارج از دامنهٔ دیتابیس | ❌ خیر |
| BrsApi/TSETMC زنده | ممنوع/نیازمند دسترسی؛ هیچ درخواستی ارسال نشد | ❌ خیر |
| PostgreSQL عملیاتی، migration اجرا، introspection | عملیات روی DB عملیاتی ممنوع؛ DB تست اختصاصی در دسترس نبود | ❌ خیر |
| Redis و صف/worker واقعی | سرویس تست در دسترس نبود | ❌ خیر |
| `venv/`، `node_modules/`، `_base_wt*/`، دایرکتوری‌های دادهٔ حجیم | وابستگی/تولیدی/باینری | ❌ خیر |
| `docs/New folder/` و گزارش‌های قدیمی `AUDIT_BATCH_*` | در worktree/index/history یافت نشدند | ❌ خیر |

هیچ ادعای «کل پروژه بررسی شد» وجود ندارد.

---

## 4. جدول الزام‌های پرامپت

| # | الزام | شاهد | نتیجه | کار باقی‌مانده |
|---|---|---|---|---|
| 1 | شناسایی ریشه/شاخه/HEAD/status/diff بدون حدس | `pwd`، `git rev-parse`، `git status --short --branch`، `git diff --cached --stat` | **PASS** | — |
| 2 | حفظ staged/unstaged/untracked؛ پرهیز از عملیات مخرب Git | HEAD ثابت `90597e05`؛ ۱۳۸ فایل staged دست‌نخورده؛ هیچ reset/clean/stash/commit | **PASS** | — |
| 3 | عدم درخواست زنده BrsApi/TSETMC و عدم دست‌کاری cooldown/rate limit | هیچ کلاینت BrsApi اجرا نشد؛ تست‌ها fake/SQLite | **PASS (compliance)** | تأیید E2E زنده **BLOCKED** |
| 4 | عدم TRUNCATE/DELETE/reset روی DB عملیاتی؛ عدم چاپ secret | هیچ اتصال DB/DSN استفاده نشد؛ هیچ TRUNCATE/DELETE اجرا نشد؛ خروجی‌ها بدون credential | **PASS** | — |
| 5 | گزارش‌های قدیمی به‌عنوان سرنخ؛ تأیید مستقل ادعاها | `git ls-files`/`git log --all` برای `AUDIT_BATCH_*` و `ROOT_CAUSE_VERIFICATION` خالی؛ شاخه/فایل تست/`useMarketData.ts`/۱۵ تست مستقل بررسی شد | **PASS** | گزارش‌های قدیمی در دسترس نبودند (ثبت شد) |
| 6 | خواندن کامل فایل‌های دامنه و manifest | بخش ۳ | **PARTIAL** | `sync_service.py` کامل خوانده نشد؛ صادقانه ثبت شد |
| 7 | تغییر کوچک/هدفمند، بدون formatter سراسری | ۶ فایل کد + تست‌های جدید؛ بدون `ruff --fix` سراسری | **PASS** | — |
| 8 | گزارش در فایل، بدون overwrite | `run3` و `QA_STAGE_3_RUN2.md` | **PASS** | — |
| 9 | ساختار کامل گزارش (تاریخ، Git، manifest، یافته‌ها، جدول ایراد، ریشه، تست، ریسک، پذیرش) | `run3` + همین گزارش | **PASS** (با اصلاح یک ادعا در بخش ۷) | — |
| 10 | انجام واقعی مأموریت نه چک‌لیست | کد تغییر کرد، تست‌ها اجرا شدند، diff بررسی شد | **PASS** | — |
| 11 | تطبیق مدل writerها با migration/schema (unique، conflict target، fetched_at، زمان بازار، id) | `tsetmc.py:131-141`، `base.py:304-330`، `brsapi/migrations/001:108`، `0020:28-41` | **PARTIAL** | نوع واقعی `fetched_at`، وجود constraint و زنجیرهٔ Alembic **BLOCKED** |
| 12 | بررسی انتخاب آخرین داده با `MAX(id)`/`created_at` | `query_service.py:108-135,203-248,269-272,293-300`؛ تست‌های `test_query_latest_snapshot.py`/`test_enriched_symbol_detail.py` | **PASS (offline)** | صحت پلن/عملکرد روی PG **BLOCKED** |
| 13 | dedup پنجره‌ای، `(symbol, fetched_at)`، snapshot تکراری، دو writer، timestamp برابر/دیررس | upsert idempotency تست شد؛ رفتار late data تعریف/تست شد؛ same-second last-write-wins مستند شد | **PARTIAL** | تست هم‌زمانی دو writer و سیاست timestamp برابر روی PG باقی است |
| 14 | حفاظت قبل از truncate/replace | Gold Pro به `delete_where` محدود شد؛ `replace_filter` چندکلیدی/خالی رد می‌شود (`sync_service.py:469-480`)؛ rollout تراکنشی | **PARTIAL** | اعتبارسنجی کامل‌بودن payload قبل از replace باقی است |
| 15 | commit/rollback، received vs inserted/updated، partial failure، رکورد خراب | `sync_service.py:489-520`؛ commit per section `:1376,1502`؛ تست `test_partial_batch_failure...` | **PASS (offline)** | اعتبارسنجی رکورد خراب/partial payload محدود است |
| 16 | رفتار `needs_sync()` و ۱۵ تست واقعی | `tests/unit/repositories/test_sync_log_repository.py` → ۱۵ تست، ۱۵ pass | **PASS** | — |
| 17 | تست repository روی SQLite/test DB/fake نه DB عملیاتی | همهٔ ۳۷ تست هدف روی SQLite/fake | **PASS** | — |
| 18 | معیار پذیرش: latest/idempotency/counters/partial failure مستند + تست | بخش‌های ۵ و ۶؛ ۲۲ تست جدید | **PASS (offline)** | تأیید PostgreSQL **BLOCKED** |
| 19 | هیچ دادهٔ عملیاتی حذف/reset نشود | هیچ دستور DB اجرا نشد | **PASS** | — |
| 20 | بدون اجازه commit نشود | HEAD بدون تغییر | **PASS** | — |

---

## 5. اصلاحات: مسیر، diff، دلیل، تست

diff محتوایی نهایی (بدون نویز CRLF):

```
brsapi/models/base.py                 |   6 +-
brsapi/repositories/base.py           |  36 +++++++-
brsapi/services/query_service.py      | 190 ++++++++++++++++++++-----------
brsapi/services/sync_service.py       |  49 +++++++++-
ingestion/storage/__init__.py         |  14 ++-
ingestion/worker.py                   |  74 ++++++++++-----
6 files changed, 254 insertions(+), 115 deletions(-)
```

| # | مسیر/خط | خلاصهٔ diff | دلیل | تست مرتبط |
|---|---|---|---|---|
| F-1 | `brsapi/services/sync_service.py:1494` | `await repo.truncate()` → `await repo.delete_where("section", section_name)` در حلقهٔ Gold Pro | TRUNCATE هر بخش، بخش‌های قبلی را حذف می‌کرد | `test_gold_pro_replaces_each_section_without_truncate` (مستقیم) |
| F-2 | `brsapi/services/sync_service.py:1538` + `:469-480` | افزودن `replace_filter={"symbol": symbol}` و مسیر delete محدود در `sync()` | TRUNCATE کل جدول ۲۴ساعته برای هر symbol، تاریخ سایر نمادها را پاک می‌کرد | `test_scoped_refresh_deletes_only_the_filtered_slice` (غیرمستقیم) |
| F-3 | `brsapi/services/query_service.py:108-135,203-248,269-272` | جای `MAX(id)`/`created_at` → `row_number() ... ORDER BY fetched_at DESC, id DESC` | رکورد backfill دیررس نباید «آخرین» شود | `test_get_symbol_snapshot_uses_fetched_at_not_created_at`، `test_get_latest_snapshots_ignores_late_backfill` |
| F-4 | `brsapi/services/query_service.py:289-300` | حذف فیلتر `fetched_at == MAX(fetched_at)` جهانی؛ اکتفا به `latest_id` همان symbol | symbol با دادهٔ معتبر در صورت تازه‌بودن symbol دیگر `None` می‌شد | `test_uses_this_symbols_latest_row_not_global_max` |
| F-5 | `ingestion/worker.py:115-193` | خواندن `is_duplicate`؛ حذف try/except داخلی `_write_event`؛ `payload_written_all`؛ counter = persisted؛ skip شناسهٔ resolve‌نشده | silent loss و dedup بی‌اثر و NameError | ۴ تست `test_ingestion_worker_persistence.py` |
| F-6 | `brsapi/models/base.py:63,108` + `brsapi/repositories/base.py:222` | `datetime.now` → `utc_now_naive`؛ `fetched_at` صریح در `store()` | مقایسه‌ها UTC است ولی نوشتن محلی (UTC+03:30) بود | ۲ تست `test_clock_semantics.py` |
| F-7 | `brsapi/services/query_service.py:716-749,830-850` | `_latest_per_symbol()` و استفاده در crypto/gold/currency | حذف TRUNCATE قبلی + append هر سیکل ⇒ خروجی تکراری هر symbol | ۳ تست `test_query_latest_commodity.py` |
| F-8 | `brsapi/services/sync_service.py:469-480` | رد `replace_filter` چندکلیدی/خالی و رد `replace_filter` بدون `truncate_first` | فیلتر چندکلیدی به‌صورت OR حذف می‌کرد؛ فیلتر خالی می‌توانست به TRUNCATE سقوط کند | `test_multi_key_or_empty_replace_filter_never_truncates` |
| F-9 | `ingestion/storage/__init__.py:10,91-94` | `x or fallback` → `_first_not_none` | مقدار `0` معتبر باید حفظ شود | `test_daily_ohlcv_keeps_zero_price` |
| F-10 | `brsapi/services/sync_service.py:489-520,1376,1502` | `items_count=0` پس از rollback؛ commit per section | شمارندهٔ خطا و موفقیت بخش‌ها نادرست بود | `test_partial_batch_failure_rolls_back_and_reports_zero_persisted` (مستقیم rollback) |

**نکتهٔ صداقت تست:** F-1 با fake repo مستقیم تست شده ولی خود endpoint/DB واقعی نه. F-2 فقط از طریق `sync()` تست شده، نه wrapper 24h. F-7/F-8 در جریان همین ممیزی اضافه شدند و در `run3` نیستند.

---

## 6. فرمان‌های تست و نتیجهٔ واقعی

> همه با `venv/Scripts/python.exe` (Python 3.11.9) و `PYTHONIOENCODING=utf-8`؛ هیچ اتصال PostgreSQL/BrsApi زنده انجام نشد.

| فرمان | Passed | Failed | Skipped/Deselected | Exit |
|---|---|---|---|---|
| `pytest tests/unit/repositories/test_sync_log_repository.py tests/unit/repositories/test_bulk_upsert_repository.py tests/unit/repositories/test_query_latest_snapshot.py tests/unit/repositories/test_query_latest_commodity.py tests/unit/repositories/test_enriched_symbol_detail.py tests/unit/repositories/test_clock_semantics.py tests/unit/test_ingestion_worker_persistence.py tests/unit/test_sync_service_persistence_scope.py tests/unit/test_storage_layer_params.py -q --no-header -p no:cacheprovider` | **37** | **0** | 0 | **0** |
| `pytest tests/unit/repositories/test_sync_log_repository.py -q ...` | **15** | 0 | 0 | **0** |
| `pytest tests/unit/test_brsapi_sync_fixes.py ingestion/tests/test_layered_store.py tests/unit/test_brsapi_codal_sync.py tests/unit/api/test_market_aggregate_cache.py tests/unit/api/test_market_dashboard_aggregates.py tests/unit/test_deep_confirmed_fixes.py -q ...` | **54** | 0 | 0 | **0** |
| `pytest tests/unit/test_brsapi_sync_integration.py -q ...` | 0 | 0 | **3 deselected** | **5** |
| `python -m py_compile` روی ۶ فایل کد + ۸ فایل تست | — | — | — | **0** |

- جمع تست‌های هدف: ۳۷ = ۱۵ تست قبلی + ۲۲ تست جدید (۵ فایل تست از مرحله + ۳ فایل تست جدید ممیزی).
- `3 deselected` به‌دلیل `addopts = ["--capture=no","-m","not needs_db"]` در `pyproject.toml:130` است؛ این تست‌ها **اجرا نشده‌اند** و موفق اعلام نمی‌شوند.

### تست‌های اجرانشده و علت

| تست/بررسی | علت |
|---|---|
| `test_bulk_insert_upsert_conflicts_on_real_pg`، `test_bulk_insert_do_nothing_plain_insert_on_real_pg` و یک تست `needs_db` دیگر | PostgreSQL تست/مجاز در دسترس نبود؛ اجرا روی DB عملیاتی ممنوع |
| `alembic upgrade` و introspection نوع/constraint | عملیات schema روی DB عملیاتی ممنوع؛ DB اسکرچ در دسترس نبود |
| E2E `sync_gold_currency_pro` با API زنده | BrsApi زنده ممنوع/در دسترس نبود |
| dedup با Redis واقعی و دو writer هم‌زمان | Redis/DB تست در دسترس نبود |
| EXPLAIN/benchmark کوئری‌های `row_number` روی حجم واقعی | نیازمند DB با دادهٔ واقعی؛ بدون آن نتیجه‌گیری عملکردی نمی‌کنیم |

---

## 7. اصلاح ادعاهای گزارش قبلی (`run3`)

1. **جهت اثر ناسازگاری ساعت اشتباه توصیف شده بود.** در `run3` آمده بود `purge_older_than` رکوردهای «جوان‌تر» را حذف می‌کند. با offset محلی `+03:30`، timestamp محلی **جلوتر** از UTC است؛ بنابراین رکوردهای legacy **دیرتر** حذف می‌شوند (نه زودتر) و پنجرهٔ `count_since/get_sync_stats` **بزرگ‌تر** می‌شود. اصلاح در همین گزارش ثبت شد. تست‌های `test_clock_semantics.py` جهت درست را pin می‌کنند.
2. **آمار تست `run3` به‌روزرسانی شد:** ۲۹ تست در زمان `run3`؛ پس از دو اصلاح جدید ممیزی اکنون **۳۷ تست** هدف (۱۵ قبلی + ۲۲ جدید) pass است.
3. **دو نقص جدید که در `run3` نبودند:**
   - خروجی تکراری gold/currency/crypto پس از حذف TRUNCATE از `sync_gold_currency` (F-7).
   - خطر حذف بیش‌ازحد/سقوط به TRUNCATE در `replace_filter` چندکلیدی/خالی (F-8).
4. **تعداد فایل‌های تست جدید:** ۸ فایل (۵ فایل مرحله + ۳ فایل ممیزی) با ۲۲ تست.

---

## 8. موارد BLOCKED (نیازمند دسترسی خارجی)

| مورد | مانع | اثر بر پذیرش |
|---|---|---|
| تأیید نوع واقعی `brsapi_symbol_snapshots.fetched_at` و وجود `uq_snap_symbol_fetched` | PostgreSQL عملیاتی/تست در دسترس نیست | تطبیق schema–مدل کامل تأیید نشد (S-12) |
| اجرای upsert واقعی `ON CONFLICT (symbol, fetched_at)` | همان مانع | idempotency فقط روی SQLite تأیید شد |
| زنجیرهٔ Alembic و migration `0020` روی DB خالی | اجرای migration ممنوع/بدون DB اسکرچ | ریسک شکست migration و نبود constraint باز است |
| E2E Gold Pro/AllSymbols و رفتار cooldown | BrsApi زنده ممنوع | نتیجهٔ end-to-end **BLOCKED** |
| Redis dedup واقعی و رقابت دو writer | سرویس Redis/DB تست در دسترس نیست | رفتار هم‌زمانی **BLOCKED** |
| عملکرد `row_number` روی جدول چندمیلیون‌ردیفی | نیازمند DB با حجم واقعی | regression عملکردی تأیید/رد نشد |

---

## 9. کارهای باقی‌مانده (دقیق)

1. **PostgreSQL verification:** introspection نوع `fetched_at`، وجود `uq_snap_symbol_fetched`، اجرای تست‌های `needs_db` و `alembic upgrade head` روی DB اسکرچ.
2. **رفع schema drift و migration orphan:** ساخت جداول `brsapi_*` داخل زنجیرهٔ Alembic یا مستندسازی صریح `create_all`؛ حل collision `revision="0022"` در `brsapi/migrations/001_create_brsapi_tables.py`.
3. **viewهای latest:** انتقال `mv_latest_brsapi_symbol_snapshot` از `id DESC` و `vw_fund_symbols` از `created_at DESC, id DESC` به `fetched_at DESC, id DESC` + refresh/test.
4. **سایر کوئری‌های latest:** `get_latest_indices` (created_at)، `get_nav` (created_at)، `get_intraday_trades` (created_at) — اصلاح یا مستندسازی قرارداد.
5. **دو writer و timestamp برابر:** تست هم‌زمانی/سیاست last-write-wins، گارد batch تکراری در `bulk_insert` و تصمیم برای `market_snapshots` بدون کلید طبیعی.
6. **source time:** پیاده‌سازی `StorageLayer._source_time` و پرکردن `source_timestamp` (migration 0103) و جلوگیری از overwrite دادهٔ تازه‌تر در `daily_ohlcv`.
7. **retention/کلید یکتا برای gold/currency/crypto:** رشد بی‌رویه پس از حذف TRUNCATE، افزودن unique/retention/partition و benchmark کوئری جدید dedup.
8. **اعتبارسنجی کامل‌بودن payload قبل از replace بخشی/symbol:** آستانهٔ تعداد رکورد یا مقایسه با cycle قبلی؛ در غیر این صورت replace را متوقف کن.
9. **گارد `truncate()` و اسکریپت full update:** `scripts/brsapi_full_update.py:539` پیش‌فرض `truncate_first=True` دارد؛ تأیید صریح/حالت dry-run اضافه شود.
10. **CI:** اجرای `needs_db` روی PostgreSQL واقعی، تست Redis و E2E با fixture؛ benchmark/EXPLAIN کوئری‌های جدید.
11. **مستندسازی رفتار شمارنده‌ها:** `bulk_insert` در نبود `rowcount` عدد attempted برمی‌گرداند (warning دارد)؛ مصرف‌کننده‌ها باید این را بدانند.

---

## 10. معیارهای پذیرش و نتیجه

| معیار پذیرش مرحله | وضعیت | شاهد |
|---|---|---|
| انتخاب «آخرین داده» مستند + تست | ✅ PASS (offline) | `test_query_latest_snapshot.py`، `test_query_latest_commodity.py`، `test_enriched_symbol_detail.py` |
| idempotency مستند + تست | ✅ PASS (SQLite) | `test_upsert_is_idempotent_and_refreshes_on_conflict`، `test_plain_insert_counter_reports_affected_rows` |
| معنای شمارنده‌ها مستند + تست | ✅ PASS | شمارندهٔ DO NOTHING=۰، خطای DB=۰، worker=persist‌شده |
| نتیجهٔ partial failure مستند + تست | ✅ PASS (offline) | `test_partial_batch_failure_rolls_back_and_reports_zero_persisted` + commit per section |
| هیچ دادهٔ عملیاتی حذف/reset نشود | ✅ PASS | هیچ اتصال/دستور DB اجرا نشد |
| تأیید روی PostgreSQL واقعی | ⛔ BLOCKED | DB تست/مجاز در دسترس نبود |
| تأیید E2E زنده | ⛔ BLOCKED | BrsApi زنده ممنوع |

### نتیجهٔ نهایی: **PARTIAL**

دلیل: اصلاحات کد و ۳۷ تست آفلاین موفق‌اند (۰ failed)، اما تأیید کامل معیارهای وابسته به PostgreSQL واقعی و BrsApi زنده ممکن نشد و چند ریسک schema/view/retention باز است. بنابراین مرحله «کامل/PASS» اعلام نمی‌شود.

---

## 11. فایل‌های ایجاد/تغییر یافته در ممیزی

**تغییر یافته (روی unstaged موجود، بدون حذف staged):**
- `brsapi/services/query_service.py` — افزودن dedup gold/currency/crypto (F-7)
- `brsapi/services/sync_service.py` — گارد `replace_filter` (F-8)

**ایجاد شده:**
- `tests/unit/repositories/test_query_latest_commodity.py` (۳ تست)
- `tests/unit/repositories/test_enriched_symbol_detail.py` (۱ تست)
- `tests/unit/repositories/test_clock_semantics.py` (۲ تست)
- `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_3_RUN2.md` (همین گزارش)
- (فایل `tests/unit/test_sync_service_persistence_scope.py` از مرحله قبل با ۱ تست جدید Gold Pro و ۱ تست گارد تکمیل شد.)

**بدون commit؛ HEAD همچنان `90597e05` است.**
