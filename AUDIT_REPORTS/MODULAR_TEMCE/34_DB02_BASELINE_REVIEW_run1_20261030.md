# ۳۴ — بازبینی مستقل baseline هم‌زمان + تست‌ها (۳۰ اکتبر ۲۰۲۶)

> شمارهٔ ۳۳ قبلاً برای «اجرای تمیز DB خالی» استفاده شده بود؛ برای پرهیز از overwrite، این گزارش ۳۴ است.

**وضعیت کلی: PARTIAL** — baseline روی زنجیره درست است و تست‌ها اضافه شدند، اما یک نقص واقعی باقی است:
ستون‌های mixin اورم (`ins_id`/`instrument_id`) روی DB تازه وجود ندارند (DB-13).

## ۰) پیش‌شرط هم‌زمانی — PASS
دو snapshot با ۳۰ ثانیه فاصله (HEAD + `git status`): HEAD ثابت `095cc98f`؛ اختلاف فقط دو فایل موقت خودِ بررسی.
هیچ ویرایش/commit/stage/reset انجام نشد؛ `.env` دست‌نخورده؛ هیچ فرمانی روی 5432/6379.

## ۱) diff پنج migration و دلیل هر تغییر

### 0005 — فقط سیم‌کشی زنجیره (بدون تغییر schema)
`down_revision: "0004_ml_symbol_results" → "0004b_core_baseline"`. دلیل: قرار دادن baseline قبل از اولین مصرف‌کننده.

### 0006 — تغییر guard (transaction-safe)، بدون تغییر schema
`contextlib.suppress(op.add_column(...))` → `op.execute('ALTER TABLE IF EXISTS … ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE')`.
- **چرا:** خطای ADD COLUMN داخل تراکنش آن را abort می‌کند؛ suppress فقط exception را می‌بلعد و تراکنش خراب می‌ماند.
- **اثر:** نوع ستون همان `DateTime` است؛ روی DB تازه idempotent. تغییر **guard** است، نه ستون/منطق.
- ⚠️ رفتار جدید: اگر جدول نباشد، بی‌صدا skip می‌شود (مثل suppress قبلی، ولی بدون خرابی تراکنش).

### 0011 — تغییر منطق (نه ستون) — علامت‌گذاری‌شده
`NULLIF({col}, '')` → `NULLIF({col}::text, '')`. دلیل: اگر ستون از قبل numeric باشد، `NULLIF(numeric,'')` سعی می‌کند `''` را عدد بخواند و روی DB تازه FAIL می‌شود. **این یک تغییر منطقی است** (cast امن)، schema را عوض نمی‌کند.

### 0012 — تغییر DDL فراتر از guard — علامت‌گذاری‌شده
حذف `op.create_index("ix_saved_filters_user_id", ...)` (و drop متناظر)، چون ستون با `index=True` همان ایندکس را در `create_table` می‌سازد و ایجاد دوباره `DuplicateTable` می‌داد. **تغییر DDL** است، اما ایندکس نهایی یکی است.

### 0099 — بازنویسی DDL/idempotency — علامت‌گذاری‌شده
`op.add_column(signals, ...)`های suppress‌شده → `ALTER TABLE IF EXISTS signals ADD COLUMN IF NOT EXISTS …` با همان نوع‌ها
(`VARCHAR(64)`, `DOUBLE PRECISION`, `TEXT`, `TIMESTAMP WITHOUT TIME ZONE`, `INTEGER DEFAULT 1`, `BOOLEAN`).
تغییر **DDL/منطق** است ولی type mapping معادل قبلی است؛ مزیت: idempotent و بدون abort تراکنش.

## ۲) بازبینی `0004b_core_baseline.py`

- `revision = "0004b_core_baseline"`, `down_revision = "0004_ml_symbol_results"`؛ موقعیت در زنجیره: **۴ از ۹۰** (بین 0004 و 0005).
- **۳۴ جدول**: ۸ هسته + ۲۵ `brsapi_*` + `dual_date_columns`؛ `funds` عمداً نیست (0015 می‌سازد).
- `downgrade()` خالی (no-op) با دلیل مستند.

### ۲.۱ خطر DuplicateColumn (ستونی که baseline دارد و migration بعدی دوباره add می‌کند)
**۱۹ مورد، همه idempotent (IF NOT EXISTS) ⇒ هیچ خطر خطای واقعی:**
`alerts.user_id` (0117) · `news_articles.published_at_ts` (0054) ·
`brsapi_candlesticks.gregorian_date/shamsi_date` (0032) · ۱۵ ستون `signals.*` (0099).
**non-idempotent risks: هیچ.** (0025 هم `gregorian_date/shamsi_date` را برای همهٔ جدول‌ها با IF NOT EXISTS اضافه می‌کند.)

### ۲.۲ Drift با منابع
| مقایسه | نتیجه |
|---|---|
| هسته vs `0118` | ۷ جدول **دقیقاً برابر**؛ `users` فقط ۵ ستون MFA کمتر (عمدی؛ 0022–0024 اضافه می‌کنند) |
| `brsapi_*` vs درخت orphan | ۲۳ جدول دقیقاً برابر؛ `brsapi_ime_futures` (+۱۴ ستون قیمتی) و `brsapi_symbol_snapshots` (+۳۰ ستون bid/ask) **superset از ORM** هستند، نه orphan |
| `dual_date_columns` | برابر با `scripts/install_dual_dates.py` (`table_name`, `source_column`) |
| ORM هسته | baseline زیرمجموعهٔ ORM است؛ تنها اختلاف همان ۵ ستون MFA کاربر |
| ORM brsapi | **۲۱ جدول از ۲۵**: ORM ستون‌های `ins_id` و `instrument_id` را map می‌کند ولی baseline (بر اساس orphan) ندارد و هیچ migration بعدی هم اضافه نمی‌کند |

### ۲.۳ نقص واقعی (DB-13، P1) — روی DB تازه ستون‌های mixin غایب‌اند
- `InstrumentRefMixin` در ORM همهٔ `brsapi_*` را با `ins_id` (و FK `instrument_id`) map می‌کند؛
  DDL orphan (و در نتیجه baseline) این ستون‌ها را ندارد و زنجیره هیچ‌جا آن‌ها را اضافه نمی‌کند.
- تأیید روی DB خالی مهاجرت‌شدهٔ `tse_quant_clean_1030`: فقط ۴ جدول `ins_id` دارند
  (`brsapi_ime_funds`, `brsapi_option_snapshots`, `brsapi_symbol_details`, `brsapi_symbol_snapshots`);
  `brsapi_candlesticks` **۰** ستون از `ins_id/instrument_id`.
- پیامد: insert/select مبتنی بر ORM روی این جدول‌ها در deployment تازه با `UndefinedColumn` می‌شکند
  (در DBهای قدیمی این ستون‌ها با `create_all` ساخته شده‌اند).
- **اصلاح نشد** (خارج از محدودهٔ این مأموریت: فقط تست/گزارش). نیازمند migration تکمیلی برای افزودن
  `ins_id`/`instrument_id` (مطابق ORM) است.

### ۲.۴ `alembic heads` و history
```
alembic heads → 0119_service_private_tables (head)   exit 0
history --verbose: 0119 (parent 0118_core_tables_backfill) → 0118 (parent 0117)
```

## ۳) تست‌های افزوده‌شده (آفلاین؛ بدون 5432/DB)
فایل: `tests/unit/test_db02_baseline_review.py` — **12 passed، 1 xfailed** (strict).

| تست | ادعا |
|---|---|
| `test_chain_has_a_single_head` | head واحد `0119…` |
| `test_baseline_sits_between_0004_and_0005` | revision/down و سیم‌کشی 0005 |
| `test_baseline_has_the_expected_surface` | ۳۴ جدول = ۸+۲۵+dual، بدون funds |
| `test_every_referenced_table_is_created_before_its_first_consumer` | ماتریس ۱۸تایی گزارش ۳۱ |
| `test_core_tables_match_0118_except_the_documented_mfa_omission` | drift هسته |
| `test_brsapi_tables_match_the_orphan_tree` | drift brsapi (با دو استثنای مستند) |
| `test_dual_date_columns_matches_the_install_script` | drift dual |
| `test_no_later_migration_unconditionally_readds_a_baseline_column` | ۰ collision غیر-idempotent |
| `test_no_later_create_table_redeclares_a_baseline_table` | هیچ create_table دوباره |
| `test_baseline_ddl_is_idempotent` | همهٔ CREATEها IF NOT EXISTS |
| `test_baseline_downgrade_is_a_noop` | downgrade خالی |
| `test_offline_upgrade_to_0005_renders_without_a_database` | `alembic upgrade 0005 --sql` exit 0 |
| `test_orm_instrument_reference_columns_are_reachable_after_upgrade` | **xfail(strict)** — نقص DB-13 |

## ۴) اجرا (مرحلهٔ ۳ مأموریت) — BLOCKED تا تأیید
طبق دستور، بازسازی `temce_pgdata` و `alembic upgrade head` + `needs_db` **اجرا نشد**.
آخرین شاهد معتبر: اجرای تمیز روی DB جداگانه `tse_quant_clean_1030` (گزارش ۳۳) = **PASS**
(`upgrade head` exit 0، `current=0119`، ۲۱۸ جدول؛ needs_db 42P/6F/3S — همه محیطی).

## ۵) وضعیت

| مورد | وضعیت |
|---|---|
| پیش‌شرط هم‌زمانی | **PASS** |
| diff و دلیل‌گذاری ۵ فایل | **PASS** |
| بازبینی ۳۴ جدول baseline + drift 0118/orphan/dual | **PASS** |
| DuplicateColumn | **PASS** (۰ غیر-idempotent) |
| `alembic heads` / history | **PASS** (تک‌head) |
| تست‌های جدید | **PASS** (12 passed، 1 xfailed مستند) |
| پوشش ستون‌های ORM روی DB تازه | **FAIL** — DB-13 (P1، blocker deployment تازه) |
| اجرای مرحلهٔ ۳ (بازسازی volume + upgrade + needs_db) | **BLOCKED** (منتظر تأیید) |
