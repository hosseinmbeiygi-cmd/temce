# step2 — چهار آزمون اعتبار روی کد موجود

> تاریخ اجرا: 2026-10-09 | ماشین: Windows (bash) | مفسر: `Python 3.11.9` (venv پروژه)
> pytest: `9.1.1` | numpy `1.26.4` | pandas `2.3.3` | scikit-learn `1.9.0` | scipy `1.15.3`

---

## ۰) پیش‌نیاز الزامی: `audit_out/step1_run.md` — **ندیدم**

> **به‌روزرسانی بعدی:** `audit_out/step1_run.md` ساخته شد و بازه/دستور مرحله ۱ را قطعی کرد (`2024-01-01..2024-12-29` میلادی = `1402-10-11..1403-10-09` جلالی، ۵ نماد، `strategy_type="ml_signal"`). بخش ۵ همین سند آزمون‌های الف/ب/ج را روی همان بازهٔ واقعی دوباره اجرا می‌کند و جای نتایج مصنوعی بخش‌های ۲ و ۳ می‌نشیند.

- `audit_out/` **وجود نداشت**؛ با `ls -la audit_out` هیچ خروجی نیامد و خود پوشه پیدا نشد.
- `find . -maxdepth 3 -iname "step1*"` فقط یک نتیجه داد: `./scripts/step1_select_symbols.py` (نامش مشابه است ولی این فایلِ درخواستی نیست).
- پس **دستور و بازه اجرای مرحله ۱ در دسترس نبود** و از آن استفاده نشد.
- در نتیجه، برای آزمون‌های الف/ب/ج/د از داده مصنوعیِ seed‌دار روی یک هارنس موقت استفاده شد و برای pytest کل بازه، کل `tests/` اجرا شد. **این بازه، بازه‌ی مرحله ۱ نیست.**

## ۰.۱) فایل‌های خروجی این مرحله

| فایل | نقش |
|---|---|
| `audit_out/_tmp/validity_harness.py` | هارنس موقت (کپی/جدید) برای چهار آزمون — روی داده مصنوعی |
| `audit_out/_logs/validity_harness.out` | خروجی JSON هارنس |
| `audit_out/_logs/pytest_full.log` | لاگ کامل اجرای `pytest tests/` |
| `audit_out/_logs/summary.txt` | بخش «short test summary» (لیست ۱۷۵ FAILED و ۷ SKIPPED) |

هیچ فایل موجودی تغییر یا حذف نشد؛ فقط فایل/پوشه‌های جدید بالا ساخته شد.

---

## ۱) خلاصه

| آزمون | از قبل در `tests/` بود؟ | مسیر | نتیجه واقعی (عدد) | پاس/رد مطابق انتظارِ داده‌شده |
|---|---|---|---|---|
| الف) استراتژی تصادفی (بدون هزینه / با هزینه) | خیر | — | بدون هزینه `-12.36%` ؛ با هزینه `-85.46%` | **جزئی** (هزینه: مطابق؛ بدون‌هزینه: بازده ≈۰ نشد چون سری drift داشت) |
| ب) استراتژی آینده‌بین | بله (آزمون leakage مرتبط) | `tests/unit/backtesting/test_audit_fixes_regression.py::TestLookAheadBias` (خ.: 116) | آزمون leakage **پاس** شد؛ اما استراتژی آینده‌بین توسط موتور vectorized **رد نشد**: `+829.58%` | **رد** (نشت در مسیر vectorized قابل‌تشخیص نبود) |
| ج) شیفت داده یک روز | خیر | — | baseline `-85.46%` ؛ `+1` → `-85.68%` ؛ `-1` → `-80.85%` | **نامعین** (اختلاف‌ها در حد نویزِ استراتژی تصادفی) |
| د) label shuffle روی ML | خیر (نزدیک‌ترین: shuffle بازده و ML-002) | `tests/unit/services/test_backtest_framework.py::TestMonteCarloEngine` (خ.: 121) و `tests/unit/test_audit_fixes_batch2.py::TestTimeSeriesCV` (خ.: 66) | IC واقعی `0.5199` → IC پس از shuffle (میانگین ۳۰ بار) `0.0001` | **IC: پاس / سود خالص: رد** (net ≈ 0 نشد) |

---

## ۲) جزئیات هر آزمون

### الف) استراتژی تصادفی — یک‌بار بدون هزینه، یک‌بار با هزینه

**از قبل در `tests/`؟** [خوانده‌شده] نه. جست‌وجوی `random.*strateg|strateg.*random` در `tests/` تنها به `tests/benchmark_signal_quality.py` رسید که یک تولیدکننده سیگنال mock است (خطوط ۴۱۴–۴۴۶: `random.seed(42)`، `random.choice(markets)`)، نه آزمون اعتبار استراتژی تصادفی.

**اجرا:** [خوانده‌شده+اجراشده] هارنس موقت `audit_out/_tmp/validity_harness.py`.
موتور استفاده‌شده موجود است؛ نگاشت سیگنال→بازده در کد:

```python
# services/backtest_framework.py:49
strategy_returns.append(signals[i - 1] * returns[i])
```

`VectorizedBacktest.run` هیچ پارامتر هزینه ندارد (بدون هزینه اجرا می‌شود). نرخ هزینه از ماژول کانونیک:

```python
# domain/trading/iran_costs.py:8-10
BROKER_PCT = 0.004
CLEARING_FEE_PCT = 0.00085
SELL_TAX_PCT = 0.005
```
→ خرید `0.00485` ، فروش `0.00985`.

**داده:** random walk، ۵۰۰ کندل، `seed=42`, `vol=0.012`. سیگنال تصادفی long/flat با `seed=7` (۲۴۳ گذار).

| سنجه | بدون هزینه | با هزینه (نرخ بالا) |
|---|---|---|
| total_return_pct | `-12.3606` | `-85.4625` |
| sharpe | `-0.4233` | `-6.3911` |
| max_drawdown_pct | `20.1993` | `85.5730` |
| final_equity | `876,393,833.33` | `145,374,836.29` |

- خروجی موتور (`VectorizedBacktest`) برای حالت بدون‌هزینه: `total_return_pct=-12.36`, `sharpe_ratio=-0.42`, `max_drawdown_pct=20.2`, `final_equity=876393833.0` (مطابق هارنس).
- برای زمینه: بازده buy&hold همان سری = `-10.9091%`.
- واریانت long/short بازار-خنثی: بازده ناخالص `+24.0472%`, sharpe `0.6865` (با σ روزانه ۱.۲٪ روی ۵۰۰ روز، این در حد نویز حول صفر است).

**عدد و پاس/رد:** بدون هزینه `-12.36%` (انتظار «≈۰» → **مطابق نشد**)، با هزینه `-85.46%` (انتظار «منفی» → **مطابق**).

---

### ب) استراتژی آینده‌بین

**از قبل در `tests/`؟** [خوانده‌شده] یک آزمون مرتبط با leakage وجود دارد:

```
tests/unit/backtesting/test_audit_fixes_regression.py:113  # ── BT-009: look-ahead bias ──
tests/unit/backtesting/test_audit_fixes_regression.py:116  class TestLookAheadBias:
tests/unit/backtesting/test_audit_fixes_regression.py:117  def test_order_executes_on_next_bar_open(self):
tests/unit/backtesting/test_audit_fixes_regression.py:154  assert fill_price >= 12.0, f"filled at {fill_price} — look-ahead not fixed"
tests/unit/backtesting/test_audit_fixes_regression.py:156  def test_last_bar_order_never_fills(self):
```

**اجرای همان آزمون:** [خوانده‌شده+اجراشده]

```
python -m pytest tests/unit/backtesting/test_audit_fixes_regression.py::TestLookAheadBias \
  tests/unit/services/test_backtest_framework.py::TestMonteCarloEngine \
  tests/unit/test_audit_fixes_batch2.py::TestTimeSeriesCV -q -p no:cacheprovider
# → 8 passed in 6.57s   (TestLookAheadBias پاس شد)
```

این آزمون فقط بررسی می‌کند که در موتور رویدادمحور `BacktestEngine` سفارشِ بارِ `t` روی open بارِ `t+1` پر شود — **یک استراتژی که از دادهٔ آینده استفاده می‌کند را رد نمی‌کند.**

**اجرای استراتژی آینده‌بین:** [خوانده‌شده+اجراشده] هارنس — سیگنالِ بار i از `price[i+1]` ساخته شد (یعنی از آینده).

| سنجه | موتور vectorized |
|---|---|
| total_return_pct | `+829.58` |
| sharpe_ratio | `10.54` |
| max_drawdown_pct | `0.0` |
| final_equity | `9,295,823,479` |
| همان با هزینه‌های TSE | `+85.191%` (sharpe `2.84`) |

**عدد و پاس/رد:** آزمون leakage موجود **پاس** می‌شود، ولی استراتژی آینده‌بین در مسیر `VectorizedBacktest` با `+829.58%` **رد نمی‌شود** → **رد**.

**نشت چطور قابل‌تشخیص است / نیست:**
- در مسیر **رویدادمحور** (`BacktestEngine`) قابل‌تشخیص است (آزمون BT-009 این را تضمین می‌کند).
- در مسیر **vectorized** قابل‌تشخیص نیست: `services/backtest_framework.py:49` سیگنالِ `i-1` را روی بازدهِ `i` می‌گذارد و هیچ بررسی‌ای بر منشأ سیگنال ندارد.

---

### ج) شیفت داده یک روز به جلو

**از قبل در `tests/`؟** [خوانده‌شده] نه. تنها ارجاع به `shift(` در `tests/unit/backtesting/test_vectorized_engine.py:20` است:
```python
"price_open": close.shift(1).fillna(close.iloc[0]),
```
که فقط برای ساخت ستون open است، نه آزمون شیفت داده.

**اجرا:** [خوانده‌شده+اجراشده] هارنس — همان سیگنال‌های تصادفی، ولی سری قیمت یک روز جابه‌جا شد.

| حالت | total_return_pct | sharpe | max_drawdown_pct |
|---|---|---|---|
| baseline | `-85.4625` | `-6.3911` | `85.5730` |
| `prices_shifted_plus1` (ورودی یک روز دیرتر) | `-85.6845` | `-6.3576` | `85.7933` |
| `prices_shifted_minus1` (ورودی یک روز زودتر) | `-80.8471` | `-5.5011` | `81.2298` |

**عدد و پاس/رد:** با `+1` عملکرد بهتر نشد (`-85.68` بدتر از `-85.46`) → مطابق انتظار. با `-1` عملکرد بهتر شد (`-80.85` در برابر `-85.46`، حدود `+4.6` واحد درصد) → **مغایر با انتظار**. اما چون سیگنال تصادفی است و اختلاف‌ها در حد نویزند، این آزمون با هارنس فعلی **نامعین** است (تشخیص «بهتر شدن» به سیگنالی با edge واقعی نیاز دارد که در این harness وجود ندارد).

---

### د) label shuffle روی مدل ML

**از قبل در `tests/`؟** [خوانده‌شده] آزمون اختصاصیِ «label shuffle روی مدل ML» **ندارد**. نزدیک‌ترین‌ها:
- `tests/unit/services/test_backtest_framework.py:121` → `test_shuffle_test_returns_p_value` که **بازده/equity** را shuffle می‌کند، نه برچسب مدل:
  ```
  tests/unit/services/test_backtest_framework.py:121    def test_shuffle_test_returns_p_value(self) -> None:
  ```
  (اجرا شد → پاس)
- `tests/unit/test_audit_fixes_batch2.py:66` → `TestTimeSeriesCV` / `test_default_cv_is_not_shuffled_kfold` با `assert cv.allow_shuffle is False` (اجرا شد → پاس).

**اجرا:** [خوانده‌شده+اجراشده] هارنس — یک فاکتور پیش‌بین واقعی + ۴ ستون نویز، برچسب = بازده روزانه؛ مدل `sklearn.linear_model.Ridge` (مدلِ خودِ پروژه نیست؛ فقط هارنس).

| حالت | IC (Spearman) | gross | net (پس از هزینه TSE) |
|---|---|---|---|
| برچسب واقعی | `0.5199` | `+84.7462%` | `-97.8887%` (۲۹۹ flip) |
| برچسب shuffle‌شده (میانگین ۳۰ بار) | `0.0001` (std `0.0467`) | `+3.8840%` | `-96.7933%` |

**عدد و پاس/رد:**
- IC: `0.5199 → 0.0001` → **≈۰ شد → پاس**.
- سود خالص: `-97.89% → -96.79%` → **≈۰ نشد → رد** (کشش هزینه روی ۲۹۹ flip غالب است). این هارنس مدل واقعی پروژه نیست و «سود خالص» را روی داده مصنوعی و با مدل long/short محاسبه می‌کند.

---

## ۳) اجرای کل `pytest tests/`

[خوانده‌شده+اجراشده]
```
python -m pytest tests/ -q -p no:cacheprovider -rA --no-header > audit_out/_logs/pytest_full.log 2>&1
```
(تنظیمات پروژه: `pyproject.toml:129` → `testpaths=["tests"]`, `addopts=["--capture=no"]`, `asyncio_mode="auto"`)

### شمار نهایی (خط آخر لاگ)
```
175 failed, 5876 passed, 7 skipped, 50 warnings, 1 error in 3875.57s (1:04:35)
EXIT=1
```
| | تعداد |
|---|---|
| passed | `5876` |
| failed | `175` |
| skipped | `7` |
| error | `1` |

### تنها error آزمون
```
ERROR tests/test_all_pages.py::test_page
# ERROR at setup of test_page  (tests/test_all_pages.py:77 → def test_page(path, name):)
E       fixture 'path' not found
```

### شکست‌ها بر اساس فایل (۱۷۵ مورد)
| تعداد | فایل |
|---|---|
| 87 | `tests/comprehensive/test_all.py` |
| 21 | `tests/test_backtest_api_integration.py` |
| 11 | `tests/unit/test_rate_limit_middleware.py` |
| 7 | `tests/unit/services/test_news_read_canary.py` |
| 6 | `tests/unit/services/test_signal_decision_engine.py` |
| 6 | `tests/test_phase_engine.py` |
| 6 | `tests/e2e/test_backtest_api.py` |
| 4 | `tests/unit/test_api_inbound_simulation.py` |
| 3 | `tests/unit/test_signals_rate_limit.py` |
| 3 | `tests/unit/test_brsapi_budget_governor.py` |
| 2 | `tests/unit/test_confirmed_runtime_fixes.py` |
| 2 | `tests/unit/test_brsapi_sync_status.py` |
| 2 | `tests/unit/services/test_news_items_read_path.py` |
| 2 | `tests/test_forecast_engine_integration.py` |
| 1 | `tests/unit/test_rbac.py` |
| 1 | `tests/unit/test_precompute_worker_callbacks.py` |
| 1 | `tests/unit/test_funds_api.py` |
| 1 | `tests/unit/test_critical_runtime_fixes.py` |
| 1 | `tests/unit/test_brsapi_usage_simulator.py` |
| 1 | `tests/unit/test_api_v6_hardening.py` |
| 1 | `tests/unit/services/test_fund_discovery.py` |
| 1 | `tests/unit/services/test_backtest_service_v2.py` |
| 1 | `tests/unit/services/test_adjusted_price_reader.py` |
| 1 | `tests/unit/scripts/test_build_feature_store.py` |
| 1 | `tests/test_raw.py` |
| 1 | `tests/integration/test_screener_endpoint.py` |
| 1 | `tests/integration/test_ml_training_flow.py` |

### الگوی خطاها (خلاصه از بخش FAILURES)
| تعداد | نوع پیام |
|---|---|
| 81 | `assert N == N` (ناسازگاری مقدار) |
| 50 | `Response [429 Too Many Requests]` |
| 30 | `KeyError: 'data'` |
| 19 | `Response [401 Unauthorized]` |
| 3 | `brsapi.rate_limiter.RateLimitExhaustedError: BrsApi daily budget exhausted` |
| 2 | `AttributeError: 'ScoringEngine' object has no attribute '_smooth_phase'` |
| 1 | `ModuleNotFoundError: No module named 'database_handler'` |
| 1 | `TypeError: BooleanDefaultFalse.__init__() got an unexpected keyword argument '_create_events'` |
| … | بقیه تک‌موردی |

لیست کامل ۱۷۵ node-id و ۷ skip در `audit_out/_logs/summary.txt` و ترِیس‌های کامل در `audit_out/_logs/pytest_full.log` موجود است.

### skip‌ها (۷ مورد)
```
tests/test_kiss.py:4: kiss_agent_framework is not installed
tests/integration/test_celery_chain_broker.py:168,188,257,273: Redis broker not reachable at redis://localhost:6379/0 — skipping Celery broker integration
tests/test_db.py:32: Database unavailable: password authentication failed for user "Iran"
tests/unit/services/test_adjusted_price_reader.py:344: factor table populated; needs the empty state
```

---

## ۴) محدودیت‌ها و آنچه اجرا نشد

1. ~~**`audit_out/step1_run.md` نبود** → دستور/بازه مرحله ۱ در دسترس نبود (بخش ۰).~~ **رفع شد** — بخش ۵ آزمون‌های الف/ب/ج را روی بازهٔ واقعی مرحله ۱ دوباره اجرا کرد.
2. آزمون‌های الف/ب/ج/د **در `tests/` وجود نداشتند**؛ اجراهای بخش‌های ۲ و ۳ روی هارنس موقت با داده مصنوعیِ seed‌دار بود. (الف/ب/ج در بخش ۵ روی داده و بازهٔ واقعی مرحله ۱ دوباره اجرا شدند؛ د همچنان فقط روی داده مصنوعی اجرا شده است.)
3. آزمون د **مدل واقعی پروژه را بارگذاری نکرد** (نیازمند DB/آرتیفکت مدل بود)؛ با `sklearn.Ridge` روی داده مصنوعی اجرا شد و در بخش ۵ روی داده واقعی اجرا **نشد**.
4. اجرای کل `tests/` به یک PostgreSQL محلی وصل شد (`Database connected: localhost:5432/my_first_db`) و Redis در دسترس نبود؛ ۴۰۰+/۵۰ خطای ۴۲۹/۴۰۱ نتیجه همین محیط است، نه لزوماً باگ کد.
5. تست‌های نیازمند DB ممکن است در CI (با سرویس postgres) نتیجه متفاوت بدهند.

---

## ۵) به‌روزرسانی — اجرای دوبارهٔ آزمون‌های الف/ب/ج روی بازهٔ واقعی مرحله ۱

> `audit_out/step1_run.md` اکنون وجود دارد و بازهٔ واقعی را قطعی کرده است، پس سه آزمون وابسته به قیمت (الف، ب، ج) روی همان داده اجرا شدند. آزمون د (label shuffle) قابل اجرا نبود چون به مدل آموزش‌دیده نیاز دارد و مرحله ۱ ثابت کرد چنین مدلی وجود ندارد.
>
> - اسکریپت: `audit_out/_tmp/step2_real_window.py` | خروجی JSON: `audit_out/_logs/step2_real_window.out` | لاگ: `audit_out/_logs/step2_real_window.log`
> - بازه: `2024-01-01..2024-12-29` میلادی = `1402-10-11..1403-10-09` جلالی (همان شرط `date >= :start AND date <= :end` در `services/backtest_service.py:495-505`)
> - تعداد کندل هر نماد (منطبق بر عین لاگ‌های مرحله ۱: `Loaded 238/239 bars ...`): وپترو ۲۳۸، وساخت ۲۳۹، خودرو ۲۳۹، وسپه ۲۳۸، خبهمن ۲۳۹
> - نرخ هزینه از SSOT: خرید `0.00485`، فروش `0.009850` (`domain/trading/iran_costs.py`)

### ۵-۱) آزمون الف — استراتژی تصادفی (long/flat) روی قیمت واقعی

| نماد | کندل | Buy&Hold | ناخالص | خالص با هزینه TSE | گذار |
|---|---|---|---|---|---|
| وپترو | 238 | +45.12 | +48.14 | **−39.48** | 121 |
| وساخت | 239 | −28.37 | +1.97 | **−58.64** | 122 |
| خودرو | 239 | +36.63 | +19.27 | **−51.58** | 122 |
| وسپه | 238 | +18.20 | +17.20 | **−52.13** | 121 |
| خبهمن | 239 | −2.53 | +14.01 | **−53.64** | 122 |
| میانگین | — | +13.81 | +20.12 | **−51.09** | — |

**عدد و پاس/رد:** با هزینه، هر ۵ نماد منفی (`−39.5%` تا `−58.6%`) → **مطابق انتظار** («استراتژی تصادفی با هزینه سودآور نباشد»). بدون هزینه، میانگین **+۲۰.۱٪** شد نه ≈۰ → **مطابق نشد**: سیگنال تصادفیِ long/flat روی بازهٔ صعودی فقط بتا (قرار گرفتن در بازار) است، نه لبه؛ Buy&Hold همان ۵ نماد میانگین **+۱۳.۸٪** بوده است. یعنی «سود ناخالص مثبت» شاهدِ edge نیست.

### ۵-۲) آزمون ب — استراتژی آینده‌بین روی قیمت واقعی

| نماد | ناخالص (موتور) | خالص با هزینه | Sharpe موتور |
|---|---|---|---|
| وپترو | +634.71 | +288.60 | 10.61 |
| وساخت | +771.72 | +387.16 | 10.26 |
| خودرو | +658.24 | +304.12 | 10.54 |
| وسپه | +263.85 | +127.43 | 8.97 |
| خبهمن | +439.79 | +205.25 | 9.13 |
| میانگین | **+553.66** | +262.51 | — |

**عدد و پاس/رد:** سیگنالی که از `price[i+1]` ساخته شده در مسیر vectorized **رد نمی‌شود** و سود بزرگ می‌سازد → **رد** (همان نتیجهٔ داده مصنوعی، این بار روی داده واقعی). نشت فقط در مسیر رویدادمحور (`BacktestEngine`، آزمون BT-009) قابل تشخیص است.

### ۵-۳) آزمون ج — شیفت یک‌روزهٔ داده (روی قیمت واقعی، با هزینه)

| نماد | baseline | ورودی +۱ روز | ورودی −۱ روز |
|---|---|---|---|
| وپترو | −39.48 | −41.90 | −50.85 |
| وساخت | −58.64 | −56.99 | −66.64 |
| خودرو | −51.58 | −35.82 | −57.07 |
| وسپه | −52.13 | −54.08 | −60.50 |
| خبهمن | −53.64 | −57.04 | −64.30 |

**عدد و پاس/رد:** شیفت `+1` در ۲ از ۵ نماد «بهتر» شد و شیفت `−1` در **۰ از ۵** → هیچ جهتی به‌طور سیستماتیک سود نمی‌سازد، اما چون دامنهٔ اختلاف‌ها در حد نویزِ یک استراتژی تصادفی است، این آزمون با این هارنس **نامعین** می‌ماند.

### ۵-۴) آزمون د — اجرا نشد

`d_label_shuffle.run = false` در `audit_out/_logs/step2_real_window.out`؛ دلیل: نیازمند یک مدل آموزش‌دیده است و مرحله ۱ ثابت کرد `ArtifactManager` هیچ مدلی ندارد (`No ML model available for <symbol>, using zero predictions`). این نبودِ مدل، خودْ یافتهٔ اصلی است، نه محدودیت ابزار.

### ۵-۵) نتیجهٔ کل آزمون‌های اعتبار (روی داده واقعی)

| آزمون | انتظار | نتیجه واقعی | حکم |
|---|---|---|---|
| الف | تصادفی با هزینه سودآور نباشد | هر ۵ نماد منفی (میانگین −۵۱.۱٪) | ✅ |
| ب | استراتژی آینده‌بین رد شود | پذیرفته شد؛ میانگین +۵۵۳.۷٪ ناخالص | ❌ |
| ج | شیفت عملکرد را بهتر نکند | ۲/۵ بهتر (در حد نویز) | ⚪ نامعین |
| د | سود پس از shuffle ≈ صفر | اجرا نشد (مدل نیست) | ⚪ |
