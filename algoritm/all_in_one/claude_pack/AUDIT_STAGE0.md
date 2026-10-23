# AUDIT_STAGE0 — خلاصه‌ی ممیزی بک‌تست و ML برای Claude Code

> منبع: `audit/REPORT_FULL.md` و `audit/findings_new.csv` (۴۹ یافته). اجرای ممیزی: ۲۰۲۶-۱۰-۰۹ و ۲۰۲۶-۱۰-۱۰ روی ماشین مالک (Windows، Python 3.11.9، PostgreSQL محلی؛ فقط SELECT).
> **هشدار:** ممیزی توسط مدلی دیگر انجام شد. هر یافته را پیش از اقدام خودت بازتأیید کن (باز کردن فایل:خط، اجرای آزمون). برچسب‌ها: `[RE]` خوانده‌شده+اجراشده، `[R]` فقط خوانده‌شده.

## ۱. حکم

**غیرقابل‌اتکا.** دلیل: ابزار اندازه‌گیری خراب است، نه اینکه ثابت شده باشد سیگنال بی‌ارزش است. هنوز **نمی‌دانیم ML لبه دارد یا نه**.

سه دلیل اصلی:
1. اندازه‌گیری: فروش از cash سایز می‌گیرد؛ MDD برابر MDD قیمت؛ سه موتور نتیجه‌ی متناقض؛ اجرا روی close کندل تصمیم؛ Vectorized بدون هزینه و بدون گارد آینده‌بین.
2. ML: مسیر آرتیفکت اشتباه ⇒ پیش‌بینی صفر ⇒ صفر معامله؛ مدل‌های موجود (۳۵۹) اعتبارسنجی‌نشده.
3. داده/کنترل: `gregorian_date` تاریخ سینک است؛ قیمت خام؛ سود نقدی ثبت نشده؛ survivorship؛ دروازه‌ی ۹ fail-open.

## ۲. یافته‌های محکم (همه [RE] مگر ذکر شود)

### اندازه‌گیری (بک‌تست)
| ID | یافته | فایل (مسیر از ممیزی) | شدت |
|---|---|---|---|
| A-03 | شاخه‌ی فروش `MlSignalStrategy` سایز را از cash می‌گیرد؛ پوزیشن هرگز کامل بسته نمی‌شود (fillها: ۳۱۵٬۶۷۸ → ۲۶٬۰۵۴ → … → ۱ سهم) | `backtesting/strategies/ml_based/ml_signal_strategy.py`, `backtesting/sizing.py`, `backtesting/strategies/base.py` | بحرانی |
| A-04 | MDD ۳۸.۷۳٪ برابر MDD خود قیمت (۳۸.۷۳۰۹) در هر ۵ آزمایش؛ علت: استراتژی همیشه ~۹۰٪ در بازار است (خودِ فرمول MDD لزوماً غلط نیست) | `backtesting/metrics/drawdown_metrics.py`, `services/backtest_service.py` | بحرانی |
| A-06 | سه موتور، یک سیگنال: Simulator +۲۸.۲۵٪، Vectorized ناخالص −۲۰.۹۴٪ | `services/backtest_framework.py`, `services/signal_backtest_engine.py` | بحرانی |
| B-01 | «baseline تصادفی» در Simulator عملاً buy-and-hold است (۰ از ۲۰۰ seed منفی) | `backtesting/sizing.py`, `ml_signal_strategy.py` | بحرانی |
| B-04/B-05 | آینده‌بین در Vectorized قابل‌سنجش (+۲۶۴٪ تا +۷۷۲٪ ناخالص) و هیچ گارد منشأ سیگنال ندارد؛ تست پیشنهادی شکست می‌خورد | `services/backtest_framework.py` | بحرانی/بالا |
| C-01 | `BacktestSimulator` سفارش را روی close همان کندل پر می‌کند؛ `BacktestEngine` روی open کندل بعد | `backtesting/engine/simulator.py`, `backtesting/engine/backtest_engine.py` | بحرانی [R] |
| A-02/A-05/G-04 | لغزش خرید اول به سقف ۱۵۰bps (ADV fallback = ۱٬۰۰۰٬۰۰۰)؛ ADV resolve‌شده ~۸.۴e9 (مشکوک)؛ هزینه‌ی کل ~ثابت چون ارزش اسمی ~ثابت و ۶۴٪ آن در یک fill | `backtesting/engine/broker.py`, `backtesting/engine/adv.py` | بالا |
| A-07/C9 | `SignalBacktestEngine`: نرخ هزینه‌ی ثابت `0.003` در برابر رفت‌وبرگشت SSOT `0.0147` (۴.۹ برابر کم) | `services/signal_backtest_engine.py` | بالا |
| D-04/C-08 | `profit_factor` در یک موتور `inf` و در دیگری floor ۱.۰؛ معامله‌ی ساختگی +۷۸۶٪؛ `json.dumps` می‌شکند | `services/signal_backtest_engine.py`, `backtesting/analytics/engine.py` | بالا |
| C7/C4 | `AttributeError: 'MarketSignal' ... 'to_dict'`؛ `'BacktestRun' ... 'current_value'` | `apps/api/endpoints/signal_insights.py:120`, `repositories/backtest_repository.py` | بحرانی/متوسط |
| E-04 | `run_backtest` روی داده‌ی خالی «موفق» برمی‌گرداند (ناپایدار) | `services/backtest_service.py` | متوسط |

### قوانین بازار و هزینه
| ID | یافته | فایل | شدت |
|---|---|---|---|
| A-01 | **تصحیح ادعای قبلی:** در `BacktestSimulator` کمیسیون + کارمزد تسویه + مالیات فروش اعمال می‌شوند (خرید ۰.۰۰۴۸۵، فروش ۰.۰۰۹۸۵) | `backtesting/engine/broker.py`, `backtesting/costs/iran_costs.py` | اطلاعاتی |
| C-02 | `IRAN_LIMIT_HISTORY` زمان‌دار ولی کد مرده؛ مقدار ۲۰۲۴ = `0.03` با کامنت «example» (placeholder) | `backtesting/data/price_limits.py` | بالا [R] |
| C-03 | `rule_versioning` (tick/T+2/session) وجود دارد، به بک‌تست وصل نیست | `backtesting/market/rule_versioning.py` | متوسط [R] |
| C2 | کارمزد/تسویه/مالیات/لغزش/ADV/tick/T+2/ساعت‌ها ثابت و بی‌زمان‌اند | `domain/trading/iran_costs.py` و موارد بالا | بالا |

### داده
| ID | یافته | شدت |
|---|---|---|
| G-01/G-02 | `gregorian_date`/`shamsi_date` در `brsapi_historical_daily` تاریخ سینک است؛ چند تاریخ معاملاتی یک `gregorian_date` دارند؛ `_fetch_future_prices` روی آن فیلتر می‌کند (با معامله‌ی ساختگی هم‌خوان است، اما ارتباط مستقیم اثبات نشده) | بحرانی |
| C-04 | بک‌تست قیمت **خام** می‌خواند؛ `vw_daily_history_adjusted` و `daily_adjust_factors` (۶۲۱٬۸۱۸ ردیف) بی‌استفاده | بالا |
| C-05/G-05 | `corporate_action_events` فقط `capital_increase` (۵۸۶ ردیف/۱۴۵ نماد)، همه `dps=0`؛ `corporate_actions` صفر ردیف ⇒ سود نقدی ثبت نشده | بالا |
| G-03 | `brsapi_historical_daily` hypertable نیست؛ بدون knowledge_time؛ upsert گذشته را بازنویسی می‌کند؛ bitemporal نیست | بالا |
| C-08 | survivorship: نمادهای ۹۰ روز اخیر = کل تاریخچه (۲۴۰۷)؛ جدول `symbols` فقط ۵۱۱ ردیف | بالا |
| — | خودرو در ۲۰۲۴ رویداد شرکتی نداشت (آخرین ۲۰۲۰، بعدی ۲۰۲۵-۰۴-۲۲)؛ پس آزمایش‌های خودرو ۲۰۲۴ از این جهت آلوده نیستند | اطلاعاتی |

### ML
| ID | یافته | شدت |
|---|---|---|
| F-01 | ۳۵۹ مدل در `ml_artifacts/`؛ `ArtifactManager` ریشه را `data/models` می‌گیرد ⇒ `FileNotFoundError` ⇒ `predicted_change_pct=0.0` ⇒ صفر معامله (`services/backtest_service.py::_inject_ml_predictions`, `ml/artifacts.py`) | بحرانی |
| F-02 | متادیتای **یک** مدل نمونه (`xgboost_خودرو`): دقت جهت ۰.۱۸۳، R² منفی ۰.۵۴؛ بقیه‌ی ۳۵۸ بررسی نشدند | بالا |
| F-04 | canary «بازده فردا» بی‌صدا پذیرفته شد (IC=۰.۹۹۹)؛ هیچ دروازه‌ی نشت‌یابی نیست | بالا |
| F-05 | label shuffle ⇒ IC≈۰ (مثبت) | مثبت |
| C-06 | برچسب ML روی `close[t]` ولی اجرا روی `open[t+1]`؛ قفل/توقف در برچسب لحاظ نمی‌شود (`ml/datasets/labeling.py`) | بالا |
| C-07 | `GridSearchCV(cv=5)` معمولی روی سری زمانی؛ بدون purge/embargo؛ `WalkForwardEngine.split` بدون embargo؛ DSR/PBO پیاده اما مصرف‌نشده؛ n_trials ثبت نمی‌شود (`ml/models/sweeper.py`, `services/backtest_framework.py`) | بالا |
| C-09/C-10 | دو باگ HIDDEN_ERRORS (`float_turnover_pct`, `net_inst_ratio`) رفع شده؛ بازآموزی خودکار مدل را کورکورانه جایگزین نمی‌کند (`_min_accuracy_gain=0.02`) | مثبت |
| F-03 | آزمایش Ridge (۵ نماد): RankIC مقطعی با N=۵ بی‌معناست؛ **نادیده گرفته شود** | — |

### کنترل‌ها و تست‌ها
| ID | یافته | شدت |
|---|---|---|
| D-03 | دروازه‌ی ۹ `quant_signal_orchestrator.py:1253-1261` fail-OPEN است در حالی که `AUDIT_REPORT.md` «fail-closed اصلاح شد» ثبت کرده [R] | بحرانی |
| D-02 | اعداد `docs/quant-signal-goal-assessment.md` کهنه: دقت ۳۶.۷٪→۳۸.۴۳٪؛ بازده/سیگنال −۴.۰٪→−۳.۷۳٪؛ Win Rate پیپر ۲۸.۴۳٪ و بازده پیپر −۱۵.۲۵٪ بازتولید شد | متوسط |
| E-01..E-05 | از ۱۷۵ شکست pytest، عمده محیطی (۴۰۱/۴۲۹)؛ `test_phase_engine` ۶ شکست واقعی؛ تست‌های اعتبارسنجی (تصادفی≈۰، label shuffle، canary فیچر، بقای دفتر) **ندارد** | بالا |
| H-01..H-04 | ۶ کلید حساس روی دیسک (`.env`, `.env.bak.*`, `.env.production`؛ در git نیستند)؛ ToS منابع اسکرپ‌شده نامشخص؛ اسکن تاریخچه‌ی git انجام نشد | متوسط |

## ۳. جدول پیشنهادی «حفظ / بازنویسی / تعلیق» (مبنا: ممیزی؛ مالک تأیید می‌کند)

| ماژول | تصمیم | دلیل |
|---|---|---|
| `backtesting/engine/backtest_engine.py` (`BacktestEngine`) | **حفظ** (مرجع پیشنهادی) | اجرا روی open بعد + تست look-ahead؛ **کد کامل خوانده نشده**؛ ابتدا تست parity |
| `backtesting/engine/simulator.py`, `broker.py` | **بازنویسی** بخش اجرا/ADV | اجرا روی close؛ ADV fallback؛ هسته‌ی `cost_model` حفظ |
| `backtesting/costs/iran_costs.py`, `domain/trading/iran_costs.py` | **حفظ + اتصال به `rule_at`** | فرمول درست؛ نرخ‌ها بی‌زمان |
| `services/backtest_framework.py` (`VectorizedBacktest`, CPCV, `StatisticalValidator`) | **بازنویسی** Vectorized؛ CPCV/DSR حفظ | بدون هزینه/گارد؛ DSR مصرف‌نشده |
| `services/signal_backtest_engine.py` | **بازنویسی** | نرخ ثابت، ستون سینک، `profit_factor` |
| `backtesting/strategies/ml_based/ml_signal_strategy.py` | **بازنویسی** شاخه‌ی فروش | A-03 |
| `backtesting/sizing.py`, `strategies/base.py` | **حفظ + اصلاح** (فروش از پوزیشن) | — |
| `backtesting/metrics/drawdown_metrics.py` | **حفظ** + افزودن گزارش نسبی | فرمول احتمالاً درست |
| `backtesting/data/price_limits.py`, `market/rule_versioning.py` | **حفظ ساختار، بازنویسی داده، اتصال، مهاجرت به جدول `rules`** | کد مرده/placeholder |
| `services/backtest_service.py` | **بازنویسی** بارگذاری داده، تزریق ML، خطای داده‌ی خالی | C-04, F-01, E-04 |
| `ml/artifacts.py` + `ml_artifacts/` (۳۵۹ مدل) | **اصلاح مسیر؛ مدل‌ها `UNVERIFIED`/بایگانی** | F-01, F-02 |
| `ml/datasets/labeling.py` | **بازنویسی** | C-06 |
| `ml/models/sweeper.py` | **بازنویسی** (purged/CPCV + ثبت n_trials) | C-07 |
| `services/feature_engine.py` | **حفظ + knowledge_time + گارد نشت + تست** | F-04, C5 |
| `services/auto_retrain_pipeline.py` | **حفظ + مرحله‌ی shadow/paper** | گارد ۰.۰۲ خوب است |
| `services/quant_signal_orchestrator.py` (دروازه‌ی ۹) | **اصلاح** fail-closed | D-03 |
| ensemble، calibrator، رژیم، ۱۰ دروازه، Agent-Based، ژنتیک (`cascade_engine`) | **تعلیق** (`suspended`) تا عبور baseline | اعتبارسنجی‌نشده؛ بخش C8 ناقص ماند |
| `brsapi_historical_daily` و جدول‌های مرتبط | **افزودن** `trade_date`, `first_seen_at`؛ بدون حذف ستون | G-01, G-03 |
| `fix_critical_errors.py`, `fix_test_syntax.py`, `gen_all.py`, `mkpages.py`, `funds-all-code.txt`, چهار پوشه‌ی گزارش | **بایگانی/حذف** پس از تأیید مالک (و تأیید import) | I-01..I-03؛ استفاده با import تأیید نشد |

## ۴. بررسی‌نشده (باید در گام‌ها انجام شود)

- `knowledge_time` فیچرهای حقیقی/حقوقی، بنیادی، کدال، NAV؛ نرمال‌سازی مقطعی روزانه و winsorize؛ فیت رژیم/ensemble/calibrator روی چه داده‌ای.
- فهرست اسمی نمادهای حذف‌شده؛ بازاجرای کل suite؛ اسکن git برای رمز؛ ۱۵ PR و ۱ issue باز؛ اجرای واقعی `SignalBacktestEngine` با هزینه‌ی SSOT.
- **موارد مخصوص بازار ایران که ممیزی نپوشاند** (`SPEC_IRAN_MARKET.md`): `fillable_rate` و مدل صف/قفل؛ آیا Vectorized سیگنال منفی (short) را رد می‌کند؛ `lock_up_today/lock_streak` و بازده سانسورشده؛ سود نقدی؛ تقویم جلالی/تعطیلی غیرعادی و شمارش افق؛ `regime_epoch`/`policy_events`؛ `N_eff`؛ سه‌معیاره؛ ریسک خروج سیستماتیک (joint-lock)؛ شناوری/بازارگردان/عرضه اولیه؛ منطقه‌ی زمانی/ساعت تابستانی؛ نرمال‌سازی متن فارسی نماد.

## ۵. سوال‌های باز برای مالک

1. تأیید جدول بالا (به‌ویژه موتور مرجع، ADR-001).
2. `gregorian_date` عمداً زمان سینک است یا باگ ingest است؟ (ADR-002)
3. آیا تاکنون مدلی عمداً آموزش و فقط در `ml_artifacts/` ذخیره شده؟ هدف آن ۳۵۹ مدل چه بود؟
4. منابع رسمی قوانین (اطلاعیه‌ها) در دسترس شماست؟ از چه بازه‌ای؟
5. `acceptance.yaml` و نرخ‌های مرجع (ارز، بدون ریسک، تورم) چه می‌شود؟
6. آیا `own_order_log` (سفارش‌های واقعی خودتان) وجود دارد؟ (برای گام صف/خروج)
7. ماژول‌های ریشه‌ای (`fix_*.py` …) و پوشه‌های گزارش: حذف یا بایگانی؟
