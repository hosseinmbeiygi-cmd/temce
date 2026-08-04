# 🤖 ml/ — سیستم یادگیری ماشین

> **آخرین به‌روزرسانی:** ۲۰۲۶-۰۸-۰۱ — فاز ۹

لایه ML سیستم بازار سرمایه ایران — آموزش، ارزیابی، استنتاج و مدیریت مدل‌های یادگیری ماشین
با معماری pipeline-based و registry pattern.

---

## 🏗️ معماری

```
┌─────────────────────────────────────────────┐
│                 Data Pipeline                │
│          (dataset_builder.py)               │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│              Feature Engineering             │
│          (features/ — BaseFeatureBuilder)    │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│                 Training                     │
│    (training/ — Trainer + CVTrainer)        │
└──────────────────┬──────────────────────────┘
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
┌─────────────────┐  ┌─────────────────────┐
│   Model Registry │  │   Artifact Store     │
│ (models/registry,│  │ (artifacts.py)       │
│  model_registry) │  │                      │
└─────────────────┘  └─────────────────────┘
         │                   │
         └─────────┬─────────┘
                   ▼
┌─────────────────────────────────────────────┐
│               Inference                      │
│   (inference/ — Predictor + Pipeline)       │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│              Evaluation                      │
│   (evaluation/ — MetricsCalculator)         │
└─────────────────────────────────────────────┘
```

---

## 📁 ساختار

### 🧠 مدل‌ها (`models/`)
| فایل | توضیح |
|------|-------|
| `base.py` | `BaseModel` — کلاس abstract با fit/predict/save/load |
| `registry.py` | `ModelRegistry` — ثبت و ساخت مدل با نام |
| `__init__.py` | پیاده‌سازی‌های آماده مدل |

### 🏋️ آموزش (`training/`)
| فایل | توضیح |
|------|-------|
| `trainer.py` | `Trainer` — آموزش استاندارد با validation و محاسبه metrics |
| `cv_trainer.py` | `CVTrainer` — cross-validation training |
| `__init__.py` | export trainer classes |

### 🔮 استنتاج (`inference/`)
| فایل | توضیح |
|------|-------|
| `predictor.py` | `Predictor` — single prediction با model caching |
| `pipeline.py` | `PredictionPipeline` — multi-step preprocessing + prediction |
| `__init__.py` | export predictor classes |

### 🏗️ ویژگی‌ها (`features/`)
| فایل | توضیح |
|------|-------|
| `base.py` | `BaseFeatureBuilder` — compute, get_feature_names, compute_from_dict |
| `__init__.py` | feature builder implementations |

### 📊 ارزیابی (`evaluation/`)
| فایل | توضیح |
|------|-------|
| `metrics.py` | `MetricsCalculator` — regression (MAE, MSE, RMSE, MAPE, R²) + classification (Accuracy, Precision, Recall, F1, AUC) |

### 📦 مدیریت
| فایل | توضیح |
|------|-------|
| `artifacts.py` | `ArtifactManager` — save/load مدل‌ها |
| `feature_store.py` | `FeatureStore` — ثبت و مدیریت featureها با group |
| `model_registry.py` | `ModelRegistry` — versioning، staging، metadata |
| `global_registry.py` | Global registry instance |
| `dataset_builder.py` | ساخت dataset از داده‌های خام |
| `experiments.py` | مدیریت experimentها |
| `types.py` | `FeatureMatrix`، `PredictionResult`، `TargetVector`، `ModelArtifactMeta` |
| `policies.py` | سیاست‌های training/inference |
| `metrics.py` | متریک‌های سطح بالا |

---

## 🔑 الگوهای طراحی

### Registry Pattern
```python
from ml.models.registry import model_registry
from ml.models.base import BaseModel

# ثبت مدل
model_registry.register("random_forest", RandomForestModel)

# ساخت نمونه
model = model_registry.create("random_forest", params={"n_estimators": 100})
```

### Pipeline Pattern
```python
from ml.training.trainer import Trainer
from ml.inference.predictor import Predictor
from ml.artifacts import ArtifactManager

# آموزش
trainer = Trainer()
result = await trainer.train(model, X_train, y_train, X_val, y_val)

# استنتاج
predictor = Predictor(ArtifactManager())
pred = await predictor.predict("my_model", features)
```

### Feature Store
```python
from ml.feature_store import FeatureStore

store = FeatureStore()
store.register_feature("rsi_14", group="momentum", dtype="float64")
store.register_feature("volume_ratio", group="volume", dtype="float64")
features = store.get_features_by_group("momentum")
```

---

## 📊 متریک‌های ارزیابی

### Regression
| متریک | توضیح |
|-------|-------|
| MAE | Mean Absolute Error |
| MSE | Mean Squared Error |
| RMSE | Root Mean Squared Error |
| MAPE | Mean Absolute Percentage Error |
| R² | R-squared (ضریب تعیین) |

### Classification
| متریک | توضیح |
|-------|-------|
| Accuracy | دقت کل |
| Precision | دقت مثبت |
| Recall | بازخوانی |
| F1 | میانگین هارمونیک Precision/Recall |
| AUC | Area Under ROC Curve |

---

## 🧪 تست‌ها

- **۲۰ تست پاس** ✅ — پوشش dataset builder، feature store، forecast metrics، model registry
- **ruff پاک** ✅ — بدون خطا در کل ۱۴ فایل + ۷ زیرپوشه
- **همه importها سالم** ✅

---

## 🚀 اجرای سریع

```python
import pandas as pd
from ml.training.trainer import Trainer
from ml.models.base import BaseModel
from ml.evaluation.metrics import MetricsCalculator

# داده
df = pd.read_parquet("features.parquet")
X = FeatureMatrix(data=df.drop("target", axis=1))
y = TargetVector(data=df["target"])

# آموزش
trainer = Trainer()
result = await trainer.train(model, X, y)

# ارزیابی
y_pred = result.value.predictions  # خروجی مدل
calc = MetricsCalculator()
metrics = calc.compute(y.values, y_pred, task="regression")
print(f"R²: {metrics['r2']:.3f}, RMSE: {metrics['rmse']:.3f}")
```
