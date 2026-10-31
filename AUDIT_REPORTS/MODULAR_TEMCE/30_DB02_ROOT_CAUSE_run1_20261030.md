# ۳۰ — ریشهٔ DB-02: `alembic upgrade head` روی DB خالی (run1، ۳۰ اکتبر ۲۰۲۶)

**شدت:** Blocker انتشار (بالا) — DB تازه هرگز به head نمی‌رسد.
**دامنه:** فقط `localhost:15432/tse_quant` (compose). هیچ دستوری روی 5432 اجرا نشد؛ `.env` تغییر نکرد؛
هیچ migration/model ویرایش نشد؛ commit/reset/stash/clean انجام نشد؛ رمزها در این گزارش چاپ نمی‌شوند.
**وضعیت‌ها:** PASS / PARTIAL / BLOCKED / FAIL.

---

## ۱) Git و هدف

| مورد | مقدار |
|---|---|
| HEAD | `9a4bfe93` |
| DB هدف (بدون رمز) | `postgresql+asyncpg://quant_dev:***@localhost:15432/tse_quant` (تأیید برنامه‌ای: host/port/db) |
| Alembic heads | یک سر: `0119_service_private_tables` |
| نتیجهٔ اجرا پیش‌تر | FAIL در `0005_add_performance_indexes` → `relation "quotes" does not exist`؛ rollback کامل |

---

## ۲) بخش A — کجا ساخته می‌شوند؟ (فقط‌خواندنی)

### ۲.۱ جدول‌های `quotes` / `trades` / `instruments` / `news_articles` / `users`

| جدول | تنها سازنده در زنجیرهٔ اصلی | مصرف‌کنندهٔ زودتر |
|---|---|---|
| `quotes` | `migrations/versions/0118_core_tables_backfill.py:489` (`CREATE TABLE IF NOT EXISTS quotes`) | `0005_add_performance_indexes.py:9-24` (ایندکس)، `0102_…:30,39` (قید/شمارش) |
| `trades` | `0118_core_tables_backfill.py:577` | `0005:26` (ایندکس) |
| `instruments` | `0118_core_tables_backfill.py:228` | `0005:33-35` (ایندکس GIN) |
| `news_articles` | `0118_core_tables_backfill.py:390` | `0054_news_module_foundation.py:23` (خودش اقرار می‌کند ALTER روی جدولِ بدون migration) |
| `users` | `0118_core_tables_backfill.py:594` | migrationهای MFA/refresh (0007…) |

`0118` صریحاً می‌گوید این ۲۸ جدول تاریخی با `Base.metadata.create_all` ساخته می‌شدند و migration نداشتند؛
DDL آن‌ها «فریز» شده و همه `IF NOT EXISTS` هستند — بنابراین روی DB موجود no-op است و فقط جای خالی DB تازه را پر می‌کند.
اما شمارهٔ آن **۰۱۱۸** است، در حالی که `0005` و `0054` و `0102` **قبل** از آن به همان جدول‌ها نیاز دارند.

`0001_initial_schema.py` فقط ۱۹ جدول قدیمی بازار را می‌سازد (`symbols`, `daily_history`, `intraday_trades`, …) و
`quotes`/`trades`/`instruments`/`news_articles`/`users` در آن نیستند.

### ۲.۲ `funds`
- مدل: `apps/funds/models.py:43` (`__tablename__ = "funds"`).
- سازنده: فقط `apps/funds/db.py:38` (`Base.metadata.create_all(_engine)` در `init_db`)، با پیش‌فرض
  `SANDOOGHYAR_DB_URL`/SQLite (`apps/funds/db.py:34`).
- **هیچ migrationی در `migrations/versions/` جدول `funds` را نمی‌سازد** (grep روی `op.create_table` بدون نتیجه).

### ۲.۳ `brsapi_symbol_details`
- تنها سازنده: `brsapi/migrations/001_create_brsapi_tables.py:134` (و downgrade :856).
- این درخت **بخشی از زنجیرهٔ Alembic نیست**: `alembic.ini:2` → `script_location = migrations`؛ revision آن
  `brsapi_0001`/`down_revision=None` است (DB-01). یعنی روی DB خالی هیچ‌وقت اجرا نمی‌شود.

### ۲.۴ baseline / dump / schema.sql / initdb
- فایل dump یا `schema.sql` برای schema اصلی وجود ندارد. تنها SQLها:
  `scripts/create_views.sql` (فقط view)، `InkGist/schema.sql` (repo تودرتو و بی‌ربط)،
  `scripts/create_sqlserver_schema.py` (SQL Server، بی‌ربط).
- `docker-entrypoint-initdb.d` وجود ندارد؛ compose هیچ init SQL mount نمی‌کند.
- `core/database.py:135-141` مسیر `_create_all_tables` را دارد، اما در `:212-215` فقط با فلگ
  `database_auto_create_tables` اجرا می‌شود و پیش‌فرض آن `False` است (`core/config/__init__.py:159`)؛
  `core/README.md:119` صریح می‌گوید production باید Alembic باشد.
- مستندات راه‌اندازی: `README.md:362` و `migrations/README.md` فقط `alembic upgrade head` را تجویز می‌کنند
  و هیچ bootstrap/baseline ای ذکر نشده — یعنی مسیر مستندشده برای DB خالی **کار نمی‌کند**.

### ۲.۵ طبقه‌بندی
**دستهٔ (ج) — ترتیب/revision اشتباه** (غالب):
`0005`/`0054`/`0102` قبل از `0118` اجرا می‌شوند، در حالی که جدول‌های هدفشان فقط در `0118` ساخته می‌شوند.
اجزای (ب) هم وجود دارد: `funds` (فقط create_all در اپ صندوق) و `brsapi_*` (درخت orphan خارج از زنجیره).
ریشهٔ تاریخی (الف) هم هست: schema اولیه با `create_all` ساخته می‌شد و هیچ baseline ای برای آن نوشته نشد.

---

## ۳) بخش B — بوت‌استرپ فقط‌ممیزی

**وضعیت: BLOCKED** — طبق شرط مأموریت، بخش B فقط وقتی مجاز است که طبقه‌بندی (الف) باشد؛ نتیجهٔ بخش A
«(ج) با اجزای (ب)» است.

دلیل فنی اینکه stamp کردن مسئله را حل نمی‌کند:
- جدول‌های legacy به هیچ revision ای تعلق ندارند؛ `0118` فقط backfill با `IF NOT EXISTS` است، نه سازندهٔ آن‌ها.
  هر stamp یعنی DDL آن revision اجرا نشود.
- `create_all` schema **نهایی** را می‌سازد؛ سپس `upgrade` از 0001 با `DuplicateTable` شکست می‌خورد.
- `stamp head` هم ۰۱۰۹ (تابع/ویو `vw_daily_history_adjusted`) و backfillهای داده‌ای را رد می‌کند؛
  نتیجه یک DB با جدول‌ها اما بدون view/function است و needs_db را به خطای کاذب می‌برد.
- تنها راه درست: یک **baseline migration** که schema پیش از Alembic را ثبت کند و `0005`/`0102`/`0118` را
  هماهنگ کند — ویرایش/ساخت migration در این مأموریت ممنوع است.

در نتیجه:
- `alembic upgrade head` دوباره اجرا نشد (نتیجه تغییری نمی‌کرد).
- `pytest -m needs_db` دوباره اجرا نشد؛ آخرین اندازه‌گیری معتبر: **15 failed / 33 passed / 3 skipped / 2 errors
  — exit 1** (schema خالی؛ `evidence/needs_db_run_20261030.log`). وضعیت: **FAIL**.

---

## ۴) اثبات‌های Redis — PASS

خروجی خام: `evidence/redis_proofs_20261030_run2.log` (رمزها در لاگ‌ها redact شدند).
اسکریپت اثبات دو-فرایندی: `evidence/two_process_cache_proof.py`.

| اثبات | خروجی | exit |
|---|---|---|
| API-03 با **دو فرایند واقعی** (PIDهای جدا، Redis مشترک) | `B_WARM: ['stale']` → `A_INVALIDATED: True` → `B_AFTER: None`؛ `pids: 20360 20248 exit_a: 0 exit_b: 0` | 0 |
| WS ticket یک‌بارمصرف | `ticket_issued: True first_use: True replay: False` | 0 |
| ابطال کاربر پس از تغییر رمز | `revoke_written: True old_session_revoked: True future_session_revoked: False` | 0 |
| JobLocking واقعی | `first: True second: False extend_non_owner: False release_non_owner: False release_owner: True reacquire: True` | 0 |

**مشاهدهٔ جانبی (OBS-1، خارج از دامنهٔ این مأموریت):** `core/cache_manager.py` و `core/cache.py` هنگام اتصال،
URL کامل Redis (شامل رمز) را در لاگ می‌نویسند. لاگ‌های شاهد با `***` redact شدند، اما خود کد باید اصلاح شود.

---

## ۵) جمع‌بندی وضعیت

| مورد | وضعیت |
|---|---|
| بخش A — ریشه‌یابی فقط‌خواندنی | **PASS** |
| طبقه‌بندی | **(ج) ترتیب/revision** + اجزای (ب) + ریشهٔ (الف) |
| بخش B — بوت‌استرپ/stamp | **BLOCKED** (gate مأموریت؛ stamp راه‌حل معتبر نیست) |
| `alembic upgrade head` | **FAIL** (DB-02 در 0005) |
| `needs_db` | **FAIL** (اندازه‌گیری قبلی؛ schema خالی) |
| اثبات‌های Redis | **PASS** |
| DB-02 به‌عنوان blocker انتشار | ثبت شد |

## ۶) اقدام لازم برای رفع (خارج از این مأموریت)
1. baseline جدید: ثبت ۲۸ جدول `0118` (و `funds`/`brsapi_*`) در ابتدای زنجیره یا جلو کشیدن `0118` به قبل از `0005`
   با تضمین idempotent بودن migrationهای بعدی.
2. تعیین تکلیف درخت `brsapi/migrations` (ادغام در زنجیره یا حذف رسمی با مستندسازی).
3. به‌روزرسانی `README.md:362` و `migrations/README.md` با مسیر معتبر DB خالی.
