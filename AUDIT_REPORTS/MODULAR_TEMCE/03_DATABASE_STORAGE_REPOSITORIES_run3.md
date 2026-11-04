# گزارش ممیزی مرحله ۳ — دیتابیس، Schema، Repository و صحت ذخیره‌سازی (اجرای سوم)

**مسیر گزارش:** `AUDIT_REPORTS/MODULAR_TEMCE/03_DATABASE_STORAGE_REPOSITORIES_run3.md`  
**تاریخ اجرا:** 2026-10-28 — 09:40 به وقت محلی میزبان (UTC+03:30)، معادل 06:10 UTC  
**وضعیت:** گزارش مرجع کامل این اجرا؛ پاسخ چت فقط خلاصه است.

> گزارش‌های `03_DATABASE_STORAGE_REPOSITORIES.md` و `..._run2.md` و `QA_STAGE_3.md` از قبل وجود داشتند و overwrite نشدند. این فایل اجرای سوم است.

---

## 0. خلاصهٔ اجرایی

چند مسیر واقعی از دست‌رفتن/انتخاب نادرست داده پیدا و رفع شد:

1. **از دست رفتن داده در `sync_gold_currency_pro`:** حلقهٔ سه‌بخشی برای هر بخش `TRUNCATE` کامل جدول را اجرا می‌کرد و بخش‌های قبلی را حذف می‌کرد؛ نتیجهٔ نهایی فقط بخش آخر (`cryptocurrency`) بود.
2. **از دست رفتن داده در تاریخ ۲۴ساعتهٔ Gold Pro:** `truncate_first=True` برای هر symbol کل جدول را پاک می‌کرد؛ جاب که روی چند symbol حلقه می‌زند فقط تاریخ آخرین symbol را باقی می‌گذاشت.
3. **انتخاب «آخرین snapshot» بر اساس `id`/`created_at`:** رکورد دیررس/backfill که دیرتر درج شده ولی `fetched_at` قدیمی‌تری دارد، «آخرین» دیده می‌شد. مسیرهای snapshot در `query_service.py` به `fetched_at DESC, id DESC` اصلاح شد.
4. **از دست رفتن silent رویدادهای ingestion:** `_write_event()` خطا را می‌بلعید و payload حتی بعد از شکست نوشتن `mark_seen` می‌شد؛ همچنین `is_duplicate()` هرگز خوانده نمی‌شد. هر دو رفع شد.
5. **ناسازگاری ساعت:** `started_at` و `fetched_at` برخی مدل‌ها با `datetime.now` محلی (UTC+03:30 روی این میزبان) نوشته می‌شدند ولی مقایسه‌ها با `utc_now_naive()` انجام می‌شد؛ به UTC منتقل شد.
6. **شمارنده‌های گمراه‌کننده در partial failure:** خطای DB با `items_count=len(records)` ثبت می‌شد در حالی که تراکنش rollback شده و صفر رکورد مانده بود؛ اکنون `0` با ذکر تعداد تلاش‌شده در پیام خطا ثبت می‌شود.

موارد باز و نیازمند تصمیم/محیط واقعی (handoff): drift بین مدل و migrations برای نوع `fetched_at`، نبود migration سازندهٔ جداول `brsapi_*` در زنجیرهٔ Alembic، استفادهٔ viewهای materialized/fund از `id`/`created_at`، نبود idempotency/source-time در `market_snapshots` و `daily_ohlcv`، و رفتار دو writer هم‌زمان. جزئیات در بخش‌های ۵ و ۱۰.

هیچ درخواست زندهٔ BrsApi، هیچ TRUNCATE/DELETE/reset روی دیتابیس، هیچ migration و هیچ عملیات مخرب Git اجرا نشد. هیچ secret/DSN/token چاپ نشد.

---

## 1. شناسایی مخزن و وضعیت اولیهٔ Git

| مورد | مقدار |
|---|---|
| ریشهٔ مخزن | `C:/Users/Iran/Desktop/temce` (`pwd` → `/c/Users/Iran/Desktop/temce`) |
| شاخه | `integration/golddesk-fixes` |
| HEAD | `90597e05b9f4328bcd82ee819a31ba5c55413c12` |
| وضعیت اولیه | `## integration/golddesk-fixes`؛ حجم زیادی تغییر staged از قبل (۱۳۸ فایل) + `?? AUDIT_REPORTS/` + `?? docs/New folder/` + `m InkGist` |
| `git diff --stat` اولیه | فقط `InkGist | 0` (تغییر محتوایی unstaged در کد نبود) |
| `git diff --cached --stat` اولیه | ۱۳۸ فایل، از جمله `brsapi/services/query_service.py`، `brsapi/services/sync_service.py`، `ingestion/worker.py`، `tests/unit/repositories/test_sync_log_repository.py` |

### هشدار تغییرات هم‌زمان

در طول اجرا working tree توسط فرآیند/عامل هم‌زمان دیگری تغییر کرد: حدود **۲۰۹ فایل زیر `docs/` در working tree حذف (unstaged)** شدند و یک تغییر خارج از دامنه نیز داخل `brsapi/services/sync_service.py` (بلوک `invalidate_agg_cache` در `sync_all`) ظاهر شد. این تغییرات **توسط این مأموریت ایجاد نشده‌اند** و حذف/بازیابی/بازنویسی نشدند. HEAD در پایان اجرا هنوز `90597e05` است. `git status` پایانی ۱۵۱ ورودی دارد.

عملیات ممنوع انجام‌نشده: `git reset --hard`، `git clean`، `checkout/restore` برای دور ریختن تغییرات، `stash`، `force push/rebase`، commit خودکار، حذف فایل، بازنویسی سراسری فرمت.

---

## 2. هدف و مرز دامنه

**هدف:** بررسی صحت persistence: چه رکوردی با چه کلید طبیعی/timestamp/تضمین تراکنشی ذخیره می‌شود و query «آخرین رکورد» واقعاً آخرین داده را انتخاب می‌کند یا نه.

**در دامنه:** مدل‌های `brsapi_*`، migrations مربوط، `brsapi/repositories/base.py`، `BulkUpsertRepository.bulk_insert()`، `StorageLayer.write_market_snapshot()`، `ingestion/worker.py::_write_event/_ingest_source`، جدول `brsapi_symbol_snapshots`، `SyncLogModel`/`RawPayloadModel`، callerهای writer/query، و تست‌های repository.

**خارج از دامنه:** فرانت‌اند (به‌جز تأیید وجود و staged بودن `useMarketData.ts` طبق درخواست)، BrsApi زنده، اجرای migration، تغییر schema عملیاتی، و بازطراحی performance کوئری‌های multi-million-row بدون DB قابل‌آزمون.

---

## 3. Manifest فایل‌های خوانده‌شده

### کامل خوانده شد

| فایل | توضیح |
|---|---|
| `brsapi/repositories/base.py` | `SyncLogRepository`، `RawPayloadRepository`، `BulkUpsertRepository` (قبل/بعد از تغییر) |
| `brsapi/services/query_service.py` | کل ۸۳۱ خط (همهٔ queryهای «آخرین») |
| `ingestion/worker.py` | کل فایل (قبل/بعد از تغییر) |
| `ingestion/storage/__init__.py` | `StorageLayer` و هر چهار writer |
| `ingestion/storage/dedup.py` | `DeduplicationEngine` |
| `ingestion/storage/layered_pipeline.py` | Hot/Warm و dedup دقیقه‌ای |
| `ingestion/layered_store.py` | `HotLayer`، `SymbolSnapshotWarmSink`، `LayeredStoragePipeline` |
| `ingestion/db/models.py` | schema جداول ingestion (`trade_ticks`, `market_snapshots`, `daily_ohlcv`, `orderbook_events`) |
| `ingestion/db/session.py` | لایهٔ asyncpg (`$1` placeholders) |
| `brsapi/models/base.py` | `RawPayloadModel`، `SyncLogModel`، `BrsApiDailyUsageModel` |
| `brsapi/models/tsetmc.py` | همهٔ مدل‌های TSETMC از جمله `SymbolSnapshotModel` |
| `brsapi/models/__init__.py` | نگاشت جداول |
| `brsapi/migrations/001_create_brsapi_tables.py` | DDL اولیهٔ (orphan) جداول brsapi |
| `migrations/versions/0020_brsapi_snapshots_unique.py` | constraint یکتایی snapshot + DELETE dedupe |
| `migrations/versions/0103_ingestion_source_timestamp.py` | `source_timestamp` و ادعای `_source_time` |
| `migrations/versions/0048_materialized_latest_views.py` | `mv_latest_*` |
| `migrations/versions/0104_fund_market_views.py` | `vw_fund_symbols` |
| `migrations/versions/0105_alert_eval_indexes.py` | ایندکس `(symbol, fetched_at DESC)` |
| `migrations/versions/0066_historical_daily_unique.py` | نمونهٔ migration محافظه‌کارانه |
| `migrations/versions/0102_quotes_unique_daily.py` | dedupe شرطی + unique constraint |
| `migrations/versions/0022_add_user_mfa_columns.py` | بررسی collision شناسه‌ها |
| `tests/unit/repositories/test_sync_log_repository.py` | ۱۵ تست `needs_sync`/stats |
| `tests/unit/repositories/conftest.py` | fixture SQLite در حافظه |
| `tests/conftest.py`، `tests/unit/conftest.py` | auto-skip `needs_db`، fixtureها |
| `tests/unit/test_brsapi_sync_fixes.py` | تست‌های SQL تولیدی `bulk_insert` |
| `ingestion/tests/test_layered_store.py` | تست‌های Hot/Warm |
| `core/time/__init__.py` | `utc_now_naive()` و `IRAN_TZ` |
| تست‌های جدید این اجرا | ۵ فایل (بخش ۷) |

### بخشی خوانده شد

| فایل | بخش |
|---|---|
| `brsapi/services/sync_service.py` | خطوط ۱–۴۵، ۲۴۰–۵۶۰، ۱۲۴۰–۱۵۴۰، ۱۶۰۰–۱۷۹۰ (کل ۱۸۱۹ خط خوانده نشد) |
| `brsapi/parsers/tsetmc.py` | ۱–۱۱۰ (`parse_all_symbols`) |
| `brsapi/parsers/commodity.py` | `GoldCurrencyProParser` و `parse_section` |
| `brsapi/models/commodity.py` | سه مدل Gold/Currency Pro |
| `tests/unit/test_brsapi_sync_integration.py` | ۲۳۰–۳۱۲ (تست‌های upsert واقعی PG) |
| `jobs/definitions/alert_jobs.py` | ۷۸–۱۱۸ (کوئری latest) |
| `jobs/definitions/sync_jobs.py` | ۲۲۸–۲۶۳ |
| `apps/api/endpoints/funds.py` | ۷۵۲–۷۹۵ |
| `scripts/brsapi_full_update.py` | ۳۰۰–۳۳۵ و ۵۰۰–۵۴۸ (create_all و truncate) |
| `brsapi/jobs/registry.py` | ۶۴۰–۷۲۰ (حلقهٔ 24h/daily) |
| `pyproject.toml` | تنظیمات pytest (`addopts = -m "not needs_db"`) |
| گزارش‌های قبلی | `03...md` بخش‌های ۱–۱۲۰ و ۳۰۵–۴۳۴؛ outline `run2`؛ کل `QA_STAGE_3.md` |

### بررسی نشد

- فرانت‌اند به‌جز diff staged فایل `useMarketData.ts` (خارج از دامنهٔ DB).
- سرویس‌های BrsApi زنده، لاگ‌های runtime امروز، Docker/DB عملیاتی (ممنوع/در دسترس نبود).
- دایرکتوری‌های دادهٔ حجیم، `venv/`، `.venv/`، `node_modules/`، `_base_wt*/`، `docs/New folder/` (باینری/تولیدی/وابستگی).
- هیچ ادعای «کل پروژه بررسی شد» مطرح نمی‌شود.

---

## 4. یافته‌های تأییدشده در برابر فرضیه‌ها

### تأییدشده با شاهد کد/تست

1. **قرارداد upsert snapshot:** `UniqueConstraint("symbol","fetched_at")` در مدل (`brsapi/models/tsetmc.py:131-141`) و `ON CONFLICT (symbol, fetched_at) DO UPDATE` در `BulkUpsertRepository` (`brsapi/repositories/base.py:304-327`). تست SQLite جدید نشان داد فراخوانی دوم همان کلید، رکورد را update می‌کند و تعداد ردیف ۱ می‌ماند.
2. **`fetched_at` snapshot = زمان دریافت، نه زمان بازار:** `TsetmcParser.parse_all_symbols` یک timestamp مشترک `datetime.now(UTC)` با microsecond=0 می‌سازد (`brsapi/parsers/tsetmc.py:53,92`). زمان بازار فقط در ستون متنی `time` ذخیره می‌شود و در مرتب‌سازی نقشی ندارد ⇒ دادهٔ دیررس از دادهٔ تازه قابل تفکیک نیست.
3. **dedup پنجره‌ای در ingestion عملاً مرده بود:** `DeduplicationEngine.is_duplicate()` تعریف شده (`ingestion/storage/dedup.py:21`) ولی در `_ingest_source` هیچ فراخوانی نداشت؛ فقط `mark_seen` نوشته می‌شد. اکنون قبل از store/parse خوانده می‌شود (`ingestion/worker.py:115-122`).
4. **خطای نوشتن در worker بلعیده می‌شد:** `_write_event` خودش `try/except` داشت و `mark_seen` بیرون از آن همیشه اجرا می‌شد؛ نتیجه: رویداد شکست‌خورده برای همیشه seen می‌شد. شاهد نسخهٔ staged: `git show :ingestion/worker.py` خطوط ۱۶۳–۱۸۱. همچنین `instrument_id` در except تعریف‌نشده بود (NameError).
5. **`MAX(id)`/`created_at` به‌جای `fetched_at`:** `get_latest_snapshots` و `_enriched_snapshots_join` قبلاً `MAX(id)` می‌گرفتند و `get_symbol_snapshot` بر `created_at` مرتب می‌کرد. شاهد نسخهٔ staged: `git diff --cached -- brsapi/services/query_service.py` (خطوط قدیمی ۱۰۵–۱۲۳، ۲۶۳). تست جدید `test_query_latest_snapshot.py` نشان می‌دهد رکورد backfill با id بزرگ‌تر ولی `fetched_at` قدیمی‌تر دیگر انتخاب نمی‌شود.
6. **فیلتر global `MAX(fetched_at)` در `get_enriched_symbol_detail`:** اگر یک symbol دیگر تازه‌تر باشد، برای symbol جاری `None` برمی‌گشت (staged lines ~۲۸۴–۳۱۸). حذف شد.
7. **TRUNCATE بخشی/کلی در Gold Pro:** `sync_gold_currency_pro` برای هر سه بخش `repo.truncate()` داشت (staged/current قبل از اصلاح: خط ۱۴۶۸ نسخهٔ قبل) و `sync_gold_currency_pro_history_24h` با `truncate_first=True` کل جدول ۲۴ساعته را برای هر symbol پاک می‌کرد (`sync_service.py:1516` قبل از اصلاح).
8. **partial failure در syncهای ترکیبی:** rollback یک بخش، insertهای موفق بخش‌های قبلی را نیز برمی‌گرداند ولی `reports` آن‌ها را `success=True` نگه می‌داشت. اکنون هر بخش پس از ثبت لاگ commit می‌شود (`sync_service.py:1365`, `1491`).
9. **شمارندهٔ خطای DB:** `items_count=len(records)` بعد از rollback ثبت می‌شد؛ اکنون `0` و تعداد تلاش در `error_message` (`sync_service.py:499`).
10. **ناسازگاری ساعت:** `date` میزبان `09:40 IST` و `date -u` `06:10 UTC` ⇒ offset +03:30. `SyncLogModel.started_at` و `RawPayloadModel.fetched_at` قبلاً `datetime.now` محلی بودند، در حالی که `needs_sync`, `count_since`, `get_sync_stats`, `purge_older_than` با `utc_now_naive()` مقایسه می‌کنند. شاهد: `brsapi/models/base.py:63,108` (قبل)، `brsapi/repositories/base.py:112,121,149,243`. رفع شد.
11. **۱۵ تست `needs_sync`:** فایل واقعی ۱۵ تست دارد (۵ تست stats + ۱۰ تست needs_sync) و هر ۱۵ از ۱۵ pass شدند؛ ادعای قبلی تأیید شد (بخش ۸).
12. **شاخه/فایل‌های ادعاشدهٔ نشست قبل:** شاخه `integration/golddesk-fixes` روی `90597e05` تأیید شد؛ `frontend/src/hooks/useMarketData.ts` وجود دارد و diff staged شامل گارد «future date» است (`git diff --cached -- frontend/src/hooks/useMarketData.ts`).
13. **عدم وجود گزارش‌های قدیمی:** `AUDIT_BATCH_001_FA.md` تا `AUDIT_BATCH_009_FA.md` و `ROOT_CAUSE_VERIFICATION_FA.md` نه در working tree (مسیرهای محتمل)، نه در index (`git ls-files`) و نه در history (`git log --all`) یافت نشدند. غیبت ثبت می‌شود؛ برای پیدا کردنشان حدس زده نشد. (یک فایل مرتبط `docs/audits/ROOT_CAUSE_BATCH10.md` در index وجود دارد ولی همان نام درخواستی نیست.)

### فرضیهٔ تأییدنشده (نیازمند DB واقعی)

- نوع واقعی ستون `brsapi_symbol_snapshots.fetched_at` (model: `DateTime`؛ `brsapi/migrations/001`: `String(30)`؛ کامنت‌ها: `timestamptz`). بدون `\d`/introspection روی DB عملیاتی قابل اثبات نیست. این تناقض به‌عنوان ریسک باز ثبت می‌شود.
- وجود واقعی constraint `uq_snap_symbol_fetched` در همهٔ محیط‌ها؛ migration `0020` آن را می‌سازد ولی migration سازندهٔ جدول در زنجیرهٔ Alembic نیست (بخش ۵، مورد S-3).
- رفتار rowcount درایور asyncpg برای `ON CONFLICT DO NOTHING` در محیط production؛ تست SQLite فقط قرارداد را pin می‌کند.
- صحت پلن اجرایی کوئری جدید `row_number()` روی جدول چندمیلیون‌ردیفی؛ به‌دلیل ممنوعیت/نبود DB اجرا نشد.

---

## 5. جدول ایرادها

شدت: **Critical** = از دست رفتن دادهٔ عملیاتی؛ **High** = انتخاب/ذخیرهٔ نادرست داده یا silent loss؛ **Medium** = شمارنده/ناسازگاری/ریسک محیطی؛ **Low** = مستندسازی/قرارداد.

| # | شدت | عنوان | شاهد (path:line) | بازتولید | اثر | وضعیت |
|---|---|---|---|---|---|---|
| S-1 | Critical | TRUNCATE کل جدول Gold Pro برای هر بخش، بخش‌های قبلی را حذف می‌کند | قبل از اصلاح: `brsapi/services/sync_service.py:1468` (نسخهٔ قبل)؛ کد فعلی: `:1483` | فراخوانی `sync_gold_currency_pro(session)` با دادهٔ سه‌بخشی؛ بعد از حلقه فقط rows بخش `cryptocurrency` می‌ماند | از دست رفتن gold/currency در هر اجرای جاب | رفع شد (delete محدود به `section`) |
| S-2 | Critical | `truncate_first=True` در تاریخ ۲۴ساعتهٔ Gold Pro کل جدول را برای هر symbol پاک می‌کند | قبل: `sync_service.py:1506`؛ فعلی: `:1525-1529` + `:468-474` | جاب `brsapi_gold_currency_pro_history_24h` روی ۲۰ symbol؛ فقط تاریخ symbol آخر می‌ماند | از دست رفتن history سایر نمادها در هر اجرا | رفع شد (`replace_filter={"symbol": symbol}` + `delete_where`) |
| S-3 | High | آخرین snapshot با `MAX(id)`/`created_at` انتخاب می‌شد، نه `fetched_at` | `brsapi/services/query_service.py:110-130` (قبل `MAX(id)`), `:250-273` (قبل `created_at`) | درج رکورد backfill با id بزرگ‌تر و `fetched_at` قدیمی‌تر؛ `get_latest_snapshots`/`get_symbol_snapshot` آن را «آخرین» می‌دید | نمایش قیمت کهنه به‌عنوان جاری؛ ناسازگاری alert/quote | رفع شد (row_number بر `fetched_at DESC, id DESC`) |
| S-4 | High | فیلتر global `MAX(fetched_at)` در `get_enriched_symbol_detail` | `query_service.py:277-300` (فیلتر حذف شد؛ `latest_id` ماند) | دو writer با timestamp متفاوت؛ symbol قدیمی‌تر `None` برمی‌گرداند | نبود دادهٔ معتبر برای symbol | رفع شد |
| S-5 | High | `_write_event` خطا را می‌بلعید و payload بعد از شکست seen می‌شد | نسخهٔ staged: `ingestion/worker.py:163-181`؛ فعلی: `:176-193` | storage را به خطا وادار کنید؛ `_ingest_source` بدون exception برمی‌گشت و `mark_seen` اجرا می‌شد | silent data loss، عدم retry | رفع شد (propagate + `payload_written_all`) |
| S-6 | High | `is_duplicate()` هرگز خوانده نمی‌شد (dedup پنجره‌ای مرده) | `ingestion/storage/dedup.py:21`؛ `ingestion/worker.py:115-122` | payload یکسان دو بار؛ هر دو بار parse/write | هزینه/نوشتن تکراری؛ dedup بی‌اثر | رفع شد |
| S-7 | High | `NameError` روی `instrument_id` در except | نسخهٔ staged: `ingestion/worker.py:172` (قبل) | خطای storage؛ هندلر except خودش NameError می‌داد | abort پردازش بقیهٔ payload | رفع شد (`ins_id`) |
| S-8 | High | partial failure در `sync_gold_currency`/`_pro`: rollback بخش بعدی، موفقیت بخش قبلی را باطل می‌کرد ولی report موفق می‌ماند | `sync_service.py:1365`, `1491` (commit per section) | بخش دوم را به خطا وادار کنید؛ report بخش اول success ولی داده rollback شده | گزارش نادرست + از دست رفتن دادهٔ گزارش‌شده موفق | رفع شد |
| S-9 | Medium | `items_count` خطای DB = تعداد تلاش‌شده بعد از rollback | `sync_service.py:494-503` | خطای insert در batch دوم؛ log قدیمی `items_count=len(records)` | شمارندهٔ گمراه‌کننده/داشبورد نادرست | رفع شد (`0` + attempted در پیام) |
| S-10 | Medium | پاسخ خالی/بدون رکورد در `sync()` بدون commit برمی‌گشت | `sync_service.py:379`, `399` (commit اضافه شد) | پاسخ empty؛ log در session دیگر دیده نمی‌شد/از دست می‌رفت | dedup و observability نادرست | رفع شد |
| S-11 | Medium | ناسازگاری ساعت محلی/UTC در `started_at` و `fetched_at` | `brsapi/models/base.py:63,108`؛ مقایسه‌ها `repositories/base.py:112,121,149,243` | میزبان UTC+03:30؛ `purge_older_than` رکوردهای تا ۳.۵ ساعت جوان‌تر را حذف می‌کند و پنجرهٔ stats جابه‌جا می‌شود | حذف بیش از حد raw payload / stats نادرست | رفع شد برای نوشتن‌های جدید؛ رکوردهای legacy باز |
| S-12 | Medium | schema drift: مدل `DateTime` vs migration `String(30)` vs کامنت `timestamptz`؛ جدول‌ساز در Alembic نیست | `brsapi/models/tsetmc.py:127`؛ `brsapi/migrations/001...:108`؛ `migrations/versions/0020...:37-41` | `alembic upgrade head` روی DB خالی بدون `create_all` | migration 0020 با «relation does not exist» شکست می‌خورد؛ خطر نبود unique constraint و شکست upsert | باز (handoff) |
| S-13 | Medium | migration orphan با revision تکراری `0022` | `brsapi/migrations/001_create_brsapi_tables.py:22-23`؛ `migrations/versions/0022_add_user_mfa_columns.py:14-15` | `script_location=migrations` فقط درخت اصلی را می‌خواند؛ درخت `brsapi/migrations` اجرا نمی‌شود | DDL اولیهٔ brsapi خارج از Alembic می‌ماند؛ revision collision | باز (handoff) |
| S-14 | Medium | viewهای latest بر `id`/`created_at` بنا شده‌اند | `migrations/versions/0048...:33-35`؛ `migrations/versions/0104...:38` | مقایسه با دادهٔ backfill | همان خطای S-3 در مسیر fund/materialized | باز (handoff) |
| S-15 | Medium | `get_top_gainers/losers/most_active` به `MAX(fetched_at)` جهانی تکیه می‌کنند | `query_service.py:345,358,370` | دو writer با timestamp diferente در یک چرخه | فقط symbolهای یک writer در لیست دیده می‌شوند | باز (مستند) |
| S-16 | Low | `get_latest_indices`, `get_nav`, `get_intraday_trades` بر `created_at` (زمان درج) مرتب می‌کنند | `query_service.py:388,411,433,791` | درج دیررس | انتخاب رکورد کهنه به‌عنوان آخرین | باز (مستند) |
| S-17 | Medium | `StorageLayer` بدون idempotency/source-time؛ `market_snapshots` کلید طبیعی ندارد؛ `daily_ohlcv` با دادهٔ دیررس overwrite می‌شود؛ `source_timestamp` مهاجرت 0103 پیاده نشده | `ingestion/storage/__init__.py:29-92`؛ `migrations/versions/0103...:10,39` | retry/tick دیررس | رکورد تکراری در snapshots؛ overwrite دادهٔ تازه‌تر در OHLCV | باز (handoff) |
| S-18 | Low | شمارنده‌های `layered_pipeline` گمراه‌کننده‌اند | `ingestion/storage/layered_pipeline.py:172,187` | dedup hit یا Redis down | `deduped` همیشه ۰؛ `hot_stored` برای Redis-down افزایش می‌یابد | باز (مستند) |
| S-19 | Low | `truncate()` بدون گارد؛ اسکریپت full update پیش‌فرض `truncate_first=True` | `brsapi/repositories/base.py:375-381`؛ `scripts/brsapi_full_update.py:539` | اجرای اسکریپت روی پارس ناقص | پاک شدن جدول کامل (اسکریپت دستی) | باز (handoff) |
| S-20 | Low | `bulk_insert` در نبود rowcount، تعداد تلاش را برمی‌گرداند | `brsapi/repositories/base.py:340-349` | درایور بدون rowcount | شمارندهٔ «نوشته‌شده» = attempted | کاهش ریسک: warning اضافه شد؛ قرارداد مستند شد |

---

## 6. علت ریشه‌ای

1. **قرارداد «آخرین» در چند لایه ناهمگون بود:** بعضی مسیرها `fetched_at` (alert/sync jobs)، بعضی `MAX(id)` (query_service)، بعضی `created_at` (fund views، NAV)، و بعضی `id` (materialized view). تا وقتی writer می‌تواند دیرتر از دادهٔ تازه‌تر بنویسد، این ناهمگونی به انتخاب دادهٔ کهنه منجر می‌شود.
2. **`fetched_at` زمان دریافت است، نه زمان رویداد:** parser هر چرخه یک timestamp ساختگی مشترک می‌سازد و `source_timestamp` (که migration 0103 برای همین اضافه کرده) در `StorageLayer` پیاده نشده است. بنابراین «دیررس» و «تازه» قابل تفکیک نیستند.
3. **full-refresh با TRUNCATE بدون scope:** منطق refresh برای «یک بخش/یک symbol» با «کل جدول» اشتباه گرفته شده بود؛ هیچ تستی جلوی آن را نگرفته بود.
4. **مدیریت خطا در worker معکوس بود:** خطا در پایین‌ترین لایه بلعیده می‌شد و در لایهٔ بالا «موفق» فرض می‌شد؛ همچنین dedup فقط write-side بود.
5. **شمارنده‌ها از «تلاش» پر می‌شدند نه «اثر واقعی»:** و rollback در محاسبهٔ آن‌ها لحاظ نمی‌شد.
6. **مدیریت schema دوپاره:** مدل‌های `BrsApiBase` با `create_all` در اسکریپت ساخته می‌شوند، در حالی که migrationهای Alembic فقط ایندکس/constraint اضافه می‌کنند و یک درخت migration orphan با revision تکراری هم وجود دارد.

---

## 7. تغییرات کد و دلیل هرکدام

همهٔ تغییرات کوچک و در دامنهٔ همین مأموریت هستند. diff محتوایی (بدون نویز CRLF):

```
brsapi/models/base.py                 |  4 +-
brsapi/repositories/base.py           | 35 +-
brsapi/services/query_service.py      | 77 +-
brsapi/services/sync_service.py       | 28 +-
ingestion/storage/__init__.py         | +10
ingestion/worker.py                   | 41 +-
```

### 7.1 `brsapi/services/sync_service.py`

- افزودن `replace_filter` به `sync()` (`:332`) و اجرای `repo.delete_where` به‌جای `repo.truncate` وقتی filter داده شده (`:468-474`).
- `sync_gold_currency_pro`: `repo.delete_where("section", section_name)` قبل از insert (`:1483`) تا بخش‌های دیگر حفظ شوند.
- `sync_gold_currency_pro_history_24h`: `replace_filter={"symbol": symbol}` (`:1527`) تا فقط history همان نماد جایگزین شود.
- commit per section در دو sync ترکیبی (`:1365`, `:1491`) تا خطای بخش بعدی، موفقیت بخش قبلی را rollback نکند.
- `await sess.commit()` در دو مسیر success بدون رکورد (`:379`, `:399`).
- خطای DB: `items_count=0` و ذکر «N attempted rows (rolled back)» (`:494-503`).

**دلیل:** S-1، S-2، S-8، S-9، S-10. هیچ‌کدام رفتار «refresh کامل» را برای جدول‌های واقعاً full-refresh حذف نمی‌کند؛ فقط scope را در جایی که payload یک برش است اجباری می‌کند.

### 7.2 `brsapi/services/query_service.py`

- `_enriched_snapshots_join` و `get_latest_snapshots`: جای `MAX(id)` از `row_number() OVER (PARTITION BY symbol ORDER BY fetched_at DESC NULLS LAST, id DESC)` استفاده می‌شود (`:110-130`, `:206-230`). پنجرهٔ `_SNAPSHOT_SCAN_WINDOW` حفظ شد تا پلن فعلی index-range باقی بماند.
- `get_symbol_snapshot`: `ORDER BY fetched_at DESC NULLS LAST, id DESC` (`:270-273`).
- `get_enriched_symbol_detail`: حذف فیلتر `fetched_at == MAX(fetched_at)` جهانی و اکتفا به `latest_id` همان symbol (`:293-300`).
- docstringها به‌روزرسانی شدند تا قرارداد «آخرین = بیشترین fetched_at، tie با id» صریح باشد.

**دلیل:** S-3، S-4. محدودیت باقی‌مانده: symbolهای بدون رکورد در پنجرهٔ ۵۰هزار id هنوز از خروجی حذف می‌شوند (در بخش ۱۰ ثبت شد).

### 7.3 `ingestion/worker.py`

- خواندن `is_duplicate` قبل از `store_raw`/parse و ادامه در صورت تکراری بودن (`:115-122`).
- حذف try/except داخلی `_write_event` تا خطا به caller برسد (`:195-207`).
- `payload_written_all` و `mark_seen` فقط بعد از موفقیت همهٔ eventهای payload (`:153,176-190`)؛ خطای dedup backend فقط warning است.
- شمارندهٔ بازگشتی = تعداد eventهای persist‌شده (`:112,193`).
- `ins_id` تعریف‌نشده در except رفع شد و در صورت `None` بودن identity، event با warning skip می‌شود تا insert با `instrument_id=NULL` و retry بی‌پایان رخ ندهد (`:158-173`).
- رفع شکستگی خط ۱۴۷ (CR جاسازی‌شده) در نسخهٔ قبلی.

**دلیل:** S-5، S-6، S-7. ریسک باقی‌مانده: retry کل payload می‌تواند برای `market_snapshots` (بدون کلید طبیعی) رکورد تکراری بسازد؛ این ترجیح آگاهانه «دادهٔ تکراری بر دادهٔ گم‌شده» است و در بخش ۱۰ ثبت شد.

### 7.4 `ingestion/storage/__init__.py`

- `_first_not_none()` و جایگزینی `x or fallback` در `write_daily_ohlcv` تا مقدار `0` معتبر حفظ شود.

**دلیل:** S-17 (بخش falsy). رفتار source-time و idempotency عمداً تغییر نکرد (نیازمند migration/DB).

### 7.5 `brsapi/models/base.py` و `brsapi/repositories/base.py`

- `RawPayloadModel.fetched_at` و `SyncLogModel.started_at` از `datetime.now` محلی به `utc_now_naive` منتقل شدند (`models/base.py:63,108`).
- `RawPayloadRepository.store` صریحاً `fetched_at=receive_time or utc_now_naive()` می‌نویسد (`repositories/base.py:222`).
- `BulkUpsertRepository.delete_where()` اضافه شد (`:352-373`) با اعتبارسنجی شناسهٔ ستون از schema مدل و bind پارامتری.
- در نبود rowcount، warning صریح اضافه شد (`:344-349`).

**دلیل:** S-11، S-1/S-2 (ابزار لازم)، S-20.

### 7.6 تست‌های جدید

- `tests/unit/repositories/test_bulk_upsert_repository.py` — idempotency upsert، معنای شمارنده، scope حذف، رد ستون ناشناخته (SQLite).
- `tests/unit/repositories/test_query_latest_snapshot.py` — backfill دیررس باید بازنده باشد؛ برای `get_symbol_snapshot` و `get_latest_snapshots`.
- `tests/unit/test_ingestion_worker_persistence.py` — dedup read-side، عدم mark_seen بعد از شکست، شمارندهٔ persist‌شده، skip شناسهٔ resolve‌نشده.
- `tests/unit/test_sync_service_persistence_scope.py` — scoped replace (بدون TRUNCATE)، rollback و `items_count=0` در partial failure، commit پاسخ خالی.
- `tests/unit/test_storage_layer_params.py` — حفظ `0` در OHLCV و fallback فقط برای `None`.

---

## 8. فرمان‌های تست دقیق، نتیجه و exit code

> همهٔ اجراها با `venv/Scripts/python.exe` (Python 3.11.9، pytest 9.1.1، SQLAlchemy 2.0.51) و `PYTHONIOENCODING=utf-8` انجام شد. هیچ تستی به PostgreSQL عملیاتی/BrsApi زنده وصل نشد.

### 8.1 تست هدف اصلی (۱۵ تست `needs_sync`)

```
venv/Scripts/python.exe -m pytest tests/unit/repositories/test_sync_log_repository.py -q --no-header -p no:cacheprovider
```
**نتیجه:** `15 passed in 12.11s` — **exit 0**. ادعای «۱۵/۱۵ pass» از نشست قبل مستقل تأیید شد.

### 8.2 مجموعهٔ تست‌های هدفمند این اجرا (۱۵ تست قبلی + ۱۴ تست جدید)

```
venv/Scripts/python.exe -m pytest \
  tests/unit/repositories/test_sync_log_repository.py \
  tests/unit/repositories/test_bulk_upsert_repository.py \
  tests/unit/repositories/test_query_latest_snapshot.py \
  tests/unit/test_ingestion_worker_persistence.py \
  tests/unit/test_sync_service_persistence_scope.py \
  tests/unit/test_storage_layer_params.py \
  -q --no-header -p no:cacheprovider
```
**نتیجه:** `29 passed in 14.58s` — **exit 0** (آخرین اجرا روی وضعیت نهایی فایل‌ها).

### 8.3 تست‌های مرتبط موجود

```
venv/Scripts/python.exe -m pytest \
  tests/unit/repositories/test_sync_log_repository.py \
  tests/unit/test_brsapi_sync_fixes.py \
  ingestion/tests/test_layered_store.py \
  tests/unit/test_brsapi_codal_sync.py \
  -q --no-header -p no:cacheprovider
```
**نتیجه:** `37 passed in 23.57s` — **exit 0**.

### 8.4 تست‌های مجاور API/repository

```
venv/Scripts/python.exe -m pytest \
  tests/unit/api/test_market_aggregate_cache.py \
  tests/unit/api/test_market_dashboard_aggregates.py \
  tests/unit/test_deep_confirmed_fixes.py \
  -q --no-header -p no:cacheprovider
```
**نتیجه:** `32 passed in 25.94s` — **exit 0**.

### 8.5 تست‌های integration واقعی PostgreSQL

```
venv/Scripts/python.exe -m pytest tests/unit/test_brsapi_sync_integration.py -q --no-header -p no:cacheprovider
```
**نتیجه:** `3 deselected in 6.04s` — **exit 5**. علت: `pyproject.toml:130` پیش‌فرض `-m "not needs_db"` را اعمال می‌کند و هیچ PostgreSQL تستی در دسترس/مجاز نبود. این تست‌ها شامل `test_bulk_insert_upsert_conflicts_on_real_pg` و `test_bulk_insert_do_nothing_plain_insert_on_real_pg` هستند (شاهد: `tests/unit/test_brsapi_sync_integration.py:247-312`).

### 8.6 بررسی syntax

```
venv/Scripts/python.exe -m py_compile <all modified .py files>
```
**نتیجه:** `COMPILE_OK` — exit 0.

---

## 9. تست‌های اجرانشده و علت

| تست/بررسی | علت اجرا نشدن |
|---|---|
| upsert/idempotency روی PostgreSQL واقعی (`needs_db`) | DB تست محلی در دسترس نبود؛ اجرای تست روی DB عملیاتی ممنوع است. |
| اجرای migrationها (`alembic upgrade`) و introspection نوع ستون‌ها | عملیات schema روی DB عملیاتی ممنوع؛ محیط تست جداگانه در دسترس نبود. |
| `sync_gold_currency_pro` به‌صورت end-to-end با API واقعی | BrsApi زنده ممنوع/در cooldown؛ دادهٔ fixture کافی برای سه بخش در دسترس نبود. |
| dedup واقعی Redis + PostgreSQL | Redis/DB تست در دسترس نبود؛ منطق با fake و تست SQLite پوشش داده شد. |
| benchmark/EXPLAIN کوئری جدید `row_number()` روی جدول چندمیلیون‌ردیفی | نیازمند DB با حجم واقعی؛ تغییر پلن بدون اندازه‌گیری ریسک دارد و عمداً اجرا نشد. |
| فرانت‌اند/`useMarketData.ts` runtime | خارج از دامنهٔ این مرحله؛ فقط وجود و staged بودن گارد future-date تأیید شد. |

---

## 10. ریسک‌های باقی‌مانده و وابستگی‌ها

1. **نوع واقعی `fetched_at` و وجود constraint یکتایی:** تا introspection روی DB واقعی انجام نشود، نمی‌توان مطمئن بود `ON CONFLICT (symbol, fetched_at)` در همهٔ محیط‌ها کار می‌کند. اگر جدول قدیمی بدون migration `0020` مانده باشد، sync با خطای «no unique or exclusion constraint matching the ON CONFLICT specification» شکست می‌خورد.
2. **زاویهٔ کور پنجرهٔ ۵۰٬۰۰۰ id:** symbolهایی که در ~۲۰ چرخهٔ اخیر رکورد ندارند از `get_latest_snapshots` حذف می‌شوند. این tradeoff عملکردی است و در docstring صریح شده؛ رفع کامل نیازمند DISTINCT ON سراسری + ایندکس `(symbol, fetched_at DESC)` و اندازه‌گیری روی DB واقعی است.
3. **دو writer هم‌زمان:** `BrsApiSyncService.sync_all_symbols` و `SymbolSnapshotWarmSink` هر دو با `(symbol, fetched_at)` upsert می‌کنند. در همان ثانیه، آخرین نویسنده برنده است (last-write-wins)؛ در ثانیه‌های مختلف دو رکورد باقی می‌ماند که با `fetched_at` قابل تفکیک است. تکرار کلید در یک batch واحد (که PostgreSQL را با «cannot affect row a second time» شکست می‌دهد) در writerهای فعلی رخ نمی‌دهد چون هر symbol یک رکورد دارد؛ اما هیچ گارد دفاعی در `bulk_insert` نیست.
4. **`market_snapshots` بدون کلید طبیعی:** retry بعد از شکست جزئی worker می‌تواند رکورد تکراری بسازد. `trade_ticks` هم `ON CONFLICT DO NOTHING` بدون target دارد که فقط PK را پوشش می‌دهد.
5. **source time:** `StorageLayer` هنوز `source_timestamp` مهاجرت 0103 را پر نمی‌کند و `daily_ohlcv` می‌تواند با دادهٔ دیررس، رکورد تازه‌تر را overwrite کند. پیاده‌سازی `_source_time` نیازمند تأیید وجود ستون در DB و تغییر parserهاست.
6. **رکوردهای legacy با timestamp محلی:** رفع ناسازگاری ساعت فقط نوشتن‌های جدید را UTC می‌کند؛ ردیف‌های قدیمی `brsapi_raw_payloads`/`brsapi_sync_log` ممکن است محلی باشند و `purge_older_than`/stats برای آن‌ها تا ۳.۵ ساعت خطا داشته باشد.
7. **Gold Pro بدون کلید یکتا:** `delete_where("section")` + insert در یک تراکنش است، اما دو writer هم‌زمان می‌توانند در فاصلهٔ delete/insert یکدیگر را حذف/تکرار کنند. افزودن unique `(section, symbol, fetched_at)` نیازمند migration و dedupe است (خارج از این مأموریت).
8. **viewهای fund/materialized:** `mv_latest_brsapi_symbol_snapshot` و `vw_fund_symbols` هنوز insertion-based هستند و باید در migration جداگانه به `fetched_at` منتقل شوند.
9. **`truncate()` بدون گارد:** برای جدول‌های full-refresh واقعی باقی مانده است؛ اسکریپت دستی `scripts/brsapi_full_update.py` پیش‌فرض `truncate_first=True` دارد. هیچ اجرایی از آن انجام نشد.
10. **`layered_pipeline` جدول جداگانهٔ `armor_raw_ingest`:** این مسیر دوم ingestion است و شمارنده‌های `deduped/hot_stored` آن معنای دقیق ندارند؛ خارج از writer اصلی brsapi اما در دامنهٔ storage.

---

## 11. معیارهای پذیرش و وضعیت

| معیار | وضعیت | شاهد |
|---|---|---|
| شرط انتخاب «آخرین داده» مستند شود | ✅ PASS | docstringهای `query_service.py` و بخش ۴؛ قرارداد: بیشترین `fetched_at`، tie با `id` |
| شرط انتخاب «آخرین داده» با آزمون پوشش داده شود | ✅ PASS | `test_query_latest_snapshot.py` (۲ تست) — backfill دیررس بازنده است |
| idempotency مستند و آزمون‌شده باشد | ✅ PASS | `test_bulk_upsert_repository.py::test_upsert_is_idempotent_and_refreshes_on_conflict` + قرارداد `ON CONFLICT (symbol, fetched_at)` |
| معنای شمارنده‌ها روشن باشد | ✅ PASS | تست `test_plain_insert_counter_reports_affected_rows` (DO NOTHING = ۰)؛ خطای DB = ۰؛ worker = persist‌شده؛ warning برای نبود rowcount |
| نتیجهٔ partial failure مستند/آزمون‌شده باشد | ✅ PASS | `test_partial_batch_failure_rolls_back_and_reports_zero_persisted`؛ commit per section برای syncهای ترکیبی (code review) |
| هیچ دادهٔ عملیاتی حذف/reset نشود | ✅ PASS | هیچ اتصال DB عملیاتی، TRUNCATE/DELETE/migration اجرا نشد |
| تغییرات کوچک/هدفمند و بدون بازنویسی سراسری | ✅ PASS | diff محتوایی محدود به ۶ فایل + ۵ فایل تست جدید |
| گزارش در مسیر الزامی و بدون overwrite | ✅ PASS | همین فایل `_run3.md`؛ فایل‌های قبلی دست‌نخورده |

---

## 12. تأیید مستقل ادعاهای نشست قبل

| ادعا | نتیجهٔ بررسی مستقل |
|---|---|
| شاخه `integration/golddesk-fixes` | ✅ تأیید؛ HEAD `90597e05` در ابتدا و انتها |
| `tests/unit/repositories/test_sync_log_repository.py` دارای ۱۵ تست | ✅ تأیید؛ ۱۵ تست شمارش شد (۵ stats + ۱۰ needs_sync) |
| «۱۵/۱۰ از ۱۵» / ۱۵ تست pass | ✅ ۱۵ از ۱۵ pass، exit 0 (دستور در ۸.۱) |
| `frontend/src/hooks/useMarketData.ts` و گارد future-date | ✅ فایل موجود است؛ diff staged شامل گارد `fetched > now` است |
| گزارش‌های `AUDIT_BATCH_001..009_FA.md` و `ROOT_CAUSE_VERIFICATION_FA.md` | ❌ یافت نشدند (worktree/index/history)؛ غیبت ثبت شد |
| «هیچ تغییری در DB/storage در نشست قبل انجام نشد» | ✅ در این checkout تغییر DB دیده نشد؛ فقط تغییرات staged کد از قبل وجود داشت |

---

## 13. فایل‌های ایجاد/تغییر یافته در این اجرا

**تغییر یافته (unstaged، روی تغییرات staged قبلی حفظ شده):**

- `brsapi/models/base.py`
- `brsapi/repositories/base.py`
- `brsapi/services/query_service.py` (`MM`: staged قبلی + unstaged این اجرا)
- `brsapi/services/sync_service.py` (`MM`: staged قبلی + unstaged این اجرا؛ یک تغییر هم‌زمان خارج از دامنه نیز حفظ شد)
- `ingestion/storage/__init__.py`
- `ingestion/worker.py` (`MM`: staged قبلی + unstaged این اجرا)

**ایجاد شده (untracked):**

- `tests/unit/repositories/test_bulk_upsert_repository.py`
- `tests/unit/repositories/test_query_latest_snapshot.py`
- `tests/unit/test_ingestion_worker_persistence.py`
- `tests/unit/test_sync_service_persistence_scope.py`
- `tests/unit/test_storage_layer_params.py`
- `AUDIT_REPORTS/MODULAR_TEMCE/03_DATABASE_STORAGE_REPOSITORIES_run3.md` (همین گزارش)

**تغییر نکرده/بازیابی‌نشده:** تمام فایل‌های staged قبلی، `docs/` (شامل حذف‌های هم‌زمان خارج از این مأموریت)، `InkGist`، و گزارش‌های قبلی `AUDIT_REPORTS/`.

---

## 14. جمع‌بندی

مسیرهای بحرانی از دست رفتن داده (TRUNCATE بخشی/کلی Gold Pro)، silent loss در worker، و انتخاب «آخرین» بر اساس insertion به‌صورت هدفمند رفع و با تست‌های SQLite/fake پوشش داده شدند. آنچه باقی می‌ماند عمدتاً به schema واقعی PostgreSQL، migrationهای سازگار، و بازطراحی viewهای latest و source-time وابسته است و در بخش‌های ۵ و ۱۰ به‌صورت handoff ثبت شده است.
