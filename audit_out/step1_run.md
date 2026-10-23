# مرحله ۱ — مسیر سیگنال ML تا نتیجه بک‌تست + اجرای واقعی

## ۱) مسیر فراخوانی (فهرست مرتب) [خوانده‌شده+اجراشده]

۱. نقطه ورود: `services/backtest_service.py:174`
   - عین سطر: `async def run_backtest(`
   - پارامتر کلیدی، عین سطر `services/backtest_service.py:178`: `strategy_type: str = "moving_average_cross",`
۲. انتخاب استراتژی، عین سطر `services/backtest_service.py:200`: `strategy_cls = _get_strategy_class(strategy_type)`
   - رجیستری، عین سطر `backtesting/strategies/registry.py:198`: `("ml_signal", MlSignalStrategy),`
۳. بارگذاری دیتای تاریخی، عین سطر `services/backtest_service.py:228`: `data = await self._load_historical_data(symbols[0], start, end, source=data_source)`
   - منبع واقعی: جدول `brsapi_historical_daily` — عین سطر `services/backtest_service.py:506`: `logger.info("Loaded %d bars from brsapi_historical_daily for %s", len(rows), symbol)`
۴. تزریق پیش‌بینی ML، عین سطر `services/backtest_service.py:245`: `await self._inject_ml_predictions(data, symbols[0], strategy_params)`
   - تابع تزریق، عین سطر `services/backtest_service.py:767`: `async def _inject_ml_predictions(`
   - تلاش بارگذاری مدل، عین سطر `services/backtest_service.py:791`: `model_obj, _ = artifact_mgr.load_model(model_id)`
   - fallback صفر، عین سطر `services/backtest_service.py:797`: `if model is None or not hasattr(model, "predict"):`
۵. استراتژی، عین سطر `backtesting/strategies/ml_based/ml_signal_strategy.py:25`: `class MlSignalStrategy(BaseStrategy):`
   - شرط خرید، عین سطر `backtesting/strategies/ml_based/ml_signal_strategy.py:100`: `if predicted_change >= self.buy_threshold and self._position <= 0:`
۶. اجرای شبیه‌ساز، عین سطر `backtesting/engine/simulator.py:67`: `def run(`
   - حلقه بارها، عین سطر `backtesting/engine/simulator.py:104`: `orders = strategy.on_bar(bar)`
۷. نرمال‌سازی نتیجه: `backtesting/runner.py:59` (`class BacktestRunner:`) و خلاصه متریک‌ها `services/backtest_service.py:35` (`def _compute_metrics(result: BacktestResult, risk_free_rate: float | None = None) -> tuple[dict[str, float], list[str]]:`)

نکته مسیر جایگزین (تولید سیگنال زنده، در این اجرا استفاده نشد) [خوانده‌شده]:
- `services/ml_signal_connector.py:161`: `class MLSignalConnector:`
- fallback هیوریستیک، عین سطر `services/ml_signal_connector.py:266`: `if closes and len(closes) >= 10:`

## ۲) دستور دقیق اجرا [خوانده‌شده+اجراشده]

- اسکریپت (فقط خواند/اجرا، بدون تغییر فایل موجود؛ اسکریپت در پوشه موقت): `C:\Users\Iran\AppData\Local\Temp\opencode\step1.py`
- دستور (از ریشه ریپو):
  - `venv/Scripts/python.exe C:\Users\Iran\AppData\Local\Temp\opencode\step1.py`
- مشخصات اجرا: `strategy_type="ml_signal"`، بازه `2024-01-01` تا `2024-12-29`، سرمایه `1_000_000_000`، نمادها: وپترو، وساخت، خودرو، وسپه، خبهمن (۵ نماد واقعی با بیش از ۲۰۰ بار روزانه در `brsapi_historical_daily`)، منبع دیتا `auto` (عملاً `brsapi_historical_daily`)، هزینه/لغزش پیش‌فرض سرویس.
- خروجی خام کامل: `C:\Users\Iran\AppData\Local\Temp\opencode\step1_raw.json`

## ۳) خروجی خام (بدون خلاصه‌سازی) [خوانده‌شده+اجراشده]

لاگ بارگذاری دیتا (عین لاگ):
- `Loaded 238 bars from brsapi_historical_daily for وپترو`
- `Loaded 239 bars from brsapi_historical_daily for وساخت`
- `Loaded 239 bars from brsapi_historical_daily for خودرو`
- `Loaded 238 bars from brsapi_historical_daily for وسپه`
- `Loaded 239 bars from brsapi_historical_daily for خبهمن`

لاگ مدل (عین لاگ، هر ۵ نماد تکرار شد):
- `Unknown model: xgboost`
- `No ML model available for <symbol>, using zero predictions`

هشدار جانبی (عین لاگ):
- `Failed to get result from DB: 'BacktestRun' object has no attribute 'current_value'`

متریک‌های خام هر ۵ نماد (عین JSON، یکسان برای هر ۵ نماد):
- `total_return_pct: 0.0`، `sharpe_ratio: 0.0`، `sortino_ratio: 0.0`، `max_drawdown_pct: 0.0`، `total_trades: 0.0`، `win_rate: 0.0`، `avg_profit: 0.0`، `total_return: 0.0`، `annualized_return_pct: 0.0`، `volatility: 0.0`، `cumulative_return: 0.0`، `positive_days: 0.0`، `negative_days: 0.0`، `risk_free_return: 0.25`، `downside_volatility: 1.0`
- هزینه کل (کمیسیون/لغزش پرداختی): در متریک‌ها فیلد جدا ندیدم — با صفر معامله، هزینه تحقق‌یافته صفر است. [خوانده‌شده+اجراشده]
- تعداد معامله هر نماد: `0` (هر ۵ نماد). بازده هر نماد: `0.0%`. Sharpe هر نماد: `0.0`. MDD هر نماد: `0.0`.

علت صفر بودن (عین کد):
- `services/backtest_service.py:798-800`:
  - `logger.warning("No ML model available for %s, using zero predictions", symbol)`
  - `for b in bars:`
  - `b["predicted_change_pct"] = 0.0`
- با پیش‌بینی صفر و آستانه‌های پیش‌فرض (`buy_threshold = 1.0`، `sell_threshold = -1.0` در `ml_signal_strategy.py:42-43`) هیچ شرطی در `on_bar` فعال نشد → صفر معامله.

## ۴) وضعیت: موفق (اجرا کامل شد؛ سیگنال ML صفر بود)

- اجرا از نظر فنی موفق بود (هر ۵ نماد `status: ok` + `run_id` صادر شد)، اما مسیر ML عملاً هیچ سیگنالی تولید نکرد چون مدل آموزش‌دیده‌ای در `ArtifactManager` وجود ندارد.
- کوچک‌ترین رفع پیشنهادی (فقط پیشنهاد، بدون تغییر): آموزش/ثبت یک مدل `xgboost_<symbol>` در `ArtifactManager` (یا فعال‌سازی fallback هیوریستیک `_heuristic_trend_predict` داخل `_inject_ml_predictions`) و تکرار همین دستور؛ آزمون قبولی: `total_trades > 0` در خروجی خام.

---

## ۵) مسیر دومی که در همین مرحله اجرا شد — `POST /signal-insights/backtest` (شواهد خام داخل `audit_out/`)

> این بخش برای تکمیل همین سند اضافه شد: مسیر «endpoint بک‌تست سیگنال» جدا از مسیر ML بالا اجرا شده بود و شواهد خامش داخل `audit_out/` بود، اما در بندهای ۱–۴ سند مستند نشده بود. اکنون بند ۵ سند `step3_criticals.md` به همین بخش ارجاع می‌دهد.
>
> - اسکریپت: `audit_out/_tmp/step1_run.py` (بخش A زنده، بخش B روی کپی ایزوله)
> - لاگ‌ها: `audit_out/_logs/step1_run.log` (۲۰:۱۹)، `audit_out/_logs/step1_run_b.log` (۲۰:۲۰)، `audit_out/_logs/step1_rerun1.log` (۲۰:۲۹)، `audit_out/_logs/step1_rerun2.log` (۲۰:۳۰)
> - خروجی JSON: `audit_out/_tmp/step1_run_raw.json`
> - کپی ایزوله: `audit_out/_tmp/step1_copy.sqlite`؛ سیگنال‌های پین‌شده: `audit_out/_tmp/step1_pinned_signals.json`

### ۵-۱) بخش A — روی DB زنده

[خوانده‌شده+اجراشده] مسیر فراخوانی: `apps/api/endpoints/signal_insights.py:89` → `services/multi_market_signal_engine.py:357` → `services/signal_backtest_engine.py:138` → `_fetch_future_prices` (SQL زنده).

| سنجه | مقدار (عین خروجی) |
|---|---|
| `generate_all(market_filter="stock", limit=30)` | `45.86` ثانیه |
| سیگنال خام بازگشتی / گزارش بازار | `30` / `n=600` |
| `date` سیگنال‌ها | `"None"` (هر ۳۰ سیگنال نمونه) |
| سریال‌سازی خودِ endpoint (`apps/api/endpoints/signal_insights.py:120` → `s.to_dict()`) | **خطا**: `AttributeError: 'MarketSignal' object has no attribute 'to_dict'` (برچسب داخل لاگ `:112` است؛ سطر واقعی کد `:120` است) |
| بک‌تست با کارگردان جایگزین (`dataclasses.asdict`) | `total_signals: 0` در `0.12` ثانیه |
| رکوردهایی که در `signal_accuracy` نوشته می‌شد | `0` |

### ۵-۲) بخش B — روی کپی ایزوله (همان موتور + SQL واقعی، SQLite به‌جای PostgreSQL)

دو لنگر روی یک کپی (`brsapi_historical_daily`، ۲۰۰۰ سطر، ۲ نماد، `2026-09-16..2026-10-08`):

| لنگر `date` | total_signals | total_return_pct | sharpe | MDD | profit_factor | JSON سخت‌گیرانه |
|---|---|---|---|---|---|---|
| `2026-09-16` (قدیمی‌ترین) | `2` | **`788.87`** | `11.301` | `0.0` | `Infinity` | ❌ `ValueError: Out of range float values are not JSON compliant` (فیلد `profit_factor`) |
| `2026-10-08` (جدیدترین سینک) | `0` | `0.0` | `0.0` | `0.0` | `0.0` | ✅ |

معاملهٔ ساختگی لنگر اول (عین JSON): نماد `آ س پ3`، ورود `3163.0` → خروج `28040.0` ⇒ **`+786.2%`** با `entry_date 2026-10-03` و `exit_date 2026-10-08` — یعنی دو تاریخ جلالی متفاوت روی یک `gregorian_date`.

نرخ هزینهٔ خودِ موتور (`services/signal_backtest_engine.py:124-132`) برای `stock` برابر `0.003` است و در `:228` همان کسر می‌شود؛ در برابر SSOT (`domain/trading/iran_costs.py` ⇒ رفت‌وبرگشت سهام ~۱.۴۷٪) حدود **۴.۹ برابر کم‌برآورد**.

### ۵-۳) آزمون قبولی تکرارپذیری (بخش B)

```
python audit_out/_tmp/step1_run.py --only-b     # 20:29
python audit_out/_tmp/step1_run.py --only-b     # 20:30
diff <(grep -v "^2026-" audit_out/_logs/step1_rerun1.log) \
     <(grep -v "^2026-" audit_out/_logs/step1_rerun2.log)
# → IDENTICAL (تنها تفاوت، مهر زمانی خط لاگ است)
```
`audit_out/_logs/step1_run_b.log` نیز با `step1_rerun2.log` یکسان است ⇒ خروجی بخش B روی کپی ایزوله تکرارپذیر است. (بخش A روی DB زنده تکرارپذیر نیست.)

### ۵-۴) انحراف از production و محدودیت‌ها

- تنها انحراف: `SignalAccuracyTracker.record_outcome` با یک stub گیرندهٔ رکورد جایگزین شد تا جدول زندهٔ `signal_accuracy` نوشته نشود (`write_guard`؛ `0` رکورد نوشته شد). موتور، `evaluate_signal` و SQL واقعی بودند.
- بخش B با درایور `aiosqlite` اجرا شد نه `asyncpg`؛ SQL و منطق موتور یکسان است.
- بخش A روی DB زنده تکرارپذیر نیست (داده و sync در حال تغییرند).
