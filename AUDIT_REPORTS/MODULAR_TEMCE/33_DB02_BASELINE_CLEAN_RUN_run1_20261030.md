# ۳۳ — DB-02: اجرای تمیز روی DB خالی compose — PASS (۳۰ اکتبر ۲۰۲۶)

**نتیجهٔ اصلی: DB-02 از FAIL به PASS روی DB خالی رسید** (`alembic upgrade head` exit 0، `current = 0119_service_private_tables`).
`pytest -m needs_db` با exit 1 تمام شد، اما **هیچ شکست واقعی** نداشت (۶ شکست محیطی، ۰ واقعی).

## ۰) قواعد رعایت‌شده
- فقط `localhost:15432`؛ هیچ فرمانی روی 5432/6379. `.env` تغییر نکرد؛ هیچ migration/model ویرایش نشد؛
  commit/stage/reset/stash/clean انجام نشد؛ رمز/DSN کامل چاپ نشد.
- کنترل هم‌زمانی: دو snapshot ۳۰ ثانیه‌ای از `migrations/` (status و mtime) **بدون تفاوت** ⇒ پایدار در بازه.

## ۱) چرا DB جداگانه ساخته شد (و نه wipe)
- `tse_quant` دیگر خالی نبود: **۲۱۸ جدول** و `alembic_version = 0119_service_private_tables`
  (کسی/عاملی قبلاً زنجیره را اجرا کرده بود).
- `pg_stat_activity` نشان داد عامل دیگری روی DB دوم `tse_quant_verify` فعال است.
- طبق قاعدهٔ «drop/recreate فقط با تأیید»، هیچ DB/volume حذف یا بازسازی نشد. برای «اجرای تمیز روی DB خالی»
  یک DB جدید خالی روی همان instance ساخته شد: **`tse_quant_clean_1030`** (owner `quant_dev`, ۰ جدول).
- هدف تأییدشده (بدون رمز): `postgresql+asyncpg://quant_dev:***@localhost:15432/tse_quant_clean_1030`.

## ۲) اجرای اول — FAIL محیطی (encoding، نه schema)
```
alembic upgrade head → exit 1
File "...\0011_add_price_volume_columns.py", line 74, in upgrade
    print("  ✅ Migration 0011 complete")
UnicodeEncodeError: 'charmap' codec can't encode character '\u2705'
```
- علت: `print` ایموجی در migration 0011 روی stdout ویندوز (cp1252) هنگام redirect به فایل.
  این نقص **قابل حمل‌بودن migration** است (نه اسکیمای DB).
- DB پس از شکست: ۰ جدول و بدون `alembic_version` (rollback کامل تراکنشی).
- لاگ: `evidence/alembic_upgrade_clean_20261030.log`.

## ۳) اجرای دوم — PASS
با `PYTHONIOENCODING=utf-8` و `PYTHONUTF8=1` (فقط env همان دستور؛ بدون ویرایش فایل):

```
alembic upgrade head   → exit 0
alembic current        → 0119_service_private_tables (head)   exit 0
alembic heads          → 0119_service_private_tables (head)   exit 0
```
وضعیت schema روی `tse_quant_clean_1030`:

| مورد | مقدار |
|---|---|
| جدول‌های `public` | **۲۱۸** |
| extensions | timescaledb 2.28.3، pg_trgm 1.6 |
| `jalali_to_gregorian` | موجود (۱ تابع) |
| materialized views | ۲ (`mv_latest_brsapi_symbol_snapshot`, `mv_latest_symbol_snapshot`) |

لاگ: `evidence/alembic_upgrade_clean_run2_20261030.log`.

## ۴) `pytest -m needs_db` (روی DB خالیِ مهاجرت‌شده)

```
42 passed, 6 failed, 3 skipped, 8159 deselected — exit 1   (198s)
```
بدون خطای collection (نسبت به اجرای قبلی روی DB بدون schema که ۲ collection error داشت).

### تفکیک شکست‌ها
| تست | خطا | تفکیک |
|---|---|---|
| `test_brsapi_sync_status::test_sync_status_returns_all_sections` | `assert 401 == 200` | **محیطی** (endpoint نیازمند auth؛ تست توکن ندارد) |
| `test_brsapi_sync_status::test_sync_history_returns_list` | `assert 401 == 200` | **محیطی** |
| `test_funds_api::test_list_search_by_symbol` | `assert data["total"] >= 1` (0) | **محیطی** (جدول `funds` بدون seed؛ تست دادهٔ از پیش موجود فرض کرده) |
| `test_funds_api::test_list_sort_by_nav_desc` | `len(items) >= 2` (1) | **محیطی** (seed ناکافی) |
| `test_funds_api::test_list_sort_by_nav_asc` | همان | **محیطی** |
| `test_funds_api::test_list_pagination_offset` | همان | **محیطی** |

**شکست واقعی مرتبط با کد/schema: هیچ (۰).** لاگ: `evidence/needs_db_clean_20261030.log`.

## ۵) ارزیابی baseline هم‌زمان (مستقل، بدون ویرایش)
- زنجیره روی DB خالی تا head رسید؛ یعنی `0004b_core_baseline` (۳۴ جدول + ۷۶ ایندکس) و اصلاحات
  0005/0006/0011/0012/0099 در عمل کافی بودند.
- **OBS-1:** `0011` با `print("✅ …")` روی ویندوز/redirect می‌شکند (رفع موقت: `PYTHONIOENCODING=utf-8`؛
  رفع کد نیازمند حذف ایموجی/استفاده از logging است — بدون تأیید انجام نشد).
- **OBS-2:** 0006/0099 با `ALTER TABLE IF EXISTS` در صورت نبود جدول بی‌صدا رد می‌شوند؛ پوشش baseline حیاتی است.
- `0007`/`0026` در حالت offline (`upgrade --sql`) همچنان BLOCKED (پیشنهاد در گزارش ۳۱؛ بدون ویرایش).

## ۶) وضعیت

| مورد | وضعیت |
|---|---|
| اجرای تمیز `upgrade head` روی DB خالی compose | **PASS** (exit 0) |
| `alembic current` = 0119 | **PASS** |
| تک‌head بودن | **PASS** |
| schema (۲۱۸ جدول + extension + تابع + matview) | **PASS** |
| `pytest -m needs_db` | **FAIL** (exit 1؛ ۶ شکست، همه محیطی/داده‌ای — ۰ واقعی) |
| **DB-02 روی DB خالی** | **PASS** (طبق معیار تعیین‌شده) |
| DB-02 روی DB موجود (`tse_quant`) | مشاهده: قبلاً 0119 و ۲۱۸ جدول — تأیید مستقل انجام نشد |
| 0007/0026 offline | **BLOCKED** |
| پایداری tree برای commit | **BLOCKED** (فایل‌های migration هم‌زمان تغییر می‌کنند) |

## ۷) فایل‌ها/DBهای ایجادشده
- DB جدید: `tse_quant_clean_1030` روی همان container (حذف نشد؛ برای شاهد باقی می‌ماند).
- لاگ‌ها: `evidence/alembic_upgrade_clean_20261030.log` (FAIL اولیه)،
  `evidence/alembic_upgrade_clean_run2_20261030.log` (PASS)،
  `evidence/needs_db_clean_20261030.log` (needs_db).
- هیچ فایل گزارش قبلی overwrite نشد.
