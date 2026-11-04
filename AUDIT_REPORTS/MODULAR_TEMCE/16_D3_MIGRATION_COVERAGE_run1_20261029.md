# گزارش ممیزی — تکمیل پوشش migration برای ۲۸ جدول ORM (یافتهٔ D3)

- **شناسهٔ اجرا:** `RUN2-D3-MIGRATION-BACKFILL`
- **تاریخ:** 2026-10-29 (Asia/Tehran)
- **شاخه:** `integration/golddesk-fixes`
- **HEAD:** `90597e05b9f4328bcd82ee819a31ba5c55413c12` (بدون تغییر)
- **دامنه:** ادامهٔ گزارش ۱۴ — بستن یافتهٔ **D3**: ۲۸ جدول ORM که هیچ migration سازنده‌ای نداشتند.

> فایل جدید؛ هیچ گزارش قبلی بازنویسی نشد و هیچ فایل متعلق به عامل دیگر تغییر نکرد.

---

## ۱. خلاصهٔ مدیریتی

| مورد | نتیجه |
|---|---|
| migration جدید برای ۲۸ جدول | ✅ `migrations/versions/0118_core_tables_backfill.py` |
| پوشش ۱۰۸/۱۰۸ جدول ORM | ✅ تأییدشده با تست DB-free |
| گارد drift (ORM ↔ DDL منجمد) | ✅ اضافه شد |
| اجرای واقعی migration روی PostgreSQL | ⛔ **BLOCKED** (DB آزمایشی در دسترس نیست) |

- DDL به‌صورت **منجمد (frozen)** از متادیتای ORM استخراج شد؛ تست گارد هرگونه انحراف آیندهٔ مدل از این DDL را می‌گیرد و مهاجرت جدید می‌طلبد.
- همهٔ دستورات `IF NOT EXISTS` هستند: روی DBهای فعلی (که این جدول‌ها را تاریخی با `create_all` دارند) **no-op** است و تنها در DB تازه فاصله را پر می‌کند.
- رخداد مهم هم‌زمانی: عامل دیگری هم‌زمان فایل `0117_user_owned_alerts_watchlist.py` (rev `0117`) را ساخت. برای پرهیز از دو-head، مهاجرت من به **`0118`** با `down_revision="0117"` زنجیر شد (تضاد بازنویسی/حذف نشد).

---

## ۲. علت ریشه‌ای (خلاصهٔ گزارش ۱۴)

`core/database.init_database` قبلاً با `Base.metadata.create_all` جدول‌ها را می‌ساخت (مسیر dev). در نتیجه ~۲۶٪ جداول ORM هرگز در Alembic بازتاب نیافتند. یک استقرار تمیز production که `create_all` اجرا نمی‌کند، این جدول‌ها را ندارد → هر کوئری وابسته `UndefinedTable` می‌دهد. شاهد تاریخی: docstring خودِ `scripts/stamp_migration.py` می‌گوید جدول‌های 0001–0021 با `create_all` ساخته شده‌اند.

---

## ۳. فهرست ۲۸ جدول و مصرف‌کننده‌های زنده

`alert_history, alerts, audit_logs, backtest_runs, backtest_trades, codal_audit_summary, codal_reports, compare_results, indicators, instruments, job_runs, macro_indicators, markets, ml_model_versions, ml_models, ml_predictions, ml_training_runs, news_articles, orderbooks, portfolio_positions, portfolios, provider_health, provider_health_history, quotes, recommendations, signals, trades, users`

مصرف‌کننده‌های زندهٔ نمونه (grep): `instruments` (۴ فایل)، `quotes` (۱۴ فایل)، `portfolios`/`portfolio_positions` (`services/risk_metrics.py`)، `news_articles` (۵ فایل)، `job_runs` (۳ فایل)، `codal_reports` (۳ فایل)، `macro_indicators` (`services/real_return_calculator.py`).

---

## ۴. اصلاح انجام‌شده

### ۴.۱ `migrations/versions/0118_core_tables_backfill.py` (جدید، ۱۰۶۵ خط)

- ۲۸ `CREATE TABLE IF NOT EXISTS` + ۸۶ `CREATE INDEX IF NOT EXISTS` (بر اساس متادیتای ORM با dialect پستگرس).
- `revision = "0118_core_tables_backfill"`, `down_revision = "0117"` → زنجیرهٔ تک‌head.
- `upgrade()` هر دو بلوک `_TABLES`/`_INDEXES` را اجرا می‌کند؛ `downgrade()` به‌ترتیب معکوس `DROP INDEX`/`DROP TABLE` می‌زند.
- نکتهٔ طراحی: DDL **literal** است (نه `create_all`) تا مهاجرت تکرارپذیر و مستقل از drift مدل باشد؛ گارد drift در تست این را تضمین می‌کند.

### ۴.۲ `tests/unit/test_core_tables_migration.py` (جدید، ۳ تست)

1. `test_every_orm_table_is_created_by_a_migration` — هیچ جدول ORM نباید بی‌migration بماند.
2. `test_backfill_ddl_matches_orm_metadata` — DDL منجمد باید دقیقاً با مجموعه‌ستون ORM بخواند (گارد drift).
3. `test_backfill_migration_is_single_head_chain` — بررسی `revision`/`down_revision`.

---

## ۵. فرمان‌ها، تست‌ها و exit codeها

همه با `$env:PYTHONUTF8=1` و `python` (3.11.9).

| موضوع | فرمان | نتیجه | exit |
|---|---|---|---|
| گارد پوشش (قبل از 0118 — شبیه‌سازی) | اسکریپت پویش migrationها بدون فایل 0118 | **۲۸ جدول بدون پوشش** → گارد FAIL می‌شود | 0 (شبیه‌سازی) |
| گارد پوشش/drift (بعد از 0118) | `python -m pytest tests/unit/test_core_tables_migration.py -q -p no:cacheprovider --no-header` | `3 passed` | 0 |
| مجموعهٔ رگرسیون این مرحله | `python -m pytest tests/unit/test_core_tables_migration.py tests/unit/test_runtime_ddl_consistency.py tests/unit/services/test_gold_macro_migration.py tests/unit/services/test_gold_futures_migration.py tests/unit/services/test_gold_feed_health_migration.py tests/unit/test_runtime_patches.py tests/unit/test_dockerfile_hygiene.py -q -p no:cacheprovider --no-header` | `28 passed` | 0 |
| ruff | `python -m ruff check migrations/versions/0118_core_tables_backfill.py tests/unit/test_core_tables_migration.py tests/unit/test_runtime_ddl_consistency.py` | `All checks passed!` | 0 |
| بررسی head | `python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; print(ScriptDirectory.from_config(Config('alembic.ini')).get_heads())"` | `['0118_core_tables_backfill']` | 0 |
| رندر SQL آفلاین (برش) | `python -m alembic upgrade 0116:0118 --sql` | `Running upgrade 0117 -> 0118_core_tables_backfill` + `CREATE TABLE IF NOT EXISTS …` | 0 |

---

## ۶. موارد مسدود / باز

1. **اجرای واقعی روی PostgreSQL — BLOCKED.** نه DB آزمایشی در دسترس است، نه daemon. علاوه بر آن، `alembic upgrade head --sql` (offline کامل) در **مهاجرت پیش‌موجود `0007_signal_accuracy.py:26`** با `NoInspectionAvailable` شکست می‌خورد (چون از `sa.inspect(conn)` روی `MockConnection` استفاده می‌کند). این یک نقص مستقل و پیش‌موجود است (خارج از دامنهٔ این مرحله، مربوط به عامل migration-های قبلی) و رفع نشد؛ فقط ثبت شد.
2. **بررسی نوع واقعی ستون‌ها (introspection)** روی DB عملیاتی ممنوع است → BLOCKED.
3. **جدول‌های خصوصی سرویس‌ها (D4):** `signal_performance`, `signal_weight_accuracy`, `diagnostic_runs/findings`, `isotonic_calibration`, `calibration_models`, `bar_data`, `market_regimes`, `trading_signals`, `strategy_performance` هنوز DDL زمان‌اجرا دارند و ORM/Alembic ندارند؛ تصمیم محصولی + DB آزمایشی لازم است (باز).

---

## ۷. معیارهای پذیرش

| معیار | نتیجه | شاهد |
|---|---|---|
| پوشش ۱۰۸/۱۰۸ جدول ORM توسط migration | ✅ PASS | `test_every_orm_table_is_created_by_a_migration` |
| عدم drift بین ORM و DDL منجمد | ✅ PASS | `test_backfill_ddl_matches_orm_metadata` |
| تک‌head بودن زنجیرهٔ Alembic | ✅ PASS | `get_heads() == ['0118_core_tables_backfill']` |
| رندر شدن 0118 در SQL آفلاین | ✅ PASS | برش `0116:0118 --sql` |
| ruff | ✅ PASS | exit 0 |
| هیچ فایل/مهاجرت عامل دیگر تغییر نکرد | ✅ PASS | فقط ۲ فایل جدید از این مرحله |
| اجرای واقعی روی DB آزمایشی | ⛔ BLOCKED | DB در دسترس نیست؛ PASS اعلام نشد |

---

## ۸. نتیجهٔ نهایی

- یافتهٔ D3 در سطح کد **رفع شد**: اکنون هر ۱۰۸ جدول ORM یک مهاجرت Alembic سازنده دارند (۲۸ جدول با `0118`).
- **BLOCKED باقی‌مانده:** اجرای واقعی روی PostgreSQL و introspection نوع ستون‌ها (نیازمند DB آزمایشی/daemon)؛ به‌اشتباه PASS اعلام نشد.
- وضعیت کلی مرحله: **PARTIAL/PASS در سطح کد، BLOCKED در سطح اجرای DB**.
