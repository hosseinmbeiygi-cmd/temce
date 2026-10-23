# بخش C — هشت منبع بی‌اعتباری (جدول کامل)

> هر ردیف چهار ستون: «وجود دارد؟ | شدت | شواهد (مسیر:خط + عین سطر) | راه‌حل».
> برچسب‌ها: [خوانده‌شده] / [خوانده‌شده+اجراشده] / [حدس از نام].
> ابزارها: `audit_out/_tmp/partC_db.py` (SELECT فقط)، خواندن کد.

---

## C1) قیمت اجرا: آیا سفارش با قیمت همان کندلِ تصمیم پر می‌شود؟

**وجود دارد؟ بله — و بین موتورها ناسازگار.** | شدت: بحرانی

| موتور | پرکردن | شواهد |
|---|---|---|
| `BacktestSimulator` | **همان کندل، روی close** | `simulator.py`: `orders = strategy.on_bar(bar)` سپس `fill = self.broker.submit_order_sync(order)`؛ و `ml_signal_strategy.py` قیمت سفارش را `price = bar.get("close", 0)` می‌گذارد. ⇒ سفارش بار `t` روی `close[t]` پر می‌شود. [خوانده‌شده+اجراشده: `fills_B.csv`] |
| `BacktestEngine` (رویدادمحور) | **کندل بعدی، روی open** | `backtesting/engine/backtest_engine.py`: کامنت `Orders queue and are executed on bar t + 1 at that bar's open price` و کد `fill = self.execution.execute(order, ..., fill_price=bar["open"])` |
| `VectorizedBacktest` | غیرمستقیم: `signals[i-1] * returns[i]` ⇒ موقعیت از `t-1` روی بازده `t` | `services/backtest_framework.py`: `strategy_returns.append(signals[i - 1] * returns[i])` |
| `SignalBacktestEngine` | روز بعد: `entry = hist_data[0].get("open", ...)` | `services/signal_backtest_engine.py` |

**راه‌حل:** یک قاعدهٔ اجرای واحد (همه روی open کندل `t+1`) انتخاب و در همهٔ موتورها اعمال شود؛ آزمون: برای یک استراتژی ثابت، `fill_price` در دو مسیر برابر شود.

---

## C2) ثابت‌های بازار در کد

**وجود دارد؟ بله، با نرخ‌های SSOT ولی «زمان‌دار» فقط در کد مرده.** | شدت: بالا

| مورد | مقدار | مسیر:خط (عین سطر) | زمان‌دار؟ |
|---|---|---|---|
| کمیسیون کارگزار | `0.004` | `domain/trading/iran_costs.py`: `BROKER_PCT = 0.004` | خیر |
| کارمزد تسویه | `0.00085` | `domain/trading/iran_costs.py`: `CLEARING_FEE_PCT = 0.00085` | خیر |
| مالیات فروش | `0.005` | `domain/trading/iran_costs.py`: `SELL_TAX_PCT = 0.005` | خیر |
| لغزش پایه/سقف | `5bps` / `150bps` | `backtesting/engine/broker.py`: `base_slippage_bps: float = 5.0` / `max_slippage_bps: float = 150.0` | خیر |
| ADV پیش‌فرض | `1_000_000` | `backtesting/engine/broker.py`: `average_daily_volume: int = 1_000_000` | خیر |
| حد نوسان روزانه | `0.03` برای ۲۰۲۴! | `backtesting/data/price_limits.py`: `LimitRule("2024-01-01", None, 0.03, "3pct_current")  # example, update with real rule` | **دارد ولی placeholder/احتمالاً غلط** |
| tick | `base_tick=1.0` (ریال) | `backtesting/market/rule_versioning.py`: `tick_size: float = 1.0  # Rial` | خیر |
| تسویه | `T+2` | `backtesting/market/rule_versioning.py`: `t_plus: int = 2  # T+2 for stocks` | خیر |
| سشن‌ها | `08:45 / 09:00 / 12:30` | `backtesting/market/rule_versioning.py`: `preopen="08:45"`, `open="09:00"`, `close="12:30"` | خیر |
| حجم مبنا | — | در `rule_versioning.py`: `volume_base_enabled: bool = True` (فقط پرچم؛ پیاده‌سازی عددی ندیدم) | — |

**مکانیزم `rule_at`:** بله وجود دارد — `backtesting/market/rule_versioning.py` (`MarketRuleSet.is_active(on_date)`، `effective_from/effective_to`) و `backtesting/data/price_limits.py` (`limit_for_date`, `IRAN_LIMIT_HISTORY`).

**اما [خوانده‌شده+اجراشده]:** تابع‌های `tag_bars`/`limit_for_date` **هیچ‌جا فراخوانی نمی‌شوند** (grep در `backtesting services domain api apps` فقط خودِ تعریف را یافت؛ `pipeline` بک‌تست از `BacktestService._load_historical_data` می‌خواند که این تگ را اضافه نمی‌کند). یعنی حد نوسانِ زمان‌دار **کد مرده** است.

**راه‌حل:** فعال‌سازی واقعی `tag_bars` در لود بارها + بازنویسی `IRAN_LIMIT_HISTORY` با قاعدهٔ درست ۲۰۲۴ (نه `0.03` «مثال»)؛ آزمون: هر بار `price_limit_pct` غیرصفر داشته باشد و برای ۲۰۲۴ برابر قاعدهٔ واقعی باشد.

---

## C3) قیمت خام یا تعدیل‌شده

**وجود دارد؟ ترجیح خام.** | شدت: بالا

ستون‌های `brsapi_historical_daily` (از `information_schema.columns`, ۲۳ ستون) [خوانده‌شده+اجراشده]:
```
symbol varchar | date varchar | time varchar | trade_count int | trade_volume bigint |
trade_value float | price_min float | price_max float | price_yesterday float |
price_first float | price_last float | price_last_change float | price_last_change_pct float |
price_close float | price_close_change float | price_close_change_pct float |
created_at timestamp | ins_id varchar | instrument_id varchar | updated_at timestamp |
gregorian_date date | shamsi_date varchar
```
⇒ **هیچ ستون قیمت تعدیل‌شده یا ضریب تعدیل در این جدول نیست.** جدول جدا `daily_adjust_factors(symbol_id, trade_date, adj_factor, computed_at)` با **۶۲۱٬۸۱۸** ردیف و ویو `vw_daily_history_adjusted` وجود دارد (`services/adjusted_price_reader.py`).

**بک‌تست کدام را می‌خواند؟ خام.** عین سطر `services/backtest_service.py::_load_historical_data`:
```python
SELECT date, price_first, price_max, price_min, price_close,
       trade_volume, trade_value
FROM brsapi_historical_daily
WHERE symbol = :symbol AND date >= :start AND date <= :end ...
```
هیچ join‌ای به `daily_adjust_factors` یا `vw_daily_history_adjusted` ندارد ⇒ **بک‌تست ML/Signal از قیمت خام استفاده می‌کند.**

`tests/unit/services/test_adjusted_price_reader.py` [خوانده‌شده]: مسیر جدا و مستقل `adjusted_price_reader` را آزمون می‌کند (نگاشت `jalali↔gregorian`، اسکیل ضرایب، یک کندل در هر روز معاملاتی). دربارهٔ «۱ شکست»: در اجرای ممیزی قبلی یکی از تست‌های DB-backed شکست خورد؛ من در این بخش تک‌تک اجرا نکردم — در بخش E دوباره اجرا می‌شود.

**خودرو در ۲۰۲۴ رویداد شرکتی داشت؟** [خوانده‌شده+اجراشده، `audit_out/_tmp/partC_db.json`]: رویدادهای `corporate_action_events` خودرو:
```
2011-07-23 capital_increase 0.063796
2011-10-31 capital_increase 0.400457
2013-01-08 capital_increase 0.043233
2014-03-17 capital_increase 0.142487
2015-07-21 capital_increase 0.005229
2015-11-24 capital_increase 0.113917
2020-03-24 capital_increase 18.718910
2025-04-22 capital_increase 7.501099
```
⇒ **در ۲۰۲۴ هیچ رویداد شرکتی برای خودرو نیست** (بعدی: ۲۰۲۵-۰۴-۲۲). ضریب تعدیل در بازهٔ اطراف ۲۰۲۴ ثابت است (`0.1176318497` در همهٔ ۲۸۱ ردیف 2023-12-02..2025-01-29) ⇒ درون بازهٔ ۲۰۲۴ اثر ex-date وجود ندارد، پس بک‌تست ۲۰۲۴ خودرو از این جهت آلوده نیست.

نکتهٔ جانبی مهم: `action_type` تنها `capital_increase` است (۵۸۶ ردیف/۱۴۵ نماد) و **همهٔ `dps = 0.00`** ⇒ **رویداد سود نقدی (DPS) ثبت نشده**؛ `corporate_actions` هم **۰ ردیف** دارد. پس تعدیل سود نقدی پوشش داده نشده است.

**راه‌حل:** `_load_historical_data` به `adjusted_price_reader.load_daily_candles(adjusted=True)` وصل شود؛ آزمون: قیمت‌های بک‌تست با `vw_daily_history_adjusted` برابر شوند.

---

## C4) برچسب‌ها (target)

**وجود دارد؟ بله، ولی تعریف واحد نیست.** | شدت: بالا

| محل | تعریف برچسب | افق | قیمت پایه | شواهد |
|---|---|---|---|---|
| `ml/datasets/labeling.py::LabelGenerator.future_return` | `prices.shift(-horizon)/prices - 1` | `horizon=5` پیش‌فرض | **close همان روز `t`** | عین سطر `future = prices.shift(-horizon) / prices - 1` |
| `ml/datasets/labeling.py::binary_direction` | `(shift(-h) > prices)` | h | close `t` | `direction = (future > prices).astype(int)` |
| `ml/datasets/builders.py::DatasetBuilder.load` | `future_return(df["close"] or df["price_close"], horizon=config.get("horizon",5))` | ۵ | close | — |
| `services/signal_backtest_engine.py` | خروجی `_tracker.evaluate_signal` (return از entry=open روز بعد تا exit=close آخر) | `days_forward=30` | **open روز بعد** | `entry_price = hist_data[0].get("open", signal_price)` |

**مشکل:** برچسب ML با close روز `t` ساخته می‌شود، ولی اجرای موتور رویدادمحور روی open روز `t+1` است ⇒ شکاف یک‌روزه؛ روز قفل خرید/فروش و نماد متوقف‌شده در برچسب لحاظ نمی‌شود (در `labeling.py` هیچ اشاره‌ای به session/قفل/توقف نیست).

**راه‌حل:** برچسب بر پایهٔ «قیمت قابل‌اجرای بعدی» (`open[t+1]`→`open[t+1+h]`) ساخته شود و روزهای بی‌معامله/قفل صریحاً مدیریت شوند؛ آزمون: بازده برچسب با بازده معاملهٔ مرجع هم‌خوان باشد.

---

## C5) فیچرها و knowledge_time + دو باگ ثبت‌شده

**وجود دارد؟ بله (کد)، ولی زمان‌آگاهی نامشخص.** | شدت: بالا

`services/feature_engine.py` → ۸ بلوک (IDs 1-115):

| بلوک | IDها | نمونه فیچرها | پنجره | مرجع |
|---|---|---|---|---|
| A: Identity & Data Quality | 1-10 | — | — | `:199` |
| B: Fundamental | 11-25 | — | — | `:228` |
| C: Valuation & Macro | 26-35 | — | — | `:287` |
| D: Daily Trading & Technical | 36-50 | `avg_volume_50`, `volume_spike`, `float_turnover_pct`, `sma_20`, `rsi_14`, `macd_signal`, `atr_14`, `breakout_flag`, `trend_20d` | ۲۰/۵۰ روز | `:325` |
| E: Money Flow | 51-60 | `inst_buy_volume`, `net_inst_volume`, `net_inst_ratio`, `retail_to_inst_ratio` | روز | `:402` |
| F: Microstructure & Queue | 61-75 | — | — | `:437` |
| G: Events & Qualitative | 76-95 | — | — | `:493` |
| H: Scores/Penalty/Decision | 96-115 | — | — | `:521` |

**knowledge_time:** برای حقیقی/حقوقی (`brsapi_historical_real_legal`) و بنیادی/کدال، در کد `feature_engine` هیچ ارجاعی به `knowledge_time`/`published_at`/`created_at` ندیدم؛ `computed_at` فقط در `daily_adjust_factors` است. نرمال‌سازی مقطعی روزانه/کل‌بازه: در این ماژول (که فیچرهای هر نماد را روزانه می‌سازد) ندیدم — [حدس از نام] یکسان‌سازی احتمالاً بالادست انجام می‌شود. winsorize و مقدار گمشده: `_ff = min(max(free_float_pct, 0.0), 100.0)` تنها clamp دیده‌شده است؛ برای گمشده `0.0` جایگزین می‌شود (نه NaN صریح).

**دو باگ `HIDDEN_ERRORS_REPORT`** (`reports/audits/2026-08-25_audit_hidden-errors-report.md` §2.2/§2.3):

- `float_turnover_pct` ۱۰۰× غلط — **رفع شده.** عین سطر فعلی (`services/feature_engine.py`):
```python
float_shares_count = shares_count * _ff / 100.0 if shares_count > 0 else 0
_denom = float_shares_count * last_price
if _denom > 1e-9:
    f["float_turnover_pct"] = round(100 * f["trade_value"] / _denom, 2)
```
- `net_inst_ratio` مخرج غلط — **رفع شده.** عین سطر فعلی:
```python
if float_shares_count > 1e-9:
    f["net_inst_ratio"] = round(f["net_inst_volume"] / float_shares_count * 100, 2)
```
(هر دو اکنون از `shares_count × free_float_pct/100` استفاده می‌کنند، نه از pct خام.) [خوانده‌شده]

---

## C6) survivorship

**وجود دارد؟ احتمالاً بله.** | شدت: بالا | [خوانده‌شده+اجراشده]

`audit_out/_tmp/partC_db.json`:
```json
"survivorship": {
  "distinct_symbols_last_90d": 2407,
  "distinct_symbols_all_time": 2407,
  "symbols_table_rows": 511,
  "symbols_only_before_90d": 0
}
```
⇒ **هیچ نمادی نیست که در تاریخچه داده داشته باشد ولی در ۹۰ روز گذشته نداشته باشد** (`0`). یعنی نماد حذف‌شده/تغییرنام‌یافته در جدول تاریخی **دیده نمی‌شود** — نشانهٔ survivorship bias. جدول `symbols` فقط ۵۱۱ ردیف دارد در برابر ۲۴۰۷ نماد تاریخی ⇒ universe ثبت‌شده هم کامل نیست.

**راه‌حل:** universe آموزش/بک‌تست از snapshot تاریخ‌دار ساخته شود (شامل نمادهای حذف‌شده)؛ آزمون: `distinct_symbols_last_90d < distinct_symbols_all_time`.

---

## C7) تنظیم هایپرپارامتر و شمارش آزمایش

**وجود دارد؟ بله، ولی DSR/PBO به پایپ‌لاین وصل نیست.** | شدت: بالا [خوانده‌شده]

- `ml/models/sweeper.py::HyperparamSweeper`: `GridSearchCV(..., cv=5)` و `RandomizedSearchCV(..., cv=5)` ⇒ **CV پنج‌تایی معمولی (نه purged/embargo، نه walk-forward)** روی سری زمانی ⇒ ریسک نشت.
- `services/cascade_engine.py`: `GeneticOptimizer` + فاز `grid_search` (`PARAM_GRID`) + `genetic_generations=12`.
- **شمارش آزمایش (trial counting):** در `sweeper.py` و `cascade_engine` هیچ شمارندهٔ `n_trials` که به گزارش اعتبار برسد ندیدم.
- **DSR/PBO:** توابع وجود دارند — `backtesting/metrics/deflated_sharpe.py::deflated_sharpe_ratio` و `services/backtest_framework.py::StatisticalValidator.deflated_sharpe/reality_check` — اما grep هیچ **مصرف‌کننده‌ای** در سرویس‌های بک‌تست/گزارش نیافت ⇒ [خوانده‌شده] پیاده‌شده ولی استفاده‌نشده.
- **hold-out نهایی:** در `walk_forward_validator.py` ندیدم؛ `is_reliable = avg_test_accuracy > 0.55 and overfitting < 0.15`.
- **purge/embargo:** فقط `CPCV` در `services/backtest_framework.py` (`embargo_pct: float = 0.01`، `embargo_len = max(1, int(n_total * self.embargo_pct))`). `WalkForwardEngine.split` **هیچ embargo/purge ندارد**. هیچ‌کدام نسبت به افق برچسب کالیبره نشده‌اند (embargo صرفاً ۱٪ طول سری است).

**راه‌حل:** `GridSearchCV` با `TimeSeriesSplit`/CPCV purged، ثبت `n_trials`، و مصرف DSR در گزارش؛ آزمون: هر گزارش شامل `n_trials` و `deflated_sharpe` باشد.

---

## C8) رژیم، ensemble، calibrator، ۱۰ دروازه، بازآموزی خودکار

**وجود دارد؟ بله.** | شدت: متوسط/بالا [خوانده‌شده]

**۱۰ دروازه `services/signal_decision_engine.py`** (از docstring عین کد): 1 Data Quality, 2 Model, 3 Probability, 4 Regime, 5 Consensus, 6 Liquidity, 7 Risk/Reward, 8 Expectancy, 9 Portfolio, 10 Execution.

آستانه‌های گرید (عین کد، `:306-309`):
```
a_plus: min_probability 0.70, min_rr 2.0, min_expectancy 0.20, all_pass_required True
a:      min_probability 0.65, min_rr 1.5, min_expectancy 0.12, max_warnings 1
b:      min_probability 0.60, min_rr 1.0, min_expectancy 0.05, max_warnings 2
watchlist: min_probability 0.55, min_rr 0.0, min_expectancy 0.0
```
آستانهٔ پیش‌فرض احتمال: `base_threshold = 0.55` (`:365`)؛ حداقل انتظار خالص: `cfg.get("minimum_net_expectancy_r", 0.05)` (`:859`). سایر دروازه‌ها از `get_gate_config(gate, market)` خوانده می‌شوند (رژیم/نقدشوندگی/ریسک-بازده/پورتفوی/اجرا — `:268-300`).

**فیت روی چه داده‌ای؟** [حدس از نام برای بخش‌های فیت‌نشدنی]: رژیم/ensemble/calibrator در `services/` ماژول‌های جدا دارند (`services/ensemble_engine.py`, `services/calibration_loop.py`) که در این زمان اجرای کاملشان بررسی نشد؛ در کد این بخش شاهدی از فیت روی دادهٔ آینده **ندیدم** اما **تأیید نکردم**.

**ماشهٔ بازآموزی** (`services/auto_retrain_pipeline.py`): عین کد:
```python
ACCURACY_THRESHOLD = 0.55  # retrain if accuracy drops below 55%
SCHEDULE_DAYS = 7  # retrain at least every 7 days
MIN_SAMPLES_FOR_RETRAIN = 50
_min_accuracy_gain = 0.02
```
و کامنت: `Audit ML-004: a retrain only "sticks" if holdout accuracy improves on the current accuracy by this margin (guards against noise-promotion).` ⇒ **مدل جدید مستقیماً جایگزین نمی‌شود؛** باید ≥ ۰.۰۲ بهتر شود. [خوانده‌شده]

**راه‌حل:** مستندسازی دادهٔ فیت هر ماژول + آزمون منشأ سیگنال (بند B4).

---

## جمع‌بندی بخش C

| id | شرح | شدت | فایل:خط | اقدام |
|---|---|---|---|---|
| C-01 | `BacktestSimulator` روی close همان کندل پر می‌کند؛ `BacktestEngine` روی open روز بعد | بحرانی | `simulator.py`, `backtest_engine.py`, `ml_signal_strategy.py` | یکسان‌سازی قاعدهٔ اجرا |
| C-02 | `IRAN_LIMIT_HISTORY` زمان‌دار ولی **کد مرده** و مقدار ۲۰۲۴ = `0.03` (مثال) | بالا | `backtesting/data/price_limits.py` | فعال‌سازی + قاعدهٔ واقعی |
| C-03 | `rule_versioning` (tick/T+2/session) وجود دارد ولی به بک‌تست وصل نیست | متوسط | `backtesting/market/rule_versioning.py` | اتصال |
| C-04 | بک‌تست قیمت **خام** می‌خواند؛ `vw_daily_history_adjusted` بی‌استفاده | بالا | `services/backtest_service.py::_load_historical_data` | سوئیچ به adjusted |
| C-05 | رویداد فقط `capital_increase`؛ `dps` همه صفر؛ `corporate_actions` صفر ردیف | بالا | جدول‌های DB | افزودن سود نقدی |
| C-06 | برچسب ML با close روز `t` ولی اجرا با open `t+1` | بالا | `ml/datasets/labeling.py` | برچسب قابل‌اجرای بعدی |
| C-07 | `GridSearchCV(cv=5)` روی سری زمانی؛ بدون purge/embargo؛ DSR استفاده‌نشده | بالا | `ml/models/sweeper.py`, `backtest_framework.py` | TimeSeriesSplit/CPCV + DSR |
| C-08 | survivorship: نماد حذف‌شده در تاریخچه نیست (`2407 == 2407`) | بالا | DB | snapshot تاریخ‌دار universe |
| C-09 | ۲ باگ HIDDEN_ERRORS رفع شده (float_turnover_pct, net_inst_ratio) | اطلاعاتی | `services/feature_engine.py` | — |
| C-10 | بازآموزی کورکورانه جایگزین نمی‌کند (`_min_accuracy_gain=0.02`) | مثبت | `services/auto_retrain_pipeline.py` | — |
