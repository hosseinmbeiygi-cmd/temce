# قسمت ۰۸ — موتور بکتست، هزینه تراکنش و گیت پذیرش

| | |
|---|---|
| **مبنای اندازهگیری** | `73a6c52d` — همان مبنای قسمتهای ۰۵ تا ۰۷؛ HEAD بین چهار قسمت جابهجا نشد. |
| **وضعیت worktree** | **۱۲۲ فایل Dirty** (بدون تغییر نسبت به قسمت ۰۷). تغییرات مرتبط با بکتست فقط **جابهجایی دو اسکریپت** است: `analyze_high_trades.py` و `backtest_collector.py` از ریشه به `scripts/` (`D` + `??`). هسته `backtesting/`, `config/backtest_costs.yaml`, `acceptance.yaml` و `domain/trading/iran_costs.py` **جزو فایلهای اصلاحشده نیستند**؛ شواهد زیر هم در HEAD و هم در worktree معتبراند. |
| **تعهد** | فقط فایلهای Markdown تحلیلی ساخته/ویرایش شدند. **هیچ فایل کد، پیکربندی، تست، compose یا مهاجرتی تغییر نکرد.** |
| **یادداشت روش** | جستجوی بیپیرایهٔ کلدرخت به `.freebuff/worktrees/<uuid>/` — worktree پنهان فرایند همزمان — برخورد و timeout میخورد؛ همان دلیل timeoutهای قسمتهای قبل. تمام جستجوها با مسیرهای محدودشده انجام شدند. |
| **زبان** | فارسی (هماهنگ با سری) |

---

## ۱ — فهرست فایلها و ابعاد (شمارش واقعی، فقطخواندنی)

| درخت / فایل | تعداد | خط | یادداشت |
|---|---:|---:|---|
| `backtesting/` | **۳۰۲ فایل `.py`** | **۲۹٬۶۱۵** | ۴۵ زیرپوشه؛ عدد گزارش ۱۶۰ لایهای ۲۹٬۵۵۷ بود (۵۸+ خط از مبنا) |
| `backtesting/engine/` | ۲۸ | ۳٬۲۲۱ | `simulator.py`, `broker.py`, ۶ موتور |
| `backtesting/strategies/` | ۴۴ | ۳٬۰۷۲ | بزرگترین زیرپوشه از نظر تعداد فایل |
| `backtesting/composer/` | ۶ | ۱٬۳۶۶ | `indicator_registry.py` (۵۹۳ خط، بزرگترین فایل درخت) |
| `backtesting/optimization/` | ۸ | ۱٬۱۱۱ | `walk_forward.py` (۴۸۷), `monte_carlo.py` (۳۳۵) |
| `backtesting/costs/` | ۸ | ۸۷۷ | `iran_costs.py` (۱۱۱), `transaction_cost_model.py` (۱۵۷) |
| `config/backtest_costs.yaml` | ۱ | ۴۷ | «Canonical … single source of truth» |
| `acceptance.yaml` (ریشه) | ۱ | ۱۰۰ | آستانهها + تعرفه طلا + ساعات بازار |
| `domain/trading/iran_costs.py` | ۱ | ۱۴۲ | `MARKET_RATES` (۱۰ بازار)، مرجع واقعی نرخها |

شمارش ایستا: **۱۰ فایل** در `backtesting/` همچنان تعریف `commission`/`cost` محلی دارند؛ `config/backtest_costs.yaml` فقط در **۲** نقطه خوانده میشود؛ `acceptance.yaml:market_rules` (`get_gold_market_rules`) **صفر مصرفکننده** در `backtesting/`, `services/`, `apps/`, `core/`, `src/` دارد.

---

## ۲ — ردیابی جریان اجرا

### ۲‑الف — مسیرproduction بکتست

```
apps/api/endpoints/backtests.py:54,78,1070-1073  (body.commission_pct / slippage_bps)
  └─ services/backtest_service.py:199-208
       └─ BacktestSimulator(broker=Broker(commission_pct=..., slippage_bps=...))   ← BT-03
            └─ BacktestSimulator.__init__ :55  → execution_timing = _default_timing()
                 ├─ open("config/backtest_costs.yaml")  :62  ← مسیر نسبی به CWD   ← BT-05
                 └─ except ⇒ "next_open" (خاموش)
            └─ run(strategy, capital, bars)  :82
                 ├─ portfolio.reset() / strategy.reset()
                 ├─ if execution_timing == "next_open": fill کندل t+1 با open
                 └─ else: fill همان کندل t با close  ← مسیر legacy/look-ahead
                      └─ Broker.submit_order_sync()  :200
                           ├─ _resolve_daily_volume()  → None ⇒ ADV generic  ← BT-06
                           ├─ participation cap  :214
                           ├─ _compute_slippage() :169 → فقط self.config.base_slippage_bps
                           └─ _compute_commission() :198 → cost_model.compute() → MARKET_RATES
```

### ۲‑ب — دو گیت پذیرش موازی

```
مسیر A (بکتست استراتژی)
  WalkForwardOptimizer.optimize()  → oos_results, WFE, DSR, profit_factor
    └─ apps/api/endpoints/backtests.py:943
         result["acceptance"] = evaluate_walk_forward_result(result)   :515
              ├─ walk_forward_metrics()  → ۶ اسکالر (profit_factor=None ⇒ +inf)
              ├─ evaluate_acceptance()   :263 → PASS / REJECT
              └─ _threshold_rows()       → جدول شواهد
    └─ return ApiResponse(success=True, data=result)   :946   ← حکم NEVER enforced  ← BT-04

مسیر B (اعتبارسنجی مدل ML)
  services/walk_forward_validator.py:255-267
    └─ از test_accuracy پنجرهها معاملات ساختگی میسازد:
         TradeOutcome(pnl_pct=+1.0 / -1.0, cost_pct=0.5)     ← BT-02
    └─ services.statistical_acceptance_gate.evaluate_acceptance()  :121
         معیارهای کاملاً متفاوت: ≥۱۰۰ نمونه، Wilson CI، شارپ دونیمه، پایداری EV
    └─ result.acceptance_passed = acceptance.passed   ← بدون مصرفکننده مسدودکننده
```

---

## ۳ — سیاست شکست (گامبهگام)

| گام | رویداد شکست | سیاست | سطح لاگ | اثر |
|---|---|---|---|---|
| `IranTransactionCosts.from_config` | فایل YAML یافت نشد / خطای YAML | **swallow** → `cfg = {}` | بیصدا | سقوط به نرخهای کانونی |
| `_default_timing` | فایل یافت نشد / خطا | **fail-open** → `next_open` | بیصدا | تغییر خاموش زمان اجرا |
| `execution_timing` مقدار ناشناخته | غلطاملایی در YAML/ورودی | **fail-open** → شاخه `same_close` | بیصدا | نشت نگاهبهآینده |
| `_resolve_daily_volume` | نبود ADV | هشدار + fallback `۱٬۰۰۰٬۰۰۰` | `warning` | لغزش کمبرآورد |
| `Broker.require_daily_volume=True` | نبود ADV | **fail-fast** `ValueError` | — | درست، ولی پیشفرض `False` و هیچ مصرفکنندهای آن را ست نمیکند |
| `submit_order_sync` | سفارش > سقف مشارکت | partial-fill یا skip | `warning` | قابلتنظیم، ولی از کد هاردکد میآید |
| `_eval_combo` | هر استثناء | `return (-1e9, params, 0.0)` | **بیصدا** | شکست کل grid قابلتشخیص نیست |
| `optimize` پنجره OOS | هر استثناء | `continue` | **بیصدا** | پنجره حذف و `n_trials` کم شمرده میشود |
| `BacktestRunner._dispatch` | خطای موتور | **fail-fast** `RuntimeError` | — | نقطه قوت |
| `BacktestRunner` موتور deprecated | نام `simulation`/`backtest_engine` | `DeprecationWarning` | پیشفرض پایتون نادیده میگیرد | اجرا بلامانع |
| `evaluate_walk_forward_result` | معیار غایب | **fail-closed** → `REJECT` | — | نقطه قوت |
| **مصرف حکم `REJECT`** | — | **هیچ اقدامی** | — | گیت صرفاً informative ← BT-04 |

---

## ۴ — جدول یافتهها (`BT-01`…`BT-16`)

| ID | شدت | خط دقیق | شاهد | اثر عملی | جهت اصلاح |
|---|---|---|---|---|---|
| **BT-01** | 🔴 بحرانی | `config/backtest_costs.yaml:1`; `iran_costs.py:72`; `simulator.py:62` | سربرگ فایل ادعای «single source of truth» دارد، ولی `IranTransactionCosts.from_config()` **صفر فراخواننده** در کل مخزن است و تنها خواننده زندهٔ فایل `_default_timing()` است که **فقط** `execution_timing` را برمیدارد | نرخها، `base_slippage_bps`، `volume_impact_factor`، سقف لغزش، `max_participation`، `allow_particial_fill`، `market_close` و `seed` هیچ اثری بر اجرا ندارند؛ مقادیر واقعی از `MARKET_RATES` و `IRAN_MARKET_COSTS` هاردکدشده در `broker.py:62-81` میآیند. تغییر YAML برای تنظیم هزینه **بیصدا بیتأثیر** است | یا حذف فایل و اعلام کد بهعنوان مرجع، یا تزریق `from_config()` به `Broker`/`Runner` + تست پاریتی YAML↔کد + مسیر مخزنمحور |
| **BT-02** | 🔴 بحرانی | `services/walk_forward_validator.py:255-268`; `services/statistical_acceptance_gate.py:121-175` | `n_win = round(win.test_accuracy * win.test_size)` ⇒ ساخت `TradeOutcome(pnl_pct=±1.0, cost_pct=0.5)`؛ کامنت میگوید هزینه «از policy YAML» است ولی `0.5` هاردکد است | پذیرش/رد مدل ML بر اساس **معاملاتی که هرگز رخ ندادهاند** تعیین میشود، با هزینهای که با مدل کانونی ۱۴۰۵ (۰٫۳۷۱۲٪/۰٫۸۸٪) هیچ نسبتی ندارد. افزون بر آن، گیتی کاملاً متفاوت از `acceptance.yaml` اعمال میشود (۱۰۰ نمونه، Wilson CI، شارپ دو نیمه) و نتیجه فقط در `result.acceptance_passed` ذخیره میگردد | تغذیه `TradeOutcome` از `backtest_trades` واقعی؛ `cost_pct` از `iran_costs`؛ یکی کردن دو گیت |
| **BT-03** | 🟠 بالا | `broker.py:96-97,169,198`; `iran_costs.py:42-46,56-60`; `backtest_service.py:199-208`; `endpoints/backtests.py:1031-1032` | `self.commission_pct` و `self.slippage_bps` فقط **ذخیره** میشوند؛ `_compute_slippage` از `self.config.base_slippage_bps` و `_compute_commission` از `cost_model.compute()` (⇒ `MARKET_RATES`) میخواند. فیلدهای `broker_pct`/`clearing_fee_pct`/`sell_tax_pct` در `IranTransactionCosts` طبق docstring «فقط نمایشی»اند | API عملاً پارامتر `commission_pct`/`slippage_bps` را میپذیرد و `BacktestService` بروکر تازهای با آنها میسازد، ولی **هیچ تغییری در PnL رخ نمیدهد**؛ docstring بروکر «Custom rates via commission_pct are still honoured» خلاف واقع است | حذف پارامترها، یا اعمالشان از طریق `market="ledger-custom:..."`؛ اصلاح docstring؛ تست پاریتی با ورودی سفارشی |
| **BT-04** | 🟠 بالا | `apps/api/endpoints/backtests.py:943-946`; `walk_forward_validator.py:268` | `result["acceptance"] = evaluate_walk_forward_result(result)` بلافاصله با `return ApiResponse(success=True, data=result)` دنبال میشود؛ جستجو در `apps/ services/ jobs/ backtesting/` هیچ خوانندهای برای `status == "REJECT"` یا `acceptance_passed` نیافت | «Production Gate» نامگذاری شده ولی یک **حاشیه حسابرسی** است، نه گیت: استراتژی `REJECT` دقیقاً همان پاسخ `success=True` و همان `best_params` را میگیرد. قسمت ۰۴/۰۳ الگوی «گیت ساخته شده، وصل نشده» اینبار در لایه اعمال حکم تکرار شد | مسدود کردن promotion/ذخیره `best_params` روی `REJECT`؛ یا تغییر نام به `audit` و مستندسازی صریح |
| **BT-05** | 🟠 بالا | `simulator.py:55,62-65,124-145` | `if self.execution_timing == "next_open": … else: …` — **هر** مقدار دیگر (از جمله غلطاملایی `nextopen`) وارد شاخه `same_close` میشود؛ `_default_timing` مسیر **نسبی به CWD** را با `except: return "next_open"` میخواند | غلطاملایی در تنها کلید زندهٔ YAML یا اجرای فرایند از CWD دیگر، **بیشدت خاموش** حالت legacy «پر کردن روی close همان کندل سیگنال» را فعال میکند — یعنی نشت نگاهبهآینده در تمام معاملات. همان الگوی `CFG-06` (قسمت ۰۵) و `SIG-03` (قسمت ۰۷) | `match` صریح با `raise ValueError` روی مقدار ناشناخته؛ مسیر مطلق مخزنمحور؛ لاگ `warning` روی fallback |
| **BT-06** | 🟠 بالا | `broker.py:90,130-135,161-163,224-230`; `submit_order_sync:211` | پیشفرض `average_daily_volume=1_000_000`؛ `_resolve_daily_volume` در نبود داده `None` میدهد (فقط هشدار)؛ `_compute_slippage` در `adv<=0` از `100_000` استفاده میکند؛ `require_daily_volume` پیشفرض `False` و هیچ مصرفکنندهٔ production آن را ست نمیکند | لغزش و سقف مشارکت برای نمادهای بیداده با **حجم جعلی** محاسبه میشود. گزارش ۱۶۰ لایهای (لایه ۳۲۸) میگوید ۶۰٫۲۱٪ ردیفهای `brsapi_historical_daily` حجم صفر/تهی دارند — پس این مسیر برای اکثریت نمادهاست، نه استثنا | `require_daily_volume=True` در production؛ یا fail-closed روی ADV ناشناخته؛ لاگ ساختاریافته بهجای هشدار یکبارهمصرف |
| **BT-07** | 🟠 بالا | `analytics/engine.py:36,64,69`; `metrics/risk_metrics.py:17-18`; `walk_forward.py:73-74`; `core/trading_constants.py:22,25,28`; `acceptance.yaml:6-22` | `AnalyticsEngine` (مصرفکننده `BacktestRunner._summarize`) واریانس را بر `len(returns)` (ddof=0) و `risk_free_rate=0.0` میگیرد؛ `RiskMetrics` و walk-forward از `ddof=1` و `get_risk_free_rate("moderate")=0.25` استفاده میکنند. ثابتهای ۲۵۲ (GLOBAL) / ۲۵۰ (TSE) / ۲۴۰ (IME) و `acceptance.yaml:market_rules` (۲۵۲/۲۴۰) سه منبع جدااند | `sharpe_ratio` خروجی `BacktestRunner` با `sharpe_ratio` خروجی `BacktestService` و با `avg_oos_sharpe`ای که گیت پذیرش قضاوت میکند **همعدد نیست**؛ اختلاف نرخ بدون ریسک ۲۵ واحد درصد، شارپ را کاملاً جابهجا میکند. `get_gold_market_rules` صفر مصرفکننده دارد | یکی کردن تابع محاسبه شارپ؛ تزریق `market_rules` بهجای ثابت سراسری؛ تست پاریتی دو مسیر |
| **BT-08** | 🟡 متوسط | `iran_costs.py:92-105`; `tests/unit/backtesting/test_consumer_cost_parity.py:35-37` | `from_config` برای اعمال override، `MARKET_RATES[f"config:{market}"] = (b,s,t)` مینویسد — **جهش دیکشنری سراسری**؛ تست هویت مالیات صریحاً کلیدهای `config:` و `ledger-custom:` را رد میکند | نرخها در سطح ماژول و قابلتغییراند؛ دو بکتست همزمان با override متفاوت روی همان کلید یکدیگر را بازنویسی میکنند، و تست پاریتی عمداً از آنها چشمپوشی میکند. امروز چون `from_config` مرده است نهفته است، ولی بهمحض وصلکردن `BT-01` فعال میشود | `MappingProxyType` / ساخت `frozen` جدول محلی بهجای جهش global؛ پوشش تست کلیدهای سفارشی |
| **BT-09** | 🟡 متوسط | `backtesting/validation.py:10-26` | `BacktestValidator` در ۲۶ خط فقط سه کلید `strategy/start_date/end_date` را چک میکند و `validate_results` تنها `result is None`؛ **صفر فراخواننده** در کل مخزن | هیچ اعتبارسنجیای برای ترتیب تاریخها، سازگاری `execution_timing`، حضور ADV، انطباق هزینه با YAML، یا `min_trade_count` وجود ندارد. لایه ۴۴۶ گزارش اصلی این فایل را جزو چارچوب acceptance میشمارد، ولی عملاً یک stub مرده است | یا گسترش به گیت ورودی واقعی و فراخوانی از `BacktestRunner.run`، یا حذف |
| **BT-10** | 🟡 متوسط | `runner.py:141`; `core/seed.py:8-10`; `config/backtest_costs.yaml:47` | `set_global_seed(int(kwargs.pop("seed", 42)))` — مقدار YAML خوانده نمیشود؛ `os.environ["PYTHONHASHSEED"]` **پس از بوت مفسر** نوشته میشود (بیتأثیر بر hash randomization)؛ `random`/`numpy`/`torch` بهصورت سراسری reseed میشوند | reproducibility شعار دادهشده برای اجراهای موازی (`max_workers`) تضمین نیست: هر ران، بذر فرایندهای همزمان را عوض میکند. `seed` در YAML یک کلید مرده دیگر است | بذر محلی بهازای ران (`random.Random(seed)` / `np.random.default_rng`)؛ حذف نوشتن `PYTHONHASHSEED` |
| **BT-11** | 🟡 متوسط | `walk_forward.py:211-212`, `:380`, `:395-396`, `:398-399` | `_eval_combo` هر استثناء را `except Exception: return (-1e9, params, 0.0)` میبلعد؛ `_optimize_window` با امتیاز `-1e9` و شرط `score > best_score` ⇒ `best_params={}`؛ پنجرههای OOS خطا `continue` بیصدا | اگر کلاس استراتژی برای همه ترکیبها شکست بخورد، خروجی `{"error": "No valid walk-forward results"}` است — دقیقاً همان پیامی که برای «داده ناکافی» میآید؛ ریشهیابی بدون لاگ ناممکن است | لاگ `warning` با نوع استثناء؛ شمارش شکستها در نتیجه؛ تمایز خطا از کمبود داده |
| **BT-12** | 🟡 متوسط | `walk_forward.py:57-66`, `:434-439`, `:445-447` | پنجره بیمتامعامله `max_dd=100` و `trades=0` برمیگرداند؛ `n_trials = len(all_combos) * max(len(oos_results), 1)` فقط **پنجرههای موفق** را میشمارد؛ `profit_factor=None` وقتی `gross_loss=0` | حذف بیصدای پنجرهها، تعداد آزمونهای چندگانه را کم میشمارد و `deflated_sharpe_ratio` را خوشبینانه میکند — دقیقاً همان سوگیریای که DSR قرار بود اصلاح کند. پنجره بیمتامعامله با `max_dd=100` وارد `max(drawdowns)` گیت میشود و میتواند بهتنهایی `REJECT` بسازد | `n_trials` بر اساس پنجرههای **برنامهریزیشده**؛ جداسازی پنجرههای بیمتامعامله از محاسبه drawdown؛ ثبت `skipped_windows` |
| **BT-13** | 🟡 متوسط | `backtesting/commission.py` (۳۵), `costs.py` (۴۰), `slippage.py` (۳۴); `runner.py:56,143-149`; `ci.yml:269-271` | سه ماژول ریشهای قدیمی در کنار پکیج `costs/`اند؛ `commission.py` فقط در ۲ فایل تست و `slippage.py` در **هیچ** فایلی ارجاع دارد. `DEPRECATED_ENGINES` فقط `warnings.warn(DeprecationWarning)` میدهد — که پایتون پیشفرض نادیده میگیرد | ۱۰ فایل همچنان تعریف `commission/cost` محلی دارند؛ موتورهای «deprecated بدون مصرفکننده production» همچنان از API قابل فراخوانی و عملاً بیهشدارند. F2 پاریتی هفت مصرفکننده را پوشش میدهد ولی این ماژولها بیرون از آناند | حذف سه ماژول یا افزودن به گارد پاریتی؛ `raise`/`UserWarning` برای موتورهای منسوخ |
| **BT-14** | 🟢 کم | `acceptance.yaml:2,25-33`; `acceptance_loader.py:272` | `asset_class: "gold"` و آستانههای سند «دستیار طلا و نقره» (`min_wfe ۰٫۵۰`, `min_dsr ۰٫۹۵`, `min_trade_count ۵۰`) بدون هیچ شرط بازار/نماد، برای **هر** استراتژی بکتست (`moving_average_cross` روی سهام و غیره) اعمال میشود | یک مشخصات مخصوص ابزار طلا، دروازه جهانی کل موتور بکتست شده است؛ `min_risk_reward: 2.0` همان `assumption` تأییدنشدهٔ قسمت ۰۷ (`SIG-12`) است | اسکوپ کردن گیت بر `asset_class`/`market`، یا جداکردن فایل پیکربندی بکتست از سند طلا |
| **BT-15** | 🟢 کم | `walk_forward.py:447`; `acceptance_loader.py:370-372,410-415` | هنگام نبود معامله زیانده، `profit_factor=None` است؛ `walk_forward_metrics` آن را `math.inf` میگذارد تا گیت PASS شود، ولی `_threshold_rows` با `_json_scalar` همان مقدار را **`value: None`** و `passed: true` سریال میکند | ردیف شواهد حسابرسی خودمتناقض است: «مقدار ناموجود، معیار برآورده شد». رفتار گیت درست است (استراتژی بینقص رد نمیشود)؛ نقص فقط در قابلیت حسابرسی است | `value: "Infinity"` / `observed: "no losing trades"` / `detail` صریح بهجای `None` |
| **BT-16** | 🟢 کم | `domain/trading/iran_costs.py:17-28`; `acceptance.yaml:48-81`; `config/backtest_costs.yaml:2` | دو جدول تعرفه مستقل: ۱۰ بازار سهام/ETF/گواهی در `MARKET_RATES` (بازبینی ۲۰۲۶-۱۱-۱۴، بازبینی بعد ۱۴۰۶/۰۱/۰۱) و ۵ ابزار طلا در `fee_schedule` با `provenance: assumption/unavailable`؛ هیچ تست پاریتی بینشان نیست | `futures` و `option` در سند طلا `fee_per_side: null` / `provenance: unavailable`اند، ولی `MARKET_RATES` و `OPTION_BUY_PCT=0.00125` عدد قطعی میدهند؛ دو منبع میتوانند همزمان «هزینه کانونی» ادعا کنند | ثبت صریح حاکمیت (کدام جدول برای کدام دامنه)، تست پاریتی، و `null` بهجای عدد جایگزین |

**توزیع شدت:** ۲ بحرانی · ۵ بالا · ۶ متوسط · ۳ کم = **۱۶ یافته**.

---

## ۵ — نقاط قوت تأییدشده

1. **نرخهای خرید/فروش واقعاً تکمنبعاند.** `iran_costs.py:16-23` مستقیماً از `domain.trading.iran_costs` وارد میکند؛ هیچ کپی محلی از `MARKET_RATES` در موتور نیست. مالیات انتقال ۰٫۵٪ **داخل** نرخ فروش ۰٫۸۸٪ است و `sell_tax_cost()` صریحاً «زیرمجموعه، نه اضافه» تعریف شده — ساختار ضد دوبارشمارش محکم است.
2. **گارد پاریتی F2 در CI اجرا میشود و هفت مصرفکننده را پوشش میدهد.** `tests/unit/backtesting/test_consumer_cost_parity.py` بروکر، `CommissionModel`, `ExecutionEngine`, `SignalBacktestEngine`, `RebalanceCost`, `PortfolioLedger` و توابع دامنه را با اعداد ثابت (۱٬۸۵۶ / ۴٬۴۰۰ / ۲٬۵۰۰) قفل کرده؛ `ci.yml:269-271` گارد اختصاصی و `ci.yml:276-280` اجرای کامل `pytest tests/unit` هر دو آن را اجرا میکنند.
3. **تک nقطه ورود موتورها (`D1`) برقرار است.** `runner.py:73-80` شش موتور را در یک رجیستری مهار، خروجیها را به `BacktestResult` نرمال و خطای موتور را به `RuntimeError` fail-fast تبدیل میکند (`:185-186`).
4. **ضد نشت اطلاعات جدی گرفته شده.** `next_open` پیشفرض است (`:52-55`)، walk-forward از `embargo_pct`/`purge_pct` استفاده میکند (`:341-369`)، `_compute_metrics` شارپ را با `ddof=1` میگیرد (`:72-74`)، و `deflated_sharpe_ratio` سوگیری آزمونهای چندگانه را اصلاح میکند (`:434-439`).
5. **گیت پذیرش روی معیار غایب fail-closed است.** `_read_metric` غیبت را `REJECT` میکند (`:256-260`)، `evaluate_acceptance` هر شش معیار را با دلیل مینویسد، و `evaluate_walk_forward_result` یک ردیف شواهد بهازای هر آستانه با نام فیلد خام تولید میکند (`:515-527`) — حسابرسیپذیری بسیار بهتر از میانگین پروژهها.
6. **لغزش و مشارکت فیزیکی مدل شدهاند.** Almgren-Chriss سادهشده، کران `min/max_slippage_bps`، سقف `max_participation`، partial-fill و ADV تفکیکشده بهازای نماد (F5) همگی در `broker.py` حاضرند؛ `SINGLE-CHARGE RULE` (`:203-205`) صریحاً جلوی محاسبه دوباره کمیسیون در Ledger را میگیرد.

---

## ۶ — تصحیح گزارش ۱۶۰ لایهای و حدسهای ردشده

### ۶‑الف — تصحیحات (۴ مورد)

| لایه | ادعای گزارش | واقعیت در `73a6c52d` |
|---|---|---|
| **۳۸ / ۴۲۵** | «ماژول بکتست **۳۰۲ / ۲۹٬۵۵۷ خط**» | تعداد فایلها همچنان ۳۰۲ است، ولی شمارش مجدد **۲۹٬۶۱۵ خط** میدهد (۵۸+ خط از مبنا؛ ۴۵ زیرپوشه). عدد قدیمی کهنه است. |
| **۱۱۲ / ۴۳۴ (F1/F2)** | «هیچ کپی محلی وجود ندارد»، «مستندات، کد و CI هر سه همسو و قفلشدهاند (**امتیاز کامل**)» | درباره **نرخها** درست است؛ ولی `config/backtest_costs.yaml` خود را «single source of truth» مینامد در حالی که `from_config()` بیفراخواننده است (`BT-01`)، ثابتهای لغزش/مشارکت در `broker.py:62-81` کپی محلی دارند، و سه ماژول ریشهای قدیمی بیرون از گارد پاریتیاند (`BT-13`). پاریتی **هزینه** قفل شده، پاریتی **پیکربندی هزینه** نه. |
| **۴۴۶ / ۱۲۰** | «چارچوب acceptance … **گلوگاه، وصل کردن خروجی واقعی رانها به این گیت است**» | گیت **وصل است** (`endpoints/backtests.py:943`) و `walk_forward_metrics` خروجی واقعی را مسطح میکند. گلوگاه جای دیگری است: حکم `REJECT` هیچ اقدامی را مسدود نمیکند (`BT-04`)، و گیت دوم مدل ML روی معاملات **ساختگی** قضاوت میکند (`BT-02`). |
| **۶۱۸ / ۲۱** | «مدل هزینه تکمنبع … [بهعنوان نقطه قوت قطعی]» | نرخها تکمنبعاند، ولی `sharpe_ratio` در `BacktestRunner` (ddof=0، rf=0) با `BacktestService`/گیت پذیرش (ddof=1، rf=۰٫۲۵) همخوان نیست (`BT-07`)؛ یعنی «تکمنبع» تا لایه متریکها گسترش نیافته است. |

### ۶‑ج — حدسهایی که حین راستیآزمایی **رد شدند** (۷ مورد)

1. «`test_consumer_cost_parity.py` در CI اجرا نمیشود چون گارد اختصاصی فقط دو فایل را نام میبرد» → **رد**: `ci.yml:276-280` اجرای کامل `pytest tests/unit` دارد و آن فایل را هم میگیرد. گارد اختصاصی صرفاً زودهنگام/`-x` است.
2. «استراتژی بدون معامله زیانده (`profit_factor=None`) بهاشتباه `REJECT` میشود» → **رد**: `walk_forward_metrics` مقدار `math.inf` جایگزین میکند و `_read_metric` آن را حاضر میبیند؛ گیت PASS میدهد. تنها نقص، ردیف شواهد است (`BT-15`).
3. «`same_close` دیگر قابل دسترسی نیست» → **رد**: هم از YAML و هم از پارامتر سازنده قابلتنظیم است، و **مهمتر آنکه هر مقدار ناشناخته** هم به همان شاخه میرود (`BT-05`).
4. «نرخهای کارمزد در `broker.py` کپی شدهاند» → **رد**: `BROKER_PCT`/`CLEARING_FEE_PCT`/`SELL_TAX_PCT` همگی از `iran_costs` وارد میشوند. تکثیر واقعی در **ثابتهای لغزش و مشارکت** (`IRAN_MARKET_COSTS`, `CONSERVATIVE_COSTS`, `TransactionCostConfig`) است، نه نرخها.
5. «گیت پذیرش کلاً وصل نیست» → **رد**: فراخوانی در endpoint و flattening و جدول شواهد همگی زندهاند. مسئله **اعمال نشدن حکم** است، نبود وصل.
6. «`WalkForwardOptimizer` و `PurgedWalkForward` فرمول embargo/purge متفاوتی دارند» → **رد**: هر دو `max(1, int(total * 0.01))` بهکار میبرند؛ کامنت «same sizing formula» درست است. تفاوت در `n_trials` و حذف پنجرههاست (`BT-12`).
7. «`config/backtest_costs.yaml` در ایمیج production موجود نیست» → **رد**: `Dockerfile.api:28` و همتایان `COPY config/ ./config/` با `WORKDIR /app` دارند (همان نتیجه قسمت ۰۷). خطر `BT-05` محدود به CWD غیراستاندارد و **بلع خطا** است.

---

## ۷ — مرز روش

- **هیچ چیز اجرا نشد**: نه pytest، نه بوت سرور، نه اتصال به DB/Redis زنده، نه اجرای بکتست. همه یافتهها ایستا و مبتنی بر خواندن فایل، `git status/diff` و جستجوی محدودشدهاند.
- `BT-03` (بیتأثیری `commission_pct`/`slippage_bps`) و `BT-05` (سقوط به شاخه `same_close`) **استنتاج از مسیر کد**اند، نه مشاهده زماناجرا؛ برای اثبات اجرایی نیاز به یک بکتست دوتایی با مقادیر متفاوت است.
- اعداد ۷٬۸۰۵ ران `completed` / صفر ردیف `backtest_trades` / ۶۰٫۲۱٪ حجم صفر از `NUMERIC_AUDIT_2026-11-12.md` و گزارش ۱۶۰ لایهای نقل شدند و در این قسمت **بازشماری نشدند**.
- جستجوی «صفر مصرفکننده» برای `get_gold_market_rules`, `BacktestValidator`, `from_config`, `slippage.py` در مسیرهای `backtesting/ services/ apps/ core/ src/ tests/` و با ابزار جستجوی محدود انجام شد؛ `.freebuff/worktrees/` (کپی پنهان مخزن) بهدلیل timeout عمداً **مستثنا** شد تا نتیجه با شاخهٔ اصلی آلوده نشود.
- محتوای ۳۱+ فایل تست بکتست اجرا یا تحلیل نشد؛ درباره کافیبودن پوشش حکمی داده نمیشود.

---

## ۸ — خوشههای تازه برای ماتریس تجمیعی

| خوشه | یافتهها | شدت مؤثر | پیوند با قسمتهای قبل |
|---|---|---|---|
| **W — پیکربندی هزینه مرده / هزینه سفارشی بیکار** | `BT-01`, `BT-03`, `BT-08`, `BT-13`, `BT-16` | 🔴 بحرانی | سومین تکرار `CFG-06`/`SIG-03`: ابزار ساخته شده، فایل کانفیگ وصل نشده؛ `R` (کد مرده) گسترش یافت |
| **X — گیت پذیرش بیاثر و ورودی ساختگی** | `BT-02`, `BT-04`, `BT-14`, `BT-15` | 🔴 بحرانی | مستقیم به `S` (دقت ساختگی قسمت ۰۷) و `R1`؛ همان «عددی که اندازهگیری نشده، تصمیم میگیرد» |
| **Y — انحراف عددی و نشت نگاهبهآینده** | `BT-05`, `BT-06`, `BT-07`, `BT-12` | 🟠 بالا | `K` (کهنگی مستندات) + `T` (ورودی ساختگی)؛ ۶۰٫۲۱٪ حجم صفر لایه ۳۲۸ |
| **Z — شکست خاموش در حلقه بهینهسازی** | `BT-09`, `BT-10`, `BT-11` | 🟡 متوسط | `G`/`EX-09` (استثناءهای بیلآگ) در لایه بکتست؛ `SIG-13` (گلوگاه فرایندمحلی) |

**ترتیب بستن پیشنهادی** (بدون تغییر کد، صرفاً اولویت): `X → W → S → T → Y → P → V → U → N → Q → H → B → Z → …`.

**عبارت خلاصه قسمت ۰۸:** قسمت ۰۷ گفت «عددی که به دروازهها میرسد اندازهگیری نشده است»؛ قسمت ۰۸ نشان میدهد **همان عدد، دروازهای هم ندارد**. مدل هزینه از نظر نرخها یکی از منضبطترین بخشهای مخزن است (تکمنبع، مالیات داخل نرخ فروش، گارد پاریتی در CI)، ولی `config/backtest_costs.yaml` تقریباً بهطور کامل مرده، پارامترهای هزینه سفارشی API بیکار، حکم `REJECT` گیت پذیرش صرفاً یک فیلد اضافی در JSON، و گیت دوم روی معاملات `±1.0` ساختگی قضاوت میکند. الگوی چهار قسمت اخیر اکنون کامل است: **ابزار ساخته میشود → وصل نمیشود → یا وصل میشود ولی حکمش اعمال نمیشود**.
