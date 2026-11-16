# قسمت ۰۹ — ML، feature store و رجیستری مدل

| | |
|---|---|
| **مبنای اندازهگیری** | `73a6c52d` — همان مبنای قسمتهای ۰۵ تا ۰۸؛ HEAD برای پنجمین قسمت متوالی جابهجا نشد. |
| **وضعیت worktree** | **۱۲۲ فایل Dirty** در آغاز قسمت (بدون تغییر نسبت به قسمت ۰۸) → **۱۲۴ در پایان نگارش**؛ دو فایل تازه ناشی از جابهجایی ۹+ سند `.md` حسابرسی/معماری از ریشه به `docs/` توسط فرایند همزمان است، نه تغییر کد. جستجوی `git status` برای الگوی `ml/\|feature\|model_\|inference\|train\|registry` **هیچ فایل اصلاحشدهٔ مرتبط با ML** نشان نداد؛ هسته `ml/`, `services/ml_signal_connector.py`, `services/training_service.py`, `services/inference_service.py` و `data/models/` هم در HEAD و هم در worktree یکساناند. |
| **تعهد** | فقط فایلهای Markdown تحلیلی ساخته/ویرایش شدند. **هیچ فایل کد، پیکربندی، تست، compose، مهاجرت یا artifact مدلی تغییر نکرد.** |
| **یادداشت روش** | جستجوها با مسیرهای محدود و مستثنا کردن `.freebuff/worktrees/` انجام شدند (پروتکل قسمت ۰۸). شمارش artifactها **روی دیسک مخزن محلی** است، نه volume استقرار production؛ نتیجهگیریها با این مرز بیان میشوند. |
| **پیشوند یافتهها** | `MLD-*` (ML Deep-dive) — عمداً با شناسههای داخلی کد `ML-006` / `ML-007` اشتباه نشود. |
| **زبان** | فارسی (هماهنگ با سری) |

---

## ۱ — فهرست فایلها و ابعاد (شمارش واقعی، فقطخواندنی)

| درخت / فایل | تعداد | خط | یادداشت |
|---|---:|---:|---|
| `ml/` | **۱۱۸ فایل `.py`** | **۶٬۶۹۰** | **۶** زیرپوشه (گزارش ۱۶۰ لایهای «هفت» گفته و خودش شش تا لیست کرده) |
| `ml/models/` | ۴۲ | ۲٬۳۳۰ | بزرگترین؛ تعریف مدل بسیار جلوتر از آموزش |
| `ml/features/` | ۱۶ | ۸۱۶ | `PriceFeatures` / `TechnicalFeatures` واقعاً مصرف میشوند |
| `ml/datasets/` | ۱۱ | ۵۸۶ | صفر مصرفکننده production |
| `ml/training/` | ۱۱ | ۳۱۲ | فقط `Trainer` / `MetricsCalculator` وصلاند |
| `ml/inference/` | ۱۰ | ۲۳۱ | ** صفر مصرفکننده production**؛ فقط `__init__` خودش export میکند |
| `ml/evaluation/` | ۱۰ | ۳۰۶ | `MetricsCalculator` تنها نقطهٔ وصل |
| `services/` (فایلهای ML-named) | ۳۱ | ۱۴٬۰۷۹ | `ml_signal_connector` (۵۸۹), `training_service` (۳۶۹), `inference_service` (۵۱۲) |
| `jobs/definitions/` | ۲۶ | ۳٬۲۶۰ | `feature_store_jobs.py`, `ml_jobs.py` |
| تستهای ML-named | ۴۴ | ۷٬۹۴۶ | `ml/README.md` میگوید «۲۰ تست پاس ✅» |
| `data/models/` (دیسک محلی) | **۳ پوشه** | **۳۷ نسخه** | `linear_regression_فولاد` (۲۴), `random_forest_فولاد` (۷), `random_forest_شپنا` (۶) |
| `ml_artifacts/` (دیسک محلی) | **۰ پوشه** | — | docstringهای `artifacts.py` / `model_loader.py` آن را محل «همه artifactها» / «۳۵۹ پوشه» میدانند |

شمارش ایستا: **۴ پیادهسازی `ModelRegistry`** (`ml/registry.py`, `ml/model_registry.py`, `ml/global_registry.py`, `ml/models/registry.py`) · **۴ کلاس `FeatureStore`** (`ml/feature_store.py`, `ml/features/store.py`, `services/smart_money/feature_store.py`, و `scripts.build_feature_store.FeatureStoreBuilder`) · **۵ ماژول ریشهای `ml/` با صفر مصرفکننده** (`policies`, `experiments`, `constants`, `exceptions`, `utils`) · **۳۷/۳۷** فایل `metadata.json` دارای `artifact_hash` معتبر · **۳۷/۳۷** نسخه با `stage: development` و **صفر** نسخهٔ production.

---

## ۲ — ردیابی جریان اجرا

### ۲‑الف — مسیر استنتاج سیگنال (production)

```
apps/api/app.py:928   register_all_models()   ← فقط در lifespan API، داخل try/except «optional»  ← MLD-07
  └─ ml/models/__init__.py:34   مدلها را به global_registry (دمو) هم ثبت میکند        ← MLD-01

QuantSignalOrchestrator._apply_voting()  (قسمت ۰۷: SIG-05)
  └─ services/quant_signal_orchestrator.py:2168  _get_ml_connector() → MLSignalConnector()
       └─ services/ml_signal_connector.py:215  predict(features, market, closes)
            ├─ trained = self._trained_models.get(market, {})         :233
            ├─ if not trained: حلقهٔ lazy-load از ModelLoader          :239-248
            │    └─ break بعد از **اولین** الگوریتم موجود              :247  ← MLD-04
            ├─ self._trained_models.setdefault(market, {})[...] = obj :251  ← دیکشنری دیگری، ۱ عضو
            └─ if model_obj is None:  closes کافی؟
                 └─ _heuristic_trend_predict(closes)                  :268  ← MLD-03
                      MA(5/20) + RSI(14) + MACD + ATR ⇒ ml_score
                      models_used = ["heuristic_trend"]  (قواعد دستی، نه مدل آموزشدیده)
            └─ ml_score → get_signal_boost() :376 → گیتهای ۲/۵ تصمیم (قسمت ۰۷)
```

### ۲‑ب — مسیر آموزش / بازآموزی و گیت پذیرش

```
SignalAccuracyTracker  (قسمت ۰۷ SIG-01: سطوح هدف/حدضرر ساختگی)
  └─ AutoRetrainPipeline.check_and_retrain(force=True)   :87  (آستانه ۵۵٪ / ۷ روز / ۵۰ نمونه)
       └─ MLSignalConnector.train_for_market()           :490
            ├─ model_registry.create(...) / model.fit(...)   :533-535
            └─ WalkForwardValidator.validate_model()        :543
                 └─ services/walk_forward_validator.py:255  معاملات ±1.0 / cost 0.5 ساختگی  ← قسمت ۰۸ BT-02
                      └─ statistical_acceptance_gate.evaluate_acceptance()
                      └─ if not wf_val.is_reliable: فقط logger.warning  :563  ← حکم اعمال نمیشود

apps/api/endpoints/ml.py:446  /train
  └─ TrainingService(quote_repo=QuoteRepository(session))  ← endpoint درست repo میدهد
       └─ train_with_db_data()  :185
            └─ _fetch_ohlcv()  :71
                 ├─ if not quote_repo        → _synthetic_ohlcv()  :74   ← MLD-02
                 ├─ استثناء در query         → _synthetic_ohlcv()  :87
                 └─ result ناموفق/خالی       → _synthetic_ohlcv()  :90
                      └─ rng.default_rng(42)، قیمت پایه ۳۸٬۵۰۰، حجم تصادفی  :59-68
            └─ ArtifactManager.save_model(meta stage="development")  :242  ← MLD-15
                 └─ metadata.json با artifact_hash معتبر (هیچ پرچم synthetic ندارد)
```

### ۲‑ج — مسیر «داشبورد مدلها»

```
apps/admin/dashboard.py:207    get_registry().list_models()   ← بدون هیچ fallback DB   ← MLD-01
apps/api/endpoints/ml.py:140   /models
  ├─ _db_list_models(session) → اگر جدول ml_models پر بود، همان
  └─ except/خالی ⇒ get_registry()  (دموی seeded)               ← MLD-01
       └─ ml/global_registry.py:53  _registry = _create_seeded_registry()  در لحظه import
            «XGBoost Price Predictor» v1.0.0  stage=production  accuracy=0.871  r2=0.892
```

---

## ۳ — سیاست شکست (گامبهگام)

| گام | رویداد شکست | سیاست | سطح لاگ | اثر |
|---|---|---|---|---|
| `ml/global_registry` import | — | **eager seed** با ۴ مدل دمو | — | داشبورد همیشه داده نشان میدهد، حتی با DB خالی |
| `/models` | DB خالی یا خطا | **fail-open → رجیستری دمو** | `warning` | اعداد جعلی با `success=True` |
| `register_all_models()` | هر استثناء | **swallow** «ML model registration failed (optional)» | `warning` | رجیستری خالی ولی startup سبز |
| `_fetch_ohlcv` | نبود repo / خطای query / خالی | **fail-open → OHLCV تصادفی** | **بیصدا** | مدل روی داده موهوم آموزش میبیند |
| `save_model` | خطای ذخیره artifact | `artifact_path=""` + `warning` | `warning` | run همچنان `status: completed` |
| `ModelLoader._assert_integrity` | ناهماهنگی هش / نبود هش | **fail-closed** `ValueError` | — | نقطه قوت (ML-007) |
| `ModelLoader.get_model` | `FileNotFoundError` | `continue` به الگوریتم بعدی | `debug` | نبود artifact ساکت |
| `ModelLoader.get_model` | `ValueError` یکپارچگی | **propagate** | — | درست، ولی در `predict` کرش میکند |
| `MLSignalConnector.predict` | هیچ مدلی + closes کافی | **fail-open → heuristic** | `info` | قواعد دستی بهجای ML وارد رأیگیری |
| `MLSignalConnector.predict` | هیچ مدلی + closes ناکافی | `ml_score=0.5` خنثی | `info` | همان `SIG-05` قسمت ۰۷ |
| `MLSignalConnector.predict` | استثناء `model.predict` | `logger.warning` + `continue` | `warning` | `total_weight=0` ⇒ خنثی ۰٫۵ |
| `predict_real` | نبود مدل | `_mock_predict` ⇒ **fail** | `warning` | درست |
| `/predict/{model_id}` | `predict_real` ناموفق | **fallback به `predict()` آموزشندیده** | — | شکست بلعیده میشود ← MLD-05 |
| `/predict-all` (batch) | نبود مدل | `prediction_failed: True` | — | نقطه قوت (F1 بسته شده) |
| `WalkForwardValidator` | `is_reliable=False` | فقط `logger.warning` | `warning` | مدل ذخیره و قابلاستفاده میماند |
| `prune_ml_artifacts` | `metadata.json` سطح پوشه مدل یافت نشد | `is_prod=False` | `debug` | محافظت production هرگز اعمال نمیشود ← MLD-12 |

---

## ۴ — جدول یافتهها (`MLD-01`…`MLD-16`)

| ID | شدت | خط دقیق | شاهد | اثر عملی | جهت اصلاح |
|---|---|---|---|---|---|
| **MLD-01** | 🔴 بحرانی | `ml/global_registry.py:1-5,53`; `ml/model_registry.py:8`; `apps/admin/dashboard.py:207-208`; `apps/api/endpoints/ml.py:150-155`; `ml/models/__init__.py:34-54` | رجیستری دمو صریحاً «**not for production use**» نامگذاری شده، ولی در لحظهٔ import با ۴ مدل و `stage="production"` و متریک (`accuracy 0.871`, `r2 0.892`, `mse 0.0241`) seed میشود؛ docstring هدف را «so the ML dashboard **always has data to display**» مینویسد. admin dashboard **هیچ fallback دیتابیس ندارد** و مستقیم آن را میخواند؛ `/models` هم در خالیبودن جدول `ml_models` به آن سقوط میکند | داشبورد مدیریتی production اعدادی را نمایش میدهد که **هیچ مدل، آموزش یا ارزیابی پشتشان نیست**؛ `stage=production` جعلی به بیننده القای مدل مستقر میکند. کامیت `707c1793` alias `ModelRegistry = DemoModelRegistry` را فقط برای سبز کردن import یک تست افزود و دو کلاس همنام با معنای متفاوت ساخت | حذف seed از مسیر production، یا گیت `settings.is_production` روی endpointها؛ جداکردن `DemoModelRegistry` از `ModelRegistry`؛ در حالت خالی `[]` برگرداندن نه دمو |
| **MLD-02** | 🔴 بحرانی | `services/training_service.py:43-69,73-74,86-90`; `:195,222,242`; `ml/artifacts.py:186-213` | `_synthetic_ohlcv()` قیمت پایهٔ ۳۸٬۵۰۰ با `np.random.default_rng(42)` و حجم تصادفی میسازد. `_fetch_ohlcv` در **سه** مسیر (نبود `quote_repo`، استثناء query، نتیجهٔ خالی/ناموفق) **بیصدا** به آن سقوط میکند. `train_with_db_data` مدل را روی همان DataFrame آموزش داده و `save_model` artifact را با `artifact_hash` معتبر ذخیره میکند؛ `metadata.json` هیچ پرچم `synthetic`/`data_source` ندارد و `dataset_hash` خالی است | مدل آموزشدیده روی **داده کاملاً موهوم** از مدل آموزشدیده روی داده واقعی **قابلتمایز نیست** — هش فقط یکپارچگی فایل را ثابت میکند، نه منشأ داده را. خط لولهٔ `ModelTrainingJob` و `ModelEvaluationJob` دقیقاً `TrainingService()` بدون repo میسازند. این ریشهٔ بالادست `BT-02` (قسمت ۰۸) و `SIG-01` (قسمت ۰۷) است | fail-closed بهجای synthetic در production؛ پرچم `data_provenance` اجباری در `ModelArtifactMeta` و چک آن در `ModelLoader`؛ لاگ `error` نه سکوت |
| **MLD-03** | 🔴 بحرانی | `services/ml_signal_connector.py:21-24,27-155,258-268`; `data/models/` (۳ پوشه); `services/quant_signal_orchestrator.py:2168` | کامنت میگوید heuristicها «give the signal pipeline SOMETHING … instead of returning all-neutral predictions (**which collapse the ML branch of the voting system**)». روی دیسک مخزن فقط **۳ پوشه artifact برای ۲ نماد و ۲ الگوریتم** (`linear_regression`, `random_forest`) وجود دارد، در حالی که `DEFAULT_MODELS` برای ۷ بازار الگوریتمهای `xgboost/lstm/gru/transformer` را لیست میکند. `get_model` نمادهای بدون artifact را ساکت رد میکند | برای اکثریت نمادها/بازارها «پیشبینی ML» در واقع **رأی قواعد دستی MA(5/20)+RSI+MACD+ATR** است که با `models_used=["heuristic_trend"]` و `ml_score` وارد شاخهٔ ML رأیگیری و گیتهای ۲/۵ تصمیم میشود — سیگنال ترکیبی/هیبرید روی مدل موهوم اعلام میگردد (`SIG-05`). مرز: شمارش artifact دیسک محلی است؛ volume production راستیآزمایی نشد | پرچم صریح `is_heuristic` در خروجی و محروم کردنش از گیتهای مدل/هیبرید؛ لاگ `warning` بهازای نماد بدون artifact؛ همسو کردن `DEFAULT_MODELS` با artifactهای واقعی |
| **MLD-04** | 🟠 بالا | `services/ml_signal_connector.py:232-251,290-320,344-348`; `:449` | `trained = self._trained_models.get(market, {})` وقتی کلید غایب باشد یک دیکشنری **تازه** میسازد؛ حلقهٔ lazy-load در همان دیکشنری مینویسد و بعد از **اولین** مدل `break` میکند (`:247`)، سپس `setdefault` دیکشنری **دیگری** با یک عضو میسازد. حلقهٔ رأیگیری `:290` روی `trained` (تکعضوی) میچرخد. `load_models_from_disk()` که میتواند چند مدل پر کند **صفر فراخواننده** دارد | رأیگیری چندمدلهای طراحیشده (۴ مدل با وزن ۰٫۳۵/۰٫۳۰/۰٫۲۰/۰٫۱۵) در مسیر production **هرگز رخ نمیدهد**: تنها یک مدل یافت میشود، `total_weight` همان وزن تکمدل است و تقسیم بر آن ⇒ وزنها کاملاً بیتأثیر و `model_breakdown` تکعضوی. `get_trained_models_info()` تصویر نادرستی از ensemble میدهد | نوشتن مستقیم در `self._trained_models.setdefault(market, {})` و حذف `break`؛ یا فراخوانی `load_models_from_disk()` در startup؛ تست پاریتی تعداد مدلهای مشارکتکننده |
| **MLD-05** | 🟠 بالا | `apps/api/endpoints/ml.py:214-247`; `services/inference_service.py:335-341,344-395`; `:318` | `predict_real` در نبود مدل صادقانه `Result.fail` برمیگرداند و مسیر batch `_map_real_prediction` با `prediction_failed: True` و «No mock/fallback data is generated» مستند شده (F1 بسته است). ولی endpoint تکی پس از ناموفقی `predict_real` به `service.predict()` سقوط میکند؛ آن متد صریحاً مدل **آموزشندیده** میسازد یا `pred = price_close * 0.001` میدهد و `source: "untrained"` را برمیگرداند — و endpoint **`source` را از پاسخ حذف میکند** و `success=True` مینویسد | دو مسیر API برای یک وضعیت واحد دو حکم متناقض دارند: batch میگوید شکست، تکی میگوید موفقیت. مصرفکنندهٔ `/predict/{model_id}` هیچ راهی ندارد بفهمد عدد از مدل نیامده؛ `confidence` همچنان ۰٫۵/۰٫۷۵ گزارش میشود. تکرار دقیق `BT-04` (قسمت ۰۸) در لایه استنتاج | یکی کردن سیاست: یا `success=False` برای تکی، یا دستکم عبور دادن `source`/`model_loaded_from` و `confidence=0` |
| **MLD-06** | 🟠 بالا | `apps/api/endpoints/ml.py:280-296`; `services/inference_service.py:255-260,368,390` | `_map_real_prediction` سه فیلد `accuracy`, `confidence`, `f1_score` را همگی از `pred_result.get("confidence", 0.75)` پر میکند؛ `confidence` در `predict_real` مقدار ثابت `0.75` دارد و فقط با `feature_importances_` تا ۰٫۹۵ بالا میرود. `mse: 0.0` هم ثابت است | **F1 و accuracy داشبورد اندازهگیری نشدهاند** — یک عدد اطمینان مدل (که خودش هیوریستیک است) با نام متریک طبقهبندی سریال میشود. جدول `ml_predictions` و نمودارهای مقایسهای مدلها روی این اعداد قضاوت میکنند؛ مستقیم به `BT-02` و `R1` وصل است | محاسبهٔ F1/accuracy از `signal_accuracy` واقعی یا حذف فیلدها؛ `mse` را `null` گذاشتن بهجای `0.0` |
| **MLD-07** | 🟠 بالا | `apps/api/app.py:34,926-930`; `ml/models/registry.py:28-29`; `services/ml_signal_connector.py:18` | `register_all_models()` **فقط** در lifespan فرایند API و داخل `try/except` با پیام «ML model registration failed (**optional**)» صدا زده میشود. `model_registry = ModelRegistry()` در لحظهٔ import با `_builders = {}` خالی است و `create()` روی کلید ناشناخته `ValueError("Unknown model")` میدهد | در **worker / scheduler / decision-engine** (قسمت ۰۶: `worker replicas: 2` و scheduler اختصاصی) رجیستری خالی است؛ `TrainingService.train_with_db_data` و `InferenceService.predict_real` که توسط jobها ساخته میشوند نمیتوانند مدلی بسازند. همان شکاف فرایندمحلی `SIG-13` / `JOB-07`، اینبار در لایه مدل. بلع استثناء startup هم خرابی ثبت را «اختیاری» جلوه میدهد | seed کردن رجیستری در `ml/models/registry.py` هنگام import (نه در lifespan)، یا فراخوانی صریح در هر entrypoint؛ تبدیل استثناء startup به fail-fast در production |
| **MLD-08** | 🟠 بالا | `jobs/definitions/ml_jobs.py:14-24,60-70,76-84`; `services/training_service.py:290`; `services/inference_service.py:344`; `apps/scheduler/app.py:231,279` | سه job ثبتشده در `__all__` امضاهای ناموجود صدا میزنند: `ModelTrainingJob` → `TrainingService.train(model_name=, dataset_id=, params=)` در برابر `train(self, model, dataset_config, **kwargs)`؛ `BatchInferenceJob` → `InferenceService.predict(model_id=, instrument_id=)` در برابر `predict(self, model_id, features)`؛ `ModelEvaluationJob` → `service.evaluate(...)` که **اصلاً متدی وجود ندارد**. scheduler فقط `FeatureStoreBuildJob` و `MlArtifactLifecycleJob` را `add_job` کرده است | سه `TypeError`/`AttributeError` نهفته در رجیستری ۷۰تایی قسمت ۰۶؛ بهمحض اضافهشدن trigger یا فراخوانی دستی شکست میخورند و dispatcher آنها را بهصورت شکست job ثبت میکند. مرز: چون الان trigger ندارند، **ادعای خرابی زماناجرا نمیشود** | اصلاح امضاها یا حذف jobها؛ تست قرارداد `inspect.signature` برای همه کلاسهای `__all__` در CI |
| **MLD-09** | 🟡 متوسط | `ml/registry.py`, `ml/model_registry.py`, `ml/global_registry.py`, `ml/models/registry.py`; `ml/feature_store.py`, `ml/features/store.py`, `services/smart_money/feature_store.py`, `scripts/build_feature_store.py` | چهار `ModelRegistry` با چهار قرارداد متفاوت (`ModelArtifactMeta`+`promote`, دمو+`add_version`, singleton seeded, و ثبت کلاس) و چهار `FeatureStore` (کاتالوگ درونحافظهای ۲۶ خطه، ذخیره JSON روی دیسک، حافظه TTLدار smart_money، و builder دیتابیسی) همزیستاند. `ml/__init__.py` رجیستری اول، `ml/models/__init__.py` چهارمین و endpointها سومین را export/وارد میکنند | «کدام رجیستری حاکم است» بدون خواندن تکتک فایلها پاسخ ندارد؛ `ml/README.md:93` حتی `model_registry.py` را «versioning، staging، metadata» معرفی میکند در حالی که واقعاً `DemoModelRegistry` است. بدهی تکثر لایه ۱۲۶ گزارش اصلی اکنون **چهار به چهار** شد (دو محور) | تعیین یک رجیستری حاکم + یک Feature Store حاکم؛ حذف یا تبدیل بقیه به adapter با نام صریح |
| **MLD-10** | 🟡 متوسط | `scripts/build_feature_store.py:62,171`; `jobs/definitions/feature_store_jobs.py:26-54`; `migrations/versions/0035_feature_store_tables.py:39-125`; `apps/scheduler/app.py:226-234` | جدول `ml_engineered_features` شبها (۲۳:۳۰) ساخته میشود، ولی جستجوی محدود در `ml/ services/ apps/ jobs/ core/ models/ brsapi/` **هیچ خوانندهای** پیدا نکرد (فقط کامنت scheduler و docstring خود job). همچنین در `models/` و `core/database.py` حضور ندارد | feature store واقعی «نوشته میشود ولی خوانده نمیشود»: `SignalFeaturePipeline` ویژگیها را مستقیم از داده لحظهای میسازد، نه از جدول مهندسیشده. مستقیم به خوشه `I` قسمت ۰۴ (۴۱ جدول / ۲۷٫۵٪ خارج `Base.metadata`) وصل است: `--autogenerate` میتواند پیشنهاد حذفش بدهد. لایه ۱۲۵ گزارش اصلی گفته «job وظیفه پر کردن **آن** [کاتالوگ `ml/feature_store.py`] را دارد» — نادرست است | یا وصل کردن آموزش/استنتاج به جدول، یا حذف job و مهاجرت؛ افزودن مدل ORM و پوشش `alembic check` |
| **MLD-11** | 🟡 متوسط | `ml/inference/__init__.py:1-9`; `ml/policies.py`, `experiments.py`, `constants.py`, `exceptions.py`, `utils.py`; `ml/train_weight_optimizer.py`, `ml/weight_validator.py`; `ml/dataset_builder.py` | پکیج `ml/inference/` (۱۰ فایل: `Predictor`, `PredictionPipeline`, `DriftDetector`, `ThresholdOptimizer`, `PredictionValidator`, …) فقط توسط `__init__` خودش export میشود و صفر مصرفکننده production دارد. پنج ماژول ریشهای نیز صفر مصرفکنندهاند. `train_weight_optimizer` / `weight_validator` فقط در تستها و بهصورت CLI دیده میشوند؛ `ml/README.md:125-129` همان `Predictor` را بهعنوان API جاری مستند میکند | بخش قابلتوجهی از ۶٬۶۹۰ خط `ml/` زیرساخت موازی بیکار است؛ مستندات مسیری را نشان میدهد که production از آن استفاده نمیکند (استنتاج واقعی در `services/inference_service.py` است). تشخیص drift و بهینهساز آستانه — که دقیقاً برای اعتبار خروجی لازماند — وصل نیستند | حذف یا وصل کردن `DriftDetector`/`ThresholdOptimizer` به `invalidate()`؛ بهروز کردن README به مسیر واقعی |
| **MLD-12** | 🟡 متوسط | `services/ml_lifecycle_service.py:24-30,51-58,63-88`; `data/models/*/` | `prune_ml_artifacts` بهازای هر پوشهٔ مدل `meta = d / "metadata.json"` را چک میکند، ولی در دیسک **همه ۳۷ فایل `metadata.json` در پوشههای نسخه** (`d/v1-<hash>/metadata.json`)اند و `d/metadata.json` در **هیچکدام** وجود ندارد ⇒ `_is_production` هرگز فراخوانده نمیشود و `skipped_prod` همیشه ۰. افزون بر آن `shutil.rmtree(d)` **کل پوشهٔ مدل** (تمام ۲۴ نسخه) را حذف میکند، نه «نسخههای کهنه»، و گروهبندی `p.name.split("_")[0]` الگوریتم `random_forest` را `random` و `linear_regression` را `linear` مینامد | محافظت «production» اسمی است؛ چون همه نسخهها `stage: development`اند عملاً هیچ artifactی محافظت نمیشود. امروز با ۳ پوشه و `keep_latest=3` حذفی رخ نمیدهد، ولی بهمحض ۴ پوشه، تاریخچهٔ کامل یک نماد پاک میشود. `MlArtifactLifecycleJob` یکشنبهها ۰۴:۰۰ اجرا میشود | خواندن metadata از پوشههای نسخه؛ حذف در سطح نسخه؛ تست با `stage=production` ساختگی |
| **MLD-13** | 🟡 متوسط | `ml/model_loader.py:106-140,355-391`; `apps/api/app.py:677-682`; `apps/api/endpoints/ml.py:650-652` | `get_model()`, `preload()` و `cache_info()` همگی `async def`اند، ولی بدنهٔ `_load_from_disk` شامل `read_bytes`, `hashlib` روی کل فایل، `pickle/joblib` unpickle و `mkdir` است — هیچ `run_in_executor`/`to_thread` ای وجود ندارد. `preload()` در startup تعداد نمادهای watchlist را پشتسرهم `await` میکند | بارگذاری هر مدل (و هش آن) **event loop را بلاک میکند**؛ با `preload` روی watchlist بزرگ، startup و پاسخگویی همزمان API متوقف میشود. docstring startup میگوید «**Non-blocking** and defensive» در حالی که صرفاً «شکست را بالا نمیاندازد» است، نه نابلاککننده | اجرای `_load_from_disk` در `asyncio.to_thread` (با حفظ `lru_cache` thread-safe)، یا تبدیل متدها به sync و فراخوانی صریح از executor |
| **MLD-14** | 🟡 متوسط | `ml/model_loader.py:5`; `ml/artifacts.py:30,54,128-137`; `ml/README.md:3,93,168`; `apps/api/endpoints/ml.py:293` | docstring لودر «all **359** artifact directories» و `artifacts.py` «every trained artifact lives under `ml_artifacts/`» میگویند؛ روی دیسک `ml_artifacts/` **۰ پوشه** و `data/models/` ۳ پوشه است. `ml/README.md` تاریخ «۲۰۲۶-۰۸-۰۱ — فاز ۹» (بیش از ۳ ماه کهنه) و «۲۰ تست پاس ✅» دارد در برابر ۴۴ فایل تست / ۷٬۹۴۶ خط. batch docstring «No mock/fallback data is generated» است در حالی که مسیر تکی دقیقاً چنین میکند (`MLD-05`) | مستندات و کامنتها تصویری از مقیاس و پوشش میدهند که با مخزن زنده منطبق نیست؛ همان خوشه `K` قسمت ۰۴. نکتهٔ مثبت: `resolve_artifact_root()` با `_holds_model_folders` مسیر درست (`data/models`) را انتخاب میکند، پس **عملکرد** سالم است و فقط روایت کهنه است | بهروزرسانی docstringها از روی شمارش واقعی؛ تستی که تعداد پوشهها/نسخهها را در CI چک کند |
| **MLD-15** | 🟢 کم | `services/training_service.py:231-271`; `ml/artifacts.py:186-213`; `ml/types.py` (`ModelArtifactMeta`) | `meta = ModelArtifactMeta(... stage="development")` همیشه، حتی برای آموزش در production؛ `dataset_hash` هرگز پر نمیشود؛ شکست `save_model` فقط `logger.warning` داده و `artifact_path=""` میگذارد ولی `run["status"] = "completed"` و `Result.ok(run)` برمیگرداند. `/train` همان را `MlTrainResponse(status="completed")` سریال میکند | «آموزش موفق» میتواند بدون هیچ artifact ذخیرهشده گزارش شود؛ هیچ مدلی هرگز به `production` ارتقا نمییابد (۳۷/۳۷ نسخه development) و ردیابی منشأ مجموعهداده از metadata ممکن نیست. با `MLD-02` ترکیب میشود: مدل موهوم + بدون provenance + گزارش موفقیت | `status: completed_without_artifact` یا `Result.fail`؛ پر کردن `dataset_hash`؛ مرحلهٔ `promote()` صریح |
| **MLD-16** | 🟢 کم | `services/training_service.py:41,269,311-315`; `services/global_training_service.py:53`; `services/ml_signal_connector.py:401-443`; `services/quant_signal_orchestrator.py:2164-2170` | `_runs` و `_ml_connector` دیکشنری/singleton **درونفرایندی**اند؛ `/runs` ابتدا DB را میخواند و فقط در خالیبودن به این حافظه سقوط میکند. `get_accuracy_by_market` همان جدول `signal_accuracy` را query میکند که `SIG-01` (قسمت ۰۷) نشان داد `direction_correct`اش با سطوح هدف/حدضرر **ساختگی** پر میشود | وضعیت runها بین رپلیکاها (`api: replicas: 2`, `worker: replicas: 2` در compose production) ناپایدار است؛ و دقت تطبیقی ML — که `ml_weight = confidence * 0.7` را تغذیه میکند — از همان عدد مسموم قسمت ۰۷ میآید. زنجیرهٔ کامل: داده ساختگی → دقت ساختگی → بازآموزی `force=True` → گیت روی معاملات ساختگی → دقت تطبیقی ساختگی | انتقال `_runs` به DB/Redis؛ علامتگذاری `invalidated` روی ردیفهای قدیمی `signal_accuracy` پیش از backfill (همان بند R1 گزارش اصلی) |

**توزیع شدت:** ۳ بحرانی · ۶ بالا · ۵ متوسط · ۲ کم = **۱۶ یافته**.

---

## ۵ — نقاط قوت تأییدشده

1. **امنیت زنجیرهٔ تأمین مدل واقعاً پیادهسازی شده.** `_assert_integrity` (`:320-353`) هش sha256/md5 ثبتشده را با **`hmac.compare_digest`** مقایسه، روی ناهماهنگی `ValueError` میدهد، و در نبود هش **fail-closed** است مگر escape hatch صریح `ML_ALLOW_UNVERIFIED_MODELS=1` (با `logger.warning`). روی دیسک **۳۷/۳۷** `metadata.json` دارای `artifact_hash`اند — یعنی مسیر «بدون هش» امروز فعال نیست.
2. **LRU کلیددار بر نسخه (ML-006) جلوی مدل کهنه را میگیرد.** `_artifact_version` (`:266-300`) از پوشهٔ نسخه، سپس `artifact_hash`/`checksum`، سپس `mtime-size` استفاده میکند؛ `invalidate()` LRU را `cache_clear` کرده و بازماندگان را oldest-first دوباره گرم میکند تا ترتیب تازگی حفظ شود. چهار نقطهٔ فراخوانی (`training_service`, `ml_jobs`, `jobs/model_training`, `auto_retrain_pipeline`) همگی پس از آموزش آن را صدا میزنند.
3. **سازگاری با سه چیدمان artifact (F-01) درست حل شده.** `resolve_artifact_root` مسیر پیکربندیشدهٔ مخزنمحور را با `_holds_model_folders` بررسی و فقط در صورت خالیبودن به fallback رجوع میکند؛ `MODEL_FILE_CANDIDATES` و `load_artifact_bytes` هر دو pickle ساده و joblib zlib و `latest_path.txt` را پوشش میدهند. «پوشهٔ خالی `data/models` ⇒ هیچ مدلی پیدا نشد» رفع شده است.
4. **مسیر batch استنتاج صادق است (F1 بسته شد).** `_map_real_prediction` در شکست `prediction: 0`, `confidence: 0`, `prediction_failed: True`, `error` صریح و «No mock/fallback data is generated» برمیگرداند؛ `predict_all` تعداد `successful/failed` را جدا میشمارد. مشکل فقط مسیر تکی است (`MLD-05`)، نه کل endpoints.
5. **ضد نشت اطلاعات در آموزش جدی گرفته شده.** `_split_time_series` بدون shuffle و ترتیبزمانی تقسیم میکند (`:161-183`)، `_prepare_target` از `close.shift(-1)` برچسب `(X_t, y_{t+1})` میسازد، `PurgedWeightValidator` در `ml/weight_validator.py` پنجرههای purge/embargo دارد و `tests/unit/ml/test_weight_validator.py` تست صریح «no information leakage between folds» را اجرا میکند. `get_accuracy_by_market` نیز اشتباه قدیمی `async with get_session()` را با `aclosing` اصلاح کرده است.
6. **گیت خلوص معماری توسط ابزار اعمال میشود.** `.importlinter` قرارداد `phase0-ml-purity` دارد و CI آن را اجرا میکند؛ `ml/` به `apps/`/`services/` وابسته نیست. `ml/README.md` علیٰرغم کهنگی، ساختار شش زیرپوشه را تا حد زیادی درست شرح میدهد.
7. **لایه دیتابیس feature store کامل طراحی شده.** مهاجرت `0035` جدول `ml_engineered_features` را با ایندکسهای `(symbol, trade_date)`, `calculated_at` و `target` میسازد و `FeatureStoreBuilder` با upsert وPrimaryKey مشخص مینویسد؛ مشکل **نبود مصرفکننده** است، نه کیفیت ساخت (`MLD-10`).

---

## ۶ — تصحیح گزارش ۱۶۰ لایهای و حدسهای ردشده

### ۶‑الف — تصحیحات (۴ مورد)

| لایه | ادعای گزارش | واقعیت در `73a6c52d` |
|---|---|---|
| **۱۲۲** | «`ml/` شامل ۱۱۸ فایل پایتون در **هفت** زیربسته» | تعداد فایلها و ۶٬۶۹۰ خط درست است، ولی زیربستهها **شش**اند (`models 42`, `features 16`, `training 11`, `datasets 11`, `inference 10`, `evaluation 10`) — خود همان لایه نیز شش تا برشمرده است. |
| **۱۲۳ / ۱۲۴ / ۲۳۹** | «`_verify` با `hashlib`… مقایسه میکند»؛ «`diagnostics()` اطلاعات کش را برمیگرداند» | نامهای واقعی **`_assert_integrity`** و **`cache_info`**اند. اصل ادعا (HMAC `compare_digest`، fail-closed، escape hatch) کاملاً تأیید شد؛ فقط نامها کهنهاند. همچنین `invalidate()` دیگر صرفاً «با بازماندگان گرم میکند» نیست، بلکه LRU را **کاملاً بازمیسازد** (`:233-239`). |
| **۱۲۵** | «`jobs/definitions/feature_store_jobs.py` وظیفه **پر کردن آن** [`ml/feature_store.py` کاتالوگ درونحافظهای] را دارد» | **نادرست.** آن job جدول **`ml_engineered_features`** را از طریق `scripts.build_feature_store.FeatureStoreBuilder` پر میکند و هیچ ارتباطی با کلاس ۲۶ خطهٔ `ml/feature_store.py` ندارد؛ آن کاتالوگ صفر مصرفکننده است. نتیجهٔ لایه («کاتالوگ متادیتا، نه ذخیرهساز point-in-time») درست ماند، ولی استنادش جابهجا شد و **صفر خواننده** بودن جدول واقعی دیده نشد (`MLD-10`). |
| **۱۲۶ / ۱۳۲ / ۴۷۴** | «`ml/model_registry.py` … لایهٔ حاکمیت»؛ «داراییها: … **رجیستری نسخهدار** … امتیاز زیرساخت ML بالا» | `model_registry.py` یک **`DemoModelRegistry`** با برچسب «not for production use» است و `global_registry.py` آن را در لحظهٔ import با دادهٔ دمو و `stage=production` seed میکند — و **دو endpoint production** (admin dashboard بدون fallback DB، `/models` بهعنوان fallback) دقیقاً همان را میخوانند (`MLD-01`). پس «چهار رجیستری موازی» یک بدهی نگهداری صرف نیست؛ یکی از آنها منبع اعداد جعلی داشبورد است. |

### ۶‑ج — حدسهایی که حین راستیآزمایی **رد شدند** (۷ مورد)

1. «`ml_engineered_features` توسط `ml/features/store.py` یا `FeatureStore` خوانده میشود» → **رد**: چهار کلاس `FeatureStore` هیچکدام به آن جدول وصل نیستند؛ جدول فقط نویسنده دارد و صفر خواننده (تبدیل به `MLD-10`).
2. «`prune_ml_artifacts` پوشهٔ خالی `ml_artifacts/` را هدف میگیرد» → **رد**: `services/ml_lifecycle_service.py:44-46` از همان `resolve_artifact_root()` استفاده میکند و `data/models` درست را میگیرد (F-01 رعایت شده). نقص واقعی جای دیگری است (`MLD-12`).
3. «`direction_correct` در اسکیمای `signal_accuracy` وجود ندارد و `get_accuracy_by_market` روی ستون ناموجود query میکند» → **رد**: `migrations/versions/0007_signal_accuracy.py:45` ستون و `:88` ایندکس آن را میسازند. مسئله **مسمومیت مقدار** است (`SIG-01`)، نبود ستون.
4. «artifactها فاقد `artifact_hash`اند و لودر در production به escape hatch نیاز دارد» → **رد**: **۳۷/۳۷** فایل `metadata.json` هش sha256 دارند؛ مسیر `ML_ALLOW_UNVERIFIED_MODELS` امروز فعال نیست.
5. «F1 همچنان در **همه** مسیرها شکست میخورد / همه پیشبینیها موکاند» → **رد**: `_map_real_prediction` در مسیر batch صادقانه `prediction_failed: True` میدهد. ناسازگاری فقط بین batch و تکی است (`MLD-05`).
6. «تستهای ML در CI اجرا نمیشوند چون `ci.yml` نام `tests/unit/ml` را نبرده» → **رد**: همان نتیجهٔ قسمت ۰۸ — `ci.yml:276-280` اجرای کامل `pytest tests/unit` دارد و ۴۴ فایل تست ML را میگیرد.
7. «`/train` در production همیشه روی دادهٔ تصادفی آموزش میدهد» → **رد**: `apps/api/endpoints/ml.py:456` صریحاً `TrainingService(quote_repo=QuoteRepository(session=session))` میسازد. خطر synthetic مربوط به **jobها/سرویسهای بدون repo** و سه مسیر استثناء/خالی است، نه مسیر عادی endpoint (`MLD-02` با همین مرز نوشته شد).

---

## ۷ — مرز روش

- **هیچ چیز اجرا نشد**: نه pytest، نه بوت سرور، نه unpickle کردن artifact، نه اتصال به DB/Redis زنده، نه آموزش یا استنتاج. همه یافتهها ایستا و مبتنی بر خواندن فایل، `git status/diff` و جستجوی محدودشدهاند.
- شمارش **۳ پوشه / ۳۷ نسخه / صفر `stage=production`** روی **دیسک مخزن محلی** انجام شد. در استقرار واقعی ممکن است volume یا artifact registry خارجی مدلهای بیشتری فراهم کند؛ بنابراین `MLD-03` دربارهٔ «اکثریت نمادها heuristicاند» یک **استنتاج شرطی** است، نه مشاهدهٔ زماناجرای production.
- `MLD-04` (تکمدلی بودن رأیگیری)، `MLD-05` (سقوط به مدل آموزشندیده) و `MLD-08` (ناسازگاری امضا) **استنتاج از مسیر کد**اند؛ برای اثبات اجرایی نیاز به یک بکتست دوتایی/فراخوانی job با `inspect.signature` است. سه job `MLD-08` در scheduler فعلاً `add_job` نشدهاند، پس **ادعای خرابی زماناجرا نمیشود**.
- اعداد ۴۶٬۹۰۶ پیشبینی `prediction_failed=true` و ۳٬۷۰۵ رکورد دقت یتیم از `NUMERIC_AUDIT_2026-11-12.md` و گزارش ۱۶۰ لایهای نقل شدند و در این قسمت **بازشماری نشدند**.
- جستجوی «صفر مصرفکننده» در مسیرهای `ml/ services/ apps/ jobs/ core/ models/ brsapi/ src/ tests/` انجام شد؛ `.freebuff/worktrees/` عمداً مستثنا شد. محتوای ۴۴ فایل تست ML اجرا یا تحلیل نشد؛ دربارهٔ کافیبودن پوشش حکمی داده نمیشود.
- `ml/README.md` و ۳۱ فایل ML-named در `services/` بهصورت کامل خطبهخط خوانده نشدند؛ شواهد از فایلهای محوری (`ml_signal_connector`, `training_service`, `inference_service`, `auto_retrain_pipeline`, `model_loader`, `artifacts`, چهار رجیستری، `endpoints/ml.py`) گرفته شد.

---

## ۸ — خوشههای تازه برای ماتریس تجمیعی

| خوشه | یافتهها | شدت مؤثر | پیوند با قسمتهای قبل |
|---|---|---|---|
| **AA — مدل و رجیستری جعلی در production** | `MLD-01`, `MLD-06`, `MLD-14` | 🔴 بحرانی | رجیستری دموی `stage=production` به داشبورد؛ F1/accuracy = confidence ثابت؛ مستندات ۳۵۹ artifact در برابر ۳. مستقیم به `X` (قسمت ۰۸) و `S` (قسمت ۰۷) |
| **AB — داده آموزش ساختگی و حلقه بازآموزی مسموم** | `MLD-02`, `MLD-16`, `MLD-15` | 🔴 بحرانی | بالادست `BT-02` و `SIG-01`: OHLCV تصادفی seed 42 → مدل بدون provenance → بازآموزی `force=True` → دقت تطبیقی از جدول مسموم |
| **AC — استنتاج تکمدلی / شکست بلعیده / قراردادهای شکسته** | `MLD-03`, `MLD-04`, `MLD-05`, `MLD-07`, `MLD-08` | 🔴 بحرانی | heuristic بهجای ML (`SIG-05`)؛ رأیگیری هرگز رخ نمیدهد؛ تکرار `BT-04`؛ رجیستری فقط در API seed میشود (`SIG-13`, `JOB-07`) |
| **AD — تکثر ساختاری، پاکسازی ناامن و I/O بلاککننده** | `MLD-09`, `MLD-10`, `MLD-11`, `MLD-12`, `MLD-13` | 🟡 متوسط | ۴ رجیستری × ۴ FeatureStore؛ جدول feature بیرون `Base.metadata` (خوشه `I`)؛ `ml/inference/` مرده؛ `rmtree` کل پوشه؛ `async` بلاککننده |

**ترتیب بستن پیشنهادی** (بدون تغییر کد، صرفاً اولویت): `AB → AC → AA → X → W → S → T → Y → P → V → U → N → Q → H → B → AD → Z → …`.

**عبارت خلاصه قسمت ۰۹:** قسمت ۰۷ گفت «عددی که به دروازهها میرسد اندازهگیری نشده است»، قسمت ۰۸ گفت «همان عدد دروازهای هم ندارد»؛ قسمت ۰۹ نشان میدهد **منبع عدد هم ساختگی است**. زنجیرهٔ کامل اکنون پنج حلقه دارد: OHLCV تصادفی (`MLD-02`) → مدل روی ۳ artifact وگرنه قواعد دستی MA/RSI (`MLD-03`) → دقت ساختگی (`SIG-01`) → بازآموزی `force=True` و گیت پذیرش روی معاملات `±1.0` ساختگی (`BT-02`) → داشبوردی که مدل دموی `accuracy 0.871` و `stage=production` نشان میدهد (`MLD-01`). در برابر آن، **زیرساخت فنی واقعاً خوب است**: امضای HMAC، LRU وابسته به نسخه، سازگاری سه چیدمان artifact، تقسیم زمانی بدون shuffle و گیت خلوص معماری در CI. همان تمایز لایه ۱۳۲ گزارش اصلی — «امتیاز زیرساخت بالا، اعتبار نتایج نزدیک صفر» — اینبار نه بهدلیل **۴۶٬۹۰۶ ردیف شکستخوردهٔ قدیمی**، بلکه بهدلیل مسیرهای **فعال و سالمبهنظررسنده**ای که امروز هم عدد جعلی تولید میکنند.
