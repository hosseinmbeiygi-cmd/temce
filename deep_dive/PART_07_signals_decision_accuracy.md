# قسمت ۰۷ — سیگنال، یازده دروازه تصمیم و حلقه دقت

| | |
|---|---|
| **مبنای اندازهگیری** | `73a6c52d` — همان مبنای قسمتهای ۰۵ و ۰۶؛ HEAD بین سه قسمت جابهجا نشد. |
| **وضعیت worktree** | **۱۲۲ فایل Dirty** (از ۱۰۴ در قسمت ۰۶ به ۱۲۲ رسید — فرایند همزمان همچنان فعال است). دو فایل محوری این قسمت **جزو اصلاحشدهها هستند**: `services/quant_signal_orchestrator.py` (`-	regime VARCHAR(50)` از DDL جدول `signal_accuracy`) و `models/signal_accuracy.py` (`+	updated_at` به ORM). هر دو اصلاحِ drift اسکیمای قسمت ۰۴ (`I`)اند و شواهد زیر بر **نسخه دیسکی** اندازهگیری شدهاند. شماره خطهای بالای ۱۵۴۵ در HEAD یک خط بیشترند. همچنین `test_signal_api.py` از ریشه به `tests/` منتقل شده است. |
| **تعهد** | فقط فایلهای Markdown تحلیلی ساخته/ویرایش شدند. **هیچ فایل کد، پیکربندی، تست، compose یا مهاجرتی تغییر نکرد.** |
| **زبان** | فارسی (هماهنگ با سری) |

---

## ۱ — فهرست فایلها و ابعاد (شمارش واقعی، فقطخواندنی)

| فایل / درخت | خط | نقش |
|---|---:|---|
| `services/quant_signal_orchestrator.py` | **۲٬۱۸۷** | تک نقطه ورود خط لوله؛ ۲۲ متد، ۴ کلاس |
| `services/multi_market_signal_engine.py` | ۱٬۵۷۳ | تولید سیگنال قانونمحور (مرحله ۱) |
| `services/signal_decision_engine.py` | **۱٬۲۰۸** | `SignalPolicy` + `SignalDecisionEngine` با **۱۱** گیت |
| `services/decision_gate.py` | ۳۷۲ | `SmartDecisionGate` / `GateOverride` |
| `services/signal_feature_pipeline.py` | ۴۹۱ | استخراج فیچر ML |
| `services/signal_backtest_engine.py` | ۴۳۴ | بکتست سیگنال |
| `services/signal_voting_system.py` | ۳۵۲ | رأیگیری وزندار / unanimous / ML-override |
| `services/signal_performance_tracker.py` | ۳۳۱ | جدول خصوصی `signal_performance` |
| `services/signal_circuit_breaker.py` | ۳۲۲ | قطعکننده مبتنی بر دقت |
| `services/signal_accuracy_tracker.py` | ۳۰۳ | `SignalOutcome` + کوئریهای دقت |
| `models/signal_accuracy.py` / `models/signal.py` | ۱۰۷ / ۴۰ | ORM |
| **جمع هسته سیگنال (۱۶ فایل)** | **۸٬۰۱۷** | — |

فایلهای باقیمانده با نام `signal*`: ۱۸ فایل در `services/`، ۳ در `apps/api/endpoints/`، ۲ در `domain/`، ۱ در `core/enums/`، ۱ در `jobs/definitions/`؛ **۳۱ فایل تست** با نام `*signal*.py`.

شمارش ایستا: `evaluate()` دقیقاً **۱۱** `GateResult` تولید میکند (`signal_decision_engine.py:453-486`)؛ `config/signal_policy.yaml` (۹٬۷۶۶ بایت) **۶** بخش بازاری دارد (`stock`, `gold`, `crypto`, `currency`, `commodity`, `option`) ولی **`ime` ندارد**، در حالی که سربرگ فایل و فهرست fallback اورکستراتور هفت بازار را نام میبرند. `migrations/versions/0007_signal_accuracy.py` اسکیمای مرجع جدول دقت است.

---

## ۲ — ردیابی جریان اجرا

### ۲‑الف — خط لوله `generate()` (مسیر واقعی API)

```
apps/api/endpoints/multi_market_signals.py:93/203/366, apps/api/app.py:368/1203/1214
  └─ QuantSignalOrchestrator()                 ← بدون session در هر ۶ فراخوانی API
     └─ generate(use_ml=True, use_voting=True, use_decision_engine=True [پیشفرض])
        ├─ _ensure_db_tables()          :653  → CREATE TABLE ×2 + CREATE UNIQUE INDEX + ۳ COMMIT  ← SIG-14
        ├─ ① MultiMarketSignalEngine.generate_all(limit*10)        :661
        ├─ ② _get_ml_predictions()     :695  → history < 5 کندل ⇒ skip (خاموش، debug)  ← SIG-10
        ├─ ③ _apply_voting()           :702  → ml_score پیشفرض ۰٫۵ حتی بدون پیشبینی  ← SIG-05
        ├─ ③.⁵ _apply_probability_calibration()  :710 → شکست ⇒ calibrated = raw   ← SIG-10
        ├─ ③.⁶ cap ۱۲۰ کاندید        :719
        ├─ ④ _apply_confidence_calibration()    :727 → شکست ⇒ confidence دستنخورده  ← SIG-10
        ├─ ④.⁵ _apply_signal_decision()        :748 → یازده گیت + signal_grade
        │    └─ load_portfolio_risk(self._session) :1185  ← fail-closed (نقطه قوت)
        ├─ ⑤ CrossMarketCorrelator.analyze()   :755
        ├─ ⑥ فیلتر confidence + سهمیه هر بازار + limit   :759-774
        ├─ ⑥.⁵ _persist_pending_signals()      :778 → INSERT signals + signal_accuracy
        ├─ _get_accuracy_snapshot()            :822 → ۹۰روزه، حداقل ۲۰ نمونه
        └─ ⑦ _record_outcomes_and_retrain()   :825 → گلوگاه ۶ساعته / آستانه ۵۵٪ / force=True
```

### ۲‑ب — یازده گیت (`evaluate()`، `signal_decision_engine.py:438-515`)

```
effective_threshold = get_effective_threshold(volatility, liquidity, drift, market)   :445
  ← قبل از override محاسبه میشود                                                  ← SIG-09
override = _resolve_gate_override()   :456 → SmartDecisionGate.evaluate()
  ← session=None ⇒ _MarketState() خنثی، vol_ratio=0.0                            ← SIG-02
 1 data_quality   :453  → dqs از ۴ فیلد + طول واقعی تاریخ
 2 model          :459  → ignore_ml ⇒ PASS امتیاز ۱٫۰ (در production خاموش است)
 3 probability    :462  → prob < threshold ⇒ BLOCK
 4 regime         :465  → override.regime_label != UNKNOWN ⇒ uses it;
                          else _detect_regime() با SQL جداگانه (LIMIT 1)       ← SIG-02
                          و candidate.volatility_regime را تغییر میدهد          ← SIG-09
 5 consensus      :468  → rule ⇒ PASS / hybrid ⇒ نیاز ۱ مدل موافق              ← SIG-05
 6 liquidity      :471  → بدون حجم ⇒ ۰٫۳ / ۰٫۴ (degrade صریح — نقطه قوت)
 7 risk_reward    :474  → max(cfg, floor=2.0) ⇒ هر دو آستانه ۲٫۰ میشوند       ← SIG-12
 7b net_profit    :477  → (target_pct − costs_pct) × 100 ≥ ۲٫۰٪               ← SIG-11
 8 expectancy     :480  → min = −۰٫۵۰R در YAML                                  ← SIG-12
 9 portfolio      :483  → ledger واقعی، fail-closed (نقطه قوت)
10 execution      :486  → spread > 0 > 0 ⇒ همیشه PASS                          ← SIG-04
────────────────────────────────────────────────────────────────────────────
verdict: هر BLOCK ⇒ REJECT | تعداد WARN > ۲ ⇒ WATCHLIST | وگرنه RELEASE   :489-497
  ⇒ WATCHLIST در «released» میماند، به کاربر برمیگردد و پایدار میشود          ← SIG-06
```

---

## ۳ — سیاست شکست (گامبهگام)

| گام | رویداد شکست | سیاست | سطح لاگ | اثر |
|---|---|---|---|---|
| `_ensure_db_tables` | نبود DB / خطای DDL | **swallow** | `debug` | ادامه خط لوله بدون جدول |
| `_get_ml_predictions` | خطای connector / کمبود کندل | **swallow + skip** | `debug` | `ml_predictions={}` |
| `_apply_voting` | خطای رأیگیری | **fallback** به `_basic_enrich_single` | `debug` | نمره ML صفر، ولی سیگنال زنده |
| `_apply_probability_calibration` | خطای calibrator | **fail-open** به `raw` | `debug` | احتمال کالیبرهنشده وارد گیت ۳/۸ |
| `_apply_confidence_calibration` | خطای scorer | **fail-open** (حفظ confidence) | `debug` | خروجی بدون علامت تنزل |
| `_resolve_gate_override` | هر استثناء | **fail-open** به `GateOverride()` | `debug` | override هوشمند خاموش |
| `_detect_regime` | خطای DB | **fallback** به هیوریستیک | `debug` | رژیم حدسی |
| `_apply_signal_decision` | خطای تکسیگنال | **fail-closed** → `reject` | `debug` | سیگنال حذف میشود |
| `_apply_signal_decision` | خطای دستهای | **fail-closed** → رد همه | `warning` | خروجی خالی |
| `_persist_pending_signals` | خطای INSERT تکرار | `continue` درون تراکنش | `debug` | ریسک ابطال کل تراکنش ← SIG-15 |
| `_evaluate_past_signals` | خطای تکرر | `continue` | `debug` | ردیف تا ابد pending ← SIG-07 |
| `_record_outcomes_and_retrain` | خطای کلی | **swallow** | `warning` | حلقه بازخورد بیکار |

**الگوی غالب:** «شکست لایه داده/ML ⇒ خاموش و بیعلامت»، «شکست لایه تصمیم ⇒ رد امن». مرز دقیقاً همانجاست که داده بیاعتبار میتواند وارد تصمیمی شود که خودش را امن میپندارد.

---

## ۴ — جدول یافتهها (`SIG-01`…`SIG-16`)

| ID | شدت | خط دقیق | شاهد | اثر عملی | جهت اصلاح |
|---|---|---|---|---|---|
| **SIG-01** | 🔴 بحرانی | `quant_signal_orchestrator.py:2050-2052`, `:2019-2029` | `target1_est = price×1.05`, `target2 ×1.10`, `stop ×0.97` — جدول `signal_accuracy` (`0007`: تمام ستونها) **هیچ ستون هدف/حدضرر ندارد**؛ مسیر fallback `ORDER BY id DESC LIMIT 1` قیمت **اکنون** را میگیرد، نه قیمت سررسید | `hit_target1/2`, `stopped_out`, `max_profit/loss` در ۵ بازار از ۷ بازار ساختگیاند؛ `direction_correct` با قیمت لحظه ارزیابی (سوگیری نگاهبهآینده)؛ همان نمره، `_get_accuracy_snapshot` → آستانه ۵۵٪ → `check_and_retrain(force=True)` را بهراه میاندازد | ذخیره `targets`/`stop_loss` واقعی هنگام persist؛ exit-price منطبق بر `due_date`؛ جداکردن متریک «جهت» از متریک «سطوح»؛ عدم force-retrain بر متریک ساختگی |
| **SIG-02** | 🔴 بحرانی | `decision_gate.py:196,257`; `quant_signal_orchestrator.py:1172-1175`; ۶ فراخوانی `QuantSignalOrchestrator()` | `_query_market_state` و `_fetch_volume_ratio` در `session is None` بیدرنگ `_MarketState()`/`0.0` برمیگردانند؛ تنها `jobs/definitions/paper_trading_job.py:39` session میدهد | ۳۷۲ خط «override آگاه به شرایط بازار» در **تمام مسیرهای API مرده** است؛ `ignore_ml`/`ml_boost` هرگز رخ نمیدهد؛ گیت ۴ به `_detect_regime` با SQL دیگر (`LIMIT 1` در برابر `LIMIT 3`) و کش دیگر سقوط میکند ⇒ **دو منبع رژیم** و رفتار متفاوت job در برابر API | تزریق `async_session_factory` یا session به `SmartDecisionGate`؛ یکی کردن منبع رژیم؛ تست پاریتی job/API |
| **SIG-03** | 🟠 بالا | `:2181` `_get_signal_policy(policy_path="config/signal_policy.yaml")`; `signal_decision_engine.py:241-253` | مسیر **نسبی به CWD**؛ `except Exception` فقط `logger.warning` و بازگشت به `_load_defaults()` | اگر فایل بار نشود، آستانهها خاموش و بیصدا عوض میشوند: `base_threshold ۰٫۴۲→۰٫۶۲`، `min_net_expectancy_r −۰٫۵۰→+۰٫۰۵`، `minimum_trade ۰٫۵→۱٫۰`، `A+ ۰٫۵۵→۰٫۷۰`. یعنی یک خطای مسیر، **تمام رفتار معاملاتی** را تغییر میدهد. `acceptance.yaml` درستعمل میکند (`_REPO_ROOT` مطلق) — همان الگوی `CFG-06` قسمت ۰۵ | `Path(__file__).resolve().parents[2] / "config/signal_policy.yaml"` + fail-fast در خطا (مطابق `_value_filter`) |
| **SIG-04** | 🟠 بالا | `signal_decision_engine.py:1001-1025`, `:315`; `config/signal_policy.yaml:65` | `if candidate.spread_pct > min_spread > 0` با `min_spread_pct: 0.0` ⇒ **همیشه نادرست**؛ `require_market_open: true` در کل مخزن **فقط همان یک خط تعریف** را دارد | گیت دهم همیشه `PASS / score=1.0` است. چهار تقویم متناقض همزمان وجود دارد: `acceptance.yaml:94-96` (۱۲:۰۰–۱۸:۰۰، پنجشنبه ۱۲:۰۰–۱۵:۰۰)، `core/time/__init__.py:98` (۰۹:۰۰–۱۲:۳۰)، `core/time/market_sessions.py:61-63` (۰۸:۳۰–۱۲:۳۰)، `jobs/market_hours.py:22-25` (۰۸:۴۵–۱۲:۳۰) — هیچکدام به گیت وصل نیستند | خواندن `require_market_open` و فراخوانی `get_market_hours()` بهعنوان تکمنبع؛ حذف سه تقویم موازی؛ مقداردهی `min_spread_pct` |
| **SIG-05** | 🟠 بالا | `:1006-1011`, `ml_signal_connector.py:382-395`, `:1272-1278` | `get_signal_boost(ml_pred or {"ml_score": 0.5, ...})` ⇒ `ml_contribution = 0.5` حتی بدون هیچ پیشبینی؛ سپس `active_models = 1 if sig.ml_score > 0` و `signal_type="hybrid"` | گیت ۲ (مدل) و گیت ۵ (اجماع) روی **مدل موهوم** PASS میشوند؛ `calibrated_probability` و `net_expectancy` نیز از همان نمره تغذیه میشوند. دقیقاً همان «عدد ساختگی بهجای داده» که لایه ۹۷ گزارش اصلی درباره ۴۶٬۹۰۶ پیشبینی هشدار داده | `ml_score = 0.0` و `signal_type="rule"` وقتی `ml_pred is None`؛ علامتگذاری صریح `ml_available` |
| **SIG-06** | 🟠 بالا | `signal_decision_engine.py:492-497`, `:1169-1172`; `:1304-1307`, `:759-778` | WATCHLIST فقط وقتی `len(warnings) > 2`؛ `_apply_signal_decision` آن را در `released` نگه میدارد؛ `generate()` فقط `confidence >= min_confidence` را فیلتر میکند | سیگنال «فقط تحت نظر» **همان مسیر RELEASE** را طی میکند: به API برمیگردد، در `signals`/`signal_accuracy` پایدار میشود و در خلاصه `watchlisted` جداگانه شمرده میشود. بلوک `grades.watchlist` در YAML و `signal_grade()` هرگز خوانده نمیشود | فیلتر صریح بر `decision_verdict` پیش از persist؛ یا جداسازی خروجی watchlist در قرارداد API |
| **SIG-07** | 🟠 بالا | `:1581-1586` (شاخص یکتای جزئی), `:1910`, `:1940`, `:1648-1653` | `uq_signal_accuracy_pending_key ... WHERE outcome_set_at IS NULL` + پنجره `generated_at >= now − 90d` + `LIMIT 100` + گلوگاه ۶ ساعته | ردیفهای قدیمیتر از ۹۰ روز **هرگز** ارزیابی نمیشوند و برای همیشه `NULL` میمانند؛ شاخص جزئی سپس درج هر سیگنال تازه با همان `(symbol, market, direction, timeframe)` را تا ابد مسدود میکند. ظرفیت اسمی ۴۰۰ ردیف/روز است، در حالی که تنها `/summary` با `limit=200` فراخوان میشود | ارزیابی ردیفهای کهنه یا علامتگذاری `expired`؛ حذف شرط ۹۰روزه؛ صف ارزیابی بهجای `LIMIT 100` |
| **SIG-08** | 🟡 متوسط | `signal_decision_engine.py:1,409,439`; `config/signal_policy.yaml:4`; `:730,1159` | docstring و کلاس و YAML میگویند «10-gate»؛ `evaluate()` یازده `gate_results.append` دارد و `_gate_net_profit` با برچسب «Gate 7b» | شمارهگذاری `Gate 9 = Portfolio` / `Gate 10 = Execution` با فهرست واقعی ۱۱تایی نمیخواند؛ هر تحلیلگر/مستندساز بیرونی تعداد گیتها را کم میشمارد. **گزارش ۱۶۰ لایهای (لایه ۹۸) درست گفته ۱۱** — نقص در docstring کد است | اصلاح docstringها و سربرگ YAML به ۱۱ و شمارهگذاری مجدد |
| **SIG-09** | 🟡 متوسط | `signal_decision_engine.py:445-450` در برابر `:714`; `:1041-1048` | `get_effective_threshold()` پیش از `_resolve_gate_override` اجرا میشود، ولی `_gate_regime` در خط ۷۱۴ `candidate.volatility_regime = override.volatility_regime` مینویسد | آستانه پویا از نوسان **قبل** از override محاسبه میشود؛ نسخه اصلاحشده هرگز به گیت ۳ نمیرسد. همچنین `_resolve_gate_override` **هر** استثنائی را در `debug` میبلعد و `GateOverride()` خنثی برمیگرداند | محاسبه آستانه پس از override، یا عدم جهش candidate؛ ارتقای لاگ شکست به `warning` |
| **SIG-10** | 🟡 متوسط | `:912-913`, `:1138-1141`, `:1093-1095`, `:1310`, `ml_signal_connector.py:416-419` | چهار لایه شکست تنها `logger.debug` دارند: ML، کالیبراسیون احتمال (`calibrated_probability = raw`, `method="none"`)، کالیبراسیون اطمینان، رأیگیری | قطعی کامل calibrator/ML هیچ اثری در پاسخ API ندارد: احتمال خام وارد گیت ۳، `_compute_net_expectancy` و درجهبندی A+/A/B میشود. مصرفکننده نمیتواند «کالیبرهنشده» را از «کالیبرهشده» تشخیص دهد جز خواندن `calibration_method` | پرچم `degraded` در `summary` + متریک؛ حداقل `warning`؛ یا fail-closed در production |
| **SIG-11** | 🟡 متوسط | `:1476-1497`, `:1500-1520`, `signal_decision_engine.py:892,1125` | `_parse_stop_loss_pct` در نبود/عدم تطابق رشته **`0.05` ساختگی** برمیگرداند؛ `_parse_target_pct` فقط `nums[0]` را میگیرد و در شکست `0.0` میدهد؛ `cost_r = costs_pct / abs(stop_loss_pct)` | حدضرر فرضی ۵٪ وارد محاسبه مالی `_compute_net_expectancy` میشود (در تناقض با کامنت صریح «never fabricated» برای گیت ۹)؛ هدف پارسیننشده ⇒ `net_profit_pct = −۰٫۳٪` ⇒ BLOCK دائم. `targets`ای مانند «هدف اول ۱۲٬۰۰۰ / دوم ۱۳٬۰۰۰» اولین عدد را بهعنوان درصد/قیمت میگیرد | بازگرداندن `None` بهجای مقادیر پیشفرض؛ انتقال `targets`/`stop_loss` به ساختار عددی پیش از متن |
| **SIG-12** | 🟡 متوسط | `acceptance.yaml:84-90`; `signal_decision_engine.py:849-851,888-891`; `signal_policy.yaml:52-58,68-86` | کف `min_risk_reward: 2.0` با `provenance: assumption` (تأییدنشده) از طریق `max()` بر **تمام** overrideهای شش بازار غالب میشود؛ `min_trade == min_watchlist == 2.0` ⇒ شاخه WARN مرده؛ `grades.b.min_rr=1.0` دستنیافتنی است | یک «فرض منتظر تأیید» به گیت BLOCK سراسری تبدیل شده؛ `require_positive_ev: true`, `market_hours`, `probability.margin.watchlist`, `liquidity.minimum_avg_volume`, `grades.watchlist` و **همه** تنظیمات `risk_reward` بازارها پیکربندی مردهاند؛ `ime` اصلاً بخش ندارد | اعلام صریح وضعیت assumption در API؛ یا جداکردن کف سند از تنظیمات بازار؛ حذف کلیدهای مرده / افزودن `ime` |
| **SIG-13** | 🟡 متوسط | `:1621-1626`, `:1648-1654`, `:1726-1737`, `:1664` | `_last_outcome_record`, `_last_scheduled_retrain`, `_outcome_throttle_started` متغیرهای **کلاس/فرایند**اند؛ `ACCURACY_THRESHOLD = 55.0` هاردکد | با `api: replicas: 2` (قسمت ۰۶) هر رپلیکا گلوگاه خود را دارد ⇒ ارزیابی و `force=True` بازآموزی دوگانه؛ `_last_scheduled_retrain` با هر restart پاک میشود و چون مقدار `None` ⇒ `False`، بازآموزی دورهای ۷روزه عملاً نیازمند ۷ روز بیوقفگی **پس از** یک بازآموزی قبلی است | انتقال گلوگاهها به Redis/DB؛ آستانه به پیکربندی؛ لاگ تصمیم بازآموزی |
| **SIG-14** | 🟢 کم | `:653`, `:1523-1616`, `migrations/versions/0007`, `0119` | `_ensure_db_tables()` در **ابتدای هر `generate()`** اجرا میشود: ۲ `CREATE TABLE IF NOT EXISTS` + ۱ `CREATE UNIQUE INDEX IF NOT EXISTS` + ۳ `commit()`؛ همان جداول در مهاجرتها تعریف شدهاند | DDL و commit روی هر درخواست (و با ۲ رپلیکا، همزمان)؛ دو مرجع اسکیما برای یک جدول. worktree اکنون `regime` اضافی را از DDL حذف و `updated_at` را به ORM افزوده — یعنی خوشه `I` قسمت ۰۴ زیر دست ما در حال بستهشدن است | حذف DDL زماناجرا؛ تکیه بر Alembic؛ تست پاریتی مهاجرتها |
| **SIG-15** | 🟢 کم | `:1770-1846`, `:1848-1849`, `:1837` | حلقه `for sig` داخل **یک** `async with async_session_factory()`؛ خطای INSERT در `except` گرفته شده و `continue` میشود، سپس یک `commit()` در انتها | در PostgreSQL خطای درون تراکنش، تراکنش را abort میکند؛ ادامه حلقه بعد از آن معمولاً با شکست زنجیرهای روبهرو میشود و commit نهایی کل دسته را برمیگرداند — یعنی «رد کردن تک رکورد» همانطور که نوشته شده کار نمیکند. همچنین `signal_strength = confidence × boosted_score/100` حاصلضرب است، نه قدرت سیگنال | `SAVEPOINT` / `begin_nested()` بهازای رکورد، یا `ON CONFLICT DO NOTHING` و جداکردن تراکنشها |
| **SIG-16** | 🟢 کم | `services/signal_circuit_breaker.py` (۳۲۲ خط); `:645`, `:80-81` | `evaluate`, `evaluate_cached`, `evaluate_default` **فقط در ۳ فایل تست** ارجاع دارند و در هیچ مسیر اپلیکیشنی فراخوانده نمیشوند؛ `EnrichedSignal.decision_verdict` پیشفرض `""` و `generate()` بر verdict فیلتر نمیکند | قطعکننده «توقف انتشار هنگام افت دقت» ساخته شده ولی وصل نیست؛ `use_decision_engine=False` همچنان میانبری کتابخانهای است که سیگنالهای بدون گیت را برمیگرداند و پایدار میکند (**در production رخ نمیدهد** — بند ۶‑ج) | وصل کردن `evaluate_cached` به `generate()`؛ یا حذف ماژول؛ گیت `if not decision_verdict: raise` |

**توزیع شدت:** ۲ بحرانی · ۵ بالا · ۶ متوسط · ۳ کم = **۱۶ یافته**.

---

## ۵ — نقاط قوت تأییدشده

1. **گیت ۹ واقعاً fail-closed است.** `services/portfolio_risk.py` دفتر معاملات کاغذی (`paper_trades`, `paper_equity_history`) را میخواند و در نبود دفتر `approved=False` برمیگرداند؛ `_apply_signal_decision:1185-1191` حتی این حالت را با `warning` اعلام میکند و ریسک را **یکبار بهازای هر اجرا** میخواند، نه بهازای سیگنال.
2. **کیفیت داده و نقدینگی دیگر پروکسی نیستند.** `:1221-1233` طول واقعی تاریخچه را به `compute_data_quality_score` میدهد (کامنت صریحاً میگوید پروکسی قدیمی `max(20, n_votes*10)` امتیاز ۱٫۰ دروغین میداد)؛ `:1238-1253` در نبود حجم، `0.3/0.4` «تنزل صریح» میگذارد بهجای محاسبه جعلی.
3. **شکست موتور تصمیم fail-closed است.** خطای تکسیگنال ⇒ `REJECTED_ON_ERROR` (`:1309-1313`)؛ خطای دستهای ⇒ رد همه (`:1323-1328`).
4. **تکمنبع آستانههای §۲۶ رعایت شده.** `_value_filter()` هیچ عدد پیشفرضی در ماژول نمیگذارد و `acceptance_config_path()` مسیر مطلق مخزنمحور دارد؛ `max(cfg, floor)` اجازه نمیدهد بازاری کف سند را سست کند.
5. **جلوگیری از تورم دقت.** `hold/wait` پیش از درج حذف میشوند (`:1775`، اشاره صریح به «IME ۱۰۰٪ از ۸۷۵ hold»)، `_get_accuracy_snapshot` بازارهای کمتر از ۲۰ نمونه را کنار میگذارد (`:2131-2135`)، و تجمیع دقت بر `correct/total` است نه last-wins.
6. **F3/F10 بستهاند.** درج والد `signals` پیش از `signal_accuracy` (`:1786-1811`) و `jalali_to_gregorian(date)` با `price_max/price_min` (`:1984-1997`)؛ شاخص یکتای جزئی نیز جلوی تکثیر همزمان `CacheWarmupJob` و `warm_signal_cache` را میگیرد.

---

## ۶ — تصحیح گزارش ۱۶۰ لایهای و حدسهای ردشده

### ۶‑الف — تصحیحات (۳ مورد)

| لایه | ادعای گزارش | واقعیت در `73a6c52d` |
|---|---|---|
| **۹۸** | «`DecisionResult` با `verdict ∈ {BLOCK, WARN, PASS}` و `is_approved = all(verdict != BLOCK)`» | کلاس `Decision` است؛ `verdict: FinalVerdict ∈ {RELEASE, WATCHLIST, REJECT}` و `GateResult.verdict: GateVerdict ∈ {PASS, WARN, BLOCK}`. متد `all_gates_pass()` وجود دارد، نه `is_approved`. حکم نهایی صرفاً `all != BLOCK` نیست: `REJECT` اگر هر BLOCK، `WATCHLIST` اگر **بیش از ۲ WARN**، وگرنه `RELEASE` (`:489-497`) — و WATCHLIST همچنان منتشر میشود (`SIG-06`). |
| **۹۷ / ۳۹۳** | «یافته بحرانی [یتیمبودن دقت سیگنال] دیگر زنده نیست» | ارجاع والد بسته شده (F3)، ولی **اعتبار متریک** هنوز زنده است: سطوح هدف/حدضرر ساختگی و exit-price لحظهای (`SIG-01`) یعنی ۳٬۷۰۵ ردیف قدیمی و ردیفهای تازه هر دو نمیتوانند مبنای بازآموزی `force=True` باشند. شکل یافته عوض شده، رفع نشده است. |
| **۶۱۸ (جمع بندی)** | «fail-closed مالی در یازده دروازه تصمیم» | یازده گیت وجود دارد، ولی دستکم سه مسیر fail-open/خنثی به آنها تزریق میشود: گیت ۱۰ همیشه PASS (`SIG-04`)، گیتهای ۲/۵ روی `ml_score=0.5` موهوم (`SIG-05`)، و احتمال کالیبرهنشده در شکست calibrator (`SIG-10`). توصیف دقیق: «گراف تصمیم fail-closed، **ورودیهای آن** نه». |

### ۶‑ب — تصحیح روبهجلو (worktree زنده)

دو تغییر کامیتنشده دقیقاً خوشه `I` قسمت ۰۴ را هدف گرفتهاند: حذف `regime VARCHAR(50)` از `CREATE TABLE IF NOT EXISTS signal_accuracy` (ستونی که نه در `0007` هست نه در ORM) و افزودن `updated_at` به `SignalAccuracyModel` (ستونی که از `0006/0007` در DB هست و `TimestampMixin` فقط `created_at` میدهد). **اینها توسط این تحلیل ایجاد نشدهاند**؛ صرفاً ثبت شدند.

### ۶‑ج — حدسهایی که حین راستیآزمایی **رد شدند** (۷ مورد)

1. «`use_decision_engine=False` از API قابلتنظیم است» → **رد**: هر ۶ فراخوانی `generate()` در `apps/api/*` و `paper_trading_job.py` فقط `use_ml/use_voting/use_confidence_calibration` میدهند و flag تصمیم را پیشفرض `True` میگذارند. بهصورت **میانبر کتابخانهای بالقوه** ثبت شد (`SIG-16`), نه حکم production.
2. «`config/signal_policy.yaml` در ایمیج production نیست» → **رد**: `Dockerfile.api:28`, `Dockerfile.worker:28`, `Dockerfile.scheduler:32` و `Dockerfile:19` همگی `COPY config/ ./config/` با `WORKDIR /app` دارند. خطر `SIG-03` محدود به CWD غیراستاندارد و **بلع خطا** است، نه فقدان فایل.
3. «چون orchestrator بدون session ساخته میشود، `accuracy_snapshot` خالی است» → **رد**: `SignalAccuracyTracker.get_accuracy_by_market` از `async_session_factory` سراسری استفاده میکند (`:179-185`). برعکس، `SmartDecisionGate` فقط `self._session` را میبیند — و همانجا شکاف `SIG-02` است.
4. «`ORDER BY id DESC` روی جداول طلا/ارز/کریپتو شکست میخورد چون `id` ندارند» → **رد**: مهاجرت `0004b_core_baseline.py` برای هر هفت جدول `id` تعریف کرده است. مشکل واقعی **زمان** است (`ORDER BY id` یعنی اکنون، نه `due_date`).
5. «`acceptance.yaml` هم مانند پالیسی به CWD وابسته است» → **رد**: `acceptance_config_path()` از `Path(__file__).resolve().parents[2]` مسیر مطلق میسازد و `_load` کش دارد.
6. «YAML با `minimum_net_expectancy_r: -0.50` و `base_threshold: 0.42` همهچیز را سست کرده» → **تا حدی رد شد**: در `risk_reward` کف سند با `max()` پیروز میشود و YAML را بهکلی بیکار میکند؛ ولی در `probability`/`expectancy`/`grades` YAML کاملاً حاکم است. نتیجه **برخورد دو منبع** است (`SIG-12`) نه صرفاً سستسازی.
7. «گزارش ۱۶۰ لایهای تعداد گیتها را اشتباه گفته» → **رد**: لایه ۹۸ صریحاً «یازده دروازه» و اختلاف README/کد را ثبت کرده. اشتباه در docstringهای **خود کد** و سربرگ YAML است (`SIG-08`).

---

## ۷ — مرز روش

- **هیچ چیز اجرا نشد**: نه تست، نه بوت سرور، نه اتصال به PostgreSQL/Redis زنده، نه فراخوانی `generate()`. همه یافتهها ایستا و مبتنی بر خواندن فایل، AST، `git diff` و جستجوی محدودند.
- `SIG-15` (ابطال تراکنش PostgreSQL) یک **استنتاج از رفتار استاندارد SQLAlchemy/PostgreSQL** است، نه مشاهده زماناجرا؛ بدون اجرای DB نمیتوان وقوع قطعی آن را ادعا کرد.
- اعداد ۳٬۷۰۵ ردیف یتیم / ۴۶٬۹۰۶ پیشبینی شکستخورده / ۳۸٫۴۹٪ صحت جهت از `NUMERIC_AUDIT_2026-11-12.md` نقل شدند و در این قسمت **بازشماری نشدند**.
- شمارهخطها مربوط به نسخه **دیسکی (worktree)**اند؛ HEAD پس از خط ۱۵۴۵ یک خط بلندتر است. `git status` حین تحلیل از ۱۰۴ به ۱۲۲ فایل تغییر کرد — وضعیت worktree پایدار نیست.
- پوشش تست: ۳۱ فایل `*signal*.py` شمارش شد، ولی **محتوای آنها اجرا یا تحلیل نشد**؛ بنابراین درباره کافیبودن پوشش گیتها حکمی داده نمیشود.

---

## ۸ — خوشههای تازه برای ماتریس تجمیعی

| خوشه | یافتهها | شدت مؤثر | پیوند با قسمتهای قبل |
|---|---|---|---|
| **S — اعتبار حلقه دقت / بازآموزی** | `SIG-01`, `SIG-07`, `SIG-13` | 🔴 بحرانی | `R1` (۴۶٬۹۰۶ پیشبینی بیاعتبار) همچنان زنده است، اینبار از مسیر متریک؛ `P`/`replicas: 2` آن را دوبرابر میکند |
| **T — ورودیهای ساختگی به گیتها** | `SIG-05`, `SIG-10`, `SIG-11`, `SIG-16` | 🟠 بالا | همان الگوی «ابزار ساخته شده، داده وصل نشده» قسمتهای ۰۳–۰۶، اینبار در قلب تصمیم مالی |
| **U — پیکربندی دوپاره و گیت خنثی** | `SIG-03`, `SIG-04`, `SIG-12`, `SIG-08` | 🟠 بالا | `CFG-06` (مسیر `.env` مخزنمحور) دقیقاً تکرار شده؛ `CFG-19` (پیکربندی مرده) گسترش یافت |
| **V — override هوشمند مرده / اسکیما و لاگ خاموش** | `SIG-02`, `SIG-09`, `SIG-14`, `SIG-15` | 🟠 بالا | `I` (drift رجیستری/اسکیما) و `G` (خطای خاموش)؛ `EX-09` تنها در دو endpoint بسته شده بود |

**ترتیب بستن پیشنهادی** (بدون تغییر کد، صرفاً اولویت): `S → T → P → V → U → N → Q → H → B → …`.

**عبارت خلاصه قسمت ۰۷:** قسمتهای ۰۳ تا ۰۶ نشان دادند «کلیدی در compose خاموش است»؛ قسمت ۰۷ نشان میدهد حتی با همه کلیدها روشن، **عددی که به دروازهها میرسد لزوماً اندازهگیری نشده است**. گراف یازدهگانهای تصمیم از نظر ساختار سالم و fail-closed است؛ شکاف در ورودی (ML ساختگی، احتمال کالیبرهنشده، حدضرر فرضی، رژیم بیداده) و در خروجی (دقت سنجیدهشده با سطوح و قیمت ساختگی) است — و همان خروجی، چرخ `force=True` بازآموزی را میچرخاند.
