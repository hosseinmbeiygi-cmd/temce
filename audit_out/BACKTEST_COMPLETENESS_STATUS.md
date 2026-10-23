# وضعیت کامل‌بودن کار بک‌تست — پارامترها، تست‌ها، آزمایش‌ها

تاریخ: 2026-10-11 — همه‌چیز از خودِ کد/لاگ استخراج شده، نه از حافظه.

---

## ۰) پاسخ کوتاه

| محور | انجام شده؟ | شاهد |
|---|---|---|
| استخراج **همهٔ** پارامترهای مسیر بک‌تست | **بله (نسخهٔ کامل امروز)** — نسخهٔ اول فقط ۳ ماژول بود و ناقص | `audit_out/_logs/backtest_parameters_full.out` (۷۰۸ خط) + `backtest_parameters_full.json` |
| اجرای **همهٔ** تست‌های مسیر بک‌تست | **بله، با ۲۷ استثنا** | `audit_out/_logs/pytest_backtest_path.log` → ۵۴۸ پاس / ۸ xfail / ۲۷ خطا |
| آزمایش‌ها/کدهای قبلی بک‌تست | **بله، هر ۴ مرحله موجود است** | `audit_out/step1_run.md` … `step4_numbers.md` |
| تست رگرسیون باگ‌های بحرانی صندوق | **بله اما باگ‌ها رفع نشده‌اند** (xfail) | `tests/unit/test_gold_silver_funds_critical_regressions.py` |

> نکتهٔ صریح: تست‌های رگرسیون صندوق **قرمزِ برنامه‌ریزی‌شده** هستند (`xfail`)، یعنی باگ‌های GS-01…GS-05 **هنوز در کد باقی‌اند**؛ فایل تست فقط آن‌ها را قفل و بازتولید می‌کند. هیچ‌کدام رفع نشده است.

---

## ۱) استخراج پارامترها

### ۱-۱) نسخهٔ اول — ناقص بود (فقط بک‌تست طلا)

`audit_out/_tmp/extract_backtest_parameters.py` → `audit_out/_logs/backtest_parameters_extract.out`

سه ماژول، ۱۹ تابع + ۵ dataclass:

- `src/gold_desk/backtest.py` → `run_backtest(symbol='IR_COIN_EMAMI', days=90, bubble_threshold=8.0)`
- `src/gold_desk/backtest_real.py` → `run_real_backtest(symbol='IR_COIN_EMAMI', days=180, initial_capital=100000000.0)` + ۳ استراتژی RSI/MA/Bubble
- `src/gold_desk/backtest_runner.py` → `run_strategy_backtest(symbol='IR_COIN_EMAMI', days=90, tranches_pct=(0.3,0.4,0.3), bubble_trigger=5.0, initial_capital=100000000.0)`

پارامترهای بی‌اثر کشف‌شده (شاهد کد):

- `strategy_rsi_oversold(..., dates)` → **۰ ارجاع** در بدنه
- `strategy_ma_crossover(..., dates)` → **۰ ارجاع** در بدنه
- `strategy_bubble_threshold(..., dates)` → ۱ ارجاع
- `_compute_metrics(..., all_prices)` → ۴ ارجاع (اثر دارد)

تناقض پیش‌فرض‌های هم‌نام: `run_backtest.bubble_threshold=8.0` در برابر `run_strategy_backtest.bubble_trigger=5.0`؛ و `days` ۹۰ در برابر ۱۸۰.

### ۱-۲) نسخهٔ کامل امروز — کل مسیر بک‌تست

`audit_out/_tmp/extract_backtest_parameters_full.py` (AST، بدون import، بدون DB) → `audit_out/_logs/backtest_parameters_full.out` + `backtest_parameters_full.json` (۵۰۴ KB)

| گروه | فایل |
|---|---|
| `backtesting/**` | ۲۹۸ |
| `domain/backtest/**` | ۶ |
| `services/backtest_framework.py`, `backtest_service.py`, `signal_backtest_engine.py`, `walk_forward_validator.py` | ۴ |
| `src/gold_desk/backtest*.py` | ۳ |
| **جمع** | **۳۱۱ فایل** |

- توابع: **۱٬۸۶۸** — از این‌ها **۴۵۹ تابع پارامتر پیش‌فرض‌دار** (پارامتر قابل‌تنظیم)
- dataclass ورودی/خروجی: **۱۸۶**
- ثابت‌های عددی نام‌دار سطح ماژول: **۱۰** (مثل `DEFAULT_MAX_CHANGE_PCT = 5.0`، `DEFAULT_ADV_WINDOW_DAYS = 30`، `ANNUAL_TRADING_DAYS = 250`)
- ناسازگاری پیش‌فرض هم‌نام: **۲۱ مورد**، از جمله:
  - `commission_pct`: `backtesting/commission.py:15(0.0035)` در برابر `backtesting/costs/transaction_cost_model.py:33(0.0003)` و `portfolio/ledger.py:87(0.0003)` — **۱۰ برابر اختلاف**
  - `tax_pct`: `0.005` در برابر `0.0005` — **۱۰ برابر اختلاف**
  - `initial_capital`: `1000000000` (abm/engine/ledger) در برابر `1000000.0` (`domain/backtest/entities.py:30`)
  - `slippage_bps`: `10.0` در برابر `None` در سه موتور
  - `entry_z`: `1.0` در برابر `2.0`؛ `multiplier`: `1.3` در برابر `2.0`
  - `run.capital`: `services/backtest_framework.py:320(1000000000.0)` در برابر `services/backtest_service.py:117(None)`

**وضعیت:** استخراج کامل است و خروجی خام موجود. تنها چیزی که نمانده، تبدیل این خروجی به یک سند تصمیم‌محور (کدام تناقض‌ها باگ‌اند) است.

---

## ۲) تست‌ها

### ۲-۱) زیرمجموعهٔ مسیر بک‌تست (امروز، کامل)

دستور:

```bash
venv/Scripts/python.exe -m pytest tests/unit/backtesting tests/gold_desk \
  tests/unit/services/test_backtest_service.py tests/unit/services/test_backtest_service_v2.py \
  tests/unit/services/test_backtest_framework.py tests/unit/domain/test_backtest_rules.py \
  tests/e2e/test_backtest_api.py tests/test_backtest.py tests/test_backtest_api_integration.py \
  tests/unit/test_gold_silver_funds_critical_regressions.py -q -p no:randomly
```

نتیجهٔ واقعی (عین خط پایان لاگ):

```
27 failed, 548 passed, 8 xfailed, 2 warnings in 21.12s
```

**علت هر ۲۷ خطا یکسان است: `401 Unauthorized`** — میدل‌ور احراز هویت API، و تست‌ها کلید نمی‌فرستند:

```
[warning] Unauthenticated access to sensitive endpoint: POST /api/v1/backtests/run
[info   ] POST /api/v1/backtests/run -> 401
E   AssertionError: Expected 200, got 401
```

خطاها در `tests/e2e/test_backtest_api.py` (۶) و `tests/test_backtest_api_integration.py` (۲۱) هستند — **مربوط به کار صندوق/طلا نیستند و رفع نشده‌اند.**

### ۲-۲) تست رگرسیون باگ‌های بحرانی (فایل جدید)

- اجرای عادی: `1 passed, 8 xfailed in 3.08s`
- اجرای `--runxfail` (اثبات بازتولید): `8 failed, 1 passed in 2.06s`

نگاشت تست ↔ باگ:

| شناسه | موضوع | وضعیت باگ |
|---|---|---|
| GS-01 | `nav_checker` ستون ناموجود در ORM → هیچ صندوقی برنمی‌گردد | **باز** |
| GS-02 | سقف امتیاز (۵۳) < آستانهٔ YELLOW (۵۵) | **باز** |
| GS-03 | تقویم میلادی در برابر ستون تاریخ شمسی در ۳ fetcher بک‌تست طلا | **باز** (به ازای هر سه تابع) |
| GS-04 | NAV در مسیر `holdings_missing` بدهی را دو بار کم می‌کند | **باز** |
| GS-05 | `IR_GOLD_MELTED` گرم valuation می‌شود ولی قیمت مثقالی است | **باز** (شاهد: `bubble_pct=312.65` در برابر سقف مجاز `100.0`) |

### ۲-۳) آزمون کامل مخزن (زمینه، نه امروز)

`audit_out/_logs/pytest_full.log` → `175 failed, 5876 passed, 7 skipped, 1 error in 3875.57s (1:04:35)`

یعنی ۲۷ خطای امروز **زیرمجموعهٔ همان ۱۷۵ خطای پایه** است؛ کار صندوق، خطای جدیدی اضافه نکرد.

---

## ۳) آزمایش‌ها و کدهای کار بک‌تست (از قبل انجام شده)

| فایل | نقش |
|---|---|
| `audit_out/step1_run.md` | مسیر واقعی `ml_signal`: ۵ نماد واقعی، `2024-01-01`…`2024-12-29`، سرمایه `1e9`، منبع `brsapi_historical_daily` |
| `audit_out/step2_tests.md` | ۴ آزمون اعتبار (تصادفی / آینده‌بین / شیفت یک‌روزه / label shuffle) + اجرای کل تست‌ها |
| `audit_out/step2_robustness.md` | آزمایش‌های A/B/C/D/E + baseline buy-and-hold |
| `audit_out/step3_criticals.md` | ۹ مورد بحرانی C1…C9 |
| `audit_out/step4_numbers.md` | اعداد نهایی خام |
| `audit_out/equity_A..D.csv`, `fills_B.csv` | منحنی اکوییتی و پر‌ها |
| `audit_out/_tmp/step1_run.py`, `step2_real_window.py`, `partA..partG_run.py`, `validity_harness.py` | اسکریپت‌های اجرا |
| `audit_out/_tmp/opencode/step1.py`, `step2.py`, `bh.py` + `*_raw.json` | اجرای اصلی و خروجی خام |
| `audit_out/_logs/step1_run.log`, `step2_real_window.log`, `partB.log`, `summary.txt` | لاگ‌ها |
| `audit_out/_proposed_tests/test_vectorized_signal_origin.py` | تست پیشنهادی (اجرا نشده) |

نتیجه‌های کلیدی همان کار (تکرار برای زمینه):

1. مسیر `ml_signal` همیشه `0` معامله می‌دهد چون مدل ML وجود ندارد (`No ML model available`, fallback صفر).
2. استراتژی تصادفی با هزینه **سودآور** بود (`28.2465%` با `total_cost=21079467.9`) → سود ≠ مهارت.
3. buy-and-hold (`36.6254%`) از همهٔ استراتژی‌ها، حتی آینده‌بینی کامل (`34.1354%`)، جلوتر بود.
4. `mdd_pct = 38.73` در هر ۴ آزمایش با `trades` از ۲۹ تا ۹۳ یکسان ماند.
5. ADV در هر اجرا fallback شد: `No ADV resolved for 'خودرو'`.

---

## ۴) چیزهایی که **انجام نشده**

1. **رفع باگ‌های GS-01…GS-05** — تست‌ها نوشته و بازتولید شدند، اما کد اصلاح نشد.
2. **۲۷ تست API** با `401` قرمزند و fixture/کلید احراز هویت برایشان اضافه نشده.
3. **سند تصمیم‌محور از ۲۱ تناقض پیش‌فرض** — خروجی خام هست، داوری «کدام باگ است» انجام نشده. سه مورد با اختلاف ۱۰× (`commission_pct`، `tax_pct`) و اختلاف بازار-سرمایهٔ `initial_capital` مشکوک‌ترین‌ها هستند.
4. **اجرای مجدد آزمایش‌های مرحله ۱/۲ بک‌تست** در این نوبت انجام نشد؛ فقط لاگ‌ها و خروجی‌های موجود بازخوانی و ارجاع شد.
5. `audit_out/_proposed_tests/test_vectorized_signal_origin.py` هنوز اجرا نشده.

---

## ۵) دستور بازتولید همه‌چیز

```bash
# ۱) استخراج پارامترها (نسخهٔ کامل، کل مسیر بک‌تست)
venv/Scripts/python.exe audit_out/_tmp/extract_backtest_parameters_full.py

# ۲) تست‌های مسیر بک‌تست + رگرسیون صندوق
venv/Scripts/python.exe -m pytest tests/unit/backtesting tests/gold_desk \
  tests/unit/services/test_backtest_service.py tests/unit/services/test_backtest_service_v2.py \
  tests/unit/services/test_backtest_framework.py tests/unit/domain/test_backtest_rules.py \
  tests/e2e/test_backtest_api.py tests/test_backtest.py tests/test_backtest_api_integration.py \
  tests/unit/test_gold_silver_funds_critical_regressions.py -q -p no:randomly

# ۳) اثبات بازتولید باگ‌های صندوق
venv/Scripts/python.exe -m pytest tests/unit/test_gold_silver_funds_critical_regressions.py -q --runxfail
```
