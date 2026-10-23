# بخش F — ML

> [خوانده‌شده+اجراشده] برای بازرسی آرتیفکت‌ها و آزمایش‌ها؛ [خوانده‌شده] برای کد.

---

## F1) مدل‌های ذخیره‌شده در `models/` و `ArtifactManager`

**وجود دارند.** روی دیسک `ml_artifacts/` شامل **۳۵۹ پوشه** مدل است:
```
212 xgboost | 20 lightgbm | 20 catboost | 18 random_forest | 18 huber_regressor
18 hist_gradient_boosting | 18 extra_trees | 18 bayesian_ridge | 17 stacking_ensemble
```
و جدول `ml_models` هم **۳۵۹ ردیف** دارد، همه با `created_at = 2026-08-02 08:53:54` (یک اجرای انبوه). برای خودرو، پنج خانواده مدل موجود است (`bayesian_ridge_خودرو`, `catboost_خودرو`, `extra_trees_خودرو`, `hist_gradient_boosting_خودرو`, `huber_regressor_خودرو`, و `xgboost_خودرو`).

هر پوشه نسخه‌هایی مثل `v1-a4f806b2/` دارد با `metadata.json` (۳٬۲۳۶ بایت) + `model_pipeline.pkl` (۲۰٬۴۲۷ بایت) و `latest_path.txt`.

**metadata مدل `xgboost_خودرو` (عین JSON):**
```json
"experiment_name": "xgboost-خودرو-20260718",
"created_at": "2026-07-18T22:18:20", "train_samples": 344,
"start_date": "2026-01-20", "end_date": "2026-07-19",
"metrics": {"mean_r2": -0.544574, "mean_directional_accuracy": 0.183032, "mean_mape": 125.589945},
"feature_names": [... 32 features: price + technical ...],
"feature_groups": ["price", "technical"]
```
⇒ خودِ متریک گزارش‌شدهٔ مدل: **دقت جهت ۱۸.۳٪ و R² منفی (−۰.۵۴)**؛ یعنی حتی مدل‌های ذخیره‌شده از شانس جهت‌دهی ضعیف‌ترند.

**علت صفر بودن مسیر `ml_signal` (ریشهٔ C1) [خوانده‌شده+اجراشده]:**
```
ArtifactManager().load_model('xgboost_خودرو')
→ FileNotFoundError [WinError 3] The system cannot find the path specified:
  'C:\\Users\\Iran\\Desktop\\temce\\data\\models\\xgboost_خودرو'
```
`ArtifactManager` ریشهٔ `settings.ml_model_dir` = `cwd/data/models` را می‌خواند، ولی آرتیفکت‌ها در `ml_artifacts/` هستند. لذا `services/backtest_service.py::_inject_ml_predictions`:
```python
model_id = strategy_params.get("model_id", f"xgboost_{symbol}")
...
model_obj, _ = artifact_mgr.load_model(model_id)   # ← FileNotFoundError
...
model = model_registry.create("xgboost")           # ← "Unknown model: xgboost"
```
⇒ مدل پیدا نمی‌شود ⇒ `b["predicted_change_pct"] = 0.0` ⇒ **صفر معامله**. (مدل وجود دارد؛ لودر مسیر اشتباه را می‌گردد.)

(توجه: `models/` پوشهٔ **مدل‌های ORM دیتابیس** است — `models/backtest.py`, `models/codal.py` … — نه آرتیفکت ML. آرتیفکت‌های ML در `ml_artifacts/` هستند.)

**تاریخچهٔ git:** ۴۷۶ کامیت؛ grep روی پیام‌ها چند کامیت مرتبط با ML نشان داد (مثلاً corporate-actions، options backtest). گردآوری «هرگز مدل آموزش داده نشده» رد می‌شود: مدل‌ها در `2026-08-02` ساخته شده‌اند.

---

## F2) مسیر آموزش و آزمایش کوچک [برچسب: آزمایشی، مدل پروژه نیست]

مسیر آموزش: `ml/training/trainer.py` + `services/training_service.py` + `services/ml_signal_connector.py` (که پس از آموزش، `WalkForwardValidator` را اجرا می‌کند). خروجی: پوشهٔ نسخه‌دار در `ml_artifacts/` + ردیف `ml_models`.

**آزمایش کوچک (خودم):** `audit_out/_tmp/partF_run.py` — ۵ نماد، ۲۰۲۴، ۵ فیچر ساده (ret_1, ret_5, ma5_ratio, vol_5, rsi_14)، برچسب = `close[t+5]/close[t]-1`، تقسیم زمانی ۷۰/۳۰، مدل `Ridge(alpha=1)`.

| سنجه | مقدار |
|---|---|
| ردیف‌ها / تست | ۱٬۰۶۸ / ۳۲۱ |
| **Pooled Spearman IC** | **۰.۱۱۸** |
| **RankIC مقطعی روزانه: میانگین** | **۰.۳۰۵** |
| RankIC انحراف معیار | ۰.۴۴۹ (بسیار پرنوسان) |
| **ICIR** | **۰.۶۷۹** (۶۴ روز) |
| IC تصادفی مورد انتظار | ۰.۰ |
| buy&hold ۵ نماد (میانگین) | +۱۳.۸۱٪ |

**خوانش صادقانه:** IC مقطعی روزانه (~۰.۳) با انحراف ۰.۴۵ و فقط ۶۴ روز، **خطای معیار بزرگ** دارد ⇒ قابل‌اتکا نیست. نرخ P/L استراتژی در این هارنس مطمئن محاسبه نشد (۰.۰ خروجی داد) و آن را گزارش نمی‌کنم. **این مدل پروژه نیست** — فقط نشان می‌دهد خط لولهٔ فیچر/برچسب ساده در این بازه، لبهٔ روشنی نمی‌سازد.

مقایسهٔ مفید: خودِ `xgboost_خودرو` پروژه دقت جهت `0.183` گزارش می‌کند (کمتر از شانس).

---

## F3) label shuffle (۳۰ بار) و canary

`audit_out/_tmp/partF3_run.py`، خروجی `audit_out/_tmp/partF3.json`:

| آزمون | نتیجه |
|---|---|
| label shuffle (۳۰ بار، IC) | **میانگین −۰.۰۰۹۷، انحراف ۰.۰۴۸** ⇒ **≈۰ ✅** |
| canary: افزودن «بازده فردا» به‌عنوان فیچر | **IC = ۰.۹۹۹** ⇒ خط لوله نشت را **نگرفت** ❌ |
| `pipeline_caught_canary` | **false** |

⇒ مدل با برچسب تصادفی فرو می‌ریزد (خوب)، اما **هیچ دروازهٔ نشت‌یابی** در خط لوله وجود ندارد و یک فیچر آینده‌بین را بی‌صدا می‌پذیرد (بد).

---

## جمع‌بندی بخش F

| id | شرح | شدت | فایل:خط | اقدام |
|---|---|---|---|---|
| F-01 | ۳۵۹ مدل وجود دارد ولی `ArtifactManager` ریشه را `data/models` می‌گیرد و آرتیفکت‌ها در `ml_artifacts/` ⇒ لودر شکست می‌خورد و ML صفر می‌شود | **بحرانی** | `ml/artifacts.py` + `services/backtest_service.py::_inject_ml_predictions` | یکسان‌سازی مسیر |
| F-02 | مدل‌های موجود دقت جهت ۱۸.۳٪ و R² منفی دارند | بالا | `ml_artifacts/xgboost_خودرو/*/metadata.json` | آموزش مجدد/ارزیابی |
| F-03 | آزمایش Ridge: pooled IC ۰.۱۱۸؛ RankIC روزانه ۰.۳۰۵±۰.۴۴۹ (ICIR ۰.۶۸، ۶۴ روز) | متوسط | `audit_out/_tmp/partF.json` | لبهٔ نامطمئن |
| F-04 | canary (فیچر آینده) بی‌صدا پذیرفته می‌شود (IC ۰.۹۹۹) | بالا | `ml/datasets`, `services/feature_engine.py` | گارد نشت |
| F-05 | label shuffle → IC ≈۰ (خوب) | مثبت | `audit_out/_tmp/partF3.json` | — |
