# قسمت ۰۴ — پایگاه داده و مهاجرتها

| | |
|---|---|
| **بازه** | `core/database.py`, `models/` (۵۲ فایل), `migrations/` (۹۵ ریویژن), `migrations_backup_20261030/` (۹۲ فایل), `repositories/` (۲۳ فایل), `alembic.ini`, `migrations/env.py`, سه ورکفلو CI |
| **HEAD مبنا** | `bfd1e78df055df585d5a77e9f77f1381166cc5e4` — `fix(frontend): restore 8 options components deleted by 1ad66304` |
| **فاصله از کامیت مبنا** | ۲۸ کامیت (`091fdf31..HEAD`)؛ ۱۶ کامیت پس از `d551242c` |
| **تعهد** | فقط فایل تحلیلی Markdown ساخته شد. **هیچ فایل کد، پیکربندی، تست یا مهاجرتی تغییر نکرد.** |
| **یافتهها** | `DB-01` … `DB-20` — ۲۰ مورد (۲ بحرانی، ۶ بالا، ۸ متوسط، ۴ کم) |
| **وضعیت worktree** | پاک؛ ۹ فایل اصلاحشده قسمت ۰۳ در کامیتهای اخیر ادغام و کامیت شدهاند |

> **تغییر مهم نسبت به قسمت ۰۳:** تحلیلهای قبلی بر روی HEAD ایستا انجام نمیشدند. تا این قسمت، کامیتهای `d6962d0a` و `2b4d9ddc` مستقیماً با ارجاع به شناسههای `CFG-*` نوشته شدهاند و **هفت یافته قسمت ۰۳ را بستهاند** (بند ۱۰). بنابراین تمام اعداد این گزارش در برابر `bfd1e78d` اندازهگیری تازه شدهاند؛ عدد ۹۴ مهاجرت گزارش ۱۶۰ لایهای اکنون **۹۵** است.

---

## ۱. فهرست فایلها و ابعاد

| ردیف | فایل / پوشه | اندازه | نقش |
|---|---|---|---|
| ۱ | `core/database.py` | ۳۱۴ خط | موتور async، دو session factory، گارد فقطخواندنی، صدور مجدد SQL مجاز |
| ۲ | `models/base.py` | ۲۱ خط | `DeclarativeBase` + `TimestampMixin`؛ تنها منبع `Base.metadata` |
| ۳ | `models/*.py` | ۵۲ فایل | **۱۴۹ کلاس ORM جدولدار** در ۵۰ فایل، بدون نام جدول تکراری |
| ۴ | `models/__init__.py` | ۳۶ `import-from` | **۱۰۵ نام صادرشده**؛ رجیستری ناقص (بند ۵) |
| ۵ | `migrations/versions/` | **۹۵ فایل / ۹۵ ریویژن** | زنجیره خطی `0001 → 0124` |
| ۶ | `migrations/env.py` | ۶۶ خط | پیکربندی Alembic، تعریض ستون `version_num`، commit صریح |
| ۷ | `alembic.ini` | ۳۸ خط | فقط `script_location`؛ URL عمداً حذف و به `env.py` سپرده شده |
| ۸ | `migrations_backup_20261030/` | ۹۲ فایل / **۹۰ ریویژن** | درخت موازی، head = `0119_service_private_tables` |
| ۹ | `brsapi/migrations/` | ۱ فایل / ۱ ریویژن | `brsapi_0001`، مستقل و بیرون از مسیر Alembic اصلی |
| ۱۰ | `repositories/` | ۲۳ فایل | `BaseRepository`، `InMemoryRepository`، `DbRepository` + ۲۰ ریپازیتوری دامنه |
| ۱۱ | `.github/workflows/ci.yml` | job `needs-db` در `:373` | `CREATE EXTENSION timescaledb` سپس `alembic upgrade head` |
| ۱۲ | `.github/workflows/decision-engine.yml` | `:222` | همان الگو روی DB جداگانه `tse_quant` |
| ۱۳ | `.github/workflows/fund-service.yml` | `:106`, `:185` | job `migrate` + تأیید `alembic current` |

**سنجش مصرف:** `from core.database import` در **۴۴۱ نقطه از ۲۶۵ فایل**؛ `get_replica_session` تنها در **۵ فایل**؛ `get_session_blocking` فقط در همان فایل تعریف (صفر مصرفکننده بیرونی). `database_auto_create_tables` و `database_replica_enabled` هرکدام ۳ ارجاع در ۲ تا ۳ فایل.

---

## ۲. ردیابی جریان اجرا

**مسیر الف — بوت معمولی سرویس:**

```
apps/api/app.py::lifespan
  └─ init_database()                         core/database.py:195
       ├─ Path(settings.data_dir).mkdir()    :201
       ├─ url = settings.database_url_async :203  (postgresql → +asyncpg)
       ├─ if sqlite → RuntimeError          :207-218   ← fail-closed
       ├─ _try_connect(url) → SELECT 1      :222-234   ← fail-closed
       ├─ create_async_engine(...)          :236   pool_size=20, overflow=30,
       │                                          pre_ping=True, recycle=3600
       ├─ optional replica                 :242-259   خطا → fallback به primary
       ├─ if auto_create_tables            :264-266   ← فقط برای Postgres قابلدسترس
       └─ get_session()                    :296-308   commit بیقیدوشرط پس از yield
```

**مسیر ب — مهاجرت (جدا از مسیر الف، فرایند متفاوت):**

```
alembic upgrade head
  └─ migrations/env.py
       ├─ from models.base import Base     :20  → اجرای models/__init__.py
       ├─ target_metadata = Base.metadata :27
       ├─ run_migrations_online()         :62
       │    ├─ sqlite → create_engine (sync) + do_run_migrations + commit
       │    └─ else   → asyncio.run(run_async_migrations())
       ├─ do_run_migrations()             :39
       │    ├─ CREATE TABLE IF NOT EXISTS alembic_version (VARCHAR(255))
       │    ├─ ALTER TABLE ... TYPE VARCHAR(255)      ← DB-02 قدیمی، ۲۰۲۶-۱۰-۳۰
       │    └─ context.configure(...); run_migrations()
       └─ await connection.commit()       :59  ← بدون آن کل upgrade برمیشت
```

**نکته معماری:** هیچ نقطهای از کد اپلیکیشن Alembic را فراخوانی نمیکند. مهاجرت صرفاً توسط `Makefile:65`، سه ورکفلو CI و مستندات انجام میشود. یعنی **بوت سرویس و بوت اسکیما دو فرایند مستقلاند** و هیچ گیتی در `lifespan` بررسی نمیکند که `alembic_version` با head هماهنگ است.

---

## ۳. سیاست شکست

| لایه | رفتار در برابر شکست | ارزیابی |
|---|---|---|
| `init_database()` روی SQLite | `RuntimeError` صریح | ✅ fail-closed |
| اتصال ناموفق Postgres | `RuntimeError`، بدون fallback | ✅ fail-closed |
| رپلیکای ناموفق | `logger.warning` + بازگشت به primary | ✅ تخریب تدریجی درست |
| نوشتن روی session رپلیکا | `before_flush` + `do_orm_execute` → `RuntimeError` | ✅ گارد دومسیره، شامل `text()` خام |
| `get_session()` | `commit` در مسیر موفق، `rollback` در استثناء | ⚠️ commit حتی برای خواندن محض |
| `get_session_blocking()` | session بدون context manager، بدون بستن | ⚠️ نشت منبع در صورت فراموشی فراخوان |
| `env.py` طول `version_num` | `ALTER ... VARCHAR(255)` پیش از نوشتن | ✅ workaround مستند |
| `env.py` حالت offline | همان تعریض انجام **نمیشود** | ⚠️ مسیر `--sql` محافظتنشده |
| `alembic downgrade` | ۶ تابع `pass`، صفر فراخوان در کل مخزن | 🔴 بازگشت ناپذیر و آزمایشنشده |
| `0001` بدون افزونه TimescaleDB | `create_hypertable` → خطای تابع ناموجود | 🔴 CI جبران میکند، استقرار نه |

---

## ۴. گراف مهاجرتها — اندازهگیری AST

| معیار | `migrations/versions` | `migrations_backup_20261030` |
|---|---:|---:|
| فایل `.py` | ۹۵ | ۹۲ |
| ریویژن معتبر | **۹۵** | ۹۰ |
| head | **`0124`** | `0119_service_private_tables` |
| base | `0001` | `0001` |
| نقاط انشعاب | ۰ | ۰ |
| والد گمشده | ۰ | ۰ |
| طول زنجیره / پیوستگی | ۹۵ / کاملاً متصل | — |
| فاقد `downgrade` | ۰ | ۰ |
| `downgrade` تهی (`pass`) | **۶** | — |
| فاقد `upgrade` | ۰ | ۰ |
| بدون هیچ `op.*` | ۲ (`0009`, `0010`) | ۲ |
| شناسه بلندتر از ۳۲ نویسه | ۲ (۳۶ و ۳۸ نویسه) | ۲ |

**پروفایل عملیات:** ۲۲۴ `op.execute` (SQL خام)، ۷۸ `create_index`، ۶۸ `create_table`، ۶۷ `drop_table`، ۵۸ `drop_index`، ۴۲ `get_bind`، ۱۶ `add_column` / ۱۶ `drop_column`، ۱۰ `batch_alter_table`. اسکن متنی: ۳۱۰ `CREATE INDEX`، ۴۹۸ `IF NOT EXISTS`، ۳۸ `DROP TABLE` خام، ۱۳ `create_hypertable`، ۱۱ `CONCURRENTLY`، ۲ `COMMIT`.

**تفاوت دو درخت:** پنج ریویژن `0120`, `0121_brsapi_instrument_ref`, `0122`, `0123`, `0124` فقط در درخت اصلیاند؛ درخت پشتیبان هیچ ریویژن منحصربهفردی ندارد ولی **۹۰ شناسهاش همگی با درخت اصلی همپوشانی دارند** (بند ۶، `DB-07`).

---

## ۵. پوشش رجیستری مدلها — شکاف ۲۷٫۵ درصدی

`models/__init__.py` از **۳۶** ماژول از ۵۱ ماژول مدل وارد میکند. **۱۵ ماژول هرگز وارد نمیشوند**:

```
alert_hub, approval_gateway, codal_analysis, codal_financial,
decision_engine, generated_strategy, gold, gold_feed_health,
news_items, option, queue_analysis, reference_db,
saved_filter, signal_accuracy, symbol_relation
```

این ۱۵ ماژول **۴۱ کلاس جدولدار** دارند — یعنی ۲۷٫۵٪ از ۱۴۹ موجودیت ORM هنگام `import models` هرگز در `Base.metadata` ثبت نمیشوند. نمونهها: `symbol_alerts`, `proposals`, ۱۴ جدول ستاره `codal_analysis` (`dim_*`, `fact_*`), `option_contracts`, `option_snapshots`, `volatility_surface`, `signal_accuracy`, `gold_futures_positions`, `news_items`, `saved_filters`.

چهار کلاس دیگر (`CodalAuditSummaryModel`, `FundSymbolAliasModel`, `FundIngestionRunModel`, `MlPredictionModel`) در ماژولهای واردشده تعریف شدهاند ولی از `__init__` صادر نمیشوند؛ اینها **در metadata ثبت میشوند** و فقط از `from models import X` پنهاناند.

**پیامد عملی:** `from models.base import Base` در `env.py` بهلطف معنای واردات بسته در پایتون، `models/__init__.py` را اجرا میکند — پس metadata خالی نیست. ولی شامل همان ۱۰۸ جدول ناقص است. `alembic revision --autogenerate` (`Makefile:68`) تفاوت metadata با DB را میبیند و برای ۴۱ جدول موجود در DB و غایب در metadata، پیشنهاد `drop_table` تولید میکند. `reports/SECURITY_FLOAT_LOOKAHEAD_AUDIT.md:17` از پیش به «model-vs-DB drift» در `alembic check` اشاره کرده است.

---

## ۶. یافتهها

| شناسه | شدت | سند | یافته | اثر | پیشنهاد (بدون تغییر کد) |
|---|---|---|---|---|---|
| **DB-01** | 🔴 بحرانی | `docker-compose.production.yml:118-141` | سرویس `postgres` فاقد `image`، `build` و `extends` است؛ فقط `restart`, `networks`, `environment`, `volumes`, `deploy`, `healthcheck` دارد | `docker compose up` / `docker stack deploy` با خطای «neither image nor build» شکست میخورد؛ کل استقرار تولید قابل بوت نیست | تعیین ایمیج صریح (ترجیحاً `timescale/timescaledb:...`) |
| **DB-02** | 🔴 بحرانی | `0001_initial_schema.py:73,92,106,128,149,164,177,219,313,330` و `:1` | ده فراخوانی بیقیدوشرط `create_hypertable()` بدون بررسی `pg_extension`؛ خود فایل هیچ `CREATE EXTENSION` ندارد. سه ورکفلو CI پیش از migrate دستی `CREATE EXTENSION IF NOT EXISTS timescaledb` اجرا میکنند، ولی هیچ فایل استقراری چنین گامی ندارد | اجرای `alembic upgrade head` روی Postgres معمولی در همان ریویژن نخست متوقف میشود. توسعه (`docker-compose.yml:5`) و decision-engine ایمیج Timescale دارند، **تولید ندارد** | یا ایمیج Timescale + provisioning افزونه، یا گارد شرطی مشابه `0065:49-51` در `0001` |
| **DB-03** | 🟠 بالا | `models/__init__.py` در برابر ۵۲ فایل `models/` | ۱۵ ماژول / ۴۱ کلاس جدولدار (۲۷٫۵٪) وارد رجیستری نمیشوند | `create_all` ناقص، `--autogenerate` گمراه، `alembic check` drift دائمی | تکمیل رجیستری یا واردات صریح در `env.py` |
| **DB-04** | 🟠 بالا | `Makefile:68`, `migrations/README.md:110` | `migrate-new` از `--autogenerate` استفاده میکند در حالی که metadata ناقص است و ۲۲۴ عملیات `op.execute` خام قابل بازسازی توسط autogenerate نیست | تولید مهاجرتی که ۴۱ جدول سالم را حذف میکند؛ خطر از دسترفتن داده در اجرای کور | قفل کردن autogenerate تا رفع `DB-03`؛ بررسی دستی خروجی |
| **DB-05** | 🟠 بالا | `0004b`, `0009`, `0010`, `0099`, `0121`, `0124` | شش `downgrade()` بدنه `pass` دارند؛ `0099` سه جدول `data_freshness`, `data_quality_log`, `data_gaps` میسازد و «هیچ» خراب نمیکند؛ `0124` جدول ۰٫۹۸ GiB پشتیبان را `DROP` میکند و downgradeاش تهی است | بازگشت به ریویژن قبل، اسکیما را ناهماهنگ میگذارد: جدول افتاده برنمیگردد، جدولهای ساختهشده باقی میمانند | بازنویسی downgrade یا علامتگذاری صریح «غیرقابلبازگشت» |
| **DB-06** | 🟠 بالا | اسکن کل مخزن | عبارت `alembic downgrade` **صفر** بار در هیچ فایل `.py/.yml/.md/.sh/Makefile` دیده نشد؛ همچنین `alembic current` فقط در ۲ ورکفلو و مستندات | هیچ CI، تست یا رانبوکی مسیر بازگشت را اجرا نمیکند؛ `DB-05` بنابراین کشف هم نمیشود | افزودن تست round-trip `upgrade → downgrade → upgrade` |
| **DB-07** | 🟠 بالا | `tests/unit/test_migration_revision_ids.py:15` | تست با نام «unique across **all** trees» فقط `TREES = (migrations, brsapi/migrations)` را میبیند؛ درخت سوم `migrations_backup_20261030` با **۹۰ شناسه تکراری** کنار گذاشته شده | اگر `version_locations` روزی به پشتیبان اشاره کند، ۹۰ برخورد و چند head همزمان؛ نام تست پوشش واقعی را بیشازواقع نشان میدهد | افزودن درخت سوم یا حذف/آرشیو کردن آن |
| **DB-08** | 🟠 بالا | `README.md:27,372,832`؛ `migrations/README.md:103,140`؛ همان دو خط در README پشتیبان؛ `docs/funds/ENTERPRISE_FUND_MODULE.md:108` | مستندات head را `0039` (۳۹ مهاجرت)، `0119` و `0053` اعلام میکنند؛ نمودار `migrations/README.md` تا `0020` کشیده شده | واقعیت: **۹۵ ریویژن، head `0124`**. اپراتور بر اساس عدد کهنه عیبیابی میکند | همگامسازی اعداد با گراف واقعی |
| **DB-09** | 🟡 متوسط | `core/database.py:185-192` در برابر `:207-218` و `:264` | `_create_all_tables()` در docstring «SQLite fallback» نامیده شده، ولی `init_database()` در خط ۲۱۵ برای SQLite `RuntimeError` میدهد، پیش از آنکه خط ۲۶۴ اجرا شود؛ کامنت خط ۲۶۱ هم «SQLite dev mode» میگوید | شاخه autocrate برای سناریوی مستندشده **غیرقابلدسترس** است؛ با Postgres فعال شود تاریخچه مهاجرت را دور میزند | حذف شاخه یا اصلاح مستندات + گارد production |
| **DB-10** | 🟡 متوسط | `core/database.py:296-308` | `get_session()` پس از هر `yield` بیقیدوشرط `commit()` میکند، حتی هندلرهای صرفاً خواندنی | تراکنش ناخواسته، بار اضافی WAL، و امکان پنهانشدن نوشتهای تصادفی؛ ۴۴۱ واردات در ۲۶۵ فایل در برابر تنها ۵ فایل با `get_replica_session()` | تفکیک session خواندنی/نوشتنی |
| **DB-11** | 🟡 متوسط | `core/database.py:311-314` | `get_session_blocking()` یک `AsyncSession` بیهمراه `async with` برمیگرداند؛ **صفر مصرفکننده بیرونی** | API مرده با الگوی مستعد نشت اتصال در صورت استفاده آینده | حذف یا تبدیل به context manager |
| **DB-12** | 🟡 متوسط | `0030_symbol_snapshot_dashboard_index` (۳۶ نویسه)، `0034_deprecate_old_tables_create_views` (۳۸ نویسه)، `env.py:41-49` | دو شناسه از `VARCHAR(32)` پیشفرض Alembic بلندترند؛ `do_run_migrations` ستون را به ۲۵۵ تعریض میکند، ولی `run_migrations_offline()` (`:30-36`) این کار را نمیکند | مسیر تولید SQL آفلاین (`--sql`) همچنان روی ستون ۳۲ نویسهای مینویسد؛ وابستگی به DDL زمان اجرا بهجای اصلاح شناسهها | کوتاهسازی شناسهها یا انتقال تعریض به offline |
| **DB-13** | 🟡 متوسط | `migrations/env.py:30-36` در برابر `:64-70` | حالت offline از `settings.database_url` و حالت online از `settings.database_url_async` استفاده میکند؛ `target_metadata` در هر دو پاس میشود ولی ناقص است (`DB-03`) | خروجی `--sql` ممکن است با اجرای واقعی تفاوت داشته باشد | یکسانسازی URL و پوشش metadata |
| **DB-14** | 🟡 متوسط | ۲۲۴ `op.execute`، ۳۱۰ `CREATE INDEX` خام، ۴۹۸ `IF NOT EXISTS` | اکثریت اسکیما با SQL دستی ساخته شده، نه `op.create_table`؛ بنابراین مقایسه metadata محور ذاتاً ناکارآمد است | `alembic check` همواره drift میدهد (مستند در `reports/SECURITY_FLOAT_LOOKAHEAD_AUDIT.md:17`) و اتکا به autogenerate خطرناک است | پذیرش صریح «مهاجرت دستی» و حذف وعده autogenerate از README/Makefile |
| **DB-15** | 🟡 متوسط | `0009_rechain_stub.py`, `0010_rechain_stub.py` | دو ریویژن no-op صرفاً برای ترمیم شکاف زنجیره ساخته شدهاند (docstring: خطای «Revision 0010 ... is not present») | سابقه شکست گراف؛ `test_managed_chain_has_a_single_head` فقط تعداد head را چک میکند، نه پیوستگی و والد گمشده | تست پیمایش کامل زنجیره |
| **DB-16** | 🟡 متوسط | کامیت `1ad66304` ← `052f17b8` | `0124` در ابتدا `down_revision = "0123_ingestion_core_tables"` (اسلاگ نام فایل) داشت نه `"0123"`؛ تست تکhead دو head دید و کامیت بعدی آن را اصلاح کرد | سلامت گراف به یک تست مبتنی بر regex وابسته است؛ خطای مشابه میتواند دوباره رخ دهد | تست والد معتبر (نه فقط تعداد head) |
| **DB-17** | 🟢 کم | شمارش تفکیکشده upgrade/downgrade | ۶۸ `create_table` در upgrade در برابر ۶۷ `drop_table` در downgrade؛ سه جدول `0099` هرگز حذف نمیشوند، دو جدول `codal_financial_statements` و `ml_symbol_results` در downgrade حذف میشوند ولی با `CREATE TABLE` خام ساخته شدهاند | ناترازی partly توضیحدادنی (SQL خام) و partly واقعی (`0099` ← `DB-05`) | ممیزی دستی جدولها |
| **DB-18** | 🟢 کم | `models/__init__.py` | ۴ کلاس جدولدار واردشده ولی صادراتنشده (`codal_audit_summary`, `fund_symbol_aliases`, `fund_ingestion_runs`, `ml_predictions`) | `from models import X` برای اینها شکست میخورد، گرچه در metadata هستند و ممکن است گمراهکننده باشد | تکمیل صادرات |
| **DB-19** | 🟢 کم | `tests/unit/test_migration_revision_ids.py:1-7` | docstring ادعا میکند `brsapi/migrations/001_create_brsapi_tables.py` از ریویژن `0022` استفاده میکند و «برخورد نهفته» است؛ فایل اکنون `revision = "brsapi_0001"` دارد و برخورد صفر است | مستند تست کهنه و خواننده را به دنبال خطای رفعهشده میفرستد | بروزرسانی docstring |
| **DB-20** | 🟢 کم | `migrations/README.md:100`, همان در README پشتیبان | مستندات «توسعه محلی (sqlite یا postgres)» و `alembic upgrade head` را مجاز میداند، در حالی که `init_database()` و `validate_production()` SQLite را رد میکنند | دستوری که رانتایم اجرا نمیکند | حذف گزینه SQLite از مستندات |

---

## ۷. نقاط قوت تأییدشده

1. **گراف سالم:** ۹۵ ریویژن، تک head (`0124`)، تک base (`0001`)، صفر والد گمشده، صفر انشعاب، صفر `downgrade` غایب، زنجیره کاملاً متصل. نتیجه مستقیم ترمیم `0009/0010` و اصلاح `052f17b8` است.
2. **گارد فقطخواندنی دومسیره:** `_install_readonly_session_guard()` هم `before_flush` را میگیرد و هم `do_orm_execute`؛ `_statement_is_write()` حتی `text()` خام را با بررسی کلمه نخست SQL تشخیص میدهد. تستهای `test_replica_readonly_session.py` و `test_readonly_replica_wiring.py` آن را پوشش میدهند.
3. **fail-closed در بوت:** SQLite و اتصالناموفق Postgres هر دو استثناء صریح میدهند؛ خطا لاگ نمیشود و پیام حاوی پسورد نیست (`url.split("@")[-1]`).
4. **`env.py` دقیق:** علت تعریض `version_num` و علت `await connection.commit()` هر دو در کامنت مستند شدهاند (ارجاع `DB-02, 2026-10-30`) — نمونهای از بدهی تبدیلشده به دانش.
5. **گارد TimescaleDB در `0065`:** `_timescaledb_present()` پیش از سیاستهای فشردهسازی `pg_extension` را چک میکند و در نبود افزونه «skip» میدهد — الگوی صحیحی که `0001` فاقد آن است.
6. **سه CI واقعی:** `ci.yml:373`, `decision-engine.yml:222`, `fund-service.yml:106/185` همگی `alembic upgrade head` را روی Postgres زنده اجرا میکنند؛ `fund-service` حتی `alembic current` را تأیید مینماید.
7. **تست یکتایی شناسه و تکhead:** `test_migration_revision_ids.py` گرچه ناقص است (`DB-07`)، همان تستی بود که خطای `down_revision` در `0124` را گرفت.
8. **سطح SQL مجاز:** `core/database.py:8-59` بهصراحت دروازههای import-linter را با `X as X` مشخص کرده؛ services نمیتوانند مستقیم SQLAlchemy وارد کنند.
9. **پیکربندی اتصال:** `pool_pre_ping=True`, `pool_recycle=3600`, `expire_on_commit=False`، و `close_database()` با `contextlib.suppress` برای هردو موتور.
10. **بدون نام جدول تکراری:** ۱۴۹ کلاس، ۱۴۹ `__tablename__` یکتا، صفر `__abstract__` — رجیستری ناقص است ولی متناقض نیست.

---

## ۸. فرضیههای ردشده (ثبت برای جلوگیری از تکرار)

| # | حدس اولیه | نتیجه راستیآزمایی |
|---|---|---|
| ۱ | «`env.py` فقط `models.base` را وارد میکند، پس `target_metadata` خالی است و autogenerate همهچیز را حذف میکند» | **رد شد.** واردات زیرماژول در پایتون ابتدا `models/__init__.py` بسته را اجرا میکند؛ ۳۶ ماژول ثبت میشوند. شکاف واقعی ۴۱ جدول است، نه ۱۴۹ جدول (`DB-03`). |
| ۲ | «`CREATE INDEX CONCURRENTLY` داخل تراکنش Alembic اجرا میشود و با خطای PostgreSQL روبهرو میگردد» | **رد شد.** از ۱۱ مورد `CONCURRENTLY`، شش تا در docstring ماژول، بقیه در کامنتهای توضیحی، و یکی در بدنه تابع PL/pgSQL برای `REFRESH MATERIALIZED VIEW` (زمان ساخت تابع، نه اجرای آن). کد عمداً از `CREATE INDEX` ساده استفاده میکند و دلیلش را در `0026:11-13`, `0027:8-9`, `0037:22-24`, `0105:11-13` نوشته است. |
| ۳ | «دو درخت مهاجرت همزمان چند head میسازند» | **تصفیه شد.** `alembic.ini` هیچ `version_locations` ندارد، پس پشتیبان در مسیر Alembic نیست و head زنده تک است؛ خطر صرفاً **نهفته** است و تست آنرا پوشش نمیدهد (`DB-07`). |
| ۴ | «برخورد ریویژن `0022` با `brsapi/migrations` هنوز پابرجاست» | **رد شد.** شناسه به `brsapi_0001` تغییر کرده؛ docstring تست کهنه مانده (`DB-19`). |

> **مرز روش در فرضیه ۱:** بهدلیل نبود `sqlalchemy` در مفسر سیستمی (`ModuleNotFoundError`)، اندازهگیری تجربی `len(Base.metadata.tables)` اجرا نشد؛ حکم بر اساس معنای استاندارد واردات بسته و شمارش ایستای AST است. شمارش ۴۱ جدول غایب قطعی است، عدد دقیق `Base.metadata.tables` در محیط نصبشده ممکن است بهدلیل مدلهای بدون `__tablename__` اندکی متفاوت باشد.

---

## ۹. تصحیح گزارش ۱۶۰ لایهای

| لایه | ادعای پیشین | واقعیت در `bfd1e78d` |
|---|---|---|
| ۵ / ۱۵۸ | ۹۴ مهاجرت، head `0123` | **۹۵ ریویژن، head `0124`**؛ پنج ریویژن `0120…0124` نسبت به درخت پشتیبان تازهاند |
| ۲۱ / ۲۲ | ۱۴۹ موجودیت ORM، «دو درخت مهاجرت» | ۱۴۹ تأیید شد؛ ولی **رجیستری تنها ۱۰۸ جدول** را میبیند (`DB-03`) و درخت سوم (`brsapi/migrations`) هم وجود دارد |
| ۱۵۵ | هلثچک compose | تصحیح قسمت ۰۳ (`CFG-07`) در HEAD **بسته شد**: `docker-compose.production.yml:64` اکنون `/health/ready` را صدا میزند |
| ۱۵۸ | «دو سیستم تنظیمات / ۱۸ زیرکلاس BaseSettings» | تصحیح قسمت ۰۳ (`CFG-08`) در HEAD **بسته شد**: `core/config/` اکنون فقط `__init__.py`, `acceptance_loader.py`, `ime_engine.py`, `storage.py` دارد — دقیقاً ۳ ماژول زندهای که قسمت ۰۳ شناسایی کرده بود |
| R11 / R12 | گیت production خاموش؛ اسرار ناوصل | `ENV: production` در `:22`، کلیدهای `AUTH_COOKIE_SECURE` / `REGISTRATION_OPEN` / `JOB_QUEUE_TOKEN` در `.env.example`، `INGESTION_LAKE_*` و DSN اصلاحشده — **هر دو ردیف به «بستشده در HEAD» تغییر وضعیت میدهند** |
| ۹۴ | MinIO / `LAKE_*` | تصحیح `CFG-17/18` در HEAD **بسته شد** (`docker-compose.yml:98,104-106`) |
| فصل N | «استقرار production راستیآزمایی نشد» | همچنان صادق است و اکنون مهمتر: `DB-01` نشان میدهد سرویس `postgres` فاقد ایمیج است |

---

## ۱۰. هماهنگی با کد زنده — تحلیل در حال اثرگذاری

HEAD از `d551242c` به **`bfd1e78d`** رسید (۱۶ کامیت تازه). ترتیب قابلتوجه:

```
1ad66304  fix(audit): F3+F7+F9 — signal FK integrity, ANALYZE, Redis TTL, backup table drop
          └─ 0124_drop_historical_daily_backup.py افزوده شد (down_revision اشتباه)
052f17b8  fix(migrations,tests): fix 0124 down_revision typo ...
b3a196f1  fix(api): CORS ordering, /metrics auth, hardcoded api_prefix, reload+workers
          └─ یافتههای EX-* / HTTP-* قسمتهای ۰۱ و ۰۲
d6962d0a  fix(config,security,infra): CFG-01/03/07/11/12/17/18 from deep-dive part 03
2b4d9ddc  fix(config): delete 14 dead BaseSettings subclasses (CFG-08)
```

**راستیآزمایی هفت یافته قسمت ۰۳ در HEAD تازه:**

| یافته | وضعیت | سند |
|---|---|---|
| `CFG-01` | ✅ بسته | `docker-compose.production.yml:22` → `ENV: production` |
| `CFG-03` | ✅ بسته | `.env.example:55,81,239` → سه کلید مستند شدند |
| `CFG-07` | ✅ بسته | `docker-compose.production.yml:63-64` → `/health/ready` |
| `CFG-08` | ✅ بسته | `core/config/` از ۱۸ فایل به ۴ فایل رسید؛ دقیقاً همان ۳ ماژول زنده باقی ماندند |
| `CFG-11/12` | ✅ بسته | کامیت `d6962d0a` صریحاً آنها را نام میبرد |
| `CFG-17` | ✅ بسته | `docker-compose.yml:104-106` → `INGESTION_LAKE_*` |
| `CFG-18` | ✅ بسته | `docker-compose.yml:98` / `.env.example:91` → `postgresql://` بدون `+asyncpg` |

همزمان worktree که ۹ فایل اصلاحشده داشت **اکنون پاک است** — آن تغییرات کامیت شدهاند. دو فایل `final_l1_tests.txt` و `final_l2_lint.txt` توسط فرایند موازی ساخته شده و این تحلیل آنها را نخوانده و لمس نکرده است.

**نتیجه روششناختی:** مخزن دیگر یک جسم ایستا نیست؛ هر قسمت باید «وضعیت یافتههای قسمت قبل» را نیز بازخوانی کند. از این قسمت به بعد، بند «هماهنگی با کد زنده» بخشی ثابت از پروتکل است.

---

## ۱۱. مرز روش

- تمام شمارشها با AST (`ast.Assign` + `ast.AnnAssign` برای `revision` / `down_revision`) و اسکن متنی محدودشده انجام شد؛ از regex ساده برای گراف استفاده نشد، چون در تحلیل پیشین ۷ head کاذب داده بود.
- **هیچ مهاجرتی اجرا نشد**: نه `alembic upgrade head`، نه `downgrade`، نه `create_all`. ادعای `DB-02` بر اساس نبود گارد در `0001` و نیاز CI به `CREATE EXTENSION` است، نه مشاهده خطای زنده.
- **هیچ اتصال DB برقرار نشد**؛ `sqlalchemy` در مفسر سیستمی نصب نیست، بنابراین `Base.metadata` بهصورت تجربی شمارش نشد (بند ۸).
- محتوای `.env.production` فقط از نظر نام کلید خوانده شد؛ مقادیر در این گزارش افشا نشدهاند.
- `docker compose config` اجرا نشد (PyYAML و docker CLI در محیط تحلیل در دسترس نبودند)؛ `DB-01` حاصل خواندن مستقیم بلوک YAML و نبود هر سه کلید `image` / `build` / `extends` است.
- سه ورکفلو CI از نظر متن بررسی شدند، نه اجرای واقعی روی GitHub Actions.
- اسکن مصرفکنندگان با پرش صریح از `.git`, `node_modules`, `__pycache__`, `.freebuff`, `_FRONTEND_BACKEND_COPY`, `code_dump`, `AUDIT_REPORTS` انجام شد تا از تکرار تایماوت جستوجوی سراسری جلوگیری شود.

---

**ترتیب پیشنهادی بستن (صرفاً اولویت، بدون تغییر کد):** `DB-01 → DB-02 → DB-05 → DB-06 → DB-03 → DB-04 → DB-07 → DB-08` — دو تای نخست استقرار تولید را متوقف میکنند و چون قسمت ۰۳ گیت `ENV=production` را روشن کرده، اکنون `validate_production()` واقعاً اجرا میشود و این شکافها دیگر پشت خاموشی گیت پنهان نمیمانند.

*فقط فایل تحلیلی ساخته شد؛ هیچ کدی تغییر نکرد.*
