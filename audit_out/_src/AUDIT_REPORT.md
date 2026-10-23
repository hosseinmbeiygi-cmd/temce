# گزارش ممیزی جامع — سیستم معاملات الگوریتمی بازار سرمایه ایران

**نسخه پروژه:** iran-market-platform v0.1.0  
**تاریخ ممیزی:** 2026-08-23  
**معمار ممیز:** Senior Software Architect & Quantitative Financial Systems Specialist  
**سطح ممیزی:** Deep-Dive (عمیق و ساختاری)

---

## وضعیت اصلاحات (Fix Status)

| # | ریسک | فایل | وضعیت |
|---|---|---|---|
| 1 | Default Release در خطا | `services/quant_signal_orchestrator.py` | ✅ اصلاح شد (Fail-closed) |
| 2 | Data Quality هاردکد 1.0 | `services/quant_signal_orchestrator.py` | ✅ اصلاح شد (محاسبه واقعی) |
| 3 | Smart Money weights هاردکد | `services/smart_money/layer1_price_volume.py` | ✅ اصلاح شد (Config-driven) |
| 4 | تکرار RSI/ATR/Trend | 3 فایل | ✅ اصلاح شد (`core/indicators.py` واحد) |
| 5 | عدم احتساب هزینه در بک‌تست | `services/signal_backtest_engine.py` | ✅ اصلاح شد |
| 6 | عدم Walk-Forward در آموزش ML | `services/ml_signal_connector.py` | ✅ اصلاح شد |
| 7 | MACD با SMA به جای EMA | `services/feature_engine.py` | ✅ اصلاح شد |
| 8 | Sharpe بدون annualization | `services/signal_backtest_engine.py` | ✅ اصلاح شد |
| 9 | Max Drawdown با cumsum | `services/signal_backtest_engine.py` | ✅ اصلاح شد (cumprod) |
| 10 | Buckets کالیبراتور نامتقارن | `services/probability_calibrator.py` | ✅ اصلاح شد (متقارن) |
| 11 | Profit Factor floor 0.001 | `services/signal_backtest_engine.py` | ✅ اصلاح شد |
| 12 | Trend Strength ناسازگار | `services/confidence_scorer.py` | ✅ اصلاح شد (یکپچه) |
| 13 | Volatility ناسازگار | `services/confidence_scorer.py` | ✅ اصلاح شد (یکپچه) |
| 14 | cost_r بدون abs() | `services/signal_decision_engine.py` | ✅ اصلاح شد |
| 15 | Walk-forward thresholds ضعیف | `services/walk_forward_validator.py` | ✅ اصلاح شد |
| 16 | Paper trading stop/target ثابت | `services/paper_trading_service.py` | ✅ اصلاح شد |
| 17 | RSI/ATR بدون Wilder's | `core/indicators.py` (جدید) | ✅ اصلاح شد (Wilder's) |
| 18 | کد تکراری feature_engine | `services/feature_engine.py` | ✅ اصلاح شد |

**فایل‌های ایجاد‌شده:**
- `core/indicators.py` — ماژول واحد اندیکاتورهای تکنیکال (RSI, ATR, MACD, Trend, Volatility, Data Quality)

---

## فهرست مطالب

1. [نمای کلی پروژه](#1-نمای-کلی-پروژه)
2. [بخش اول: تحلیل ساختار و کدهای تکراری (DRY & Refactoring)](#2-بخش-اول-تحلیل-ساختار-و-کدهای-تکراری-dry--refactoring)
3. [بخش دوم: بررسی معماری و ارتباطات سرویس‌ها](#3-بخش-دوم-بررسی-معماری-و-ارتباطات-سرویسها)
4. [بخش سوم: تحلیل منطق مالی و کارکردهای اصلی](#4-بخش-سوم-تحلیل-منطق-مالی-و-کارکردهای-اصلی)
5. [بخش چهارم: ممیزی سیگنال‌دهی، یادگیری ماشین و بک‌تست](#5-بخش-چهارم-ممیزی-سیگنالدهی-یادگیری-ماشین-و-بکتست)
6. [جدول ریسک‌های کلیدی](#6-جدول-ریسکهای-کلیدی)
7. [جمع‌بندی و نقشه راه](#7-جمعبندی-و-نقشه-راه)

---

## 1. نمای کلی پروژه

### مشخصات فنی

| ویژگی | جزئیات |
|---|---|
| **زبان** | Python 3.11 |
| **فریم‌ورک** | FastAPI + SQLAlchemy 2.0 + AsyncPG |
| **پایگاه‌داده** | PostgreSQL + TimescaleDB |
| **کش** | Redis |
| **ML** | scikit-learn, XGBoost, LightGBM, PyTorch |
| **استقرار** | Docker Compose (API, Worker, Scheduler, Decision-Engine, Admin, Frontend) |
| **اندپوینت‌ها** | 60+ |

### معماری کلی

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                        │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST / WebSocket
┌──────────────────────────┴──────────────────────────────────┐
│                     FastAPI Gateway                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │  Auth    │ │ Signal   │ │  ML      │ │ Backtest │       │
│  │  (JWT)   │ │ Service  │ │ Service  │ │ Service  │       │
│  └──────────┘ └────┬─────┘ └────┬─────┘ └──────────┘       │
│                     │            │                             │
│  ┌──────────────────┴────────────┴──────────────────────┐    │
│  │           Quant Signal Orchestrator (7 مرحله‌ای)       │    │
│  │  Rule Engine → ML → Voting → Calibration → Decision  │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│  PostgreSQL/TimescaleDB  │  Redis  │  External APIs (BRS,   │
│  brsapi, codal, crypto   │         │  TSE, Codalthing)       │
└─────────────────────────────────────────────────────────────┘
```

### ساختار پوشه‌های اصلی

```
temce/
├── backend/              ← اپلیکیشن اصلی FastAPI
├── core/                 ← ماژول‌های هسته (DB, cache, logging)
├── domain/               ← منطق دامنه (options, pricing, probability)
├── services/             ← سرویس‌های کاربردی (۱۹۳۷ خط در orchestrator تنها)
│   ├── smart_money/      ← موتور Smart Money (۹ لایه)
│   ├── ml/               ← مدل‌های ML (XGBoost, LSTM, Transformer, GRU)
│   └── signal_*.py       ← سیگنال‌دهی، بک‌تست، اعتماد، احتمال
├── ingestion/            ← دریافت داده
├── brsapi/               ← اتصال به بورس تهران
├── codal_data/           ← داده‌های کدال
├── crypto_history/       ← داده‌های رمزارز
├── iran_market_data/     ← داده‌های بازار ایران
├── pipelines/            ← پایپ‌لاین‌های ML
├── ml/                   ← مدل‌های ML آموزش‌دیده
├── backtesting/          ← موتور بک‌تست
├── ml_artifacts/         ← مصنوعات ML (پیش‌بینی‌ها، وزن‌ها)
├── charts/               ← سرویس رسم نمودار
├── apps/api/endpoints/   ← ۶۰+ اندپوینت
├── providers/            ← ارائه‌دهندگان داده
├── schemas/              ← اسکیماهای Pydantic
├── repositories/         ← لایه مخزن (Repository Pattern)
├── scripts/              ← اسکریپت‌های کمکی
├── orchestration/        ← هماهنگ‌کننده‌ها
├── jobs/                 ← کارهای زمان‌بندی‌شده
├── config/               ← فایل‌های پیکربندی YAML/JSON
├── deploy/               ← استقرار
└── frontend/             ← فرانت‌اند
```

---

## 2. بخش اول: تحلیل ساختار و کدهای تکراری (DRY & Refactoring)

### 2.1 تکرار محاسبات RSI

**شدت:** متوسط  
**فایل‌های متاثر:** ۲ فایل

**شواهد:**
- `services/signal_feature_pipeline.py:266` — `_compute_rsi()` (ساده، بدون Wilder's smoothing)
- `services/feature_engine.py:945` — `_compute_rsi()` (کد یکسان، فقط کامنت فارسی)

هر دو پیاده‌سازی دقیقاً یکسان هستند: میانگین ساده gains/losses در  period 14، RS formula، خروجی 0-100.

---

**راه‌حل ۱: استخراج به ماژول مشترک `core/indicators.py`**

```python
# core/indicators.py
@staticmethod
def compute_rsi(closes: list[float], period: int = 14, wilder: bool = True) -> float:
    ...
```

| معیار | امتیاز (از ۱۰) |
|---|---|
| صحت محاسباتی | ۱۰ — منبع واحد |
| قابلیت تست | ۹ — یک بار تست می‌کنید، همه‌جا استفاده می‌شود |
| مهاجرت | ۸ — فقط import تغییر می‌کند |
| **مجموع** | **۹.۰** |

---

**راه‌حل ۲: استفاده از کتابخانه `ta-lib` или `pandas-ta`**

| معیار | امتیاز (از ۱۰) |
|---|---|
| صحت محاسباتی | ۸ — کتابخانه شخص ثالث |
| قابلیت تست | ۹ |
| مهاجرت | ۷ — نیاز به pandas/numpy |
| **مجموع** | **۸.۰** |

---

**راه‌حل ۳: ساخت کلاس `TechnicalCalculator` با الگوی Strategy**

| معیار | امتیاز (از ۱۰) |
|---|---|
| صحت محاسباتی | ۱۰ |
| قابلیت تست | ۸ |
| مهاجرت | ۶ — تغییر ساختاری بزرگ |
| **مجموع** | **۷.۵** |

> **🏆 روش برگزیده: راه‌حل ۱**  
> **دلیل فنی:** ساده‌ترین، سریع‌ترین، و ایمن‌ترین راهکار. نیازی به تغییر ساختاری نیست — فقط import و فراخوانی. از آنجا که هر دو پیاده‌سازی بدون Wilder's smoothing هستند، اضافه کردن پارامتر `wilder` انتخابی می‌تواند هر دو روش را پوشش دهد.

---

### 2.2 تکرار محاسبات ATR

**شدت:** متوسط  
**فایل‌های متاثر:** ۲ فایل

**شواهد:**
- `services/signal_feature_pipeline.py:283` — `_compute_atr()` (ساده، بدون Wilder's)
- `services/feature_engine.py:977` — `_compute_atr()` (مشابه، با مقدار پیش‌فرض ۰.۰ به جای None)

تفاوت کوچکی در خروجی وجود دارد: نسخه اول `None` برمی‌گرداند وقتی داده کافی نیست، نسخه دوم `0.0`. این تناقض می‌تواند باعث باگ شود.

---

**راه‌حل ۱: یکپچه‌سازی در `core/indicators.py` (مشابه RSI)**

| معیار | امتیاز |
|---|---|
| صحت | ۱۰ |
| مهاجرت | ۹ |
| **مجموع** | **۹.۵** |

**راه‌حل ۲: استفاده از `ta-lib` ATR**

| معیار | امتیاز |
|---|---|
| صحت | ۸ |
| مهاجرت | ۷ |
| **مجموع** | **۷.۵** |

**راه‌حل ۳: نگه داشتن دو نسخه با یکسان‌سازی خروجی (None یا 0.0)**

| معیار | امتیاز |
|---|---|
| صحت | ۷ |
| مهاجرت | ۱۰ |
| **مجموع** | **۷.۰** |

> **🏆 روش برگزیده: راه‌حل ۱**  
> **دلیل فنی:** منبع واحد + رفع تناقض خروجی None/0.0

---

### 2.3 تکرار محاسبات Trend Strength (تناقض فرمولی)

**شدت:** بالا  
**فایل‌های متاثر:** ۲ فایل، ۲ فرمول متفاوت

**شواهد:**
- `services/signal_feature_pipeline.py:297` — `_trend_strength()`: نسبت روزهای صعودی (`up_days / period`)
- `services/confidence_scorer.py:309` — `_compute_trend_strength()`: منطق ADX-like (`abs(up - down) / total * 1.5`)

این دو برای یک مفهوم نتایج متفاوت می‌دهند. ممکن است مدل ML از فرمول اول و امتیازدهی اعتماد از فرمول دوم استفاده کند — این یک باگ پنهان است.

---

**راه‌حل ۱: تعریف یک فرمول استاندارد در `core/indicators.py` و استفاده یکسان همه‌جا**

| معیار | امتیاز |
|---|---|
| صحت | ۱۰ |
| یکپارچگی | ۱۰ |
| مهاجرت | ۸ |
| **مجموع** | **۹.۵** |

**راه‌حل ۲: نگه داشتن هر دو فرول اما با نام‌گذاری صریح (مثلاً `simple_trend_ratio` و `directional_trend_strength`)**

| معیار | امتیاز |
|---|---|
| صحت | ۷ |
| یکپارچگی | ۵ |
| مهاجرت | ۹ |
| **مجموع** | **۶.۵** |

**راه‌حل ۳: ترکیب دو فرمول به یک امتیاز ترکیبی وزن‌دار**

| معیار | امتیاز |
|---|---|
| صحت | ۸ |
| یکپارچگی | ۸ |
| مهاجرت | ۷ |
| **مجموع** | **۷.۵** |

> **🏆 روش برگزیده: راه‌حل ۱**  
> **دلیل فنی:** دو فرمول برای یک مفهوم یک باگ است. باید یک تعریف دقیق انتخاب شود. پیشنهاد می‌شود فرمول ADX-like (confidence_scorer) استفاده شود چون حساسیت بیشتری به قدرت روند دارد.

---

### 2.4 تکرار محاسبات Volatility

**شدت:** پایین-متوسط  
**فایل‌های متاثر:** ۲ فایل

**شواهد:**
- `services/signal_feature_pipeline.py:102` — `np.std(returns)` خام
- `services/confidence_scorer.py:332` — `np.std(returns) * 20` (نرمال‌سازی با مقیاس ثابت)

فرمول پایه یکسان است اما مقیاس‌دهی متفاوت. نرمال‌سازی `*20` در confidence_scorer یک عدد جادویی است.

---

**راه‌حل ۱: یکپچه‌سازی با نرمال‌سازی قابل تنظیم در config**

| معیار | امتیاز |
|---|---|
| صحت | ۹ |
| قابلیت تنظیم | ۱۰ |
| مهاجرت | ۸ |
| **مجموع** | **۹.۰** |

**راه‌حل ۲: استفاده از Realized Volatility (Sum of squared returns) به جای انحراف معیار**

| معیار | امتیاز |
|---|---|
| صحت | ۸ |
| قابلیت تنظیم | ۷ |
| مهاجرت | ۷ |
| **مجموع** | **۷.۵** |

**راه‌حل ۳: حفظ تفاوت با مستندسازی صریح**

| معیار | امتیاز |
|---|---|
| صحت | ۷ |
| قابلیت تنظیم | ۵ |
| مهاجرت | ۹ |
| **مجموع** | **۶.۵** |

> **🏆 روش برگزیده: راه‌حل ۱**  
> **دلیل فنی:** مقیاس‌دهی ثابت (`*20`) باید قابل تنظیم باشد. مقیاس‌دهی برای روزانه، هفتگی و ساعتی باید متفاوت باشد.

---

### 2.5 تکرار وزن‌های Smart Money Layer

**شدت:** بالا  
**فایل‌های متاثر:** `smart_money/layer1_price_volume.py:48` + `config/smart_money.yaml:14`

**شواهد:** کد وزن‌ها را هاردکد کرده است (`0.20, 0.20, 0.15, 0.15, 0.15, 0.15`)، در حالی که همین وزن‌ها در YAML تعریف شده‌اند. اما کد YAML را نمی‌خواند — تغییر config تاثیری در خروجی ندارد.

---

**راه‌حل تزریق وزن از config:**

| معیار | امتیاز |
|---|---|
| صحت | ۱۰ |
| قابلیت تنظیم | ۱۰ |
| مهاجرت | ۸ |
| **مجموع** | **۹.۵** |

---

### 2.6 تکرار `_extract_stock_features` برای بازارهای مختلف

**شدت:** متوسط  
**فایل:** `services/signal_feature_pipeline.py:180`

**شواهد:** طلا، ارز و کالا همگی از `_extract_stock_features()` استفاده می‌کنند — متدی که `real_buy_ratio` را محاسبه می‌کند (یک ویژگی مخصوص بورس). این ویژگی برای این بازارها همیشه ۰.۰ خواهد بود.

---

**راه‌حل استخراج `_extract_base_features` + افزودن ویژگی‌های اختصاصی:**

| معیار | امتیاز |
|---|---|
| صحت | ۱۰ |
| یکپارچگی | ۱۰ |
| مهاجرت | ۸ |
| **مجموع** | **۹.۰** |

---

### 2.7 سینگلتون ناسازگار

**شدت:** متوسط

**شواهد:** برخی سرویس‌ها (`SignalDecisionEngine`, `QuantSignalOrchestrator`) از سینگلتون استفاده می‌کنند، برخی دیگر (`MLSignalConnector`, `ConfidenceScorer`) هر بار instantiating می‌شوند. این باعث رفتار غیرقابل پیش‌بینی کش و state می‌شود.

---

**راه‌حل یکپچه‌سازی با الگوی Dependency Injection:**

| معیار | امتیاز |
|---|---|
| صحت | ۱۰ |
| تست‌پذیری | ۱۰ |
| مهاجرت | ۷ |
| **مجموع** | **۸.۵** |

---

## 3. بخش دوم: بررسی معماری و ارتباطات سرویس‌ها

### 3.1 ارتباطات سرویسی

**مشکل:** سرویس‌ها در یک فرآیند Python اجرا می‌شوند. ارتباط از طریق import مستقیم است. هیچ message queue، RPC، یا event bus وجود ندارد. این یک monolith است که به microservice تقلیل می‌دهد.

---

**راه‌حل сохран  monolith با ماژولاریزاسیون داخلی:**

| معیار | امتیاز |
|---|---|
| پایداری | ۸ |
| مقیاس‌پذیری | ۷ |
| مهاجرت | ۱۰ |
| **مجموع** | **۸.۰** |

> **🏆 روش برگزیده: راه‌حل ۲ (ماژولار Monolith)**  
> **دلیل فنی:** تقسیم به microservice برای این پروژه هنوز زود است. ماژولاریزاسیون داخلی با رابط‌های واضح (ABC) بهترین تعادل بین پیچیدگی و نگهداری‌پذیری است.

### 3.2 مدیریت Database Session

**مشکل:** `QuantSignalOrchestrator._fetch_smart_money_analyses()` (خط 1318) برای هر کار همزمان session جدید می‌سازد. این درست است اما می‌تواند باعث اتصال‌های بیش از به pool شود.

**مشکل دوم:** `SignalDecisionEngine` session دریافت می‌کند اما داخلی برای regime detection session جدید می‌سازد (خط 1009).

---

**راه‌حل استفاده از Session Pool با Semaphore:**

| معیار | امتیاز |
|---|---|
| پایداری | ۱۰ |
| مقیاس‌پذیری | ۹ |
| مهاجرت | ۷ |
| **مجموع** | **۸.۵** |

### 3.3 اعتبارسنجی ورودی

**شواهد:** `SignalService.generate()` پارامترهای `**kwargs` را بدون اعتبارسنجی به سرویس‌ها می‌فرستد.

---

### 3.4 در صورت خطا در Decision Engine، سیگنال آزاد می‌شود

**شدت:** بحرانی  
**فایل:** `services/quant_signal_orchestrator.py:1221`

```python
except Exception as inner_e:
    logger.debug("Decision engine failed for %s: %s — keeping signal", sig.symbol, inner_e)
    sig.decision_verdict = "release"
    sig.decision_grade = "UNGATED"
    released.append(sig)
```

و بدتر — در خط 1233:

```python
except Exception as e:
    logger.warning("Signal decision batch failed: %s — releasing all signals", e)
    for sig in signals:
        sig.decision_verdict = "release"
        sig.decision_grade = "UNGATED"
    return signals, []
```

این یعنی هر خطا (مثلاً timeout پایگاه داده، خطای ML model) باعث آزاد شدن تمام سیگنال‌ها بدون هیچ gate می‌شود.

---

**راه‌حل ۱: Fail-closed — در صورت خطا، سیگنال رد شود (reject)**

| معیار | امتیاز |
|---|---|
| امنیت مالی | ۱۰ |
| پایداری | ۱۰ |
| مهاجرت | ۱۰ — فقط تغییر "release" به "reject" |
| **مجموع** | **۱۰** |

**راه‌حل ۲: Dead-letter queue — سیگنال‌های خطا را در صف قرار دهید و بعداً پردازش کنید**

| معیار | امتیاز |
|---|---|
| امنیت مالی | ۸ |
| پایداری | ۹ |
| مهاجرت | ۶ — نیاز به زیرساخت جدید |
| **مجموع** | **۷.۵** |

**راه‌حل ۳: Watchlist — سیگنال‌ها را به watchlist بفرستید نه release**

| معیار | امتیاز |
|---|---|
| امنیت مالی | ۷ |
| پایداری | ۸ |
| مهاجرت | ۱۰ |
| **مجموع** | **۸.۰** |

> **🏆 روش برگزیده: راه‌حل ۱ (Fail-closed)**  
> **دلیل فنی:** در سیستم معاملاتی، آزاد کردن یک سیگنال بدون بررسی، خطر مالی ایجاد می‌کند. Fail-closed امن‌ترین است. اگر سیستم از کار افتاد، هیچ سیگنالی نباید منتشر شود.

---

### 3.5 Data Quality Score هاردکرد شده

**شدت:** بحرانی  
**فایل:** `services/quant_signal_orchestrator.py:1192`

```python
data_quality_score=1.0,
liquidity_score=0.7,
fill_probability=0.7,
portfolio_risk_approved=True,
open_risk_pct=0.0,
correlated_exposure_pct=0.0,
```

این مقادیر هاردکد شده باعث می‌شوند Gate 1 (Data Quality)، Gate 6 (Liquidity) و Gate 9 (Portfolio) کاملاً دور زده شوند.

---

**راه‌حل ۱: محاسبه واقعی Data Quality از روی داده‌های ورودی**

| معیار | امتیاز |
|---|---|
| امنیت مالی | ۱۰ |
| صحت | ۱۰ |
| مهاجرت | ۷ |
| **مجموع** | **۹.۰** |

> **🏆 روش برگزیده: راه‌حل ۱**  
> **دلیل فنی:** Data Quality Score باید از روی تعداد نقاط داده، تازگی، اتساق و خطاهای قابل مشاهده محاسبه شود.

---

### 3.6 Lazy Imports و Circular Import Risk

**شدت:** متوسط

**شواهد:** `signal_service.py:38` و `quant_signal_orchestrator.py` import های داخل متد دارند. این روش circular import را حل می‌کند اما ردیابی dependency را دشوار می‌کند.

---

**راه‌حل بازسازی با ABC و Protocol:**

| معیار | امتیاز |
|---|---|
| صحت | ۱۰ |
| قابلیت نگهداری | ۱۰ |
| مهاجرت | ۶ |
| **مجموع** | **۸.۵** |

---

## 4. بخش سوم: تحلیل منطق مالی و کارکردهای اصلی

### 4.1 Signal Decision Engine — ۱۰ گیت

**فایل:** `services/signal_decision_engine.py` (۱۱۳۳ خط)

#### محاسبه Net Expectancy

```python
gross = win_rate * rr - loss_rate * 1.0
cost_r = costs_pct / stop_loss_pct
net_expectancy = gross - cost_r
```

**نقد:** فرمول `cost_r = costs_pct / stop_loss_pct` درست است (هزینه به نسبت ریسک)، اما `loss_rate * 1.0` فرض می‌کند که ضرر همیشه ۱R است. در واقعیت، ضرر واقعی باید بر اساس stop_loss و اسلات محاسبه شود.

---

**راه‌حل ۱: استفاده از فرمول Expectancy استاندارد:**

```
E = (win_rate * avg_win) - (loss_rate * avg_loss) - costs
```

| معیار | امتیاز |
|---|---|
| صحت مالی | ۱۰ |
| دقت | ۱۰ |
| مهاجرت | ۸ |
| **مجموع** | **۹.۵** |

> **🏆 روش برگزیده: راه‌حل ۱**  
> **دلیل فنی:** فرمول فعلی `loss_rate * 1.0` از آنجا که R به معنای risk است، درست است. اما `cost_r` باید به صورت `costs_pct / abs(stop_loss_pct)` با مقدار مطلق محاسبه شود تا مقادیر منفی stop_loss باعث خطا نشود.

---

### 4.2 Smart Money — عدم خواندن وزن‌ها از Config

**شدت:** بالا  
**فایل:** `services/smart_money/layer1_price_volume.py:48`

**شواهد:** وزن‌ها هاردکد شده‌اند. YAML موجود در `config/smart_money.yaml` خوانده می‌شود اما به لایه‌ها ارسال نمی‌شود.

---

**راه‌حل ۱: سازنده لایه را وزن‌ها را از config دریافت کند**

```python
class PriceVolumeLayer:
    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or DEFAULT_WEIGHTS
```

| معیار | امتیاز |
|---|---|
| صحت | ۱۰ |
| قابلیت تنظیم | ۱۰ |
| مهاجرت | ۹ |
| **مجموع** | **۹.۵** |

> **🏆 روش برگزیده: راه‌حل ۱**  
> **دلیل فنی:** فقط تغییر سازنده — ساده و بدون ریسک. Fallback به DEFAULT_WEIGHTS اگر config موجود نباشد.

---

### 4.3 Feature Engine — ثابت‌های اقتصادی هاردکد

**شدت:** متوسط  
**فایل:** `services/feature_engine.py`

```python
_BASE_FX_CURRENT = 28500.0
_INFLATION_RATE = 35.0
_BANK_INTEREST_RATE = 22.5
_INVESTABLE_CAPITAL = 500_000_000
```

---

**راه‌حل ۱: استفاده از API بانک مرکزی یا داده‌های بازار**

| معیار | امتیاز |
|---|---|
| صحت | ۱۰ |
| به‌روزرسانی | ۱۰ |
| مهاجرت | ۶ |
| **مجموع** | **۸.۵** |

> **🏆 روش برگزیده: راه‌حل ۲ (Config + بروزرسانی دستی)**  
> **دلیل فنی:** API بانک مرکزی ایران ناپایدار است. ترکیب یک cron job با config بهترین تعادل است.

---

### 4.4 Feature Engine — ویژگی‌های رویداد  placeholder

**شدت:** متوسط  
**فایل:** `services/feature_engine.py` بلوک G

**شواهد:** ۱۸ از ۲۰ ویژگی رویداد (اخبار، آگاهی‌رسانی بورس، مجمع و غیره) همیشه ۰.۰ هستند.

---

**راه‌حل حذف بلوک G و جایگزینی با طراحی plugin-based:**

| معیار | امتیاز |
|---|---|
| صحت | ۹ |
| قابلیت توسعه | ۱۰ |
| مهاجرت | ۷ |
| **مجموع** | **۸.۵** |

> **🏆 روش برگزیده: راه‌حل ۲ (Plugin-based)**  
> **دلیل فنی:** هر منبع داده رویدادی باید یک plugin جداگانه باشد. حذف از feature matrix اگر داده ندارید، کاهش نویز ML است.

---

### 4.5 Probability Calibrator — buckets از 0.50 شروع می‌کند

**شدت:** متوسط  
**فایل:** `services/probability_calibrator.py`

**شواهد:** `DEFAULT_BUCKETS = [0.50, 0.55, 0.60, ...]` — احتمالات زیر 0.50 همه در یک bucket قرار می‌گیرند. این برای سیستمی که جهت را هم پیش‌بینی می‌کند (buy/sell) نامناسب است.

---

**راه‌حل ۱: Buckets متقارن در هر دو جهت (مثلاً 0.05 تا 0.95)**

| معیار | امتیاز |
|---|---|
| صحت کالیبراسیون | ۱۰ |
| گرانولاریته | ۱۰ |
| مهاجرت | ۸ |
| **مجموع** | **۹.۵** |

> **🏆 روش برگزیده: راه‌حل ۱**  
> **دلیل فنی:** کالیبراسیون باید برای هر دو جهت (buy/sell) دقیق باشد. Buckets فعلی فقط برای جهت buy مناسب است.

---

### 4.6 MACD Signal ساده‌شده

**فایل:** `services/feature_engine.py:962`

```python
ema12 = sum(closes[-12:]) / 12   # SMA به جای EMA!
ema26 = sum(closes[-26:]) / 26
signal = sum(closes[-9:]) / 9     # SMA به جای EMA!
```

**شواهد:** فرمول EMA واقعی از SMA استفاده می‌کند، اما این فقط میانگین ساده است. این یک خطای محاسباتی است.

---

**راه‌حل ۱: پیاده‌سازی EMA واقعی با smoothing factor**

| معیار | امتیاز |
|---|---|
| صحت مالی | ۱۰ |
| دقت | ۱۰ |
| مهاجرت | ۹ |
| **مجموع** | **۹.۵** |

> **🏆 روش برگزیده: راه‌حل ۱**  
> **دلیل فنی:** EMA با SMA تفاوت‌های معنادار دارد، به خصوص در بازارهای پرنوسان. خطای سیستماتیک در سیگنال‌دهی ایجاد می‌کند.

---

## 5. بخش چهارم: ممیزی سیگنال‌دهی، یادگیری ماشین و بک‌تست

### 5.1 Backtesting — عدم احتساب هزینه‌های معاملاتی

**شدت:** بالا  
**فایل:** `services/signal_backtest_engine.py`

**شواهد:** موتور بک‌تست هیچ هزینه معاملاتی (کمیسیون، مالیات، slippage) را احتساب نمی‌کند. `signal_decision_engine.py` از `costs_pct` استفاده می‌کند، اما backtest این را نادیده می‌گیرد.

---

**راه‌حل ۱: اعمال هزینه ثابت به ازای هر معامله**

```python
NET_RETURN = gross_return - (commission_pct + slippage_pct + tax_pct)
```

| معیار | امتیاز |
|---|---|
| صحت مالی | ۱۰ |
| سادگی | ۱۰ |
| مهاجرت | ۹ |
| **مجموع** | **۹.۵** |

**راه‌حل ۲: مدل هزینه پویا بر اساس حجم و بازار**

| معیار | امتیاز |
|---|---|
| صحت مالی | ۱۰ |
| سادگی | ۷ |
| مهاجرت | ۶ |
| **مجموع** | **۷.۵** |

**راه‌حل ۳: Config شده بازار به بازار در YAML**

| معیار | امتیاز |
|---|---|
| صحت مالی | ۹ |
| سادگی | ۸ |
| مهاجرت | ۸ |
| **مجموع** | **۸.۵** |

> **🏆 روش برگزیده: راه‌حل ۳ (Config شده بازار به بازار)**  
> **دلیل فنی:** هر بازار (بورس، طلا، ارز، کالا، رمزارز) ساختار کمیسیون متفاوتی دارد. Config انعطاف را فراهم می‌کند بدون اضافه کردن پیچیدگی غیرضروری.

---

### 5.2 Backtesting — Sharpe Ratio بدون Annualization

**شدت:** متوسط  
**فایل:** `services/signal_backtest_engine.py:318`

```python
result.sharpe = mean_r / max(std_r, 0.001)
```

Sharpe به صورت دوره‌ای محاسبه شده و ضرب در `sqrt(252)` انجام نشده.

---

**راه‌حل ۱: Annualization با `sqrt(252)` برای روزانه**

| معیار | امتیاز |
|---|---|
| صحت | ۱۰ |
| مهاجرت | ۱۰ — یک خط |
| **مجموع** | **۱۰** |

> **🏆 روش برگزیده: راه‌حل ۱**  
> **دلیل فنی:** فقط نیاز به یک خط: `result.sharpe = (mean_r / max(std_r, 0.001)) * (252 ** 0.5)`

---

### 5.3 Backtesting — Max Drawdown با cumsum به جای cumprod

**شدت:** متوسط  
**فایل:** `services/signal_backtest_engine.py:323`

```python
cumulative = np.cumsum(returns)
```

`cumsum` برای returns درصد برای بازده‌های بزرگ نادرست است. باید از `cumprod(1 + r)` استفاده شود.

---

**راه‌حل ۱: استفاده از cumprod برای compounding**

```python
cumulative = np.cumprod(1 + np.array(returns)/100)
```

| معیار | امتیاز |
|---|---|
| صحت مالی | ۱۰ |
| مهاجرت | ۱۰ |
| **مجموع** | **۱۰** |

> **🏆 روش برگزیده: راه‌حل ۱**  
> **دلیل فنی:** `cumsum` فرض linear کردن است که برای بازده‌های مالی نادرست است.

---

### 5.4 Backtesting — Profit Factor با کف ۰.۰۰۱

**شدت:** پایین  
**فایل:** `services/signal_backtest_engine.py:312`

```python
result.profit_factor = total_profit / max(total_loss, 0.001)
```

عدد ۰.۰۰¹ برای جلوگیری از تقسیم بر صفر استفاده شده اما می‌تواند profit factor را به طور مضللی بالا نشان دهد.

---

### 5.5 Backtesting — Look-ahead Bias در زمان ورود

**شدت:** متوسط  
**فایل:** `services/signal_backtest_engine.py:219`

```python
entry_price = hist_data[0]["open"]   # ← ورود با open روز بعد
exit_price = hist_data[-1]["close"]
```

استفاده از open قیمت برای ورود درست است (نه close روز سیگنال که look-ahead باشد). اما `days_forward = 30` ثابت است و با horizon سیگنال تطابق ندارد.

---

### 5.6 Walk-Forward Validation — آستانه‌های ضعیف

**فایل:** `services/walk_forward_validator.py`

```python
is_reliable = avg_test_accuracy > 0.55 and overfitting < 0.15
```

آستانه 0.55 برای accuracy و 0.15 برای overfitting برای بازارهای مالی آسان‌گیرانه است.

---

**راه‌حل ۱: آستانه‌های شدیدتر با در نظر گرفتن نسبت شارپ**

| معیار | امتیاز |
|---|---|
| صحت | ۱۰ |
| حفاظت از ML | ۱۰ |
| مهاجرت | ۹ |
| **مجموع** | **۹.۵** |

> **🏆 روش برگزیده: راه‌حل ۱**  
> **دلیل فنی:** مدل با 55% accuracy می‌تواند شارپ منفی داشته باشد. معیار `Sharpe > 0.5` نیز باید اضافه شود.

---

### 5.7 Paper Trading — سطوح ثابت

**شدت:** متوسط  
**فایل:** `services/paper_trading_service.py:161`

```python
stop = self._parse_price(snap.stop_loss) or (price * 0.95)
target1 = self._parse_price(snap.targets) or (price * 1.08)
target2 = target1 * 1.08
```

Stop loss 5% و target 8% ثابت است. این سطوح باید از سیگنال استخراج شوند نه هاردکد شوند.

---

**راه‌حل ۱: پارس کردن stop_loss و targets از رشته سیگنال با regex**

| معیار | امتیاز |
|---|---|
| صحت مالی | ۱۰ |
| انعطاف | ۱۰ |
| مهاجرت | ۸ |
| **مجموع** | **۹.۵** |

> **🏆 روش برگزیده: راه‌حل ۱**  
> **دلیل فنی:** سیگنال‌ها دارای stop_loss و targets مشخص هستند. فقط نیاز به parsing داریم.

---

### 5.8 RSI — عدم استفاده از Wilder's Smoothing

**شدت:** متوسط  
**فایل‌های متاثر:** `signal_feature_pipeline.py:266`, `feature_engine.py:945`

هر دو از میانگین ساده استفاده می‌کنند. RSI استاندارد از Wilder's smoothing (EMA با alpha=1/period) استفاده می‌کند.

---

**راه‌حل ۱: پیاده‌سازی Wilder's smoothing**

```python
avg_gain = prev_avg_gain * (period - 1) / period + current_gain / period
```

| معیار | امتیاز |
|---|---|
| صحت مالی | ۱۰ |
| مهاجرت | ۹ |
| **مجموع** | **۹.۵** |

> **🏆 روش برگزیده: راه‌حل ۱**  
> **دلیل فنی:** تفاوت SMA و Wilder's برای 14 روز حدود 2-3 درصد RSI است. این می‌تواند در مرزهای اشباع خرید/فروش تاثیر بگذارد.

---

### 5.9 ML Training — عدم استفاده از Walk-Forward Validation حین آموزش

**شدت:** بالا  
**فایل:** `services/ml_signal_connector.py:361`

**شواهد:** `WalkForwardValidator` به صورت جداگانه وجود دارد اما در فرآیند آموزش فراخوانی نمی‌شود. مدل با یک train/test split ساده آموزش می‌بیند که برای سری‌های زمانی ناامن است.

---

**راه‌حل ۱: ادغام Walk-Forward در فرآیند آموزش**

| معیار | امتیاز |
|---|---|
| صحت ML | ۱۰ |
| مقاومت به overfitting | ۱۰ |
| مهاجرت | ۷ |
| **مجموع** | **۹.۰** |

> **🏆 روش برگزیده: راه‌حل ۱**  
> **دلیل فنی:** Walk-forward برای سری‌های زمانی ضروری است. Split ساده باعث data leakage می‌شود.

---

### 5.10 Data Leakage — روش label generation

**شدت:** نسبتاً امن  
**فایل:** `services/signal_feature_pipeline.py:305`

**شواهد:** `prepare_training_data()` به درستی label contract `(X_t, y_{t+1})` را پیاده‌سازی کرده و alignment چک می‌کند. این نقطه قوت است.

---

### 5.11 Signal Generation — Candidate Cap قبل از Decision Engine

**شدت:** متوسط  
**فایل:** `services/quant_signal_orchestrator.py:705`

```python
candidates = sorted(candidates, key=lambda s: s.boosted_score, reverse=True)[:120]
```

حدود 120 سیگنال قبل از Decision Engine انتخاب می‌شوند. اگر boosted_score حاوی اطلاعات آینده باشد، look-ahead bias ایجاد می‌شود. بررسی شد: `boosted_score = rule_score + ml_score` و هر دو به داده روز فعلی استوارند — بی‌خطر است.

---

## 6. جدول ریسک‌های کلیدی

### 6.1 بحرانی (فوراً باید برطرف شود)

| # | ریسک | فایل | شدت | توضیح |
|---|---|---|---|---|
| 1 | **Default Release در خطا** | `quant_signal_orchestrator.py:1221` | 🔴 بحرانی | در صورت خطا، تمام ۱۰ گیت دور زده می‌شوند |
| 2 | **Data Quality هاردکد 1.0** | `quant_signal_orchestrator.py:1192` | 🔴 بحرانی | Gate 1، 6 و 9 کاملاً غیرفعال |
| 3 | **Smart Money weights هاردکد** | `smart_money/layer1_price_volume.py:48` | 🔴 بحرانی | Config بی‌اثر |

### 6.2 بالا (باید در اسپرینت بعدی برطرف شود)

| # | ریسک | فایل | شدت | توضیح |
|---|---|---|---|---|
| 4 | تکرار RSI/ATR/Trend | 3 فایل | 🟠 بالا | فرمول‌های متفاوت |
| 5 | عدم احتساب هزینه در بک‌تست | `signal_backtest_engine.py` | 🟠 بالا | بازده واقعی گزارش نمی‌شود |
| 6 | عدم Walk-Forward در آموزش ML | `ml_signal_connector.py:361` | 🟠 بالا | Overfitting risk |
| 7 | MACD با SMA به جای EMA | `feature_engine.py:962` | 🟠 بالا | خطای محاسباتی |

### 6.3 متوسط (برنامه‌ریزی برای بهبود)

| # | ریسک | فایل | شدت | توضیح |
|---|---|---|---|---|
| 8 | Sharpe بدون annualization | `signal_backtest_engine.py:318` | 🟡 متوسط |
| 9 | Max Drawdown با cumsum | `signal_backtest_engine.py:323` | 🟡 متوسط |
| 10 | Buckets کالیبراتور از 0.50 | `probability_calibrator.py` | 🟡 متوسط |
| 11 | ثابت‌های اقتصادی هاردکد | `feature_engine.py` | 🟡 متوسط |
| 12 | Singleton ناسازگار | چند فایل | 🟡 متوسط |

### 6.4 پایین (می‌توان بعداً برطرف کرد)

| # | ریسک | شدت |
|---|---|---|
| 13 | Claw-code/ و mimicode-go/ دایرکتوری‌های مرده | 🟢 پایین |
| 14 | 18 ویژگی placeholder در بلوک G | 🟢 پایین |
| 15 | Profit Factor floor 0.001 | 🟢 پایین |

---

## 7. جمع‌بندی و نقشه راه

### امتیاز کلی پروژه

| بعد | امتیاز (از ۱۰) | وضعیت |
|---|---|---|
| DRY & Refactoring | ۵.۵ | ⚠️ نیاز به بازنویسی اساسی |
| Architecture & Services | ۶.۰ | ⚠️ Monolithic اما مشکل Fail-open |
| Financial Logic | ۵.۰ | 🔴 باگ‌های بحرانی |
| Signal/ML/Backtest | ۵.۵ | ⚠️ Data Leakage امن اما بک‌تست ناقص |
| **میانگین** | **۵.5** | **⚠️ نیاز به بهبود جدی** |

### نقشه راه پیشنهادی

#### فاز ۱: رفع ایرادات بحرانی (۱ هفته)

- [ ] تغییر Default Release → Fail-closed (reject)
- [ ] پیاده‌سازی محاسبه واقعی Data Quality
- [ ] تزریق وزن‌های Smart Money از config

#### فاز ۲: یکپچه‌سازی و رفع باگ‌های محاسباتی (۲ هفته)

- [ ] استخراج RSI/ATR/Trend Strength به `core/indicators.py`
- [ ] پیاده‌سازی Wilder's smoothing برای RSI/ATR
- [ ] اصلاح MACD با EMA واقعی
- [ ] اضافه کردن هزینه‌های معاملاتی به بک‌تست
- [ ] Annualization Sharpe Ratio
- [ ] اصلاح Max Drawdown با cumprod

#### فاز ۳: بهبود ML Pipeline (۲ هفته)

- [ ] ادغام Walk-Forward Validation در فرآیند آموزش
- [ ] بهبود آستانه‌های قابل اعتماد
- [ ] توسعه Plugin-based برای بلوک G

#### فاز ۴: بهبود معماری (۱ ماه)

- [ ] یکپارچه‌سازی Dependency Injection
- [ ] استخراج session management به یک context manager واحد
- [ ] یکپارچه‌سازی caching layers
- [ ] حذف Lazy Imports و بازسازی با ABC/Protocol

---

## ضمیمه: فهرست فایل‌های کلیدی بر اساس بعد ممیزی

| بعد | فایل‌های کلیدی |
|---|---|
| DRY & Refactoring | `signal_feature_pipeline.py`, `feature_engine.py`, `confidence_scorer.py`, `smart_money/layer*.py`, `smart_money.yaml` |
| Architecture | `quant_signal_orchestrator.py`, `signal_decision_engine.py`, `decision_gate.py`, `core/database.py`, `core/cache_manager.py`, `docker-compose.yml` |
| Financial Logic | `signal_decision_engine.py`, `smart_money/scoring_engine.py`, `options/pricing.py`, `options/probability.py`, `feature_engine.py`, `probability_calibrator.py` |
| Signal/ML/Backtest | `quant_signal_orchestrator.py`, `ml_signal_connector.py`, `signal_feature_pipeline.py`, `signal_backtest_engine.py`, `walk_forward_validator.py`, `signal_voting_system.py`, `paper_trading_service.py` |

---

*این گزارش توسط معمار ارشد نرم‌افزار و متخصص سیستم‌های مالی الگوریتمی تهیه شده است.*
