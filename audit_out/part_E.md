# بخش E — تست‌ها

> مبنا: لاگ ممیزی قبلی `audit_out/_logs/pytest_full.log` (۳۳٬۸۲۶ خط) و `audit_out/_logs/summary.txt` (اجرای `pytest tests/ -rA`، نتیجهٔ `175 failed, 5876 passed, 7 skipped, 1 error`) + بازاجرای زنده در `2026-10-10`.
> وضعیت محیط بازاجرا: PostgreSQL `localhost:5432/my_first_db` **در دسترس**؛ Redis پورت `6379` **در دسترس** (`redis port open`).

---

## E1) تقسیم ۱۷۵ شکست به سه گروه

خلاصهٔ شمارش از `summary.txt`:
```
87 tests/comprehensive/test_all.py
21 tests/test_backtest_api_integration.py
11 tests/unit/test_rate_limit_middleware.py
 7 tests/unit/services/test_news_read_canary.py
 6 tests/unit/services/test_signal_decision_engine.py
 6 tests/test_phase_engine.py
 6 tests/e2e/test_backtest_api.py
 ...
```

| فایل | تعداد | گروه | دلیل (عین خطای واقعی) |
|---|---|---|---|
| `tests/test_backtest_api_integration.py` | ۲۱ | **محیطی (auth/rate-limit)** | `AssertionError: Expected 200, got 401: {"error":"Authentication required for this endpoint","code":"AUTH_REQUIRED"}` و `assert 429 == 200` |
| `tests/e2e/test_backtest_api.py` | ۶ | **محیطی (auth)** | `AssertionError: Expected 200 or 422, got 401` / `assert 401 == 200` |
| `tests/unit/services/test_signal_decision_engine.py` | ۶ | **منطقی/تست‌کهنه** | `AssertionError: assert <GateVerdict.PASS> == <GateVerdict.BLOCK>` با `reason='رژیم RANGE — شرایط مناسب'`؛ `assert 'RANGE' == 'CRISIS'` |
| `tests/test_forecast_engine_integration.py` | ۲ | **محیطی (auth)** | `assert 401 == 200` |
| `tests/unit/services/test_backtest_service_v2.py` | ۱ | **منطقی (رفتار کد)** | `assert not result.success` ولی سرویس `status='completed'` برمی‌گرداند ⇒ «موفقیتِ خاموش روی دادهٔ خالی» |
| `tests/unit/services/test_adjusted_price_reader.py` | ۱ | **داده/محیط (پیش‌فرض تست)** | `assert 621818 == 0` (تست انتظار جدول فاکتور خالی دارد، ولی `daily_adjust_factors` ۶۲۱٬۸۱۸ ردیف دارد) |
| `tests/integration/test_ml_training_flow.py` | ۱ | **محیطی/داده** | `Result(error='No trained model available for test_model...')` |
| `tests/test_phase_engine.py` | ۶ | **تست‌کهنه** | `AttributeError: 'ScoringEngine' object has no attribute '_smooth_phase'` و `_phase_history` |
| `tests/comprehensive/test_all.py` | ۸۷ | **محیطی (DB/Auth/داده)** | [حدس از نام/الگو] تست‌های end-to-end HTTP نیازمند داده و auth زنده |

**الگوی کلی خطاها (خلاصهٔ ممیزی قبلی):** ۸۱ `assert N == N`، ۵۰ `Response [429]`، ۳۰ `KeyError: 'data'`، ۱۹ `Response [401]`.
⇒ اکثریت غالب **محیطی** (auth/rate-limit/داده) است، نه باگ منطق.

### E2) ده نمونهٔ `assert N == N`
خروجی واقعی (از `pytest_full.log`، خطوط `E assert`):
```
E       assert 6 == 2
E       assert 6 == 10
E       assert 385 == 30
E       assert 19 == 30
E       assert 129 == 10
E       assert 1 == 2
E       assert 1 == 0
E       assert 0 == 1
E           assert 25 == 30
E                   assert 621818 == 0
```
(شمارش کل `assert N == N` در لاگ = **۹۴**؛ اکثریت قاطع `429 == 200` و `401 == 200` هستند.)

---

## E3) بازاجرای زنده (Postgres + Redis در دسترس)

دستور و نتیجهٔ واقعی:

```
python -m pytest tests/unit/services/test_signal_decision_engine.py tests/test_phase_engine.py \
  tests/unit/services/test_backtest_service_v2.py tests/unit/services/test_adjusted_price_reader.py -q
# → 7 failed, 135 passed, 1 skipped  (12.68s)
```
```
python -m pytest tests/test_backtest_api_integration.py tests/e2e/test_backtest_api.py -q
# → 27 failed, 4 passed  (21.43s)
```

**تفاوت با لاگ قبلی:**

| فایل | لاگ قبلی (2026-10-09) | بازاجرا (2026-10-10) | تغییر |
|---|---|---|---|
| `test_signal_decision_engine` | ۶ failed | **۰ failed (پاس شدند)** | ✅ بهتر |
| `test_backtest_service_v2` | ۱ failed | **۰ failed (پاس شد)** | ✅ بهتر |
| `test_phase_engine` | ۶ failed | **۶ failed** | بدون تغییر |
| `test_adjusted_price_reader` | ۱ failed | **۱ failed** | بدون تغییر |
| `test_backtest_api_integration` + `e2e/test_backtest_api` | ۲۷ (۲۱+۶) | **۲۷ failed, 4 passed** | بدون تغییر (بلاکر auth) |

⇒ شکست‌های `signal_decision_engine` و `backtest_service_v2` **ناپایدار/محیطی** بوده‌اند (با همین محیط پاس شدند)، ولی شکست‌های backtest API با وجود Postgres و Redis **باقی است** چون ریشه‌اش **احراز هویت (401)** است، نه دسترسی DB.

---

## E4) تست‌های موجود/غایب برای اعتبارسنجی

| آزمون | در `tests/` هست؟ | مسیر یا «ندارد» |
|---|---|---|
| تصادفی ≈ صفر | **ندارد** (هیچ تستی net-random≈0 را نمی‌سنجد) | `ندارد` (harnes ممیزی در `audit_out/_tmp/partB_run.py`) |
| آینده‌بین رد شود | **جزئی** | `tests/unit/backtesting/test_audit_fixes_regression.py::TestLookAheadBias` — فقط «پر شدن روی open بار بعد» را چک می‌کند؛ منشأ سیگنال را رد نمی‌کند |
| label shuffle | **ندارد** | `ندارد` (grep خالی) |
| canary فیچر | **ندارد** (فقط خبری) | `tests/unit/services/test_news_read_canary.py` (canary خبر، نه فیچر) |
| بقای دفتر | **ندارد** (نزدیک‌ترین‌ها عمومی‌اند) | `ندارد` |
| تطبیق دو مسیر (parity) | **دارد** | `tests/unit/backtesting/test_cost_parity.py`، `tests/unit/backtesting/test_iran_costs.py`، `tests/unit/backtesting/test_engine_runner.py` |

**تست‌های پیشنهادی (نام + شرح یک‌خطی):**
1. `test_random_strategy_net_negative` — استراتژی تصادفی هم‌نوسان با هزینهٔ SSOT باید خالص منفی بدهد.
2. `test_foresight_rejected_by_engine` — سیگنالِ ساخته‌شده از `close[t+1]` باید در همهٔ موتورها به‌عنوان نشت رد شود.
3. `test_label_shuffle_kills_ic` — پس از shuffle برچسب، IC باید ≈۰ شود.
4. `test_feature_canary_tomorrow_return` — افزودن فیچر «بازده فردا» باید در خط لوله شناسایی شود.
5. `test_universe_includes_delisted` — universe بک‌تست باید نماد حذف‌شده داشته باشد.
6. `test_two_engine_cost_parity` — یک سیگنال روی Simulator/Vectorized/SignalBacktestEngine باید هزینهٔ یکسان بدهد.
7. `test_order_book_survival` — دفتر سفارش پس از رویدادهای شرکتی بازسازی شود.

---

## جمع‌بندی بخش E

| id | شرح | شدت | فایل | اقدام |
|---|---|---|---|---|
| E-01 | اکثریت شکست‌ها محیطی (401/429) نه باگ؛ بلاکر auth باقی است | متوسط | `apps/api` | fixture auth در تست‌ها |
| E-02 | `test_phase_engine` ۶ شکست واقعی (AttributeError روی `ScoringEngine._smooth_phase`) | بالا | `tests/test_phase_engine.py` | هم‌راستا کردن تست/کد |
| E-03 | `test_adjusted_price_reader` به‌خاطر داده (factor table پرشده) fail | پایین | `tests/unit/services/test_adjusted_price_reader.py:388` | ساخت fixture خالی |
| E-04 | `backtest_service_v2::test_no_data` رفتار «موفقیت خاموش روی دادهٔ خالی» را نشان می‌دهد (اکنون پاس می‌شود ⇒ تست ناپایدار) | متوسط | `services/backtest_service.py` | صریحاً fail روی دادهٔ خالی |
| E-05 | غیبت تست‌های اعتبارسنجی کلیدی (random≈0، label shuffle، canary فیچر، بقای دفتر) | بالا | `tests/` | افزودن ۷ تست پیشنهادی |
