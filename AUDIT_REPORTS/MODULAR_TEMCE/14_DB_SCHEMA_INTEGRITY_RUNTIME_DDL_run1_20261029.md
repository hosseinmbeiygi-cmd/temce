# گزارش ممیزی مرحلهٔ ۴ — یکپارچگی دیتابیس/Schema: DDL زمان‌اجرا در برابر Alembic

- **شناسهٔ اجرا:** `RUN2-DB-SCHEMA-RUNTIME-DDL`
- **تاریخ:** 2026-10-29 (Asia/Tehran)
- **مخزن:** `C:\Users\Iran\Desktop\temce`
- **شاخه:** `integration/golddesk-fixes`
- **HEAD:** `90597e05b9f4328bcd82ee819a31ba5c55413c12` (بدون تغییر در طول این مرحله)
- **دامنه:** مرحلهٔ ۴ (پایگاه داده، Schema، Repository) — بخشی که مراحل دیگر آن را پوشش نداده بودند: تطبیق DDL زمان‌اجرا با Schema مرجع (ORM/Alembic).

> این گزارش یک فایل جدید است؛ هیچ گزارش قبلی بازنویسی نشد.

---

## ۱. خلاصهٔ مدیریتی

- **داده‌ای حذف/تغییر نکرد؛ هیچ migration روی DB عملیاتی اجرا نشد؛ هیچ عملیات مخرب Git انجام نشد.**
- یک **علت ریشه‌ای مشترک** یافت شد: چند ماژول `services/*` جدول‌هایی را با `CREATE TABLE IF NOT EXISTS` می‌سازند که تعریف مرجع آن‌ها در ORM (`models/*`) و/یا Alembic (`migrations/*`) است. چون در محیط واقعی جدول مرجع **زودتر** ساخته می‌شود، این DDL بی‌صدا no-op می‌شود و هر ستونی که کوئری زمان‌اجرا لازم دارد و در جدول مرجع نیست، در زمان اجرا با `UndefinedColumn` می‌شکند.
- دو fork مشخص و قابل‌اثبات:
  1. **`signal_accuracy` (D1 — P2):** `services/signal_performance_tracker.py` نسخهٔ دیگری از `signal_accuracy` با ستون‌های `(source, period, total_signals, correct_signals, avg_return, weight)` می‌سازد؛ جدول مرجع (migration `0007` / `models/signal_accuracy.py`) هیچ‌کدام از `period`/`weight`/`total_signals` را ندارد → `_update_accuracy_summary()` هرگز روی جدول واقعی کار نمی‌کند.
  2. **`portfolio_positions` (D2 — P2، کد مرده):** `services/ensemble_engine.py::TIMESCALE_SCHEMA` نسخهٔ متفاوتی با `(time, symbol, qty, avg_price, …)` تعریف می‌کند، در حالی که جدول مرجع (`models/portfolio.py::PortfolioPositionModel`) با `(portfolio_id, quantity, avg_cost, weight_pct, …)` است — همان ستون‌هایی که `services/risk_metrics.py` کوئری می‌کند.
- **اصلاح ریشه‌ای انجام شد:** جدول خصوصی tracker به `signal_weight_accuracy` منتقل شد؛ DDL متناقض `portfolio_positions` از `TIMESCALE_SCHEMA` حذف شد (کد مرده و منبع بالقوهٔ انحراف). یک نگهبانِ رگرسیون بدون نیاز به DB اضافه شد.
- **تست:** نگهبان جدید قبل از اصلاح `3 failed` (RED) و بعد از اصلاح `4 passed` (GREEN).
- **پوشش migration:** از ۱۰۸ جدول ORM، **۲۸ جدول (۲۶٪) هیچ migration سازنده‌ای ندارند** (D3 — P3، بدهی فنی مستندشده). این بخش به دلیل نبود DB آزمایشی `BLOCKED` است.

---

## ۲. وضعیت واقعی Git و snapshotها

وضعیت مختصات در طول این مرحله پایدار بود (`HEAD` تغییر نکرد)، اما working tree به‌شدت شلوغ و در حال تغییر هم‌زمان توسط عامل‌های دیگر است.

| snapshot | زمان | branch | head | staged | unstaged | untracked |
|---|---|---|---|---|---|---|
| `t5-schema-stage.txt` | شروع مرحله | integration/golddesk-fixes | 90597e05… | 138 | 105 | 47 |
| `t6-schema-fix.txt` | پایان مرحله | integration/golddesk-fixes | 90597e05… | 138 | 113 | 55 |

فایل‌های تغییرکرده **فقط** توسط این مرحله:

```
 M services/ensemble_engine.py
 M services/signal_performance_tracker.py
?? tests/unit/test_runtime_ddl_consistency.py
```

**هشدار هم‌زمانی:** سایر عامل‌ها در همین بازه روی tree کار می‌کردند (unstaged از ۱۰۵ به ۱۱۳ و untracked از ۴۷ به ۵۵ رسید). طبق §3.4، عملیات مخرب/مشترک انجام نشد و هیچ فایل متعلق به دیگران بازنویسی/بازگردانی نشد.

---

## ۳. علت ریشه‌ای

مسیر ساخت جدول در این سیستم دوگانه است:

1. **ORM auto-create (فقط dev):** `core/database.py::_create_all_tables` با `Base.metadata.create_all` تنها زمانی اجرا می‌شود که `settings.database_auto_create_tables=True` باشد؛ پیش‌فرض `False` است (`core/config/__init__.py`). پس در production هرگز اجرا نمی‌شود.
2. **Alembic:** منبع رسمی schema در production (`alembic.ini`، `migrations/versions/*`).

اما چند سرویس به‌صورت مستقل `CREATE TABLE IF NOT EXISTS` صادر می‌کنند که با هیچ‌کدام از دو مسیر بالا هم‌آهنگ نیست. چون `IF NOT EXISTS` است، تعریف دوم بی‌صدا رد می‌شود و «منبعِ برنده» به ترتیب اجرا بستگی پیدا می‌کند. نتیجه: هر کوئری که به ستون ویژهٔ نسخهٔ زمان‌اجرا نیاز دارد، روی جدول مرجع با خطای ستونِ ناموجود می‌شکند.

شاهد تاریخی این الگو: توضیح خودِ `scripts/stamp_migration.py:1-6` می‌گوید جدول‌های 0001–0021 «توسط `core.database.init_database -> Base.metadata.create_all` ساخته شده‌اند» و `alembic_version` وجود نداشته — یعنی ریشهٔ جدول‌های sans-migration از همان‌جاست.

---

## ۴. یافته‌ها

فرمت هر یافته: شناسه | عنوان | شدت | وضعیت | شواهد | علت ریشه‌ای | اثر.

### D1 — `signal_accuracy` دوگانه (رفع‌شده)

- **فایل/خطوط:** `services/signal_performance_tracker.py:60-95` (DDL)، `:241-291` (`_update_accuracy_summary`)، `:293-317` (`get_accuracy_by_source`).
- **جدول مرجع:** `migrations/versions/0007_signal_accuracy.py` و `models/signal_accuracy.py:17`.
- **شاهد:** DDL زمان‌اجرا ستون‌های `period VARCHAR(16)`، `weight NUMERIC`، `total_signals INT` و `UNIQUE(source, period)` را می‌سازد؛ جدول مرجع هیچ‌یک را ندارد و در عوض `symbol`/`market`/`direction`/`timeframe` و ستون‌های نتیجه دارد.
- **علت ریشه‌ای:** نام جدول با جدول مرجع یکسان انتخاب شده در حالی که قرارداد ستون‌ها کاملاً متفاوت است.
- **اثر:** `INSERT INTO signal_accuracy (source, period, …)` روی جدول مرجع با خطای ستون ناموجود شکست می‌خورد؛ در نتیجهٔ به‌روزرسانی وزن‌ها و `get_weight_adjustments()` عملاً غیرقابل‌اجرا می‌شوند (شکست پنهان زیر `except` سطح بالا).
- **reachability:** `SignalPerformanceTracker` فقط از طریق `apps/api/dependencies.py:402-405` قابل ساخت است و هیچ روتری آن را consume نمی‌کند → در runtime فعال نیست ولی مسیر آمادهٔ استفاده و شکست‌آمیز است؛ اصلاح آن کم‌ریسک و مستقل است.
- **وضعیت:** ✅ رفع‌شده.

### D2 — `portfolio_positions` دوگانه (رفع‌شده، کد مرده)

- **فایل/خطوط:** `services/ensemble_engine.py:350` (`TIMESCALE_SCHEMA`)، تعریف `portfolio_positions` در همان رشته.
- **جدول مرجع:** `models/portfolio.py::PortfolioPositionModel:22-38` (`portfolio_id`, `quantity`, `avg_cost`, `current_price`, `market_value`, `unrealized_pnl`, `weight_pct`).
- **شاهد:** نسخهٔ زمان‌اجرا `(time, symbol, qty, avg_price, market_value, unrealized_pnl, weight)` است.
- **مصرف‌کنندهٔ واقعی:** `services/risk_metrics.py:223-229` کوئری `SELECT … weight_pct FROM portfolio_positions WHERE portfolio_id = …` — هیچ‌کدام از `portfolio_id`/`weight_pct` در نسخهٔ زمان‌اجرا نیست.
- **علت ریشه‌ای:** رشتهٔ DDL (schema ماتریسی TimescaleDB) بدون تطبیق با ORM نوشته شده و به‌کد اجرا هم متصل نشده است.
- **reachability/grep:** `TIMESCALE_SCHEMA` هیچ‌جا اجرا نمی‌شود (تنها تعریف در `ensemble_engine.py:350`؛ هیچ `execute(...TIMESCALE_SCHEMA...)`). یعنی **کد مرده** است، اما اگر روزی اجرا شود، schema مرجعِ `risk_metrics` را منحرف/مخدوش می‌کند.
- **وضعیت:** ✅ رفع‌شده (حذف DDL متناقض از کد مرده).

### D3 — ۲۸ جدول ORM بدون migration سازنده (باز — P3)

- **شاهد (محاسبهٔ استاتیک):** از ۱۰۸ جدول `Base.metadata`، ۲۸ جدول در هیچ `migrations/versions/*.py` با «CREATE TABLE» ساخته نمی‌شوند:

  ```
  alert_history, alerts, audit_logs, backtest_runs, backtest_trades,
  codal_audit_summary, codal_reports, compare_results, indicators, instruments,
  job_runs, macro_indicators, markets, ml_model_versions, ml_models,
  ml_predictions, ml_training_runs, news_articles, orderbooks, portfolio_positions,
  portfolios, provider_health, provider_health_history, quotes, recommendations,
  signals, trades, users
  ```

- **کوئری‌های زندهٔ وابسته (نمونه):** `instruments` (۴ فایل از جمله `services/history_backfill_service.py`)؛ `quotes` (۱۴ فایل)؛ `portfolios`/`portfolio_positions` (`services/risk_metrics.py`)؛ `news_articles` (۵ فایل)؛ `job_runs` (۳ فایل)؛ `codal_reports` (۳ فایل)؛ `macro_indicators` (`services/real_return_calculator.py`).
- **علت ریشه‌ای:** همان الگوی بند §3 — جدول‌ها زمانی با `create_all` ساخته شده‌اند و به‌صورت migration بازتاب نیافته‌اند.
- **اثر:** در یک استقرار تمیزِ production (که `create_all` ندارد)، این جدول‌ها اگر دستی ساخته نشده باشند موجود نیستند → endpoint/سرویس وابسته `UndefinedTable` می‌دهد.
- **وضعیت:** ⛔ **BLOCKED** — تأیید وجود/عدم‌وجود و مهاجرت ایمن نیازمند DB آزمایشی جداگانه است. افزودن جهشِ schema روی DB عملیاتی ممنوع (طبق §7). این مورد باید در محیط ایزوله حل شود.

### D4 — DDL زمان‌اجرا برای جدول‌های غیر-ORM و همین‌نام (باز — P3، خارج از گارد فعلی)

- **نمونه‌های تأییدشده:** `calibration_models` در دو جا (`services/probability_calibrator.py:105` و `services/quant_signal_orchestrator.py:1578`)؛ DDL جدول `signal_accuracy` در `services/quant_signal_orchestrator.py:1525` که فقط «زیرمجموعهٔ» ستون‌های جدول مرجع است (چون هیچ FK/`CREATE TABLE` در Alembic برای ستون‌های منحصربه‌فرد آن وجود ندارد، بی‌خطر است ولی الگوی شکننده)؛ جدول‌های خصوصی `diagnostic_runs`/`diagnostic_findings` (`services/diagnostics_runner.py:767,783`)، `isotonic_calibration` (`services/isotonic_calibrator.py:250`)، `signal_performance` (`services/signal_performance_tracker.py:68`).
- **وضعیت:** ⛔ باز — این جدول‌ها هیچ تعریف ORM/Alembic ندارند؛ مهاجرت آن‌ها یک تصمیم محصولی است و به دلیل نبود DB `BLOCKED`.

---

## ۵. اصلاحات انجام‌شده

### 5.1 `services/signal_performance_tracker.py`

- جدول خصوصی tracker از `signal_accuracy` (نام مرجعِ متعلق به دیگران) به **`signal_weight_accuracy`** تغییر نام یافت؛ در `ensure_tables()`، `_update_accuracy_summary()` (هر دو INSERT) و `get_accuracy_by_source()`.
- Docstring ماژول و متدها به‌روزرسانی شد تا صراحتاً بگوید این جدول «خصوصی» است و نباید با `signal_accuracy` مرجع اشتباه شود.
- **دلیل:** رفع D1 — نگه‌داشتن قابلیت وزن‌دهی بدون دست‌بردن در قرارداد جدول مرجع.

### 5.2 `services/ensemble_engine.py`

- بلوک `CREATE TABLE IF NOT EXISTS portfolio_positions (…)` و `create_hypertable(...)` متناظر از رشتهٔ `TIMESCALE_SCHEMA` حذف شد.
- **دلیل:** رفع D2 — حذف منبعِ انحراف schema؛ بقیهٔ جدول‌های `bar_data`/`market_regimes`/`trading_signals`/`strategy_performance` که مصرف‌کننده/جدول ORM ندارند دست‌نخورده ماندند (حداقل دامنه).

### 5.3 `tests/unit/test_runtime_ddl_consistency.py` (جدید)

چهار تست بدون نیاز به DB:

1. `test_signal_performance_tracker_does_not_fork_signal_accuracy`
2. `test_ensemble_timescale_schema_does_not_fork_portfolio_positions`
3. `test_signal_performance_tracker_never_targets_canonical_signal_accuracy`
4. `test_no_runtime_ddl_forks_an_orm_table` (گارد عمومی: DDL زمان‌اجرا نباید ستون غیرمرجع برای جدول‌های ORM اعلام کند)

---

## ۶. فرمان‌ها، تست‌ها و نتایج واقعی

همهٔ فرمان‌ها با `$env:PYTHONUTF8=1` و اینترپرتر `python` (3.11.9) اجرا شدند.

| موضوع | فرمان | نتیجه | exit |
|---|---|---|---|
| گارد جدید (قبل از اصلاح — RED) | `python -m pytest tests/unit/test_runtime_ddl_consistency.py -q -p no:cacheprovider --no-header` | `3 failed` | 1 |
| گارد جدید (بعد از اصلاح — GREEN) | همان | `4 passed` | 0 |
| رگرسیون هدف‌مند | `python -m pytest tests/unit/test_risk_metrics.py tests/unit/services/test_watchlist_market_health_regression.py tests/test_all_modules.py -q -p no:cacheprovider --no-header` | `24 passed` | 0 |
| ruff روی فایل‌های تغییرکرده | `python -m ruff check services/signal_performance_tracker.py services/ensemble_engine.py tests/unit/test_runtime_ddl_consistency.py` | `All checks passed!` | 0 |
| import سالم | `python -c "import services.signal_performance_tracker, services.ensemble_engine"` | `IMPORT OK` | 0 |
| رگرسیون گسترده | `python -m pytest tests/unit/services -q -p no:cacheprovider --no-header` | `13 failed, 3258 passed, 25 skipped, 2 deselected` | 1 |

### تحلیل ۱۳ شکست در رگرسیون گسترده (پیش‌موجود، نامرتبط)

- **۹ تست `tests/unit/services/test_adjusted_price_reader.py`:** با `asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "market"` شکست می‌خورند → **BLOCKED** (دیتابیس عملیاتی در دسترس نیست، مطابق محدودیت محیط). هیچ ارتباطی با تغییر این مرحله ندارند.
- **۴ تست `tests/unit/services/test_indicator_calculation.py`:** باگ منطقی مستقل در `MarketService._stochastic` (مثلاً `assert len(d_line) == 9` در حالی که انتظار ۷ است). این فایلِ متعلق به عامل دیگر است و **خارج از دامنهٔ این مرحله** است؛ اصلاح نشد.

---

## ۷. موارد رفع‌شده / باز / مسدود / متناقض

| مورد | وضعیت |
|---|---|
| D1 `signal_accuracy` دوگانه | ✅ رفع‌شده + تست |
| D2 `portfolio_positions` دوگانه (کد مرده) | ✅ رفع‌شده + تست |
| D3 ۲۸ جدول ORM بدون migration | ⛔ BLOCKED (نیازمند DB آزمایشی) |
| D4 DDL جدول‌های غیر-ORM/همین‌نام | ⛔ باز (تصمیم + DB آزمایشی) |
| تست‌های DB-محور (`needs_db`/auth) | ⛔ BLOCKED (بدون PostgreSQL) |

---

## ۸. معیارهای پذیرش این مرحله

| معیار | نتیجه | شاهد |
|---|---|---|
| هیچ داده‌ای حذف/تغییر نکرد | ✅ PASS | هیچ TRUNCATE/DELETE/migration اجرا نشد |
| هیچ عملیات مخرب Git انجام نشد | ✅ PASS | HEAD بدون تغییر؛ فقط ۳ فایلِ این مرحله تغییر یافت |
| fork زمان‌اجرا در برابر ORM اثبات و رفع شد | ✅ PASS | تست `3 failed → 4 passed` |
| تست شکست‌خورده بدون ضعیف‌کردن assertion | ✅ PASS | گارد جدید ابتدا RED بود و سپس GREEN |
| ruff روی فایل‌های تغییرکرده | ✅ PASS | exit 0 |
| هیچ شکست جدیدی معرفی نشد | ✅ PASS | رگرسیون هدف‌مند `24 passed`؛ شکست‌های گسترده پیش‌موجود و مستقل |
| ادعای «تمام پروژه بررسی شد» | ❌ مطرح نشد | فقط دامنهٔ DDL/ORM بررسی شد؛ D3/D4 باز است |

---

## ۹. کارهای باقی‌مانده و وابستگی‌ها

1. **migrationهای بازتابی برای D3:** افزودن migration برای ۲۸ جدول ORM بدون تعریف، سپس حذف وابستگی به `create_all`. نیازمند DB آزمایشی جداگانه (اجرای `alembic upgrade head` روی DB عملیاتی ممنوع).
2. **مهاجرت جدول‌های D4** (خصوصیِ سرویس‌ها) به Alembic و حذف DDL زمان‌اجرا از `services/*` — همان الگوی `services/watchlist_service.py` که عامل دیگری روی آن کار می‌کند.
3. **تصمیم دربارهٔ `SignalPerformanceTracker`:** یا به یک endpoint متصل شود (و مصرف‌کنندهٔ واقعی پیدا کند) یا به‌عنوان کد مرده علامت‌گذاری/حذف شود.
4. **افزودن `signal_weight_accuracy` به گارد** D4 هنگام مهاجرت‌دهی آینده.

**ریسک‌ها:** (الف) هم‌زمانی ویرایش عامل‌های دیگر روی `services/*` (در این مرحله مانع نشد ولی باید همچنان رصد شود)؛ (ب) نبود DB آزمایشی که D3/D4 را مسدود می‌کند.

---

## ۱۰. نتیجهٔ نهایی

- علت ریشه‌ای مشترک «DDL زمان‌اجرا در برابر schema مرجع» شناسایی، مستند و برای دو fork بحرانی P2 اصلاح شد، با گاردِ رگرسیون مستقل از DB.
- وضعیت این مرحله: **PARTIAL** — اصلاح‌های D1/D2 موفق و آزمایش‌شده؛ D3 (پوشش migration) و D4 به‌دلیل نبود DB آزمایشی **BLOCKED** هستند و به‌اشتباه PASS اعلام نشدند.
- هیچ ادعایی دربارهٔ «تأیید کلی سامانه» مطرح نمی‌شود؛ این فقط مرحلهٔ ۴ در محدودهٔ DDL/ORM است.
