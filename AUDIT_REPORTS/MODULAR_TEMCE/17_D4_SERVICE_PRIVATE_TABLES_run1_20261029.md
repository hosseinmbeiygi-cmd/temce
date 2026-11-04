# گزارش ممیزی — جدول‌های خصوصیِ سرویس‌ها: انتقال به Alembic (یافتهٔ D4)

- **شناسهٔ اجرا:** `RUN2-D4-SERVICE-PRIVATE-TABLES`
- **تاریخ:** 2026-10-29 (Asia/Tehran)
- **شاخه:** `integration/golddesk-fixes`
- **HEAD:** `90597e05b9f4328bcd82ee819a31ba5c55413c12` (بدون تغییر)
- **دامنه:** ادامهٔ گزارش‌های ۱۴ و ۱۶ — بستن یافتهٔ **D4**: جدول‌هایی که فقط با DDL زمان‌اجرا ساخته می‌شوند و هیچ ORM/Alembic ندارند.

> فایل جدید؛ هیچ گزارش قبلی بازنویسی نشد؛ هیچ فایل عامل دیگری تغییر نکرد.

---

## ۱. خلاصهٔ مدیریتی

| مورد | نتیجه |
|---|---|
| مهاجرت `0119` برای ۶ جدول خصوصیِ در حال استفاده | ✅ ساخته شد |
| ایندکس جزئیِ `uq_signal_accuracy_pending_key` (که فقط در runtime ساخته می‌شد) | ✅ به Alembic منتقل شد |
| گارد DB-free ساختار + drift روی DDL خدمات | ✅ ۳ تست جدید |
| اجرای واقعی روی PostgreSQL | ⛔ BLOCKED (DB آزمایشی در دسترس نیست) |

- Rنشانه هم‌زمانی: عامل دیگری هم‌زمان روی `services/watchlist_service.py` (سازگار با Alembic 0117) کار می‌کند؛ به آن فایل دست نزدم.

---

## ۲. فهرست جدول‌های D4 و وضعیت

| جدول | محل DDL زمان‌اجرا | مصرف واقعی | وضعیت |
|---|---|---|---|
| `signal_performance` | `services/signal_performance_tracker.py:77` | tracker (اختصاصی) | ✅ به 0119 منتقل شد |
| `signal_weight_accuracy` | `services/signal_performance_tracker.py:95` | tracker (اختصاصی، اصلاح D1) | ✅ به 0119 منتقل شد |
| `calibration_models` | `services/probability_calibrator.py:112` + `quant_signal_orchestrator.py:1578` | `ProbabilityCalibrator` (زنده) | ✅ به 0119 منتقل شد |
| `isotonic_calibration` | `services/isotonic_calibrator.py:250` | `train_all_default`/`save_model` | ✅ به 0119 منتقل شد |
| `diagnostic_runs` | `services/diagnostics_runner.py:767` | `DiagnosticsRunner` | ✅ به 0119 منتقل شد |
| `diagnostic_findings` | `services/diagnostics_runner.py:783` | `DiagnosticsRunner` | ✅ به 0119 منتقل شد |
| `uq_signal_accuracy_pending_key` | `quant_signal_orchestrator.py:1566` | dedupe سیگنال‌های معلق | ✅ به 0119 منتقل شد |
| `watchlist` | `services/watchlist_service.py` | — | قبلاً Alembic 0117 (عامل دیگر) پوشش داد |
| `bar_data`/`market_regimes`/`trading_signals`/`strategy_performance` | `services/ensemble_engine.py` (رشتهٔ `TIMESCALE_SCHEMA`) | **کد مرده** (هیچ‌جا اجرا نمی‌شود) | باز — تصمیم محصولی |

---

## ۳. علت ریشه‌ای

همان الگوی گزارش ۱۴: این جدول‌ها نه ORM مدل دارند و نه migration، و به‌جای آن در زمان اجرا با `CREATE TABLE IF NOT EXISTS` ساخته می‌شوند. نتیجه: یک DB تمیزِ production (که نه `create_all` اجرا می‌کند و نه این سرویس لزوماً فراخوانی می‌شود) این جدول‌ها را ندارد → اولین کوئری `UndefinedTable` می‌دهد. ایندکس `uq_signal_accuracy_pending_key` نیز همین‌طور فقط در runtime ساخته می‌شد و روی DBهای قدیمی‌تر که orchestrator را اجرا نکرده‌اند وجود ندارد (ریسک درج سیگنال تکراری و تورم آمارهٔ دقت).

---

## ۴. اصلاح انجام‌شده

### ۴.۱ `migrations/versions/0119_service_private_tables.py` (جدید)

- ۶ `CREATE TABLE IF NOT EXISTS` (DDL **منجمد** از سورس همین سرویس‌ها، ۲۰۲۶-۱۰-۲۹): `signal_performance`, `signal_weight_accuracy`, `calibration_models`, `isotonic_calibration`, `diagnostic_runs`, `diagnostic_findings`.
- ۳ ایندکس: `idx_diag_findings_run`, `idx_diag_findings_level`, و `uq_signal_accuracy_pending_key` (جزئی، `WHERE outcome_set_at IS NULL`).
- `revision = "0119_service_private_tables"`, `down_revision = "0118_core_tables_backfill"` → زنجیرهٔ تک‌head.
- DDL زمان‌اجرا در سرویس‌ها **عمداً باقی ماند** به‌عنوان self-heal (بعد از اجرای migration بی‌اثر/no-op است) — همان الگوی `watchlist` در 0117.

### ۴.۲ `tests/unit/test_service_private_tables_migration.py` (جدید، ۳ تست)

1. `test_0119_defines_the_expected_tables` — ساختار و شناسه‌های revision.
2. `test_0119_ddl_matches_service_source_ddl` — **گارد drift**: DDL منجمدِ migration باید دقیقاً با DDL فعلی سرویس‌ها بخواند.
3. `test_0119_creates_pending_signal_index` — وجود ایندکس جزئی.

---

## ۵. فرمان‌ها، تست‌ها و exit codeها

همه با `$env:PYTHONUTF8=1` و `python` (3.11.9).

| موضوع | فرمان | نتیجه | exit |
|---|---|---|---|
| تست‌های جدید D4 + D3 | `python -m pytest tests/unit/test_service_private_tables_migration.py tests/unit/test_core_tables_migration.py -q -p no:cacheprovider --no-header` | `6 passed` | 0 |
| رگرسیون ترکیبی migration/DDL | `python -m pytest tests/unit/test_service_private_tables_migration.py tests/unit/test_core_tables_migration.py tests/unit/test_runtime_ddl_consistency.py tests/unit/services/test_gold_macro_migration.py tests/unit/services/test_gold_futures_migration.py tests/unit/services/test_gold_feed_health_migration.py tests/unit/test_dockerfile_hygiene.py -q -p no:cacheprovider --no-header` | `24 passed` | 0 |
| ruff | `python -m ruff check migrations/versions/0119_service_private_tables.py tests/unit/test_service_private_tables_migration.py` | `All checks passed!` | 0 |
| بررسی head | `python -c "…ScriptDirectory…get_heads()"` | `['0119_service_private_tables']` | 0 |
| رندر SQL آفلاین (برش) | `python -m alembic upgrade 0118:0119 --sql` | `Running upgrade 0118… -> 0119_service_private_tables` + `CREATE TABLE IF NOT EXISTS …` + ایندکس جزئی | 0 |
| import سرویس‌ها | `python -c "import services.signal_performance_tracker, services.probability_calibrator, services.isotonic_calibrator, services.diagnostics_runner"` | `IMPORT OK` | 0 |

---

## ۶. موارد باز / مسدود

1. **اجرای واقعی روی PostgreSQL و introspection — BLOCKED.** DB آزمایشی/daemon در دسترس نیست؛ PASS در سطح اجرای DB اعلام نشد.
2. **`ensemble_engine.TIMESCALE_SCHEMA`** (`bar_data`/`market_regimes`/`trading_signals`/`strategy_performance`) — کد مرده؛ افزودن migration برای قابلیتِ استفاده‌نشده یک تصمیم محصولی است (باز).
3. **تکرار DDL `calibration_models` در دو سرویس** (`probability_calibrator.py` و `quant_signal_orchestrator.py`) — هر دو با DDL منجمد 0119 سازگارند، ولی یکسان‌سازی به یک منبع واحد یک refactor وابسته به تصمیم است (باز).
4. **تست‌های DB-محور** (`needs_db`) همچنان BLOCKED.

---

## ۷. معیارهای پذیرش

| معیار | نتیجه | شاهد |
|---|---|---|
| ۶ جدول خصوصیِ در حال استفاده تعریف canonical دارند | ✅ PASS | `test_0119_defines_the_expected_tables` |
| DDL منجمد با DDL سرویس‌ها drift ندارد | ✅ PASS | `test_0119_ddl_matches_service_source_ddl` |
| ایندکس جزئیِ سیگنال معلق در Alembic | ✅ PASS | `test_0119_creates_pending_signal_index` |
| تک‌head بودن زنجیره | ✅ PASS | `get_heads() == ['0119_service_private_tables']` |
| رندر آفلاین 0119 | ✅ PASS | برش `0118:0119 --sql` |
| ruff | ✅ PASS | exit 0 |
| اجرای واقعی روی DB آزمایشی | ⛔ BLOCKED | PASS اعلام نشد |

---

## ۸. نتیجهٔ نهایی

- یافتهٔ D4 در سطح کد **رفع شد**: ۶ جدول خصوصیِ در حال استفاده + یک ایندکس جزئی، اکنون تعریف Alembic دارند و DDL زمان‌اجرا به self-heal کاهش یافت.
- **BLOCKED باقی‌مانده:** اجرای واقعی روی PostgreSQL (niche DB) و جدول‌های کدِ مردهٔ `ensemble_engine` (تصمیم محصولی).
- وضعیت مرحله: **PASS در سطح کد، BLOCKED در سطح اجرای DB**.
