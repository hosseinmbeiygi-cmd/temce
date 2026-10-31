# زیرساخت محلی: Redis/PostgreSQL با compose، alembic، needs_db و اثبات‌های Redis (۳۰ اکتبر ۲۰۲۶)

وضعیت‌ها فقط با واژگان PASS/PARTIAL/BLOCKED/FAIL ثبت می‌شوند. هیچ commit/reset/stash/clean انجام نشد؛
`.env` تغییر نکرد و هیچ credential ای در این فایل یا خروجی‌ها چاپ نشد (مقادیر از `docker-compose.yml` همان‌جا خوانده می‌شوند).

## ۱) compose — وضعیت

| سرویس | کانتینر | وضعیت | پورت هاست |
|---|---|---|---|
| timescale/timescaledb:latest-pg15 | `tse_timescaledb` | **PASS** (healthy، PostgreSQL 15.18، TimescaleDB 2.28.3) | `localhost:15432` → 5432 |
| redis:7.0-alpine | `tse_redis` | **PASS** (healthy، PONG) | `localhost:16379` → 6379 |

- پورت‌های 5432 و 6379 توسط سرویس‌های native (PostgreSQL و Memurai، admin-owned) اشغال بودند و از این
  session قابل توقف نبودند (`Access denied`). هیچ فرمانی روی 5432 اجرا نشد.
- برای بالا آوردن compose بدون دست‌زدن به آن سرویس‌ها، فایل override فقط‌ممیزی ساخته شد:
  `evidence/docker-compose.audit-ports.yml` (پورت‌های 15432/16379).
- کانتینر متوقف قدیمی `tse_redis` (۳ هفته پیش) با `docker rename` به `tse_redis_legacy_202609` منتقل شد
  (حذف نشد)؛ volume قدیمی `tse_redisdata` دست‌نخورده است. DB compose کاملاً تازه است (`temce_pgdata`).

## ۲) Alembic — FAIL

- هدف (بدون رمز): `postgresql+asyncpg://quant_dev:***@localhost:15432/tse_quant` — تأیید برنامه‌ای:
  `host=localhost`, `port=15432`, `db=tse_quant` ✅
- `alembic heads`: `0119_service_private_tables (head)` — **تک‌head**، ‏exit 0.
- `alembic current` روی DB خالی: بدون revision، ‏exit 0.
- `alembic upgrade head`: **exit 1**. چهار migration اول (`0001`…`0004`) اجرا شد و در پنجمی شکست:
  ```
  Running upgrade 0004_ml_symbol_results -> 0005_add_performance_indexes
  sqlalchemy.exc.ProgrammingError: (asyncpg.exceptions.UndefinedTableError):
      relation "quotes" does not exist
  [SQL: CREATE INDEX IF NOT EXISTS ix_quotes_instrument_date
        ON quotes (instrument_id, date DESC);]
  ```
- چون DDL تراکنشی است، کل upgrade rollback شد: `alembic_version` وجود ندارد و تعداد جدول‌های
  `public` صفر است. **هیچ اصلاح دستی انجام نشد** (طبق شرط). این همان **DB-02** است.
- خروجی خام: `evidence/alembic_upgrade_20261030.log`.

## ۳) تست‌های needs_db — FAIL (روی schema خالی)

- `pytest -m needs_db --collect-only`: ۴۹ تست جمع شد، ولی **۲ خطای collection**:
  `tests/test_screener_flow.py` و `tests/test_sync_2.py` (DDL در import؛ `brsapi_symbol_details` وجود ندارد).
- اجرا با `--continue-on-collection-errors`:
  **15 failed، 33 passed، 3 skipped، 2 errors — exit 1**
- علت غالب شکست‌ها: جدول‌های ساخته‌نشده (`funds`, `brsapi_symbol_details`, …) به‌دلیل شکست alembic.
  نمونهٔ خروجی خام:
  ```
  relation "funds" does not exist
  relation "brsapi_symbol_details" does not exist
  ```
- خروجی خام کامل: `evidence/needs_db_run_20261030.log`.
- نتیجه: با schema ناقص، needs_db قابل PASS نیست؛ رفع به عبور زنجیرهٔ migration (DB-02) گره خورده است.

## ۴) اثبات‌های Redis — PASS

خروجی خام: `evidence/redis_proofs_20261030.log`.

| اثبات | نتیجه | exit |
|---|---|---|
| کش aggregate بین دو نسخهٔ ماژول با Redis واقعی (`test_real_redis_invalidation_reaches_the_other_instance`) | **PASS** (1 passed؛ قبلاً skip می‌شد) | 0 |
| بلیت WS یک‌بارمصرف | `ticket_issued: True`, `first_use: True`, `replay: False` | 0 |
| ابطال کاربر پس از تغییر رمز | `revoke_written: True`, `old_session_revoked: True`, `future_session_revoked: False` | 0 |
| `JobLocking` واقعی | `first_acquire: True`, `second_acquire_same_key: False`, `extend_by_non_owner: False`, `release_by_non_owner: False`, `release_by_owner: True`, `reacquire: True` | 0 |

## ۵) وضعیت `_BaseLibParser` و dedup-before-validate در tree فعلی

### `_BaseLibParser.parse` — **رفع‌شده (PARTIAL→PASS در واحد)**
`ingestion/parser/library_parsers.py:101-134`: بدنهٔ خالی، HTML، JSON نامعتبر، نوع غیر-dict و
envelope ناشناخته دیگر `[]` بی‌صدا برنمی‌گردانند و `ParseError` با کد می‌دهند (`invalid_json` در :119،
`unexpected_shape` در :123، `missing_required_fields` در :129). یافتهٔ قدیمی C4/V8 (سکوت روی خطای
parse در خطوط ۹۷-۹۸ نسخهٔ قبل) در tree فعلی بسته است؛ `_dispatch` در :136 برای no-data خالی `[]` می‌دهد.

### dedup-before-validate — دو نقطهٔ مستقل، هر دو **PARTIAL (طراحی‌شده، نه باگ)**

1. **سطح sync** — `brsapi/services/sync_service.py:414-417`: dedup زمانی **قبل از fetch/parse/اعتبارسنجی**
   اجرا می‌شود و بر `sync_log.needs_sync` تکیه دارد. `needs_sync` فقط آخرین sync با
   `status == "success"` را مبنا می‌گیرد (`brsapi/repositories/base.py:94-116`). اما پاسخ «خالی» از
   provider به‌صورت `status="success", items_count=0` ثبت می‌شود (`sync_service.py:540-546`)، پس یک
   «no_data» واقعی تا پایان پنجرهٔ dedup دوباره fetch نمی‌شود؛ خطاها/quota/parse_error چنین نیستند و
   retry را مسدود نمی‌کنند.
2. **سطح خبر** — `services/news_ingestion.py:409-414`: بررسی `exists_by_url_or_title`
   **قبل از** parse تاریخ، استخراج نماد و طبقه‌بندی دسته انجام می‌شود؛ ردیف تکراری بدون اعتبارسنجی
   رد و به‌عنوان `skipped_existing` شمرده می‌شود (نه «saved»؛ تست
   `test_news_ingestion_skips.py`).

## ۶) وضعیت پایانی این اجرا

| مورد | وضعیت |
|---|---|
| بالا آمدن PostgreSQL/Redis با compose | **PASS** |
| `alembic upgrade head` روی DB خالی | **FAIL** (DB-02 در 0005؛ rollback؛ بدون اصلاح دستی) |
| تست‌های `needs_db` | **FAIL** (15F/33P/3S/2E؛ schema خالی) |
| اثبات‌های Redis (کش بین‌فرایندی، بلیت WS، ابطال کاربر، JobLocking) | **PASS** |
| مرحلهٔ ۳ (Scheduler/Queue) | همچنان **BLOCKED** (دو worker هم‌زمان اجرا نشد) |
| مرحلهٔ ۴ (DB) | **FAIL** تا رفع DB-02 |
