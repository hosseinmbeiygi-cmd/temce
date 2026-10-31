# ۳۳ — DB-02: طراحی baseline migration — مرحلهٔ ۲ (diff، بدون اجرا)، ۳۰ اکتبر ۲۰۲۶

**وضعیت مأموریت:** مرحلهٔ ۲ (طراحی/diff) انجام شد؛ **هیچ فایلی ساخته یا ویرایش نشد**؛
اجرا منتظر «تأیید اجرا» است.
**شدت DB-02:** Blocker انتشار — هنوز FAIL.

**قواعد رعایت‌شده:** فقط خواندن؛ `.env` دست‌نخورده؛ هیچ migration/model تغییر نکرد؛
commit/stage/reset/stash/clean انجام نشد؛ DSN کامل چاپ نمی‌شود.

---

## ۰) هدف و اصل طراحی

هدف: DB خالی باید با یک `alembic upgrade head` به `0119` برسد، بدون تغییر رفتار
DBهای موجود. اصل: **baseline فقط چیزهایی را می‌سازد که زنجیره قبل از سازندهٔ واقعی‌شان
به آن‌ها نیاز دارد، و با شکل «تا ۰۰۰۴»** — نه شکل نهایی ORM. اگر شکل نهایی ساخته شود،
migrationهای ۰۰۱۶/۰۰۱۷/۰۰۱۸/۰۰۲۲/۰۰۲۳/۰۰۲۴/۰۰۴۲/۰۱۱۶ روی ستون تکراری می‌شکنند.

---

## ۱) دامنهٔ baseline

یک فایل جدید بین `0004_ml_symbol_results` و `0005_add_performance_indexes`:

```
migrations/versions/0004b_core_baseline.py
revision      = "0004b_core_baseline"
down_revision = "0004_ml_symbol_results"
```

### ۱(الف) ۸ جدول هسته — DDL از `0118_core_tables_backfill.py` گرفته می‌شود

`users`, `instruments`, `trades`, `quotes`, `news_articles`, `signals`, `alerts`,
`ml_model_versions` — همان `CREATE TABLE IF NOT EXISTS` فریز‌شدهٔ ۰۱۱۸، **به‌جز**
ستون‌هایی که migrationهای میانی بدون محافظ اضافه می‌کنند:

| جدول | ستون‌هایی که باید از DDL حذف شوند | افزاینده |
|---|---|---|
| `users` | `totp_secret`, `totp_enabled`, `totp_confirmed_at` | `0022` (batch_alter بدون محافظ) |
| `users` | `mfa_method` | `0023` |
| `users` | `telegram_chat_id` | `0024` |

> `0021` نوع `news_articles.published_at` را از VARCHAR(30) به (40) تغییر می‌دهد؛ DDL
> نهایی ۰۱۱۸ همان (40) است و ALTER به همان نوع خطا نمی‌دهد ⇒ حذف لازم نیست.
> `0006` (updated_at)، `0099` (ستون‌های signals) و `0101` (tsetmc_id) استثنا را
> `suppress`/guarded می‌کنند ⇒ می‌توانند در baseline بمانند.
> `0054` (published_at_ts) و `0117` (alerts.user_id) با `IF NOT EXISTS`اند ⇒ بی‌خطر.

### ۱(ب) ۹ جدول `brsapi_*` — DDL از درخت یتیم

منبع: `brsapi/migrations/001_create_brsapi_tables.py` (خارج از `alembic.ini`).
این DDL دقیقاً شکل «قبل از ۰۰۱۶» است و همین چیزی است که baseline لازم دارد:

`brsapi_raw_payloads`, `brsapi_sync_log`, `brsapi_symbol_snapshots`,
`brsapi_intraday_trades`, `brsapi_historical_daily`, `brsapi_candlesticks`,
`brsapi_shareholder_records`, `brsapi_ime_funds`, `brsapi_codal_announcements`

نکته: در این DDL خبری از `audit_status` (0016)، `content_hash` (0018)،
`created_at/outcome` (0017/0116) و پنج ستون v5 (0042) نیست — یعنی افزاینده‌های
بدون محافظ بعدی سالم اجرا می‌شوند.

**ایندکس‌های یتیم** (`idx_sync_log_*`, `idx_snap_*`, `idx_trade_symbol_date`,
`idx_hist_symbol_date`, ...) هم در baseline با `CREATE INDEX IF NOT EXISTS` بازسازی
می‌شوند، چون هیچ migration دیگری آن‌ها را نمی‌سازد. بررسی شد که با نام‌های
`idx_snap_sector`/`idx_ime_fund_symbol` (0026) و `idx_hist_gregorian*`/`idx_trades_gregorian`
(0037) تداخل ندارند. `gregorian_date` را baseline لازم **نیست** بسازد؛ `0025:157`
خودش آن را با `ADD COLUMN IF NOT EXISTS` به همهٔ جدول‌ها اضافه می‌کند.

### ۱(ج) `dual_date_columns`

`CREATE TABLE IF NOT EXISTS dual_date_columns (table_name text PRIMARY KEY, source_column text NOT NULL)`
— همان DDL `scripts/install_dual_dates.py:186`. سازندهٔ دیگری در زنجیره ندارد و
`0025:168` قبل از ۰۰۲۵ به آن INSERT می‌کند.

---

## ۲) diff فایل‌ها

| فایل | تغییر |
|---|---|
| `migrations/versions/0004b_core_baseline.py` | **جدید**؛ ~۳۵۰ خط DDL فریز‌شده؛ `downgrade(): pass` |
| `migrations/versions/0005_add_performance_indexes.py` | فقط یک خط: `down_revision = "0004b_core_baseline"` |
| `migrations/versions/0118_core_tables_backfill.py` | **بدون تغییر** (روی DB خالی no-op می‌شود) |
| `brsapi/migrations/001_create_brsapi_tables.py` | **بدون تغییر** (منبع DDL، همچنان خارج از زنجیره) |

`downgrade()` عمداً no-op است: DBهای موجود که `alembic_version ≥ 0005` دارند این
revision را اجرا نمی‌کنند؛ اگر بعداً `downgrade 0004` بخورند، حذف جدول‌ها داده را
نابود می‌کند.

---

## ۳) چرا «جابه‌جایی ۰۱۱۸ به قبل از ۰۰۰۵» انتخاب نشد

۰۱۱۸ شکل **نهایی** ۲۸ جدول را دارد. اگر قبل از ۰۰۰۵ اجرا شود:
- `0016` روی `brsapi_codal_announcements.audit_status` → duplicate column
- `0022/0023/0024` روی ستون‌های users → duplicate column
- `0017/0042/0116` روی brsapi → duplicate column/index
پس baseline باید «شکل تاریخی» باشد، نه جابه‌جایی backfill.

---

## ۴) ریسک‌ها و مهار

| ریسک | مهار |
|---|---|
| ستون تکراری در ۰۰۱۶/۰۰۱۷/۰۰۱۸/۰۰۲۲–۰۰۲۴/۰۰۴۲/۰۱۱۶ | حذف همان ستون‌ها از baseline (جدول ۱-الف + DDL یتیم) |
| تداخل نام ایندکس با ۰۰۲۶/۰۰۳۷ | نام‌های یتیم بررسی شد؛ هیچ هم‌نامی نیست |
| batch_alter روی users/news (بازسازی جدول) | baseline قبل از آن‌ها اجرا می‌شود؛ ستون‌ها همان‌جا ساخته می‌شوند |
| downgrade داده‌های موجود | `downgrade(): pass` |
| DB موجود با version ≥ 0005 | baseline اجرا نمی‌شود؛ `upgrade head` فقط نوادگان را می‌راند |
| offline `--sql` | خارج از این پلن؛ ۰۰۰۷/۰۰۲۶ هنوز introspection دارند (approval جدا) |

---

## ۵) معیار پذیرش (بعد از اجرا)

روی `localhost:15432/tse_quant` (خالی، فقط `dual_date_columns`):

1. `DATABASE_URL=postgresql+asyncpg://quant_dev:***@localhost:15432/tse_quant alembic upgrade head` → **exit 0**
2. `alembic current` → `0119_service_private_tables (head)`
3. `information_schema`:
   - `alembic_version` وجود دارد و مقدارش `0119_service_private_tables` است
   - ۱۸ جدول baseline + جدول‌های زنجیره موجودند؛ `brsapi_*` = ۹+
   - `users` ستون‌های `totp_*`, `mfa_method`, `telegram_chat_id` را دارد (از ۰۰۲۲–۰۰۲۴)
   - `brsapi_codal_announcements` ستون‌های `audit_status`, `content_hash` را دارد
   - `brsapi_raw_payloads` پنج ستون v5 را دارد
4. `pytest tests/unit/test_core_tables_migration.py -q` → ۳ passed
5. `pytest tests/unit/api/test_gold_derivatives_endpoints.py tests/unit/api/test_gold_personal_surface_auth.py -q`
   با `DATABASE_URL` روی ۱۵۴۳۲ → انتظار: ۷ تست قبلاً محیطی‌بلوکه، اکنون ۵۶ passed
   (اگر شکست ماند، دلیلش جدا ثبت می‌شود)
6. خروجی خام + exit code در `evidence/32_DB02_BASELINE_APPLY_20261030.log` (رمز redact)

---

## ۶) وضعیت مرحله

| مورد | وضعیت |
|---|---|
| مرحلهٔ ۲ — طراحی/diff | **PASS** (این سند) |
| DB-02 | **FAIL** (رفع‌نشده) |
| اجرای baseline | **BLOCKED** — منتظر «تأیید اجرا» |
| ۰۰۰۷/۰۰۲۶ آفلاین | **BLOCKED** — approval جدا |
| مستندات README (مسیر DB خالی) | **BLOCKED** — بعد از اجرا |

**تصمیم لازم:** «تأیید اجرا» بده تا فایل baseline ساخته شود، ۰۰۰۵ یک‌خطی تغییر کند و
آزمون پذیرش (بند ۵) با خروجی خام اجرا شود.
