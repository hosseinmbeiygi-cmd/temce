# ۳۱ — DB-02: ممیزی baseline migration — مرحلهٔ ۱ (فقط‌خواندنی)، ۳۰ اکتبر ۲۰۲۶

**وضعیت مأموریت:** مرحلهٔ ۱ انجام شد؛ **توقف تا تأیید طراحی** (طبق دستور).
**شدت DB-02:** Blocker انتشار (بالا) — هنوز رفع نشده.

**محدوده و قواعد رعایت‌شده:** فقط خواندن؛ روی `localhost:15432/tse_quant` هیچ دستوری اجرا نشد؛
`.env` تغییر نکرد؛ هیچ migration/model ویرایش نشد؛ commit/stage/reset/stash/clean/checkout انجام نشد؛
رمز/DSN کامل در این گزارش نیست.

## ۰) Git و کنترل هم‌زمانی

| مورد | مقدار |
|---|---|
| HEAD | `095cc98f` |
| snapshot1 / snapshot2 (`git status --porcelain`، ۳۰ ثانیه فاصله) | ۳۵۶ / ۳۵۸ ورودی؛ اختلاف فقط دو فایل موقت خودِ همین بررسی (`.snap_head2`, `.snap_status2`) |
| نتیجه | **PASS** — تغییر هم‌زمان فایل توسط عامل دیگر در بازه دیده نشد (HEAD ثابت) |

روش تحلیل: زنجیرهٔ کامل ۸۹ فایل `migrations/versions/*.py` با `revision`/`down_revision` بازسازی شد
(ریشه `0001`، head واحد `0119_service_private_tables`، بدون dangling ref). جدول‌های «ساخته‌شده» و
«ارجاع‌شده» با AST/الگوی SQL استخراج و با بازبینی دستی نمونه‌ها پاک‌سازی شد.

## ۱(الف) — جدول‌هایی که migrationهای قبل از ۰۱۱۸ ارجاع می‌دهند ولی خودشان نمی‌سازند

۱۸ مورد. «مصرف‌کننده» = اولین migration (قبل از ۰۱۱۸) که به جدول ارجاع می‌دهد؛ «سازنده» = جایی که واقعاً ساخته می‌شود.

| # | جدول | اولین مصرف‌کننده (revision@file:line) | نوع ارجاع | سازنده |
|---|---|---|---|---|
| 1 | `quotes` | `0005_add_performance_indexes@0005_add_performance_indexes.py:15` | CREATE INDEX | `0118…:489` |
| 2 | `trades` | `0005@0005…:25` | CREATE INDEX | `0118…:577` |
| 3 | `instruments` | `0005@0005…:32` | CREATE INDEX | `0118…:228` |
| 4 | `brsapi_codal_announcements` | `0016@0016_add_codal_audit_status.py:25` | op.add_column | فقط درخت orphan: `brsapi/migrations/001…:778` |
| 5 | `brsapi_sync_log` | `0017@0017_add_sync_log_created_at.py:29` | op.create_index | orphan `001…:51` |
| 6 | `brsapi_symbol_snapshots` | `0020@0020_brsapi_snapshots_unique.py:30` | DELETE + batch_alter | orphan `001…:71` |
| 7 | `news_articles` | `0021@0021_news_published_at_width.py:27` | batch_alter | `0118…:390` |
| 8 | `users` | `0022@0022_add_user_mfa_columns.py:21` | batch_alter | `0118…:594` |
| 9 | `dual_date_columns` | `0025@0025_add_dual_date_columns.py:168` | INSERT | فقط `scripts/install_dual_dates.py:186` |
| 10 | `brsapi_ime_funds` | `0026@0026_funds_etf_indexes.py:47` | CREATE INDEX | orphan `001…:547` |
| 11 | `brsapi_candlesticks` | `0032@0032_candlestick_dedup_indexes.py:36` | ALTER | orphan `001…:372` |
| 12 | `brsapi_shareholder_records` | `0033@0033_add_shareholder_id.py:26` | ALTER | orphan `001…:406` |
| 13 | `brsapi_historical_daily` | `0037@0037_index_gregorian_dates.py:40` | op.create_index | orphan `001…:322` |
| 14 | `brsapi_intraday_trades` | `0037@0037…:57` | op.create_index | orphan `001…:305` |
| 15 | `brsapi_raw_payloads` | `0042@0042_raw_payload_v5_columns.py:40` | op.create_index | orphan `001…:36` |
| 16 | `ml_model_versions` | `0050@0050_ml_artifact_hash.py:78` | op.create_index | `0118…:313` |
| 17 | `signals` | `0099@0099_signal_arch_align.py:13` | op.add_column | `0118…:542` |
| 18 | `alerts` | `0117@0117_user_owned_alerts_watchlist.py:31` | ALTER | `0118…:49` |

نتیجه: علاوه بر ۸ جدول هستهٔ `0118`، زنجیرهٔ اصلی به **۹ جدول `brsapi_*`** و **`dual_date_columns`** هم
قبل از ساخته‌شدنشان ارجاع می‌دهد. این‌ها بیرون از زنجیره ساخته می‌شوند (درخت orphan و اسکریپت نصب).

> نکتهٔ اصلاحی نسبت به گزارش ۳۰: `funds` **migration دارد** (`0015_funds_table.py:26`)؛ در گزارش قبلی
> به‌اشتباه «بدون migration» ثبت شده بود. الگوی grep آن زمان `create_table("funds"` را با شکستن خط/فرمت
> ندیده بود.

## ۱(ب) — وابستگی‌های ترتیبی و ترتیب ایمن

- در DDL جدول‌های `0118` هیچ `REFERENCES`/`FOREIGN KEY` وجود ندارد (بررسی متن migration). ایندکس‌های `0118`
  فقط روی ستون‌های همان جدول‌اند. در جدول‌های brsapiorphan هم FK بین این ۹ جدولِ موردنیاز دیده نشد
  (وابستگی اصلی: ستون‌های تاریخ/ins_id، نه FK).
- پس بین خود جدول‌های baseline هیچ یال اجباری FK وجود ندارد؛ ترتیب ایمن پیشنهادی = ترتیب اعلان در `0118`
  برای جدول‌های هسته، و ترتیب داخلی orphan tree برای brsapi‌ها:
  1. `users`, `instruments`, `trades`, `quotes`, `news_articles`, `signals`, `alerts`, `ml_model_versions`
     (به ترتیب `0118`)
  2. `brsapi_raw_payloads`, `brsapi_sync_log`, `brsapi_symbol_snapshots`, `brsapi_intraday_trades`,
     `brsapi_historical_daily`, `brsapi_candlesticks`, `brsapi_shareholder_records`, `brsapi_ime_funds`,
     `brsapi_codal_announcements` (به ترتیب orphan tree)
  3. `dual_date_columns` (مستقل)
- وابستگی‌های «مصرف» که ترتیب زنجیره را تعیین می‌کنند: baseline باید قبل از `0005` باشد تا ایندکس‌های
  quotes/trades/instruments کار کنند؛ brsapi‌ها قبل از `0016`؛ `dual_date_columns` قبل از `0025`.

## ۱(ج) — `funds`

- سازنده: `0015_funds_table.py:26` (`op.create_table("funds", …)`)، ۲۹ ستون
  (`id, symbol, name, isin, fund_type, nav, nav_change, nav_change_pct, price_*, trade_*, shares_count,
  base_volume, market_value, buy_real_volume, sell_real_volume, time, data_source, snapshot_date,
  extra, created_at, updated_at`)، ۲ قید unique (`symbol`, `isin`) و ۲ ایندکس.
- `apps/funds/models.py:43` همان جدول `funds` را تعریف می‌کند و `apps/funds/db.py:38` با `create_all`
  می‌سازد (checkfirst پیش‌فرض = True ⇒ روی DB مهاجرت‌شده no-op).
- آیا migrationهای بعدی به `funds` نیاز دارند؟ در زنجیرهٔ اصلی هیچ ارجاعی به جدول `funds` (غیر از
  `fund_market_quotes_cache`, `fund_metrics`, `brsapi_ime_funds`) پیدا نشد. ⇒ **baseline به `funds` نیازی ندارد.**

## ۱(د) — `brsapi_*`

برخلاف فرض قبلی: **بله**، زنجیرهٔ اصلی به ۹ جدول `brsapi_*` وابسته است (جدول‌های ردیف ۴–۶ و ۱۰–۱۵ بالا).
تنها سازندهٔ آن‌ها `brsapi/migrations/001_create_brsapi_tables.py` است (۲۵ `op.create_table`) که
`alembic.ini:2` آن را نمی‌خواند (`script_location = migrations`).
⇒ بدون پوشش این ۹ جدول، `upgrade head` بعد از اصلاح quotes در `0016` شکست می‌خورد. طبق دستور،
ادغام درخت انجام نشد؛ این مورد به‌عنوان قید طراحی در مرحلهٔ ۲ باید حل شود (دو گزینه در ادامه).

## ۱(ه) — `0007` و حالت offline

- استفاده از inspector: `migrations/versions/0007_signal_accuracy.py:25-27` —
  `conn = op.get_bind()` (۲۵)، `inspector = sa.inspect(conn)` (۲۶)،
  `table_exists = "signal_accuracy" in inspector.get_table_names()` (۲۷).
  در `--sql`، `conn` یک `MockConnection` است و `sa.inspect` با `NoInspectionAvailable` می‌شکند.
- پیشنهاد (فقط پیشنهاد، بدون ویرایش): شاخهٔ صریح حالت offline:
  ```python
  from alembic import context
  if context.is_offline_mode():
      op.create_table("signal_accuracy", ...)   # خروجی SQL برای DB خالی
  else:
      conn = op.get_bind()
      if "signal_accuracy" not in sa.inspect(conn).get_table_names():
          op.create_table("signal_accuracy", ...)
  ```
  یا جایگزین یکنواخت: `op.execute("CREATE TABLE IF NOT EXISTS signal_accuracy (...)")` (اگر ستون‌ها به SQL
  خام منتقل شوند) تا هر دو حالت بدون inspector کار کنند.
- مشاهدهٔ مشابه (خارج از درخواست ۰۰۰۷): `0026_funds_etf_indexes.py:31-34` هم با
  `op.get_bind().execute(SELECT … pg_indexes …)` در حالت `--sql` قابل اجرا نیست. برای تست
  offline `upgrade head --sql` باید همهٔ این introspectionها شاخهٔ offline داشته باشند.

## ۱(و) — DBهای موجودی که به ۰۰۰۵ یا بالاتر رسیده‌اند

- Alembic فقط از `alembic_version.version_num` به جلو حرکت می‌کند. با درج baseline جدید بین `0004` و
  `0005` (و تغییر تنها خط `down_revision` فایل ۰۰۰۵)، برای DBی که version آن `0005` یا بالاتر است،
  `upgrade head` فقط نوادگان نسخهٔ فعلی را اجرا می‌کند ⇒ **baseline روی آن‌ها اجرا نمی‌شود** و
  `alembic_version` هم دست نمی‌خورد.
- پیامد قابل‌توجه: `alembic downgrade 0004` روی چنین DBی ابتدا 0005 را پایین می‌آورد و سپس به baseline
  می‌رسد؛ بنابراین **downgrade خود baseline باید no-op باشد** (چون جدول‌ها از قبل وجود داشته‌اند و حذفشان
  داده را نابود می‌کند). این باید در طراحی مرحلهٔ ۲ صریح بیاید.
- `alembic history` برای همهٔ DBها یک نود جدید نشان می‌دهد؛ این تغییر فقط نمایشی است و اجرا نمی‌شود.

## ۲) وضعیت مرحله

| مورد | وضعیت |
|---|---|
| مرحلهٔ ۱ — ممیزی فقط‌خواندنی | **PASS** |
| DB-02 | **FAIL** (رفع‌نشده؛ baseline نوشته نشده) |
| مرحلهٔ ۲ — طراحی/diff | **BLOCKED** (منتظر دستور «ادامه بده»/«تأیید طراحی») |
| ۰۰۰۷ offline | **BLOCKED** (نیازمند تأیید جداگانه برای ویرایش) |
| درخت `brsapi/migrations` | باز — قید طراحی؛ ادغام انجام نشد |
| `dual_date_columns` (اسکریپت نصب) | باز — قید طراحی |

**توقف عمدی:** طبق دستور «مرحلهٔ ۱ را در گزارش بنویس و ادامه نده»، هیچ فایل migration/model ساخته یا
ویرایش نشد و هیچ diff طراحی ارائه نشد. منتظر تأیید برای مرحلهٔ ۲ هستم.
